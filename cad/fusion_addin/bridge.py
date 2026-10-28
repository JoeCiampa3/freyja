"""
The Fusion-side module of the CAD bridge (Stage 3b). Pure functions: keyword arguments in, a JSON-serialisable dict out. Run inside Fusion through the
Autodesk Fusion MCP server (`tools/cad/transport.py` imports this file and prints a verb's result). Imports only `adsk` and the standard library.

Rules (CONVENTIONS section 9, rule 12):
  * a parameter is written only by setting its expression, never by assigning a value;
  * only `set_expressions` and `restore` write to a document, and both only touch user parameters;
  * the module carries no unit factors: lengths are returned in cm, angles in rad, inertia in kg cm^2, density in kg/cm^3, exactly as Fusion holds them, and
    arguments that are lengths are cm. `tools/cad/units.py` converts.
  * every verb takes `expect_name`, the name of the document it is allowed to act on, and refuses when the active document is another one.
"""
import adsk.core
import adsk.fusion

ACCURACY = {
    "low": adsk.fusion.CalculationAccuracy.LowCalculationAccuracy,
    "medium": adsk.fusion.CalculationAccuracy.MediumCalculationAccuracy,
    "high": adsk.fusion.CalculationAccuracy.HighCalculationAccuracy,
    "veryhigh": adsk.fusion.CalculationAccuracy.VeryHighCalculationAccuracy,
}
CLASS_PREFIXES = ("in_", "dv_", "dr_")
RESTORE_PASSES = 4          # a restore sets parameters in name order; a pass that fails on a dependent parameter is retried after the others are back


# ---- document access -------------------------------------------------------------------------------------------------------------------

def _design(expect_name=None):
    app = adsk.core.Application.get()
    doc = app.activeDocument
    if doc is None:
        raise RuntimeError("no active document")
    if expect_name is not None and doc.name != expect_name:
        raise RuntimeError(f"the active document is {doc.name!r}, not {expect_name!r}; nothing was done")
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        raise RuntimeError(f"{doc.name!r} has no design")
    return app, doc, design


def _version(doc):
    df = doc.dataFile
    return None if df is None else df.versionNumber


def _health(design):
    items, failed = [], []
    tl = design.timeline
    for i in range(tl.count):
        it = tl.item(i)
        state = it.healthState
        ok = state == adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState
        if not ok:
            failed.append(it.name)
        items.append({"index": i, "name": it.name, "healthy": ok, "message": "" if ok else (it.errorOrWarningMessage or "")})
    return {"healthy": not failed, "failed_features": failed, "items": items}


def _user_params(design):
    out = {}
    for p in design.userParameters:
        out[p.name] = p
    return out


def _rows(design):
    return [{"name": p.name, "expression": p.expression, "value": p.value, "unit": p.unit, "comment": p.comment}
            for p in sorted(_user_params(design).values(), key=lambda p: p.name)]


def activate_document(name):
    """Make an already open document the active one (what the other verbs act on). It changes which tab is in front and nothing in any document. Returns the
    name of the document that was active."""
    app = adsk.core.Application.get()
    previous = None if app.activeDocument is None else app.activeDocument.name
    target = next((d for d in app.documents if d.name == name), None)
    if target is None:
        raise RuntimeError(f"{name!r} is not open")
    target.activate()
    return {"previous": previous, "active": app.activeDocument.name}


# ---- read verbs ------------------------------------------------------------------------------------------------------------------------

def doc_info(expect_name=None):
    app, doc, design = _design(expect_name)
    df = doc.dataFile
    return {"name": doc.name, "id": None if df is None else df.id, "version": _version(doc), "saved": bool(doc.isSaved), "modified": bool(doc.isModified),
            "fusion_version": app.version, "length_units": design.unitsManager.defaultLengthUnits,
            "parametric": design.designType == adsk.fusion.DesignTypes.ParametricDesignType, "timeline_items": design.timeline.count}


def read_params(expect_name=None):
    _, _, design = _design(expect_name)
    return {"parameters": _rows(design)}


def timeline_health(expect_name=None):
    _, _, design = _design(expect_name)
    return _health(design)


def capture(expect_name=None):
    """Every user parameter's expression, and the timeline's health, as the restore point of a write."""
    _, _, design = _design(expect_name)
    return {"expressions": {r["name"]: r["expression"] for r in _rows(design)}, "health": _health(design)}


def physical_properties(expect_name=None, body=None, accuracy="veryhigh"):
    """Mass properties of one body (`body`, by name) or of the whole root component, at the given accuracy. Fusion's units; the inertia is about the world
    origin, as the tensor [[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]] (Fusion returns the matrix entries, not the integrals of the products; T3 verified the sign
    on an asymmetric body), `principal_kgcm2` the principal moments."""
    _, _, design = _design(expect_name)
    root = design.rootComponent
    acc = ACCURACY[accuracy]
    if body is None:
        target, bodies = root, list(root.bRepBodies)
    else:
        target = next((b for b in root.bRepBodies if b.name == body), None)
        if target is None:
            raise RuntimeError(f"no body named {body!r}")
        bodies = [target]
    pp = target.getPhysicalProperties(acc)
    _, xx, yy, zz, xy, yz, xz = pp.getXYZMomentsOfInertia()
    _, p1, p2, p3 = pp.getPrincipalMomentsOfInertia()
    c = pp.centerOfMass
    materials = sorted({b.material.name for b in bodies if b.material is not None})
    return {"body": body, "accuracy": accuracy, "mass_kg": pp.mass, "volume_cm3": pp.volume, "area_cm2": pp.area, "density_kg_cm3": pp.density,
            "com_cm": [c.x, c.y, c.z], "inertia_origin_kgcm2": {"ixx": xx, "iyy": yy, "izz": zz, "ixy": xy, "ixz": xz, "iyz": yz},
            "principal_kgcm2": [p1, p2, p3], "materials": materials, "bodies": sorted(b.name for b in bodies)}


