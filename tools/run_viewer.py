import mujoco
import mujoco.viewer

model=mujoco.MjModel.from_xml_path("sim/models/freyja.xml")
data=mujoco.MjData(model)
mujoco.viewer.launch(model, data)
