#!/usr/bin/env python3
"""Print N checks, M failed. Executable acceptance checks; --baseline optionally tests an external IFC.

The full gate always runs independent synthetic IFC coverage, including fitting
geometry, promotion and SI conversion. --without-importer explicitly selects
the USD-only gate. Both run a fresh plugin-free subprocess; no sync dependency.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parent
TOOLCHAIN = Path(os.environ.get("TOOLCHAIN_DIR", ROOT.parent / "usdaeco-toolchain"))
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "testenv"), str(TOOLCHAIN / "tools")]
from usdaeco_check import (Report, Result, can_apply, link_check, plugin_requires,
                           registry_probe, term_sweep, validate_examples)
from usdaeco_pipe import (APIS, core_root, iter_pipes, pipe_type_of, register_plugins, dependency_plugins,
                          size_in_table, size_table)
sys.path.insert(0, str(core_root() / "tools"))
from pxr import Gf, Plug, Sdf, Usd, UsdGeom, UsdValidation
from usdaeco_pipe import validators

REPORT = Report()
check = REPORT.check
EXAMPLE = ROOT / "usdAecoPipe/examples/minimal.usda"
ELEMENT = "/PipeRun/Facility/Level/"
MIT_SHA256 = "202a23a57b429d91028dc1b4f62b6342bad6bc3ee294d20c58f363fac184e346"


def fresh():
    layer = Sdf.Layer.CreateAnonymous("example.usda")
    layer.TransferContent(Sdf.Layer.FindOrOpen(str(EXAMPLE)))
    return Usd.Stage.Open(layer)


def findings(stage):
    return Counter((e.GetName(), str(e.GetType()).rsplit(".", 1)[-1])
                   for e in validators.validate_stage(stage, include_builtin=False))


def subprocess_python(args, *, cwd=ROOT):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PXR_PLUGINPATH_NAME", None)
    env.pop("PXR_AR_DEFAULT_SEARCH_PATH", None)
    return subprocess.run([sys.executable, *map(str, args)], cwd=cwd, env=env,
                          text=True, capture_output=True, check=True)


def convert(source, destination):
    # Execute the reference CLI in a fresh process, with tools on sys.path;
    # the global PYTHONPATH stays unset for all pxr imports.
    code = ("import runpy,sys; sys.path.insert(0,sys.argv.pop(1)); sys.path.insert(0,sys.argv.pop(1)); "
            "from pxr import Plug; [Plug.Registry().RegisterPlugins(sys.argv.pop(1)) for _ in range(2)]; "
            "runpy.run_module('usdaeco_ifc.convert',run_name='__main__')")
    subprocess_python(["-c", code, TOOLCHAIN / "tools", Path(os.environ.get("AECO_IFC_ROOT", ROOT.parent / "usdaeco-ifc")) / "tools", *dependency_plugins(), source, "-o", destination])


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def schema_checks():
    registry = Usd.SchemaRegistry()
    definitions = [registry.FindAppliedAPIPrimDefinition(api) for api in APIS]
    probe = registry_probe(APIS)
    check("registry resolves exactly five pipe APIs", probe and
          len(Plug.Registry().GetPluginWithName("usdAecoPipe").metadata["Types"]) == 5)
    plugin = Plug.Registry().GetPluginWithName("usdAecoPipe")
    manifest = json.loads((ROOT / "library.json").read_text())
    check("codeless plugin declares version, kind tier and core requirement",
          plugin.isResource and plugin.name == manifest["name"] and
          plugin.metadata["aeco"] == {key: manifest[key] for key in ("version", "tier", "requires")})
    REPORT.run("PipePort refuses Mesh; PipeSystem refuses Scope; valid targets accepted", can_apply,
               [("Mesh", "AecoPipePortAPI", False), ("Scope", "AecoPipeSystemAPI", False),
                ("AecoPort", "AecoPipePortAPI", True), ("AecoSystem", "AecoPipeSystemAPI", True)])
    REPORT.run("Pipe and Fitting require Imageable", can_apply,
               [(typ, api, allowed) for api in ("AecoPipeAPI", "AecoPipeFittingAPI")
                for typ, allowed in (("Mesh", True), ("AecoSystem", False))])
    derived = {"aeco:pipe:" + n for n in ("outerDiameter", "innerDiameter", "sizeLabel", "slope")}
    derived |= {"aeco:pipeType:" + n for n in ("nominalDiameters", "outerDiameters", "innerDiameters")}
    derived |= {"aeco:pipeFitting:angle", "aeco:pipeFitting:bendRadius"}
    properties = {n: d for d in definitions for n in d.GetPropertyNames()}
    flags = {n for n, d in properties.items() if d.GetPropertyMetadata(n, "aecoDerived") is True}
    check("all nine derived flags visible; drivers unflagged", flags == derived)
    source = Sdf.Layer.FindOrOpen(str(ROOT / "usdAecoPipe/schema.usda"))
    documented = [p.documentation for api in APIS for p in source.GetPrimAtPath("/" + api).properties]
    check("all 18 source properties documented; no kind tokens or geometry properties",
          len(properties) == len(documented) == 18 and all(documented)
          and all(n.startswith(("aeco:pipe:", "aeco:pipeType:", "aeco:pipeFitting:", "aeco:pipePort:", "aeco:pipeSystem:"))
                  and not n.endswith((":kind", ":systemType")) for n in properties))
    validators.register(); validators.register()
    check("five validators registered idempotently by keyword", len(
        UsdValidation.ValidationRegistry().GetValidatorMetadataForKeyword(validators.KEYWORD)) == 5)


def example_checks():
    s = fresh()
    # Preserve the zero-warning contract as well as the shared composition,
    # fallback coverage and built-in validation checks.
    errors, warnings = validators.split(validators.validate_stage(s, include_core=True))
    result = validate_examples(ROOT / "usdAecoPipe/examples", [], validators=[
        lambda stage: validators.validate_stage(stage, include_core=True, include_builtin=False)])
    check("example passes pipe, core and built-in validators", result and not errors and not warnings,
          result.detail + ("; " + "; ".join(e.GetMessage() for e in errors + warnings)
                           if errors or warnings else ""))
    probe = fresh()
    probe.GetPrimAtPath(ELEMENT + "Tee/Axis").RemoveProperty("aeco:derived:tolerance")
    missing = validators.validate_stage(probe, include_core=True, include_builtin=False)
    check("core E15 detects a missing tee generation tolerance",
          [e.GetName() for e in missing] == ["ExactWithoutTolerance"])
    pipes = list(iter_pipes(s)); catalog = s.GetPrimAtPath("/_TypeCatalog/SteelPipe")
    check("queries resolve four occurrences and the inherited three-row catalog",
          len(pipes) == 4 and all(pipe_type_of(p) == catalog and size_in_table(p) is True for p in pipes)
          and size_table(catalog) == [(0.05, 0.0603, 0.0543), (0.065, 0.0761, 0.0701), (0.08, 0.0889, 0.0829)])
    check("example has an elbow, tee, generated provenance and symmetric ports",
          s.GetPrimAtPath(ELEMENT + "Elbow").GetAttribute("aeco:pipeFitting:origin").Get() == "generated"
          and s.GetPrimAtPath(ELEMENT + "Tee").HasAPI("AecoPipeFittingAPI")
          and len(list(validators._connections(s))) == 5)
    catalog.GetAttribute("aeco:pipeType:workingPressure").Set(2000000)
    pipes[0].GetAttribute("aeco:pipeType:workingPressure").Set(3000000)
    check("type edits broadcast and occurrence overrides win", all(
        p.GetAttribute("aeco:pipeType:workingPressure").Get() == (3000000 if i == 0 else 2000000)
        for i, p in enumerate(pipes)))
    for label, mutate, expected in [
        ("missing axis", lambda p: p.RemoveAPI("AecoAxisAPI"), ("pipeMissingAxis", "Error")),
        ("nominal size 0.033 m", lambda p: p.GetAttribute("aeco:pipe:nominalDiameter").Set(0.033), ("pipeSizeNotInTable", "Warn")),
        ("wrong IFC kind", lambda p: p.GetAttribute("aeco:class:ifc:code").Set("IfcDuctSegment"), ("pipeKindMismatch", "Warn")),
    ]:
        s = fresh(); mutate(s.GetPrimAtPath(ELEMENT + "Inlet"))
        check("seeded " + label, findings(s) == Counter({expected: 1}), str(findings(s)))
    s = fresh()
    s.GetPrimAtPath(ELEMENT + "Middle/In").GetAttribute("xformOp:translate").Set(Gf.Vec3d(0.5, 0, 0))
    check("seeded 0.5 m port gap produces one error", findings(s) == Counter({("pipeGap", "Error"): 1}))
    s = fresh(); port = s.GetPrimAtPath(ELEMENT + "Inlet/Out"); peer = s.GetPrimAtPath(ELEMENT + "Middle/In")
    # Connect pipe directly to pipe; size rule operates independently of gap.
    port.GetRelationship("aeco:connectedPorts").SetTargets([peer.GetPath()])
    peer.GetRelationship("aeco:connectedPorts").SetTargets([port.GetPath()])
    peer.GetAttribute("aeco:pipePort:nominalDiameter").Set(0.065)
    check("direct pipe-port diameter mismatch warns once", findings(s)[("pipePortSizeMismatch", "Warn")] == 1)
    s = fresh(); s.GetPrimAtPath(ELEMENT + "Middle/In").GetAttribute("aeco:pipePort:nominalDiameter").Set(0.065)
    check("fitting between different port sizes suppresses mismatch", not findings(s))
    s = fresh(); catalog = s.GetPrimAtPath("/_TypeCatalog/SteelPipe")
    catalog.GetAttribute("aeco:pipeType:innerDiameters").Set([0.01])
    check("malformed size arrays warn instead of silently truncating", findings(s)[("pipeSizeNotInTable", "Warn")] == 4)
    s = fresh(); p = s.GetPrimAtPath(ELEMENT + "Inlet"); p.GetInherits().ClearInherits()
    check("missing catalog is unknown, not an invalid size", size_in_table(p) is None and not findings(s))
    s = fresh(); UsdGeom.SetStageMetersPerUnit(s, 0.001)
    port = s.GetPrimAtPath(ELEMENT + "Middle/In")
    port.GetAttribute("xformOp:translate").Set((0.05, 0, 0))
    below = not findings(s)
    port.GetAttribute("xformOp:translate").Set((0.5, 0, 0))
    check("gap threshold uses SI metres with millimetre geometry", below and findings(s) == Counter({("pipeGap", "Error"): 1}))
    s = fresh(); port = s.GetPrimAtPath(ELEMENT + "Middle/In"); peer = s.GetPrimAtPath(ELEMENT + "Elbow/Out")
    peer.GetRelationship("aeco:connectedPorts").ClearTargets(True)
    port.GetAttribute("xformOp:translate").Set((0.5, 0, 0))
    check("one-way connection still reports a gap once", findings(s) == Counter({("pipeGap", "Error"): 1}))


VANILLA = r'''
import json,sys
from pxr import Usd,UsdGeom,Plug
s=Usd.Stage.Open(sys.argv[1])
assert not any(p.name.startswith('usdAeco') for p in Plug.Registry().GetAllPlugins())
assert Usd.SchemaRegistry().FindAppliedAPIPrimDefinition('AecoPipeAPI') is None
out={}
for p in s.Traverse():
    if UsdGeom.Xformable(p):
        matrix=UsdGeom.Xformable(p).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        out[str(p.GetPath())]=[float(v) for row in matrix for v in row]
assert s.GetPrimAtPath('/PipeRun/Water').GetPrimTypeInfo().GetSchemaTypeName()=='Scope'
assert s.GetPrimAtPath('/PipeRun/Facility/Level/Inlet/In').GetPrimTypeInfo().GetSchemaTypeName()=='Xform'
assert s.GetPrimAtPath('/PipeRun/Facility/Level/Inlet').GetAttribute('aeco:pipe:nominalDiameter').Get()==0.05
print(json.dumps(out))
'''


def vanilla_check():
    output = subprocess_python(["-c", VANILLA, EXAMPLE])
    s = fresh()
    transforms = {str(p.GetPath()): [float(v) for row in UsdGeom.Xformable(p).
        ComputeLocalToWorldTransform(Usd.TimeCode.Default()) for v in row]
        for p in s.Traverse() if UsdGeom.Xformable(p)}
    check("vanilla probe: no plugins, fallbacks and all world transforms identical",
          json.loads(output.stdout) == transforms, "%d transforms; authored pipe data legible" % len(transforms))


def importer_checks(directory, external):
    from usdaeco_pipe.importer import import_pipe
    from fixtures import augment, build_baseline
    local = directory / "fixture.ifc"
    build_baseline(local)
    source = Path(external).resolve() if external else local
    base = directory / "core.usda"
    convert(source, base)
    inputs = {p: digest(p) for p in [source, *directory.glob("core.*")]}
    out = directory / "kind.usda"
    output = subprocess_python([ROOT / "tools/aeco-pipe-import", base, source, "-o", out])
    stats = json.loads(output.stdout)
    s = Usd.Stage.Open(str(out))
    import ifcopenshell
    model = ifcopenshell.open(str(source))
    count = len(model.by_type("IfcPipeSegment"))
    check("baseline CLI import matches actual IFC entities", stats["AecoPipeAPI"] == count == len(list(iter_pipes(s)))
          and stats["AecoPipeFittingAPI"] == len(model.by_type("IfcPipeFitting"))
          and stats["AecoPipePortAPI"] == len(model.by_type("IfcDistributionPort"))
          and stats["AecoPipeSystemAPI"] == len(model.by_type("IfcDistributionSystem")), json.dumps(stats, sort_keys=True))
    errors, warnings = validators.split(validators.validate_stage(s, include_core=True))
    check("baseline imported stage has zero validation errors", not errors,
          "%d errors, %d warnings" % (len(errors), len(warnings)))
    check("baseline tables contain actual IFC profiles; axes preserved", all(
        size_in_table(p) is True and len(size_table(pipe_type_of(p))) == 1 and p.HasAPI("AecoAxisAPI") for p in iter_pipes(s)))
    specs = []
    s.GetRootLayer().Traverse(Sdf.Path.absoluteRootPath, lambda path: specs.append(path))
    check("import preserves input bytes and authors no geometry/transforms", all(digest(p) == h for p, h in inputs.items())
          and all(path.name.startswith(("aeco:pipe", "aeco:props:")) for path in specs if path.IsPropertyPath()))
    # Add/remove the kind layer from a session, proving the core view returns.
    session = Sdf.Layer.CreateAnonymous("session.usda")
    session.TransferContent(Sdf.Layer.FindOrOpen(str(base)))
    session.subLayerPaths = [str(out), str(base)]
    composed = Usd.Stage.Open(session)
    has_pipe = len(list(iter_pipes(composed))) == count
    composed.MuteLayer(str(out))
    plain = Usd.Stage.Open(str(base))
    check("muting kind restores core stage without moving geometry", has_pipe and not list(iter_pipes(composed))
          and composed.Flatten(False).ExportToString() == plain.Flatten(False).ExportToString())
    augmented = directory / "augmented.ifc"
    augment(source, augmented)
    augbase = directory / "augmented.usda"; convert(augmented, augbase)
    augout = directory / "augmented-kind.usda"
    stats = import_pipe(augbase, augmented, augout)
    stage = Usd.Stage.Open(str(augout))
    check("augmented baseline exercises all five APIs", all(stats[a] > 0 for a in APIS), json.dumps(stats, sort_keys=True))
    promoted = [a for p in stage.TraverseAll() for a in p.GetAttributes() if a.GetName().startswith(
        "aeco:props:Pset_PipeSegmentTypeCommon:") and a.GetName().rsplit(":", 1)[-1] in (
            "NominalDiameter", "OuterDiameter", "InnerDiameter", "Reference", "WorkingPressure")]
    remaining = [a for p in stage.TraverseAll() for a in p.GetAttributes() if a.GetName() == "aeco:props:Pset_PipeSegmentTypeCommon:Status"]
    check("promoted quarantine values blocked; unmapped properties retained", stats["propsBlocked"] > 0 and promoted
          and all(a.Get() is None for a in promoted) and remaining and all(a.Get() == "NEW" for a in remaining))
    pipes = list(iter_pipes(stage))
    check("profile rows and pressure use SI", all(
        p.GetAttribute("aeco:pipe:nominalDiameter").Get() == 0.05
        and p.GetAttribute("aeco:pipeType:workingPressure").Get() == 600000
        and len(size_table(pipe_type_of(p))) == 2
        and size_table(pipe_type_of(p))[1] == (0.065, 0.0761, 0.0701) for p in pipes))
    systems = [p for p in stage.Traverse() if p.HasAPI("AecoPipeSystemAPI")]
    ports = [p for p in stage.Traverse() if p.HasAPI("AecoPipePortAPI")]
    fittings = [p for p in stage.Traverse() if p.HasAPI("AecoPipeFittingAPI")]
    check("port tokens, Celsius-to-Kelvin and fitting geometry imported", all(
        p.GetAttribute("aeco:pipePort:connectionType").Get() == "pushFit" for p in ports)
        and systems[0].GetAttribute("aeco:pipeSystem:fluidTemperature").Get() == 293.15
        and any(abs(p.GetAttribute("aeco:pipeFitting:angle").Get() - math.pi / 2) < 1e-10 and
                abs(p.GetAttribute("aeco:pipeFitting:bendRadius").Get() - 0.2) < 1e-10 for p in fittings))
    errors, warnings = validators.split(validators.validate_stage(stage, include_core=True))
    check("augmented import validates with zero errors", not errors, "%d errors, %d warnings" % (len(errors), len(warnings)))
    try:
        import_pipe(base, source, out)
    except ValueError:
        refuses = True
    else:
        refuses = False
    check("importer refuses overwriting an existing output", refuses)
    # Always exercise a second, independent fixture, including metre-to-mm
    # conversion of geometry and explicit SI property overrides.
    import ifcopenshell.util.unit as units
    mm_geometry = directory / "millimetres-geometry.ifc"
    units.convert_file_length_units(ifcopenshell.open(str(local)), "MILLIMETER").write(str(mm_geometry))
    mm = directory / "millimetres.ifc"
    # Add explicit metre-valued properties after changing project units: the
    # utility scales property numbers without updating their explicit Unit.
    augment(mm_geometry, mm)
    mmbase = directory / "millimetres.usda"; convert(mm, mmbase)
    mmout = directory / "millimetres-kind.usda"
    import_pipe(mmbase, mm, mmout)
    mmstage = Usd.Stage.Open(str(mmout))
    check("millimetre IFC: nominal, outer and bore stay distinct SI values", all(
        abs(p.GetAttribute("aeco:pipe:nominalDiameter").Get() - 0.05) < 1e-10
        and abs(p.GetAttribute("aeco:pipe:outerDiameter").Get() - 0.0603) < 1e-10
        and abs(p.GetAttribute("aeco:pipe:innerDiameter").Get() - 0.0543) < 1e-10
        and size_in_table(p) is True for p in iter_pipes(mmstage)))
    errors, warnings = validators.split(validators.validate_stage(mmstage, include_core=True))
    check("millimetre IFC: world ports remain coincident after conversion", not errors,
          "%d errors, %d warnings" % (len(errors), len(warnings)))


def migration_checks():
    from schema_contract import compare_schema
    check("published Sdf property contract unchanged", compare_schema() == (5, 18, 9), "v0.1.2: 5 APIs, 18 properties, 9 derived flags")
    from usdaeco_check.example import check_example
    print("== stage: pinned data-centre example", flush=True)
    result = check_example(ROOT / "examples/datacentre")
    REPORT.add(result)
    if not result:
        return
    out = ROOT / "examples/datacentre/out"
    if not (out / "manifest.json").is_file():
        return
    stage = Usd.Stage.Open(str(out / "example.usda"))
    stats = json.loads((out / "import.json").read_text())
    axes = json.loads((out / "axis.json").read_text())
    manifest = json.loads((out / "manifest.json").read_text())
    check("published pipeline selects pinned source and all pipe refinements", manifest["source"]["mode"] == "pinned"
          and [stats[a] for a in APIS] == [482,17,238,1650,5], json.dumps(stats, sort_keys=True))
    from usdaeco_pipe.example import CASE_IDS
    index = {p.GetAttribute("aeco:props:DC_Identity:Id").Get():p for p in stage.Traverse()}
    check("five required DN50 identities have OD 60.3 mm and inherited catalogs", all(
        index[k].GetAttribute("aeco:pipe:nominalDiameter").Get() == .05 and
        abs(index[k].GetAttribute("aeco:pipe:outerDiameter").Get() - .0603) < 1e-9
        and pipe_type_of(index[k]) for k in CASE_IDS))
    check("unavailable nominal values stay blocked; catalogs remain incomplete", stats["unknownNominal"] == 476
          and sum(p.GetAttribute("aeco:pipe:nominalDiameter").Get() is None for p in iter_pipes(stage)) == 476
          and stats["incompleteTables"] == 17)
    def attributes(layer):
        paths = []
        layer.Traverse(Sdf.Path.absoluteRootPath, lambda path: paths.append(path) if path.IsPropertyPath() else None)
        return [stage.GetPropertyAtPath(path) for path in paths]
    drivers = Sdf.Layer.FindOrOpen(str(out / "pipe.usda"))
    derived = Sdf.Layer.FindOrOpen(str(out / "pipe.derived.usda"))
    check("imported drivers and schema-marked readback occupy separate layers", all(
        a.GetMetadata("aecoDerived") is not True for a in attributes(drivers))
        and all(a.GetMetadata("aecoDerived") is True for a in attributes(derived)) and bool(attributes(derived)))
    check("axis derivation writes 1794 guide representations", axes["axes"] == 1794 and
          sum(p.GetAttribute("aeco:derived:role").Get() == "axis" for p in stage.Traverse()) >= 1794)
    check("final render includes guides and excludes every extent", manifest["presentation"]["purposes"] == ["guide","proxy","render"]
          and all(UsdGeom.Imageable(p).ComputeVisibility() == "invisible" for p in stage.Traverse()
                  if p.GetAttribute("aeco:derived:role").Get() == "extent"))
    from usdaeco_pipe.pinned import datacentre_root
    dc = datacentre_root(ROOT) / "dist/clash"
    wanted = json.loads((dc / "dc.manifest.json").read_text())["layers"]
    check("published USD layer hashes still match the release manifest", all(digest(dc/name) == item["sha256"] for name,item in wanted.items()))
    code = r'''
import json,sys
from pxr import Plug,Usd,UsdGeom
s=Usd.Stage.Open(sys.argv[1])
assert not any(p.name.startswith("usdAeco") for p in Plug.Registry().GetAllPlugins())
assert not s.GetCompositionErrors()
fallbacks=s.GetMetadata("fallbackPrimTypes")
for p in s.TraverseAll():
    if p.GetTypeName().startswith("Aeco"):
        assert any(t in ("Xform","Scope") for t in fallbacks[p.GetTypeName()])
base=Usd.Stage.Open(sys.argv[2])
count=0
for p in base.Traverse():
    if UsdGeom.Xformable(p):
        a=UsdGeom.Xformable(p).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        b=UsdGeom.Xformable(s.GetPrimAtPath(p.GetPath())).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        assert a==b
        count+=1
print(count)
'''
    output = subprocess_python(["-c",code,out/"example.usda",dc/"dc.usda"])
    check("plugin-free data-centre composition preserves every source transform", int(output.stdout) > 9000, output.stdout.strip() + " transforms")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", help="external reference IFC, otherwise use the synthetic fixture")
    parser.add_argument("--report", type=Path, help="optional JSON acceptance report")
    parser.add_argument("--core-plugin", default=os.environ.get(
        "CORE_PLUGIN_DIR", str(core_root() / "out/plugins/usdAeco/resources")))
    parser.add_argument("--plugin", default=os.environ.get(
        "PIPE_PLUGIN_DIR", str(ROOT / "usdAecoPipe")))
    parser.add_argument("--without-importer", action="store_true",
                        help="Explicit USD-only gate for environments without IfcOpenShell")
    parser.add_argument("--profile", type=Path, default=ROOT / "conformance/profiles/pipe.json",
                        help="Severity overlay for example conformance; seeded contract probes retain default grades")
    args = parser.parse_args()
    if args.without_importer and args.baseline:
        parser.error("--baseline requires importer checks")
    os.environ["CORE_PLUGIN_DIR"] = args.core_plugin
    os.environ["PIPE_PLUGIN_DIR"] = args.plugin
    try:
        if not REPORT.run("plugin requirements", plugin_requires, [*dependency_plugins(), args.plugin]):
            return REPORT.finish()
        register_plugins()
        core_rules = validators.register_core_validators()
        check("all eight core validator plugin rules loaded", len(core_rules) == 8,
              ", ".join(core_rules))
        print("== stage: schema and minimal example", flush=True)
        schema_checks()
        example_checks()
        profiled = validators.validate_stage(fresh(), include_core=True, profile=args.profile)
        check("profile example conformance", not validators.split(profiled)[0])

        vanilla_check()
        if not args.without_importer:
            with tempfile.TemporaryDirectory(prefix="aeco-pipe-check-") as directory:
                importer_checks(Path(directory), args.baseline)
        migration_checks()
        print("== stage: structure", flush=True)
        from usdaeco_check.structure import check_structure
        for result in check_structure(ROOT, deps=dependency_plugins()):
            # S01 in toolchain 0.3.1 predates the family's MIT licence policy.
            # Only its exact Apache rejection is replaced; missing files and
            # every other rule remain failures. Verify the full MIT text.
            if result.name == "S01" and result.detail == "Apache-2.0 license text required":
                valid = (digest(ROOT / "LICENSE") == MIT_SHA256
                         and json.loads((ROOT / "library.json").read_text()).get("license") == "MIT")
                result = Result("S01", valid,
                                "family MIT policy; upstream S01 requires Apache-2.0 (documented deviation)")
            if result.name == "S25" and result.detail == "term sweep: LICENSE:3":
                result = Result("S25", digest(ROOT / "LICENSE") == MIT_SHA256,
                                "term sweep clean except required MIT copyright line; full licence hash verified")
            REPORT.add(result)
        for path in (ROOT / "README.md", ROOT / "docs", ROOT / "examples"):
            REPORT.add(link_check(path))
        REPORT.add(term_sweep([ROOT / name for name in (
            "usdAecoPipe", "usdAecoPipeValidators", "tools", "testenv", "docs", "examples", "README.md",
            "check.py", "build.sh", "flake.nix", "dependencies.json")],
            [r'\b(?:10\.\d{1,3}|192\.168)\.\d{1,3}\.\d{1,3}\b', r'[/]Volumes[/]']))
    except Exception:
        check("check execution", False, traceback.format_exc())
    results = [{"name": r.name, "passed": r.ok, "detail": r.detail} for r in REPORT.results]
    passed = len(results) - REPORT.failed
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"passed": passed, "total": len(results), "checks": results,
            "importer": "not run (--without-importer)" if args.without_importer else "passed" if not REPORT.failed else "see checks"}, indent=2) + "\n")
    return REPORT.finish()


if __name__ == "__main__":
    sys.exit(main())
