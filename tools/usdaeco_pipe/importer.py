"""Promote IFC pipe facts into an additive kind layer above a core stage.

No geometry, bindings or sync engine are required. Input files stay unchanged.
Replaced quarantine values are blocked because USD overlays cannot delete
properties defined by a weaker layer. Unmapped property-set fields survive.
"""
import argparse
from collections import Counter, defaultdict
import json
import math
import os
from pathlib import Path
import re
import uuid

import ifcopenshell
import ifcopenshell.guid
import ifcopenshell.util.element as element
import ifcopenshell.util.shape as shape
import ifcopenshell.util.system as system
import ifcopenshell.util.unit as unit
from pxr import Gf, Sdf, Usd, UsdGeom

from . import APIS, SIZE_TOLERANCE, register_plugins, size_table

PIPE_PSET = "Pset_PipeSegmentTypeCommon"
PORT_PSET = "Pset_DistributionPortTypePipe"
SYSTEM_PSET = "Pset_PipeSystemCommon"  # documented optional exchange convention
CONNECTION_TYPES = ("undefined", "threaded", "flanged", "welded", "pushFit",
                    "compression", "solvent", "grooved", "other")


def _uid(entity):
    return str(uuid.UUID(hex=ifcopenshell.guid.expand(entity.GlobalId)))


def _si(value, source):
    """IFC named/derived units to SI, including temperature offsets."""
    value = float(value)
    if source is None:
        return value
    if source.is_a("IfcSIUnit"):
        factor = unit.get_prefix_multiplier(source.Prefix)
        if source.Name == "GRAM":
            factor *= 0.001  # SI base mass is kilogram, including derived Pa
        if source.Name == "DEGREE_CELSIUS":
            return value * factor + 273.15
        return value * factor
    if source.is_a("IfcConversionBasedUnit"):
        conversion = source.ConversionFactor
        offset = getattr(source, "ConversionOffset", 0.0)
        return _si((value + offset) * conversion.ValueComponent.wrappedValue,
                   conversion.UnitComponent)
    if source.is_a("IfcDerivedUnit"):
        factor = math.prod(_si(1.0, part.Unit) ** part.Exponent for part in source.Elements)
        return value * factor
    raise ValueError("Cannot convert IFC unit to SI: " + source.is_a())


def _property(model, entity, pset, name, unit_type=None):
    data = element.get_pset(entity, pset, name, verbose=True)
    if data is None:
        return None
    value = data["value"]
    if unit_type and value is not None:
        prop = model.by_id(data["id"])
        source = (unit.get_property_unit(prop, model)
                  or unit.get_project_unit(model, unit_type))
        return _si(value, source)
    return value


def _profiles(entity):
    """Occurrence body profiles first, then associated material profiles."""
    profiles = []
    for extrusion in shape.get_base_extrusions(entity) or []:
        profiles.append(extrusion.SweptArea)
    material = element.get_material(entity, should_skip_usage=True)
    if material and material.is_a("IfcMaterialProfileSet"):
        profiles.extend(p.Profile for p in material.MaterialProfiles if p.Profile)
    seen = set()
    unique = []
    for profile in profiles:
        if profile.is_a("IfcCircleHollowProfileDef") and profile.id() not in seen:
            seen.add(profile.id())
            unique.append(profile)
    return unique


def _nominal(model, entity, profile, scale, use_pset=True):
    value = _property(model, entity, PIPE_PSET, "NominalDiameter", "LENGTHUNIT") if use_pset else None
    if value is not None:
        return value, "pset"
    # DN is conventionally millimetres even in a metre/imperial IFC project.
    match = re.fullmatch(r"\s*DN\s*(\d+(?:\.\d+)?)\s*", profile.ProfileName or "", re.I)
    if match:
        return float(match.group(1)) / 1000.0, "profile-name"
    return float(profile.Radius) * 2 * scale, "outer-diameter-fallback"


