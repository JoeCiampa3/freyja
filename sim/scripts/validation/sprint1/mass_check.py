# Whole-body mass and CoM of models/freyja.xml, with the targets read from params/snapshot.csv.
# The logic lives in checks/mjcf_checks.py (check.mjcf.mass_closure and check.mjcf.com); this
# script only prints it. Run from anywhere:  python sim/scripts/validation/sprint1/mass_check.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "checks"))

import checklib as cl  # noqa: E402
import mjcf_checks  # noqa: E402,F401  (registers the checks)

ctx = cl.Context.from_files()
r = mjcf_checks.com_report(ctx)

if r["target_mass_kg"] is None:
    print(f"Model mass: {r['mass_kg']:.4}kg (no target_mass in the snapshot)")
else:
    print(f"Expected mass: {r['target_mass_kg']:.4}kg")
    print(f"Model mass: {r['mass_kg']:.4}kg. Percent error: {r['mass_error_pct']:.4}%")

x, y, z = r["com_m"]
print(f"Whole body CoM anterior/posterior (x in MJC): {x * 1000:.4}mm")
print(f"Whole body lateral (y) in MJC: {abs(y) * 1000:.4}mm")
print(f"Whole body vertical CoM (z in MJC): {z * 1000:.4}mm")
if r["pct_stature"] is None:
    print("Whole body vertical CoM as a percentage of height: no target_stature in the snapshot")
else:
    print(f"Whole body vertical CoM as a percentage of height: {r['pct_stature']:.4}%")
