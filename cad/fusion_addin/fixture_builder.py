"""
Builds the scratch fixture document of the CAD bridge (Stage 3b, T3): the only place the repo creates geometry in Fusion. It refuses to touch any document whose
name does not start with `freyja-bridge-fixture`. Imports only `adsk` and the standard library.

The fixture, in the ISB frame (x anterior, y proximal, z lateral, mm):

  tube    6061 aluminium, axis along -y from the origin, length `in_fixture_length`, outer diameter `dv_fx_od`, inner diameter `dr_fx_id`
  marker  a cube of edge `dv_fx_ratio * dv_fx_wall` centred at (0, -in_fixture_length, 0), the point of the frame test (gate G7)
  fillet  every edge of the marker, radius `dr_fx_id / 100`: it fails when the inner diameter reaches zero, which is how gate G3 breaks regeneration
  sector  a ring sector revolved about y by `dv_fx_angle`, away from the tube: the angular parameter drives a feature, and its asymmetry pins the sign
          convention of Fusion's products of inertia
"""
import adsk.core
import adsk.fusion

NAME_PREFIX = "freyja-bridge-fixture"
MATERIAL_LIBRARY = "Fusion Material Library"
MATERIAL = "Aluminum 6061"

# user parameters: (name, expression, unit, comment)
PARAMETERS = (
    ("in_fixture_length", "300 mm", "mm", "inherited from the fixture snapshot"),
    ("dv_fx_od", "30 mm", "mm", "tube outer diameter"),
    ("dv_fx_wall", "2 mm", "mm", "tube wall"),
    ("dr_fx_id", "dv_fx_od - 2 * dv_fx_wall", "mm", "tube inner diameter"),
    ("dv_fx_ratio", "3", "", "unitless: marker edge over wall"),
    ("dv_fx_angle", "30 deg", "deg", "sector angle"),
)
SECTOR_R_IN_MM = 40.0
SECTOR_R_OUT_MM = 46.0
SECTOR_HALF_HEIGHT_MM = 5.0


def _design():
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError("no active design")
    return app, design


def _guard(app):
    """Only a document that is new (Untitled, created for the fixture) or already a fixture may be built into."""
    name = app.activeDocument.name
    if not (name.startswith(NAME_PREFIX) or name.startswith("Untitled")):
        raise RuntimeError(f"refusing to build into {name!r}: not a bridge fixture")
    return name


def _vi(text):
    return adsk.core.ValueInput.createByString(text)