def _catalog(prim):
    for path in prim.GetInherits().GetAllDirectInherits():
        candidate = prim.GetStage().GetPrimAtPath(path)
        if candidate and candidate.IsAbstract() and candidate.HasAPI("AecoTypeAPI"):
            return candidate
    return None


def _set(prim, name, value):
    if value is not None:
        prim.GetAttribute(name).Set(value)


def _block(prim, pset, field, stats):
    attr = prim.GetAttribute("aeco:props:" + pset + ":" + field)
    if attr and attr.HasValue():
        attr.Block()
        stats["propsBlocked"] += 1


def _fitting_geometry(model, entity, scale):
    # Preserve unavailable data as schema fallbacks; do not guess from a mesh.
    if not entity.Representation:
        return None, None
    for item in model.traverse(entity.Representation):
        if not item.is_a("IfcRevolvedAreaSolid"):
            continue
        angle = _si(item.Angle, unit.get_project_unit(model, "PLANEANGLEUNIT"))
        profile_pos = getattr(item.SweptArea, "Position", None)
        coords = profile_pos.Location.Coordinates if profile_pos else (0.0, 0.0)
        center = Gf.Vec3d(float(coords[0]), float(coords[1]), 0.0)
        axis = item.Axis
        origin = Gf.Vec3d(*map(float, axis.Location.Coordinates))
        direction = Gf.Vec3d(*map(float, axis.Axis.DirectionRatios)) if axis.Axis else Gf.Vec3d(0, 0, 1)
        radius = Gf.Cross(center - origin, direction.GetNormalized()).GetLength() * scale
        return angle, radius
    return None, None


