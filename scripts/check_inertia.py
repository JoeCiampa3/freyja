import mujoco, numpy as np
m = mujoco.MjModel.from_xml_path("models/thigh_check.xml")
i = m.body("thigh").id
print(m.body_mass[i],m.body_ipos[i])
print("mujoco principal:", m.body_inertia[i])

I = np.array([[0.12548, 0.00731, 0.00060],
              [0.00731, 0.03357, -0.00731],
              [0.00060, -0.00731, 0.13429]])

print("dumas principal: ", np.sort(np.linalg.eigvalsh(I)))