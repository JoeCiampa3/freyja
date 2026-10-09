#checks model mass without having to run the pre_processor
import mujoco

targ_stature = 1.7 #target height, m
targ_mass = 65.0 #target mass, kg

model = mujoco.MjModel.from_xml_path("models/freyja.xml")
data = mujoco.MjData(model)
mujoco.mj_forward(model, data)

mass =  sum(model.body_mass[1:])
mass_error = abs((targ_mass - mass) / targ_mass) * 100
print(f"Expected mass: {targ_mass:.4}kg")
print(f"Model mass: {mass:.4}kg. Percent error: {mass_error:.4}%")


#whole body com
whole_body_com = data.subtree_com[0]
print(f"Whole body CoM anterior/posterior (x): {whole_body_com[0] * 1000:.4}mm")
print(f"Whole body lateral (y): {abs(whole_body_com[1]) * 1000:.4}mm")
print(f"Whole body vertical CoM (z): {whole_body_com[2] * 1000:.4}mm")
print(f"Whole body vertical CoM as a percentage of height: {whole_body_com[2] / targ_stature * 100:.4}%")


