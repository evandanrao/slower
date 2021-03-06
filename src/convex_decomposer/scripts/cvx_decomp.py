#!/usr/bin/env python2
"""
ROS Node for convex decomposition of the space around a segment defined by p1 and p2. 
This ROS node subscribes to the following topics:
/probability_publisher
/global_plan

This ROS node publishes to the following topics:
/CvxDecomp
/ellipsoid_disp'
/polyhedra_disp
*disp is used to display to RVIZ visualizations
"""
# Import ROS libraries
import sys, threading
import roslib
import rospy
# Import classes
from geometry_msgs.msg import Point,PoseStamped, Point32
from std_msgs.msg import Header,Float64
from nav_msgs.msg import Path
from sensor_msgs.msg import PointCloud
from convex_decomposer.msg import Polyhedron , CvxDecomp
from shape_msgs.msg import Plane
from decomp_ros_msgs.msg import Polyhedron as ph_display
from decomp_ros_msgs.msg import PolyhedronArray as pharray_display
from decomp_ros_msgs.msg import Ellipsoid as E_display
from decomp_ros_msgs.msg import EllipsoidArray as Earray_display
import hyperplane as hp
import ellipsoid as E
import plane_utils
import numpy as np
import time
#Define the convex decomposition class
class cvx_decomp(object):
    """
    cvx_decomp is used to perform a convex decomposition of the free space around obstacles. The setup is an implementation of
    the : MRSL Decomputil Library v1.0 :https://github.com/sikang/DecompUtil : http://ieeexplore.ieee.org/document/7839930/
    """
    def __init__(self):

        #Get params:
        #############################################
        self.n_int_max = 6 #Does not do anything for now : plan to use it to limit the number of hyperplanes of the polyhedron
        self.offset_x = rospy.get_param("~cvx/offset_x") #Offset of the ellipsoid around the segment
        self.drone_radius =  rospy.get_param("~cvx/drone_radius") # Radius of the drone for obstacle inflation 
        self.bbox = rospy.get_param("~cvx/bbox") # [2,2,1]  # Local bounding box of the convex decomposer
        self.angl_lim = rospy.get_param("~cvx/angle_lim") # angle below which planes have to be merged into one
        self.run_jps3d = rospy.get_param("~setup/use_jps3d")
        self.run_global_mapper = rospy.get_param("~setup/use_global_mapper_ros")
        self.frame = rospy.get_param("~cvx/global_frame")
        # Set the decomposer frequency
        self.loop_frequency = rospy.get_param("~cvx/freq")

        if np.linalg.norm(np.array(self.bbox)) == 0:
            rospy.logwarn('Bounding Box requirement set to [0,0,0]')
            
        #############################################
        

        # Declare Publishers and Subscibers
        self.point_cloud = "/occup_grid1"
        if self.run_global_mapper:
            self.point_cloud = "/SQ01s/global_mapper_ros/occupancy_grid1"
        
        self.path = '/global_plan'
        if self.run_jps3d:
            self.path = 'jps3d/global_plan'
        
        
        self.point_cloud_sub = rospy.Subscriber(self.point_cloud,PointCloud,self.point_cloud_proc)
        self.path_sub = rospy.Subscriber(self.path,Path,self.path_processor)
        self.pub_CvxDecomp = rospy.Publisher('/CvxDecomp',CvxDecomp,queue_size=1)
        #self.obs_interest = '/xnew_obs'
        #self.pub_obs_of_interest = rospy.Publisher(self.obs_interest,PointCloud,queue_size=1)

        self.threading_lock = threading.Lock()
        #Publishers to display polygon and ellipsoids
        self.pub_Ph_display = rospy.Publisher('/polyhedra_disp',pharray_display,queue_size=1) 
        self.pub_E_display = rospy.Publisher('/ellipsoid_disp',Earray_display,queue_size=1) 
        #self.pub_obs_of_interest = rospy.Publisher('/x_new_obs',PointCloud,queue_size=1) 
        self.cvx_plan_time_topic = '/cvx_decomp/replan_time'
        self.cvx_plan_time_pub = rospy.Publisher(self.cvx_plan_time_topic,Float64,queue_size=1)

        # Select trajectory type
        # Initialize messages
        self.cvx_polyhedra = CvxDecomp()

        self.ph_display_msg = pharray_display()
        self.E_display_msg = Earray_display()

        #self.obs_cloud = PointCloud() #Define type!
        self.obs_cloud = [] #Change to pc if necessary
        self.p = [] # placeholder for holding the end points of the segment in question
        self.path_list = [] #Placeholder for the path poses
        
        # Run this ROS node at the loop frequency
        self.timers = rospy.Timer(rospy.Duration(1.0 / self.loop_frequency), self.decompose_points)

    def get_obs(pcloud,channel):
        if channel ==[]:
            obs_ = np.array(pcloud)
            return obs_
        obs_probability = 0.5
        obs_ = np.array(pcloud)[np.argwhere(np.array(channel)>obs_probability).T[0],:]
        return obs_

    """Function to store the current trajectory msg to be passed to the Position Controller"""
    def point_cloud_proc(self,msg):
        #split the pointcloud to free and occupied points
        self.threading_lock.acquire()
        cloud = msg.points
        cloud_list = [[point.x,point.y,point.z] for point in cloud]
        if msg.channels:
            cloud_channel = msg.channels[0].values
            self.obs_cloud = get_obs(cloud_list,cloud_channel)
        else:
            self.obs_cloud = np.array(cloud_list)
        self.threading_lock.release()
    
    def get_obs(pcloud,channel):
        if channel ==[]:
            obs_ = np.array(pcloud)
            return obs_
        obs_probability = 0.5
        obs_ = np.array(pcloud)[np.argwhere(np.array(channel)>obs_probability).T[0],:]
        return obs_

    def path_processor(self,msg):
        self.path_list = msg.poses
        self.threading_lock.acquire()
        self.p = [[point.pose.position.x, point.pose.position.y, point.pose.position.z] for point in self.path_list]
        if len(self.p)==1:
            print("Segment cannot be formed since only one point was obtained")
        self.threading_lock.release()
    
    #def interest_cloud_callback(self,obs):
    #    msg = PointCloud(header=Header(stamp = rospy.Time.now(),frame_id = self.frame))
    #    for p in obs:
    #        msg.points.append(Point32(x=p[0],y=p[1],z=p[2]))
    #    self.pub_obs_of_interest.publish(msg)
    
    """Function called when timer matures"""
    def decompose_points(self,event):
        #Start by finding one polyhedron per segment
        self.threading_lock.acquire()

        #reinitialize the messages #Set header_info for the publish message:
        self.cvx_polyhedra = CvxDecomp(header = Header(stamp = rospy.Time.now(),frame_id = self.frame))
        self.ph_display_msg = pharray_display(header = Header(stamp = rospy.Time.now(),frame_id = self.frame))
        self.E_display_msg = Earray_display(header = Header(stamp = rospy.Time.now(),frame_id = self.frame))
        cvx_time_start = rospy.get_rostime()
        for i in range(0,len(self.p)-1):
            #Start point for the segment
            p1 = np.asarray(self.p[i])
            #End point for the segment
            p2 = np.asarray(self.p[i+1])
            if not np.sum(p1-p2):
                rospy.loginfo('Segment at position {}: p1({})==p2({}) moving to pos{}'.format(i,p1,p2,i+1))
                continue
            #Find a bounding polyhedron based on self.bbox param.
            bbox_polyhedron = hp.add_local_bbox(p1,p2,self.bbox)            
            obs = hp.set_obs_Vs(self.obs_cloud,bbox_polyhedron)            
            #Find an ellipsoid around the segment
            C,d,Cinv,obs = E.find_ellipsoid(p1,p2,self.offset_x,obs,self.drone_radius)
            #Get the hyperplanes at the extremeties and eliminate the spaces
            cvx_planes =hp.get_hyperplanes(obs,Cinv,d,self.angl_lim)
            #Add the bounding box and cvx_decomp_planes to obtain inner polyhedrons
            complex_polyhedron = cvx_planes+bbox_polyhedron
            #Simplify the plyhedrons to get inner polyhedrons only 
            # Plan is to simply eliminate planes that are parallel by distance to path segment in question.
            required_polyhedron = complex_polyhedron#np.array(plane_utils.eliminate_redundant_planes(complex_polyhedron,d))
            #vertices = plane_utils.calculate_vertices(complex_polyhedron)
            #FIND A FOOL PROOF WAY TO LIMIT TOTAL NUMBER OF PLANES IN A POLYHEDRA?
            #Append the ellipsoid for display
            self.E_display_msg.ellipsoids.append(E_display(E = C.ravel().tolist(),d = d.tolist()))
            normals_pack = []
            points_pack = []
            plane_pack = []
            for pln in required_polyhedron:
                plane_pack.append(Plane(coef = hp.get_standard_form(pln))) #convert polyhedrons from point normal to standard form >> ax+by+cz=d and append
                #form point msg and normal msgs and create the message list
                normals_pack.append(Point(x=pln[1][0],y=pln[1][1],z=pln[1][2]))
                points_pack.append(Point(x=pln[0][0],y=pln[0][1],z=pln[0][2]))
            #Make a pack for the array
            self.cvx_polyhedra.polyhedra.append(Polyhedron(planes = plane_pack))        
            self.ph_display_msg.polyhedrons.append(ph_display(points = points_pack,normals = normals_pack))

        cvx_time_finish = rospy.get_rostime()
        self.threading_lock.release()

        #publish to display on rviz
        self.cvx_plan_time = (cvx_time_finish-cvx_time_start).to_sec()
        self.cvx_plan_time_pub.publish(self.cvx_plan_time)
        self.pub_CvxDecomp.publish(self.cvx_polyhedra)
        self.pub_E_display.publish(self.E_display_msg)
        self.pub_Ph_display.publish(self.ph_display_msg)

        #plotter(p1,p2,obs_init,elp_sample (C,d,100))###PLOTTER
        #plotter_poly(globalpoly)
if __name__ == '__main__':
    # Code to create cvx_decomp
    rospy.init_node('cvx_decomp',disable_signals=True)
    cvx_decomp()
    rospy.spin()