"""Optional queries and registration for the codeless usdAecoPipe library."""
import json
import math
import os
from pathlib import Path
import sys

from pxr import Plug, Usd

__version__ = "0.2.6"
ROOT = Path(__file__).resolve().parents[2]
APIS = ("AecoPipeAPI", "AecoPipeTypeAPI", "AecoPipeFittingAPI",
        "AecoPipePortAPI", "AecoPipeSystemAPI")
SIZE_TOLERANCE = 1e-8  # metres, independent of the stage's geometry units


def core_root():
    return Path(os.environ.get("AECO_CORE_ROOT", os.environ.get(
        "CORE_DIR", ROOT.parent / "usdaeco-core")))


def _register(paths):
    kit = Path(os.environ.get("TOOLCHAIN_DIR", ROOT.parent / "usdaeco-toolchain"))
    if str(kit / "tools") not in sys.path:
        sys.path.insert(0, str(kit / "tools"))
    from usdaeco_check import plugin_requires
    result = plugin_requires(paths)
    if not result:
        raise RuntimeError(result.detail)


def _manifest():
    manifest = json.loads((ROOT / "library.json").read_text())
    return {key: manifest[key] for key in ("version", "tier", "requires")}


def dependency_plugins():
    axis = Path(os.environ.get("AECO_AXIS_ROOT", ROOT.parent / "usdaeco-axis"))
    return [os.environ.get("CORE_PLUGIN_DIR", core_root() / "out/plugins/usdAeco/resources"),
            os.environ.get("AXIS_PLUGIN_DIR", axis / "out/plugins/usdAecoAxis/resources")]


def register_core():
    """Register core first and reject missing/incompatible dependency metadata."""
    _register(dependency_plugins())
    from usdaeco_check.plugins import check_requirements
    core = Plug.Registry().GetPluginWithName("usdAeco")
    if not core or core.metadata["aeco"]["tier"] != "core":
        raise RuntimeError("usdAeco with core tier metadata is required")
    try:
        check_requirements({"usdAeco": core.metadata["aeco"], "usdAecoAxis": Plug.Registry().GetPluginWithName("usdAecoAxis").metadata["aeco"], "usdAecoPipe": _manifest()})
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc
    if "aecoDerived" not in core.metadata.get("SdfMetadata", {}):
        raise RuntimeError("usdAeco must register the aecoDerived property metadata")
    return core


def register_plugins(plugin_root=None, *, plugin_dir=None):
    """Load core then pipe before opening a stage or instantiating SchemaRegistry.

    The shared toolchain checks the full dependency closure and versions.
    plugin_root retains the legacy plugins/ layout; plugin_dir and
    PIPE_PLUGIN_DIR select a built resource directory directly.
    """
    register_core()
    if plugin_root is not None and plugin_dir is not None:
        raise ValueError("Supply plugin_root or plugin_dir, not both")
    path = plugin_dir or (Path(plugin_root) / "usdAecoPipe/resources" if plugin_root else
                         os.environ.get("PIPE_PLUGIN_DIR", ROOT / "usdAecoPipe"))
    _register([*dependency_plugins(), path])
    for folder in (ROOT, core_root(), core_root() / "tools"):
        if str(folder) not in sys.path:
            sys.path.insert(0, str(folder))
    Plug.Registry().RegisterPlugins(str(ROOT / "usdAecoPipeValidators"))
    plugin = Plug.Registry().GetPluginWithName("usdAecoPipe")
    if not plugin or plugin.metadata.get("aeco") != _manifest():
        raise RuntimeError("Rebuild usdAecoPipe from its library.json manifest")
    if Usd.SchemaRegistry().FindAppliedAPIPrimDefinition("AecoPipeAPI") is None:
        raise RuntimeError("Register pipe plugins before the first SchemaRegistry/stage; restart this process")
    return plugin


def iter_pipes(stage):
    """Yield active, defined occurrences carrying AecoPipeAPI (not catalog classes)."""
    return (prim for prim in stage.Traverse() if prim.HasAPI("AecoPipeAPI"))


def pipe_type_of(prim):
    """First inherited catalog class with AecoPipeTypeAPI, or None.

    Search inherits in strength order, including ancestral class inherits.
    An occurrence's inherited HasAPI alone is not proof it is a catalog type.
    """
    if not prim:
        return None
    if prim.IsAbstract() and prim.HasAPI("AecoPipeTypeAPI"):
        return prim
    stage = prim.GetStage()
    for path in prim.GetInherits().GetAllDirectInherits():
        candidate = stage.GetPrimAtPath(path)
        if candidate and candidate.IsAbstract() and candidate.HasAPI("AecoPipeTypeAPI"):
            return candidate
    return None


def size_table(type_prim):
    """Return ordered (nominal, outer, inner) tuples in metres.

    No type/table returns []; malformed, nonpositive, duplicate or misaligned
    catalog rows raise ValueError instead of silently truncating zipped arrays.
    """
    if not type_prim or not type_prim.HasAPI("AecoPipeTypeAPI"):
        return []
    arrays = [list(type_prim.GetAttribute("aeco:pipeType:" + name).Get() or [])
              for name in ("nominalDiameters", "outerDiameters", "innerDiameters")]
    if len({len(a) for a in arrays}) != 1:
        raise ValueError("size-table arrays must have equal lengths")
    rows = [tuple(map(float, row)) for row in zip(*arrays)]
    seen = []
    for nominal, outer, inner in rows:
        if (not all(math.isfinite(v) and v > 0 for v in (nominal, outer, inner))
                or inner > outer):
            raise ValueError("size-table dimensions must be finite and positive, inner <= outer")
        if any(abs(nominal - n) <= SIZE_TOLERANCE for n in seen):
            raise ValueError("size-table nominal keys must be unique")
        seen.append(nominal)
    return rows


def size_in_table(prim):
    """True/False for a known valid catalog; None if no type or empty table.

    Malformed tables raise ValueError. Values are schema SI metres even when
    metersPerUnit changes. Missing/blocked nominal values fail a known table.
    """
    rows = size_table(pipe_type_of(prim))
    if not rows:
        return None
    diameter = prim.GetAttribute("aeco:pipe:nominalDiameter").Get()
    return diameter is not None and any(
        abs(diameter - row[0]) <= SIZE_TOLERANCE for row in rows)