def build():
    """Create the parameters and the three bodies in the active, empty document. Returns a summary."""
    app, design = _design()
    _guard(app)
    root = design.rootComponent
    if root.bRepBodies.count or design.userParameters.count:
        raise RuntimeError("the document is not empty")
    if design.unitsManager.defaultLengthUnits != "mm":
        raise RuntimeError("the fixture is built in a document whose length unit is mm")
    up = design.userParameters
    for name, expr, unit, comment in PARAMETERS:
        up.add(name, _vi(expr), unit, comment)

    # tube: the XZ plane's normal is +y, so a negative-direction extent runs along -y
    sk = root.sketches.add(root.xZConstructionPlane)
    sk.name = "tube profile"
    c0 = adsk.core.Point3D.create(0, 0, 0)
    outer = sk.sketchCurves.sketchCircles.addByCenterRadius(c0, 1.5)
    inner = sk.sketchCurves.sketchCircles.addByCenterRadius(c0, 1.3)
    sk.geometricConstraints.addCoincident(outer.centerSketchPoint, sk.originPoint)
    sk.geometricConstraints.addCoincident(inner.centerSketchPoint, sk.originPoint)
    d1 = sk.sketchDimensions.addDiameterDimension(outer, adsk.core.Point3D.create(2.5, 2.5, 0))
    d2 = sk.sketchDimensions.addDiameterDimension(inner, adsk.core.Point3D.create(-2.5, 2.5, 0))
    d1.parameter.expression = "dv_fx_od"
    d2.parameter.expression = "dr_fx_id"
    ring = next(p for p in sk.profiles if p.profileLoops.count == 2)
    ext = root.features.extrudeFeatures
    ei = ext.createInput(ring, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ei.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(_vi("in_fixture_length")), adsk.fusion.ExtentDirections.NegativeExtentDirection)
    tube = ext.add(ei)
    tube.name = "tube"
    tube.bodies.item(0).name = "tube"

    # marker: a cube centred on (0, -L, 0): a plane offset by -L from XZ, extruded symmetrically
    pin = root.constructionPlanes.createInput()
    pin.setByOffset(root.xZConstructionPlane, _vi("-in_fixture_length"))
    plane = root.constructionPlanes.add(pin)
    plane.name = "marker plane"
    sk2 = root.sketches.add(plane)
    sk2.name = "marker profile"
    sk2.sketchCurves.sketchLines.addCenterPointRectangle(adsk.core.Point3D.create(0, 0, 0), adsk.core.Point3D.create(0.3, 0.3, 0))
    dims = sk2.sketchDimensions
    ls = [sk2.sketchCurves.sketchLines.item(i) for i in range(4)]
    horiz = next(l for l in ls if abs(l.startSketchPoint.geometry.y - l.endSketchPoint.geometry.y) < 1e-9)
    vert = next(l for l in ls if abs(l.startSketchPoint.geometry.x - l.endSketchPoint.geometry.x) < 1e-9)
    dims.addDistanceDimension(horiz.startSketchPoint, horiz.endSketchPoint, adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                              adsk.core.Point3D.create(0, 1, 0)).parameter.expression = "dv_fx_ratio * dv_fx_wall"
    dims.addDistanceDimension(vert.startSketchPoint, vert.endSketchPoint, adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
                              adsk.core.Point3D.create(1, 0, 0)).parameter.expression = "dv_fx_ratio * dv_fx_wall"
    ei2 = ext.createInput(sk2.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ei2.setSymmetricExtent(_vi("dv_fx_ratio * dv_fx_wall"), True)
    marker = ext.add(ei2)
    marker.name = "marker"
    marker.bodies.item(0).name = "marker"

    add_marker_fillet()

    # sector: a rectangle in the XY plane at x in [40, 46] mm, y in [-5, 5] mm, revolved about the y axis by dv_fx_angle
    sk3 = root.sketches.add(root.xYConstructionPlane)
    sk3.name = "sector profile"
    sk3.sketchCurves.sketchLines.addTwoPointRectangle(adsk.core.Point3D.create(SECTOR_R_IN_MM / 10, -SECTOR_HALF_HEIGHT_MM / 10, 0),
                                                      adsk.core.Point3D.create(SECTOR_R_OUT_MM / 10, SECTOR_HALF_HEIGHT_MM / 10, 0))
    rev = root.features.revolveFeatures
    ri = rev.createInput(sk3.profiles.item(0), root.yConstructionAxis, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    ri.setAngleExtent(False, _vi("dv_fx_angle"))
    sector = rev.add(ri)
    sector.name = "sector"
    sector.bodies.item(0).name = "sector"

    lib = app.materialLibraries.itemByName(MATERIAL_LIBRARY)
    mat = lib.materials.itemByName(MATERIAL)
    for b in root.bRepBodies:
        b.material = mat
    return {"bodies": [b.name for b in root.bRepBodies], "timeline": design.timeline.count, "parameters": design.userParameters.count}


def add_marker_fillet():
    """The feature that fails when the tube's inner diameter reaches zero (a wall at or above the outer radius)."""
    app, design = _design()
    _guard(app)
    root = design.rootComponent
    marker = next(b for b in root.bRepBodies if b.name == "marker")
    edges = adsk.core.ObjectCollection.create()
    for e in marker.edges:
        edges.add(e)
    fi = root.features.filletFeatures.createInput()
    fi.addConstantRadiusEdgeSet(edges, _vi("dr_fx_id / 100"), True)
    f = root.features.filletFeatures.add(fi)
    f.name = "marker fillet"
    return {"timeline": design.timeline.count}


def save(project_name, name=NAME_PREFIX):
    """Save the active (new) document under `name` in the root folder of the named project."""
    app, design = _design()
    if not name.startswith(NAME_PREFIX):
        raise RuntimeError("fixture names start with " + NAME_PREFIX)
    if not app.activeDocument.name.startswith("Untitled") or app.activeDocument.dataFile is not None:
        raise RuntimeError("only a new, unsaved document is saved by the fixture builder")
    projects = app.data.dataProjects
    project = next(projects.item(i) for i in range(projects.count) if projects.item(i).name == project_name)
    ok = app.activeDocument.saveAs(name, project.rootFolder, "bridge scratch fixture (Stage 3b)", "")
    return {"saved": bool(ok), "name": app.activeDocument.name}


def save_version(comment):
    """Save a new version of the active fixture document."""
    app, design = _design()
    name = app.activeDocument.name
    if not name.startswith(NAME_PREFIX):
        raise RuntimeError(f"refusing to save {name!r}: not a bridge fixture")
    ok = app.activeDocument.save(comment)
    return {"saved": bool(ok), "name": name, "version": app.activeDocument.dataFile.versionNumber}


def add_user_parameter(name, expression, unit):
    """Add a user parameter to the fixture (the unprefixed-parameter test of gate G4). Fixture documents only."""
    app, design = _design()
    doc_name = app.activeDocument.name
    if not doc_name.startswith(NAME_PREFIX):
        raise RuntimeError(f"refusing to add a parameter to {doc_name!r}: not a bridge fixture")
    design.userParameters.add(name, _vi(expression), unit, "added by a test")
    return {"count": design.userParameters.count}


def remove_user_parameter(name):
    """Remove a user parameter from the fixture. Fixture documents only."""
    app, design = _design()
    doc_name = app.activeDocument.name
    if not doc_name.startswith(NAME_PREFIX):
        raise RuntimeError(f"refusing to remove a parameter from {doc_name!r}: not a bridge fixture")
    p = design.userParameters.itemByName(name)
    if p is None or not p.deleteMe():
        raise RuntimeError(f"could not remove {name!r}")
    return {"count": design.userParameters.count}
