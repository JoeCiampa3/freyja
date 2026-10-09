import mujoco
import mujoco.viewer

model=mujoco.MjModel.from_xml_path("models/freyja.xml")
data=mujoco.MjData(model)
mujoco.viewer.launch(model, data)
