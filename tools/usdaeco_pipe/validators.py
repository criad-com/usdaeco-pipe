"""Five UsdValidation validators under keyword AecoPipeValidators."""
from .profiles import apply_profile, load_profile
from pxr import Gf, Usd, UsdGeom, UsdValidation

from . import SIZE_TOLERANCE, size_in_table

KEYWORD = "UsdAecoPipeValidators"
GAP_TOLERANCE = 1e-4  # metres; geometry coordinates use metersPerUnit


def _issue(name, prims, message, error=False):
    severity = (UsdValidation.ValidationErrorType.Error if error
                else UsdValidation.ValidationErrorType.Warn)
    return UsdValidation.ValidationError(name, severity, [
        UsdValidation.ValidationErrorSite(p.GetStage(), p.GetPath()) for p in prims], message)


def _kind(prim, time_range):
    if not (prim.HasAPI("AecoPipeAPI") or prim.HasAPI("AecoPipeFittingAPI")):
        return []
    code = prim.GetAttribute("aeco:class:ifc:code").Get() or ""
    if code.split(".")[0] not in ("IfcPipeSegment", "IfcPipeFitting"):
        return [_issue("pipeKindMismatch", [prim], "Pipe API has incompatible IFC classification: " + code)]
    return []


def _axis(prim, time_range):
    if prim.HasAPI("AecoPipeAPI") and not prim.HasAPI("AecoAxisAPI"):
        return [_issue("pipeMissingAxis", [prim], "AecoPipeAPI requires AecoAxisAPI", error=True)]
    return []


def _size(prim, time_range):
    if not prim.HasAPI("AecoPipeAPI"):
        return []
    try:
        valid = size_in_table(prim)
    except ValueError as exc:
        return [_issue("pipeSizeNotInTable", [prim], str(exc))]
    if valid is False:
        return [_issue("pipeSizeNotInTable", [prim], "Nominal diameter is absent from the catalog size table")]
    return []


def _owner(port):
    prim = port.GetParent()
    while prim and not prim.IsPseudoRoot():
        if prim.HasAPI("AecoElementAPI"):
            return prim
        prim = prim.GetParent()
    return None


def _connections(stage):
    # Stage callback makes an asymmetric edge visible even if its author has
    # the lexically larger path. Report each undirected pair exactly once.
    seen = set()
    for port in stage.Traverse():
        if not port.HasAPI("AecoPipePortAPI"):
            continue
        for path in port.GetRelationship("aeco:connectedPorts").GetTargets():
            peer = stage.GetPrimAtPath(path)
            if not peer or not peer.HasAPI("AecoPipePortAPI"):
                continue  # missing/incompatible targets belong to core validation
            key = tuple(sorted((str(port.GetPath()), str(path))))
            if key not in seen:
                seen.add(key)
                yield port, peer


def _port_sizes(stage, time_range):
    issues = []
    for port, peer in _connections(stage):
        owners = (_owner(port), _owner(peer))
        if any(p and (p.HasAPI("AecoPipeFittingAPI") or
                      (p.GetAttribute("aeco:class:ifc:code").Get() or "").split(".")[0]
                      == "IfcPipeFitting") for p in owners):
            continue
        a = port.GetAttribute("aeco:pipePort:nominalDiameter").Get()
        b = peer.GetAttribute("aeco:pipePort:nominalDiameter").Get()
        if a and b and abs(a - b) > SIZE_TOLERANCE:
            issues.append(_issue("pipePortSizeMismatch", [port, peer],
                                 "Connected port nominal diameters differ: %g m / %g m" % (a, b)))
    return issues


def _gaps(stage, time_range):
    issues = []
    cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    metres = UsdGeom.GetStageMetersPerUnit(stage)
    for port, peer in _connections(stage):
        a = cache.GetLocalToWorldTransform(port).Transform(Gf.Vec3d(0))
        b = cache.GetLocalToWorldTransform(peer).Transform(Gf.Vec3d(0))
        gap = (a - b).GetLength() * metres
        if gap > GAP_TOLERANCE:
            issues.append(_issue("pipeGap", [port, peer],
                                 "Connected port gap %.9g m exceeds %.9g m" % (gap, GAP_TOLERANCE), error=True))
    return issues


_RULES = (
    ("pipeKindMismatch", _kind, False, "Warn: pipe IFC classification must be IfcPipeSegment or IfcPipeFitting."),
    ("pipeMissingAxis", _axis, False, "Error: AecoPipeAPI requires the axis API."),
    ("pipeSizeNotInTable", _size, False, "Warn: unknown nominal size or malformed catalog table."),
    ("pipePortSizeMismatch", _port_sizes, True, "Warn: directly connected ports differ in nominal size without a fitting."),
    ("pipeGap", _gaps, True, "Error: connected port world positions differ by more than 0.0001 m."),
)


def register():
    """Idempotently register all rules, including after a Python module reload."""
    from . import register_plugins
    register_plugins()
    registry = UsdValidation.ValidationRegistry()
    for meta in registry.GetValidatorMetadataForKeyword(KEYWORD):
        if not registry.GetOrLoadValidatorByName(meta.name):
            raise RuntimeError("Pipe validator plugin did not load")


def register_core_validators():
    """Require the core Python plugin and every rule declared in its descriptor."""
    from . import core_root, register_plugins
    import importlib
    import json
    from pxr import Plug
    register_plugins()
    descriptor = core_root() / "usdAecoValidators" / "plugInfo.json"
    Plug.Registry().RegisterPlugins(str(descriptor.parent))
    try:
        importlib.import_module("usdAecoValidators")
    except ImportError as exc:
        raise RuntimeError("usdAecoValidators must be importable; core validation is required") from exc
    declared = json.loads(descriptor.read_text())["Plugins"][0]["Info"]["Validators"]
    names = sorted("usdAecoValidators:" + name for name, value in declared.items() if isinstance(value, dict))
    registry = UsdValidation.ValidationRegistry()
    loaded = registry.GetOrLoadValidatorsByName(names)
    if not names or len(loaded) != len(names) or not all(loaded):
        raise RuntimeError("Every declared usdAecoValidators rule must load")
    return names


def validate_stage(stage, include_core=False, include_builtin=True, profile=None):
    """Validate static/default-time pipe data, optionally with core rules."""
    register()
    keywords = [KEYWORD]
    if include_core:
        from usdaeco_tools import validators as core
        register_core_validators()
        keywords.append(core.KEYWORD)
    if include_builtin and load_profile(profile).get("include_builtin", True):
        keywords.append("UsdCoreValidators")
    registry = UsdValidation.ValidationRegistry()
    names = [m.name for key in keywords for m in registry.GetValidatorMetadataForKeyword(key)]
    context = UsdValidation.ValidationContext(registry.GetOrLoadValidatorsByName(names))
    issues = list(context.Validate(stage))
    # Compatibility for callers and profiles released before plugin discovery.
    canonical = {name[0].upper() + name[1:]: name for name, *_ in _RULES}
    issues = [UsdValidation.ValidationError(canonical[e.GetName()], e.GetType(),
              e.GetSites(), e.GetMessage()) if e.GetName() in canonical else e for e in issues]
    return apply_profile(issues, profile)


def split(issues):
    return ([e for e in issues if e.GetType() == UsdValidation.ValidationErrorType.Error],
            [e for e in issues if e.GetType() != UsdValidation.ValidationErrorType.Error])
