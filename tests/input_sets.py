"""
The `inputs` lists of the tests that are skipped on unchanged inputs (tools/testkit, CONVENTIONS section 7).

A list names every repo path the tests that carry it can read: code they import, code that code imports, and data. Completeness is what makes the
skip sound, so these are whole directories, wider than any one test needs. Widen a list when a test starts reading something new; never narrow one
to get more skips. Files git ignores (the envelope's voxel cache, the processed gait arrays) are not inputs and cannot be listed.

    @pytest.mark.inputs(*ENVELOPE)
"""

# tools/envelope reads the snapshot, the body meshes, its own results and examples, the ANSUR ratios, the model (frames.py, foreign.py, offsets.py through
# sim/scripts) and the check library; its CLI tests go through tools/fy, and the registry reads the CAD components (tools/cad, cad/).
ENVELOPE = ("tools/envelope", "tools/fy", "tools/cad", "cad", "data/envelope", "data/makehuman", "data/ansur2", "params", "sim/models", "sim/scripts", "checks")

# A simulation run: the runner and solvers, scenarios, controllers and the model under sim/, the snapshot, and the checks a run record quotes.
SIM = ("sim", "params", "checks")
