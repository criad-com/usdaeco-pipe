#!/usr/bin/env python3
"""Rebuild the deterministic pipe-run example using plain USD geometry."""
import math
import os
import sys
from pathlib import Path
import uuid

from pxr import Gf, Sdf, Usd, UsdGeom, Vt
from usdaeco_pipe import register_plugins


def build(output):
    register_plugins()
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/PipeRun", "Xform")
    stage.SetDefaultPrim(root)
    UsdGeom.SetStageMetersPerUnit(stage, 1)
    UsdGeom.SetStageUpAxis(stage, "Z")
    stage.SetMetadata("fallbackPrimTypes", {"AecoFacility": Vt.TokenArray(["Xform"]),
        "AecoLevel": Vt.TokenArray(["Xform"]), "AecoPort": Vt.TokenArray(["Xform"]),
        "AecoSystem": Vt.TokenArray(["Scope"])})

    def identity(prim):
        prim.GetAttribute("aeco:id").Set(str(uuid.uuid5(
            uuid.NAMESPACE_URL, "urn:usdaeco:example:pipe-run:" + str(prim.GetPath()))))

    def classify(prim, code):
        prim.ApplyAPI("AecoClassificationAPI", "ifc")
        prim.GetAttribute("aeco:class:ifc:code").Set(code)

    facility = stage.DefinePrim("/PipeRun/Facility", "AecoFacility")
    identity(facility); classify(facility, "IfcBuilding")
    level = stage.DefinePrim("/PipeRun/Facility/Level", "AecoLevel")
    identity(level); classify(level, "IfcBuildingStorey")
    level.GetAttribute("aeco:elevation").Set(0)
    stage.CreateClassPrim("/_TypeCatalog")
    catalog = stage.CreateClassPrim("/_TypeCatalog/SteelPipe")
    catalog.ApplyAPI("AecoTypeAPI"); catalog.ApplyAPI("AecoPipeTypeAPI")
    catalog.GetAttribute("aeco:type:model").Set("Steel pipe catalog")
    classify(catalog, "IfcPipeSegmentType.RIGIDSEGMENT")
    values = {"material": "Steel", "schedule": "Example catalog", "workingPressure": 1000000.0,
              "nominalDiameters": [0.05, 0.065, 0.08],
              "outerDiameters": [0.0603, 0.0761, 0.0889],
              "innerDiameters": [0.0543, 0.0701, 0.0829]}
    for name, value in values.items():
        catalog.GetAttribute("aeco:pipeType:" + name).Set(value)
    elements, ports = {}, {}

    def element(name, origin, code):
        prim = stage.DefinePrim(level.GetPath().AppendChild(name), "Xform")
        prim.ApplyAPI("AecoElementAPI"); identity(prim); classify(prim, code)
        UsdGeom.Xformable(prim).AddTranslateOp().Set(Gf.Vec3d(*origin))
        elements[name] = prim
        return prim

    def port(prim, name, position):
        p = stage.DefinePrim(prim.GetPath().AppendChild(name), "AecoPort")
        identity(p); p.ApplyAPI("AecoPipePortAPI")
        p.GetAttribute("aeco:medium").Set("pipe")
        p.GetAttribute("aeco:flowDirection").Set("bidirectional")
        p.GetAttribute("aeco:pipePort:nominalDiameter").Set(0.05)
        p.GetAttribute("aeco:pipePort:connectionType").Set("welded")
        UsdGeom.Xformable(p).AddTranslateOp().Set(Gf.Vec3d(*position))
        ports[prim.GetName() + "/" + name] = p

    def guide(prim, points, counts=None, approx="exact", tolerance=None):
        curve = UsdGeom.BasisCurves.Define(stage, prim.GetPath().AppendChild("Axis"))
        curve.CreateTypeAttr("linear"); curve.CreateWrapAttr("nonperiodic")
        curve.CreateCurveVertexCountsAttr(counts or [len(points)])
        curve.CreatePointsAttr(points); curve.CreateWidthsAttr([0.008])
        curve.SetWidthsInterpolation("constant"); curve.CreatePurposeAttr("guide")
        curve.GetPrim().ApplyAPI("AecoDerivedGeometryAPI")
        for name, value in {"source": prim.GetAttribute("aeco:id").Get(), "role": "axis",
                            "approx": approx, "stamp": "pipe example 0.1.0"}.items():
            curve.GetPrim().GetAttribute("aeco:derived:" + name).Set(value)
        if tolerance is not None:
            curve.GetPrim().GetAttribute("aeco:derived:tolerance").Set(tolerance)

    for name, origin, end in [
        ("Inlet", (0, 0, 1), (2, 0, 0)),
        ("Middle", (2.2, 0.2, 1), (0, 1.8, 0)),
        ("Outlet", (2.2, 2.4, 1), (0, 1.6, 0)),
        ("Branch", (2.4, 2.2, 1), (1.6, 0, 0)),
    ]:
        p = element(name, origin, "IfcPipeSegment.RIGIDSEGMENT")
        p.GetInherits().AddInherit(catalog.GetPath())
        p.ApplyAPI("AecoPipeAPI"); p.ApplyAPI("AecoAxisAPI")
        for n, v in {"start": (0, 0, 0), "end": end, "length": Gf.Vec3d(*end).GetLength()}.items():
            p.GetAttribute("aeco:axis:" + n).Set(v)
        for n, v in {"nominalDiameter": 0.05, "outerDiameter": 0.0603,
                     "innerDiameter": 0.0543, "sizeLabel": "DN50", "slope": 0.0}.items():
            p.GetAttribute("aeco:pipe:" + n).Set(v)
        port(p, "In", (0, 0, 0)); port(p, "Out", end)
    elbow = element("Elbow", (2, 0, 1), "IfcPipeFitting.BEND")
    elbow.ApplyAPI("AecoPipeFittingAPI")
    for n, v in {"origin": "generated", "angle": math.pi / 2, "bendRadius": 0.2}.items():
        elbow.GetAttribute("aeco:pipeFitting:" + n).Set(v)
    port(elbow, "In", (0, 0, 0)); port(elbow, "Out", (0.2, 0.2, 0))
    guide(elbow, [(0.2 * math.sin(i * math.pi / 16), 0.2 * (1 - math.cos(i * math.pi / 16)), 0)
                  for i in range(9)], approx="arcSegmented")
    tee = element("Tee", (2.2, 2.2, 1), "IfcPipeFitting.JUNCTION")
    tee.ApplyAPI("AecoPipeFittingAPI")
    tee.GetAttribute("aeco:pipeFitting:origin").Set("authored")
    port(tee, "In", (0, -0.2, 0)); port(tee, "Out", (0, 0.2, 0)); port(tee, "Branch", (0.2, 0, 0))
    # Straight branches: 0.2 m float32 encoding error is below 1e-8 m.
    guide(tee, [(0, -0.2, 0), (0, 0.2, 0), (0, 0, 0), (0.2, 0, 0)], [2, 2], tolerance=1e-8)
    for a, b in [("Inlet/Out", "Elbow/In"), ("Elbow/Out", "Middle/In"),
                 ("Middle/Out", "Tee/In"), ("Tee/Out", "Outlet/In"), ("Tee/Branch", "Branch/In")]:
        ports[a].GetRelationship("aeco:connectedPorts").SetTargets([ports[b].GetPath()])
        ports[b].GetRelationship("aeco:connectedPorts").SetTargets([ports[a].GetPath()])
    group = stage.DefinePrim("/PipeRun/Water", "AecoSystem")
    identity(group); classify(group, "IfcDistributionSystem.DOMESTICCOLDWATER")
    group.ApplyAPI("AecoPipeSystemAPI")
    group.GetAttribute("aeco:pipeSystem:fluid").Set("Water")
    group.GetAttribute("aeco:pipeSystem:fluidTemperature").Set(288.15)
    Usd.CollectionAPI(group, "members").GetIncludesRel().SetTargets([p.GetPath() for p in elements.values()])
    group.GetRelationship("aeco:serves").SetTargets([level.GetPath()])
    # Regenerate every driven guide with the pinned axis library. The tee and
    # segmented elbow are stored fitting geometry without single-axis drivers.
    repo = Path(__file__).resolve().parents[1]
    axis = Path(os.environ.get("AECO_AXIS_ROOT", repo.parent / "usdaeco-axis"))
    sys.path.insert(0, str(axis / "tools"))
    from usdaeco_axis.derive import derive
    derived = Sdf.Layer.CreateAnonymous("axis.derived.usda")
    derive(stage, derived)
    for prim in elements.values():
        if prim.HasAPI("AecoAxisAPI"):
            for path in (prim.GetPath().AppendChild("Axis"), prim.GetPath().AppendProperty("aeco:axis:length")):
                Sdf.CopySpec(derived, path, stage.GetRootLayer(), path)
    stage.GetRootLayer().Export(str(output))


if __name__ == "__main__":
    build(Path(__file__).resolve().parents[1] / "usdAecoPipe/examples/minimal.usda")
