#checks model mass without having to run the pre_processor
import mujoco

model = mujoco.MjModel.from_xml_path("models/freyja.xml")
data = mujoco.MjData(model)
mujoco.mj_forward(model, data)
whole_body_com = data.subtree_com[0]

mass =  sum(model.body_mass[1:])
print(f"Model mass: {mass:.4} kg")
print(f"Whole body CoM (x, y, z) (in meters): {whole_body_com}")