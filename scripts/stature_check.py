import mujoco

model = mujoco.MjModel.from_xml_path("models/freyja.xml")

print(f"Model extent: {model.stat.extent:.4} meters")