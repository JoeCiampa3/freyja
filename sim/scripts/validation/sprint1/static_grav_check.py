#This validation focuses on holding the pelvis static and measuring the torque necessary to keep the body segments stationtary

import mujoco

model = mujoco.MjModel.from_xml_path("sim/models/freyja.xml")
data = mujoco.MjData(model)
mujoco.MjForward(model,data)

