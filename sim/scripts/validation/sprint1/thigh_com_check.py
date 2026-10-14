import mujoco
import numpy as np

# Table frame (X ant, Y up, Z right), mm -> MuJoCo body frame (X ant, Y left, Z up)
R_TBL2MJ = np.array([[1, 0,  0],
                     [0, 0, -1],
                     [0, 1,  0]], dtype=float)

com_data_mm = {
    "Foot":        np.array([ 44.550,  -35.970,  6.435]),
    "Leg (shank)": np.array([-19.941, -164.414, 12.616]),
    "Thigh":       np.array([-30.609, -149.867,  3.578]),
}
body_map = {"Foot": "foot_right", "Leg (shank)": "shank_right", "Thigh": "thigh_right"}

model = mujoco.MjModel.from_xml_path("sim/models/freyja.xml")
data = mujoco.MjData(model)
mujoco.mj_forward(model, data)

ids = {k: model.body(v).id for k, v in body_map.items()}
masses = np.array([model.body_mass[ids[k]] for k in ids])

world_coms = []
for k, v_mm in com_data_mm.items():
    b = ids[k]
    local = R_TBL2MJ @ (v_mm / 1000.0)               # table -> MuJoCo axes, m
    world_coms.append(data.xpos[b] + data.xmat[b].reshape(3, 3) @ local)
world_coms = np.array(world_coms)

independent_com = (masses[:, None] * world_coms).sum(0) / masses.sum()
mujoco_com = (masses[:, None] * np.array([data.xipos[ids[k]] for k in ids])).sum(0) / masses.sum()

print("independent:", independent_com)
print("mujoco     :", mujoco_com)
print("max abs diff (m):", np.abs(independent_com - mujoco_com).max())
for i, (k, b) in enumerate(ids.items()):
    print(k, np.abs(world_coms[i] - data.xipos[b]).max())