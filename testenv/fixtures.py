"""Small independent IFC fixture and augmentation of an external baseline.

Only synthetic names/data are emitted; inputs are never modified on disk.
"""
import math

import ifcopenshell
from ifcopenshell.api import run
import ifcopenshell.util.element as element
import ifcopenshell.util.unit as unit
import numpy as np


def build_baseline(output):
    model = ifcopenshell.file(schema="IFC4X3")
    project = run("root.create_entity", model, ifc_class="IfcProject", name="Pipe fixture")
    run("unit.assign_unit", model, length={"is_metric": True, "raw": "METERS"})
    context = run("context.add_context", model, context_type="Model")
    body = run("context.add_context", model, context_type="Model", context_identifier="Body",
               target_view="MODEL_VIEW", parent=context)
    facility = run("root.create_entity", model, ifc_class="IfcBuilding", name="Facility")
    level = run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Level")
    run("aggregate.assign_object", model, relating_object=project, products=[facility])
    run("aggregate.assign_object", model, relating_object=facility, products=[level])
    material = run("material.add_material", model, name="Steel")
    pipes, pairs = [], []
    for i in range(2):
        pipe = run("root.create_entity", model, ifc_class="IfcPipeSegment", name="Pipe %d" % i,
                   predefined_type="RIGIDSEGMENT")
        typ = run("root.create_entity", model, ifc_class="IfcPipeSegmentType", name="Catalog %d" % i,
                  predefined_type="RIGIDSEGMENT")
        material_set = run("material.add_material_set", model, name="Sizes %d" % i,
                           set_type="IfcMaterialProfileSet")
        profile = model.createIfcCircleHollowProfileDef("AREA", "DN50", None, 0.03015, 0.003)
        run("material.add_profile", model, profile_set=material_set, material=material, profile=profile)
        run("material.assign_material", model, products=[typ], type="IfcMaterialProfileSet", material=material_set)
        run("type.assign_type", model, related_objects=[pipe], relating_type=typ)
        run("spatial.assign_container", model, relating_structure=level, products=[pipe])
        matrix = np.eye(4)
        matrix[:3, 0] = (0, 1, 0); matrix[:3, 1] = (0, 0, 1); matrix[:3, 2] = (1, 0, 0)
        matrix[:3, 3] = (2 * i, 0, 1)
        run("geometry.edit_object_placement", model, product=pipe, matrix=matrix)
        representation = run("geometry.add_profile_representation", model, context=body, profile=profile, depth=2.0)
        run("geometry.assign_representation", model, product=pipe, representation=representation)
        ports = []
        for j in range(2):
            port = run("system.add_port", model, element=pipe)
            port.PredefinedType = "PIPE"; port.FlowDirection = "SINK" if j == 0 else "SOURCE"
            placement = matrix.copy(); placement[:3, 3] += matrix[:3, 2] * (2 * j)
            run("geometry.edit_object_placement", model, product=port, matrix=placement)
            ports.append(port)
        pipes.append(pipe); pairs.append(ports)
    run("system.connect_port", model, port1=pairs[0][1], port2=pairs[1][0], direction="SOURCE")
    group = run("system.add_system", model, ifc_class="IfcDistributionSystem")
    group.Name = "Water"; group.PredefinedType = "DOMESTICCOLDWATER"
    run("system.assign_system", model, products=pipes, system=group)
    model.write(str(output))


def augment(source, output):
    model = ifcopenshell.open(str(source))
    scale = unit.calculate_unit_scale(model)
    metre = model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    pressure = model.create_entity("IfcSIUnit", UnitType="PRESSUREUNIT", Prefix="KILO", Name="PASCAL")
    temperature = model.create_entity("IfcSIUnit", UnitType="THERMODYNAMICTEMPERATUREUNIT", Name="DEGREE_CELSIUS")

    def pset(entity, name, fields):
        prop_set = run("pset.add_pset", model, product=entity, name=name)
        prop_set.HasProperties = [model.create_entity("IfcPropertySingleValue", Name=key,
            NominalValue=model.create_entity(typ, value), Unit=units)
            for key, typ, value, units in fields]

    for pipe in model.by_type("IfcPipeSegment"):
        typ = element.get_type(pipe)
        mat = element.get_material(typ, should_skip_usage=True)
        original_profile = mat.MaterialProfiles[0].Profile
        pset(typ, "Pset_PipeSegmentTypeCommon", [
            ("NominalDiameter", "IfcPositiveLengthMeasure", 0.05, metre),
            ("OuterDiameter", "IfcPositiveLengthMeasure", float(original_profile.Radius) * 2 * scale, metre),
            ("InnerDiameter", "IfcPositiveLengthMeasure", (float(original_profile.Radius) - float(original_profile.WallThickness)) * 2 * scale, metre),
            ("Reference", "IfcLabel", "Schedule fixture", None),
            ("WorkingPressure", "IfcPressureMeasure", 600.0, pressure),
            ("Status", "IfcLabel", "NEW", None),
        ])
        profile = model.createIfcCircleHollowProfileDef("AREA", "DN65", None, 0.03805 / scale, 0.003 / scale)
        run("material.add_profile", model, profile_set=mat, material=mat.MaterialProfiles[0].Material, profile=profile)
    for port in model.by_type("IfcDistributionPort"):
        pset(port, "Pset_DistributionPortTypePipe", [
            ("NominalDiameter", "IfcPositiveLengthMeasure", 0.05, metre),
            ("ConnectionType", "IfcLabel", "PUSH FIT", None),
        ])
    pset(model.by_type("IfcDistributionSystem")[0], "Pset_PipeSystemCommon", [
        ("Fluid", "IfcLabel", "Water", None),
        ("FluidTemperature", "IfcThermodynamicTemperatureMeasure", 20.0, temperature),
    ])
    fitting = run("root.create_entity", model, ifc_class="IfcPipeFitting", name="Elbow fixture",
                  predefined_type="BEND")
    run("spatial.assign_container", model, products=[fitting], relating_structure=model.by_type("IfcBuildingStorey")[0])
    run("geometry.edit_object_placement", model, product=fitting, matrix=np.eye(4))
    point = model.createIfcCartesianPoint((0.2 / scale, 0.0))
    profile = model.createIfcCircleHollowProfileDef("AREA", "DN50",
        model.createIfcAxis2Placement2D(point, None), 0.03015 / scale, 0.003 / scale)
    origin = model.createIfcCartesianPoint((0.0, 0.0, 0.0))
    position = model.createIfcAxis2Placement3D(origin, None, None)
    axis = model.createIfcAxis1Placement(origin, model.createIfcDirection((0.0, 1.0, 0.0)))
    solid = model.createIfcRevolvedAreaSolid(profile, position, axis, math.pi / 2)
    body = next(c for c in model.by_type("IfcGeometricRepresentationSubContext") if c.ContextIdentifier == "Body")
    representation = model.createIfcShapeRepresentation(body, "Body", "SweptSolid", [solid])
    run("geometry.assign_representation", model, product=fitting, representation=representation)
    model.write(str(output))