def import_pipe(core_stage, ifc_file, output="kind.usda"):
    """Return import statistics; output is a layer sublayering core_stage.

    Opening output shows the composed result. It can also be sublayered into
    a larger stack. Existing outputs and any input/output alias are refused.
    """
    register_plugins()
    core_stage, ifc_file, output = map(lambda p: Path(p).resolve(), (core_stage, ifc_file, output))
    if output in (core_stage, ifc_file) or output.exists():
        raise ValueError("Output must be a new file distinct from the inputs: " + str(output))
    model = ifcopenshell.open(str(ifc_file))
    base = Usd.Stage.Open(str(core_stage))
    if not base:
        raise ValueError("Cannot open core stage")
    scale = unit.calculate_unit_scale(model)
    # Build completely in memory, then export once. Relative sublayers are
    # assigned only at export because anonymous layers have no directory.
    layer = Sdf.Layer.CreateAnonymous("kind.usda")
    layer.subLayerPaths = [str(core_stage)]
    stage = Usd.Stage.Open(layer)
    for key in ("defaultPrim", "upAxis", "metersPerUnit", "fallbackPrimTypes"):
        if base.HasAuthoredMetadata(key):
            stage.SetMetadata(key, base.GetMetadata(key))
    layer.customLayerData = {"aeco:library": "usdAecoPipe", "aeco:version": "0.2.0"}
    index = {}
    for prim in stage.Traverse():
        identity = prim.GetAttribute("aeco:id").Get()
        if identity:
            if identity in index:
                raise ValueError("Core stage has duplicate aeco:id: " + identity)
            index[identity] = prim
    stats = Counter({name: 0 for name in APIS})
    stats.update({"propsBlocked": 0, "nominalFallbacks": 0, "unmatched": 0})
    applied = set()

    def apply(prim, api):
        key = (str(prim.GetPath()), api)
        if key not in applied:
            if not prim.CanApplyAPI(api):
                raise ValueError("Cannot apply " + api + " to " + str(prim.GetPath()))
            prim.ApplyAPI(api)
            applied.add(key)
            stats[api] += 1

    type_rows = defaultdict(list)
    pipe_entities = model.by_type("IfcPipeSegment") + model.by_type("IfcPipeFitting")
    nominal_by_entity = {}
    for entity in pipe_entities:
        prim = index.get(_uid(entity))
        if prim is None:
            stats["unmatched"] += 1
            continue
        if entity.is_a("IfcPipeFitting"):
            apply(prim, "AecoPipeFittingAPI")
            _set(prim, "aeco:pipeFitting:origin", "authored")
            angle, radius = _fitting_geometry(model, entity, scale)
            _set(prim, "aeco:pipeFitting:angle", angle)
            _set(prim, "aeco:pipeFitting:bendRadius", radius)
        profiles = _profiles(entity)
        pset_nominal = _property(model, entity, PIPE_PSET, "NominalDiameter", "LENGTHUNIT")
        if pset_nominal is not None:
            nominal_by_entity[entity.id()] = pset_nominal
        if entity.is_a("IfcPipeSegment"):
            apply(prim, "AecoPipeAPI")
            if profiles:
                profile = profiles[0]
                nominal, source = _nominal(model, entity, profile, scale)
                nominal_by_entity[entity.id()] = nominal
                stats["nominalFallbacks"] += source == "outer-diameter-fallback"
                _set(prim, "aeco:pipe:nominalDiameter", nominal)
                _set(prim, "aeco:pipe:outerDiameter", 2 * float(profile.Radius) * scale)
                _set(prim, "aeco:pipe:innerDiameter", 2 * (float(profile.Radius) - float(profile.WallThickness)) * scale)
                _set(prim, "aeco:pipe:sizeLabel", profile.ProfileName or "")
            elif pset_nominal is not None:
                _set(prim, "aeco:pipe:nominalDiameter", pset_nominal)
            else:
                # Avoid silently presenting the schema's DN50 fallback as IFC data.
                prim.GetAttribute("aeco:pipe:nominalDiameter").Block()
            if pset_nominal is not None:
                _block(prim, PIPE_PSET, "NominalDiameter", stats)
            for field, target in (("OuterDiameter", "outerDiameter"), ("InnerDiameter", "innerDiameter")):
                value = _property(model, entity, PIPE_PSET, field, "LENGTHUNIT")
                if value is not None:
                    if not profiles:
                        _set(prim, "aeco:pipe:" + target, value)
                    _block(prim, PIPE_PSET, field, stats)
            slope = _property(model, entity, "Pset_PipeSegmentOccurrence", "Gradient")
            if slope is None and prim.HasAPI("AecoAxisAPI"):
                start = prim.GetAttribute("aeco:axis:start").Get()
                end = prim.GetAttribute("aeco:axis:end").Get()
                if start is not None and end is not None:
                    transform = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                    delta = transform.Transform(end) - transform.Transform(start)
                    up = 2 if UsdGeom.GetStageUpAxis(stage) == "Z" else 1
                    horizontal = math.sqrt(sum(delta[i] ** 2 for i in range(3) if i != up))
                    if horizontal > 1e-12:
                        slope = delta[up] / horizontal
            if slope is None:
                prim.GetAttribute("aeco:pipe:slope").Block()
            else:
                _set(prim, "aeco:pipe:slope", float(slope))
        catalog = _catalog(prim)
        if catalog is not None:
            apply(catalog, "AecoPipeTypeAPI")
            ifc_type = element.get_type(entity) or entity
            mat = element.get_material(ifc_type, should_skip_usage=True)
            if mat and mat.is_a("IfcMaterialProfileSet"):
                names = sorted({p.Material.Name for p in mat.MaterialProfiles if p.Material and p.Material.Name})
                if len(names) == 1:
                    _set(catalog, "aeco:pipeType:material", names[0])
            for field, target, unit_type in (("Reference", "schedule", None),
                                              ("WorkingPressure", "workingPressure", "PRESSUREUNIT")):
                value = _property(model, ifc_type, PIPE_PSET, field, unit_type)
                if value is not None:
                    _set(catalog, "aeco:pipeType:" + target, value)
                    _block(catalog, PIPE_PSET, field, stats)
                    # Only suppress an occurrence copy if it agrees with the
                    # type driver. A distinct occurrence fact has no typed home.
                    occurrence = _property(model, entity, PIPE_PSET, field, unit_type)
                    if occurrence == value:
                        _block(prim, PIPE_PSET, field, stats)
            for i, profile in enumerate(profiles):
                nominal, _ = _nominal(model, entity, profile, scale, use_pset=(i == 0))
                row = (nominal, 2 * float(profile.Radius) * scale,
                       2 * (float(profile.Radius) - float(profile.WallThickness)) * scale)
                rows = type_rows[catalog.GetPath()]
                same = [r for r in rows if abs(r[0] - nominal) <= SIZE_TOLERANCE]
                if same and any(abs(a - b) > SIZE_TOLERANCE for a, b in zip(same[0], row)):
                    raise ValueError("Conflicting IFC profile rows for nominal size %g" % nominal)
                if not same:
                    rows.append(row)
            # NominalDiameter on the type is promoted to the table when its
            # selected profile is known, not erased merely because the API exists.
            if profiles and _property(model, ifc_type, PIPE_PSET, "NominalDiameter") is not None:
                _block(catalog, PIPE_PSET, "NominalDiameter", stats)
            if profiles:
                for field in ("OuterDiameter", "InnerDiameter"):
                    _block(catalog, PIPE_PSET, field, stats)
    for path, rows in type_rows.items():
        prim = stage.GetPrimAtPath(path)
        for i, name in enumerate(("nominalDiameters", "outerDiameters", "innerDiameters")):
            _set(prim, "aeco:pipeType:" + name, [row[i] for row in sorted(rows)])
        size_table(prim)  # validate before publishing
    pipe_ids = {entity.id() for entity in pipe_entities}
    for port in model.by_type("IfcDistributionPort"):
        owner = system.get_port_element(port)
        if not (port.PredefinedType == "PIPE" or (owner and owner.id() in pipe_ids)
                or element.get_pset(port, PORT_PSET)):
            continue
        prim = index.get(_uid(port))
        if prim is None:
            stats["unmatched"] += 1
            continue
        apply(prim, "AecoPipePortAPI")
        nominal = _property(model, port, PORT_PSET, "NominalDiameter", "LENGTHUNIT")
        if nominal is None and owner:
            nominal = nominal_by_entity.get(owner.id())
        _set(prim, "aeco:pipePort:nominalDiameter", nominal)
        value = _property(model, port, PORT_PSET, "ConnectionType")
        if value is not None:
            normalized = re.sub(r"[^a-z]", "", str(value).lower())
            token = next((v for v in CONNECTION_TYPES if v.lower() == normalized), "other")
            _set(prim, "aeco:pipePort:connectionType", token)
    for group in model.by_type("IfcDistributionSystem"):
        if not (any(e.id() in pipe_ids for e in system.get_system_elements(group))
                or element.get_pset(group, SYSTEM_PSET)):
            continue
        prim = index.get(_uid(group))
        if prim is None:
            stats["unmatched"] += 1
            continue
        apply(prim, "AecoPipeSystemAPI")
        _set(prim, "aeco:pipeSystem:fluid", _property(model, group, SYSTEM_PSET, "Fluid"))
        _set(prim, "aeco:pipeSystem:fluidTemperature", _property(
            model, group, SYSTEM_PSET, "FluidTemperature", "THERMODYNAMICTEMPERATUREUNIT"))
    from .usd_importer import write_layers
    write_layers(stage, layer, output, [core_stage])
    return dict(stats)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aeco-pipe-import", description=__doc__)
    parser.add_argument("core_stage")
    parser.add_argument("ifc")
    parser.add_argument("-o", "--out", default="kind.usda")
    args = parser.parse_args(argv)
    try:
        stats = import_pipe(args.core_stage, args.ifc, args.out)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, "aeco-pipe-import: " + str(exc) + "\n")
    print(json.dumps(stats, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
