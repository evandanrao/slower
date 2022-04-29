# AER1516 Winter 2022 Project
This is our implementation of the paper "FASTER: Fast and Safe Trajectory Planner for Navigation in Unknown Environments"
The main repo of the paper is at https://github.com/mit-acl/faster
This repo is further a cleaned version of the wroking repository that is available at : https://github.com/sangitasahu/AER1516.git
The authors of this work , besides the original authors from the repo are:
Vandan Eddya Rao
Matt Brymer
Sangita Sahu
Furqan A



Link to draw.io file:   https://app.diagrams.net/#G1JaMom59_h-Wq3BAk28IzTx_z-1hYDaKI

## Set up the workspace
This has been tested with Ubuntu 18.04/ROS Melodic

Install the following dependencies:
```
sudo apt-get install ros-"${ROS_DISTRO}"-gazebo-ros-pkgs ros-"${ROS_DISTRO}"-mavros-msgs ros-"${ROS_DISTRO}"-tf2-sensor-msgs ros-"${ROS_DISTRO}"-hector-sensors-description
```
```
sudo apt-get install python3-catkin-tools
sudo apt install git
```

## MOSEK Installation Steps
The project uses MOSEK instead of Gurobi.
The MOSEK optimizer needs to be installed both systemwide as well as installing a Python package to interface with it. Installation steps are described in the documentation here: https://docs.mosek.com/9.3/install/installation.html for the general setup and here: https://docs.mosek.com/latest/pythonapi/install-interface.html for the Python interface
1. Request an academic license here with your school email: https://www.mosek.com/products/academic-licenses/. It's automated and you should get an email relatively quickly
2. Download and run the overall installer for your system from here: https://docs.mosek.com/9.3/install/installation.html#general-setup
3. Add a path variable for the runnable location. I did it by adding the following to my .bashrc. I have it installed in my home directory so if you put it elsewhere you'll have to update that obviously
```
# MOSEK path
export PATH=$PATH:~/mosek/mosek/9.3/tools/platform/linux64x86/bin
```
4. Dump the license file they send you in the root install folder below. Check it's set up properly by running msktestlic in a terminal
```
$HOME/mosek/mosek.lic
```
5. Install the Python interface via Pip in the Python environment your ROS setup is using
```
pip install Mosek
```
6. That's it! If you want you can test it by downloading and running one of the tutorial problems. There's a simple QP example here: https://docs.mosek.com/latest/pythonapi/tutorial-qo-shared.html . The general documentation for the Python interface is here if you're curious: https://docs.mosek.com/latest/pythonapi/intro_info.html



## Create a workspace, and clone this repo and its dependencies:
```
git clone https://github.com/evandanrao/slower.git
```
## Initialize the workspace
```
cd slower
wstool init src slower.rosinstall
```
## Compile the code:
```
cd src
wstool update -j8
cd ..
catkin config -DCMAKE_BUILD_TYPE=Release
catkin build
```
## Source your workspace
Make sure you add the following line to your .bashrc file
```
source PATH_TO_YOUR_WS/devel/setup.bash
```
## Sample Click to Go format of the implementation can be launched by, 

Open 2 terminals in the root directory "~/slower" and execute these commands in the two different terminals:
```
roslaunch launch_all_nodes_JPS3D.launch
roslaunch master_node start_master_node.launch
```
RVIZ must launch with a sample config file. 
Select the  "2DPose" button or press-g on the keyboard while on rviz and click a goal location to let the drone fly to the goal.
Visualize the cvx_decomp and local planner using the topics in rviz.

All params are at /src/master_node/param/params.yaml or /src/jps3d_ros/src/jps3dros/jps3d_ros/param/params.yaml
