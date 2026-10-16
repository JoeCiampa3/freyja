#This validation focuses on holding the pelvis static and measuring the torque necessary to keep the body segments stationtary
#To accomplish this we will set the pelvis position using FIXME, 
#and for each joint in the body we will set the accelerations
#and velocities to zero using FIXME. This test will use at 
#least two poses so we will also set joint angles using FIXME
#THe objective of this test is to use mj_inverse to 
#calculate the joint torques required to hold this pose and
#verify them against an independent calculation. 

import mujoco

model = mujoco.MjModel.from_xml_path("sim/models/freyja.xml")
data = mujoco.MjData(model)
mujoco.MjForward(model,data)