def max_curvature_radius(expect_name=None, body=None):
    """The largest radius, in cm, of the analytic curved faces (cylinder, sphere, torus, cone) of one body or of the whole root component, or null when there is
    none, and `freeform_faces`, the number of faces that are neither planar nor one of those (free-form, elliptical): for them no chord bound can be stated. Fusion's STL export controls the tessellation by its normal deviation alone (its surface deviation setting had no effect on the triangle count in
    T3), so the client turns the binding's chord tolerance into a normal deviation with this radius: the largest radius is the strictest case."""
    _, _, design = _design(expect_name)
    root = design.rootComponent
    bodies = list(root.bRepBodies) if body is None else [b for b in root.bRepBodies if b.name == body]
    kinds = adsk.core.SurfaceTypes
    best, freeform = None, 0
    for b in bodies:
        for f in b.faces:
            g = f.geometry
            t = g.surfaceType
            if t in (kinds.CylinderSurfaceType, kinds.SphereSurfaceType, kinds.ConeSurfaceType):
                r = g.radius
            elif t == kinds.TorusSurfaceType:
                r = g.majorRadius + g.minorRadius
            elif t == kinds.PlaneSurfaceType:
                continue
            else:
                freeform += 1       # no analytic radius: the chord bound says nothing about this face
                continue
            best = r if best is None else max(best, r)
    return {"max_radius_cm": best, "freeform_faces": freeform}


def export_stl(path, surface_deviation_cm, normal_deviation_deg, expect_name=None, body=None):
    """Write an STL of the root component (or one body) to `path` at the given chord (surface) deviation in cm and normal deviation in degrees (the unit the STL options take)."""
    _, _, design = _design(expect_name)
    root = design.rootComponent
    target = root if body is None else next(b for b in root.bRepBodies if b.name == body)
    opts = design.exportManager.createSTLExportOptions(target, path)
    opts.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementCustom
    opts.surfaceDeviation = surface_deviation_cm
    opts.normalDeviation = normal_deviation_deg
    opts.isBinaryFormat = True
    opts.sendToPrintUtility = False
    if not design.exportManager.execute(opts):
        raise RuntimeError("the STL export failed")
    return {"path": path}


def export_step(path, expect_name=None):
    _, _, design = _design(expect_name)
    opts = design.exportManager.createSTEPExportOptions(path, design.rootComponent)
    if not design.exportManager.execute(opts):
        raise RuntimeError("the STEP export failed")
    return {"path": path}


# ---- write verbs: user-parameter expressions only --------------------------------------------------------------------------------------

def _set(design, name, expression):
    """Set one user parameter's expression; (True, '') or (False, the error)."""
    p = _user_params(design)[name]
    try:
        p.expression = expression
    except RuntimeError as e:
        return False, str(e)
    return True, ""


def set_expressions(expressions, allowed_prefixes=("in_",), rollback_on_failure=True, expect_name=None):
    """Set user parameters by expression, recompute, report the timeline's health and, on failure, roll back.

    `expressions` maps a parameter name to its new expression, with an explicit unit (`312.4 mm`). A name that is not a user parameter, a derived (`dr_`)
    name, or a name outside `allowed_prefixes` is refused before anything is written. Returns `ok`, the errors, the health after the write, whether it was
    rolled back and whether every expression then equals the one captured before, character for character. `failed_features` and `failure_messages` are
    those of the failed write, kept after a rollback has made `health` healthy again."""
    _, _, design = _design(expect_name)
    params = _user_params(design)
    refused = []
    for name in expressions:
        if name not in params:
            refused.append(f"{name}: not a user parameter")
        elif name.startswith("dr_"):
            refused.append(f"{name}: derived parameters are never set by the bridge")
        elif not name.startswith(tuple(allowed_prefixes)):
            refused.append(f"{name}: outside the classes this task may write {list(allowed_prefixes)}")
    if refused:
        return {"ok": False, "refused": refused, "errors": [], "rolled_back": False, "applied": [], "health": _health(design)}
    before = capture(expect_name)
    errors, applied = [], []
    for name in sorted(expressions):
        ok, err = _set(design, name, expressions[name])
        if ok:
            applied.append(name)
        else:
            errors.append(f"{name}: {err}")
            break
    health = _health(design)
    result = {"ok": not errors and health["healthy"], "refused": [], "errors": errors, "applied": applied, "health": health, "rolled_back": False,
              "failed_features": list(health["failed_features"]), "failure_messages": [i["message"] for i in health["items"] if not i["healthy"]]}
    if not result["ok"] and rollback_on_failure:
        result["rollback"] = restore(before["expressions"], expect_name=expect_name)
        result["rolled_back"] = True
        result["health"] = result["rollback"]["health"]
    return result


def restore(expressions, expect_name=None):
    """Put every user parameter back to a captured expression, then verify. Sets only the parameters that differ."""
    _, _, design = _design(expect_name)
    errors = []
    for _ in range(RESTORE_PASSES):
        errors = []
        params = _user_params(design)
        for name, expression in sorted(expressions.items()):
            if name in params and params[name].expression != expression:
                ok, err = _set(design, name, expression)
                if not ok:
                    errors.append(f"{name}: {err}")
        if not errors:
            break
    now = {r["name"]: r["expression"] for r in _rows(design)}
    differing = sorted(n for n in set(now) | set(expressions) if now.get(n) != expressions.get(n))
    health = _health(design)
    return {"equal": not differing, "differing": differing, "errors": errors, "health": health}
