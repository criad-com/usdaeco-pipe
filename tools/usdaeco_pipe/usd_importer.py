"""Promote published USD property sets without an IFC runtime or mesh inference.

Property-set dimensions use stage units; schema dimensions are SI metres.
DC_Section is a documented fallback for the demo's explicit section facts.
Missing bore and catalog rows remain unknown, including solid sweep proxies.
"""
from collections import Counter
import hashlib
import math
import os
from pathlib import Path
from pxr import Sdf, Usd, UsdGeom
from . import APIS, register_plugins

PIPE_PSET = "Pset_PipeSegmentTypeCommon"


def _section_catalog(stage):
    """Keep generated types with the project so references carry their catalog."""
    project = stage.GetDefaultPrim()
    catalog = project.GetChild('_TypeCatalog') if project else None
    if catalog:
        return catalog.GetPath()
    if project and project.HasAPI('AecoProjectAPI'):
        return stage.CreateClassPrim(project.GetPath().AppendChild('_TypeCatalog')).GetPath()
    # CreateClassPrim on a child alone would define its missing parent as a def.
    return stage.CreateClassPrim('/_TypeCatalog').GetPath()


def write_layers(stage, layer, output, sources):
    """Separate all schema-marked readback properties from imported drivers."""
    output = Path(output).resolve()
    derived_path = output.with_name(output.stem + '.derived.usda')
    if output.exists() or derived_path.exists():
        raise ValueError("Import outputs must be new files")
    derived = Sdf.Layer.CreateAnonymous('pipe.derived.usda')
    derived.customLayerData = {"aeco:pipe:layer": "derived", "aeco:pipe:producer": "aeco-pipe 0.2.0"}
    properties = []
    layer.Traverse(Sdf.Path.absoluteRootPath, lambda path: properties.append(path) if path.IsPropertyPath() else None)
    for path in properties:
        prop = stage.GetPropertyAtPath(path)
        if prop and prop.GetMetadata('aecoDerived') is True:
            Sdf.CreatePrimInLayer(derived, path.GetPrimPath())
            Sdf.CopySpec(layer, path, derived, path)
            spec = layer.GetPropertyAtPath(path)
            spec.owner.RemoveProperty(spec)
    output.parent.mkdir(parents=True, exist_ok=True)
    derived.Export(str(derived_path))
    exported = Sdf.Layer.CreateAnonymous('pipe.export.usda')
    exported.TransferContent(layer)
    exported.subLayerPaths = [derived_path.name] + [os.path.relpath(p, output.parent) for p in sources]
    exported.Export(str(output))


def import_stage(source, output):
    """Import pipe/fitting/type/port/system facts to two additive USD layers."""
    register_plugins()
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or output.exists() or output.with_name(output.stem + '.derived.usda').exists():
        raise ValueError("Import outputs must be new files distinct from the source")
    layer = Sdf.Layer.CreateAnonymous('pipe.import.usda')
    layer.subLayerPaths = [str(source)]
    stage = Usd.Stage.Open(layer)
    base = Usd.Stage.Open(str(source))
    if not base or stage.GetCompositionErrors():
        raise ValueError("Source stage does not compose")
    for key in ('defaultPrim','upAxis','metersPerUnit','fallbackPrimTypes'):
        if base.HasAuthoredMetadata(key):
            stage.SetMetadata(key,base.GetMetadata(key))
    layer.customLayerData = {"aeco:pipe:layer": "import", "aeco:pipe:producer": "aeco-pipe 0.2.0"}
    meters = UsdGeom.GetStageMetersPerUnit(stage)
    stats = Counter({a: 0 for a in APIS})
    stats.update(propsBlocked=0, unknownNominal=0, incompleteTables=0, sectionFallbacks=0)
    applied = set()

    def apply(prim, api):
        key = (prim.GetPath(), api)
        if key not in applied:
            if not prim.CanApplyAPI(api):
                raise ValueError('Cannot apply ' + api)
            prim.ApplyAPI(api)
            applied.add(key)
            stats[api] += 1

    def value(prim, pset, field):
        attr = prim.GetAttribute('aeco:props:' + pset + ':' + field)
        return attr.Get() if attr else None

    def promote(prim, target, pset, field, scale=1.0, dest=None):
        v = value(prim, pset, field)
        if v is None:
            return None
        if isinstance(v, (float,int)) and not isinstance(v,bool):
            v = float(v) * scale
            if not math.isfinite(v) or v < 0:
                raise ValueError('Invalid property-set value: ' + field)
        (dest or prim).GetAttribute(target).Set(v)
        prim.GetAttribute('aeco:props:' + pset + ':' + field).Block()
        stats['propsBlocked'] += 1
        return v

    nominal = {}
    elements = [p for p in stage.Traverse() if (p.GetAttribute('aeco:class:ifc:code').Get() or '').split('.')[0] in ('IfcPipeSegment','IfcPipeFitting')]
    for prim in elements:
        fitting = (prim.GetAttribute('aeco:class:ifc:code').Get() or '').startswith('IfcPipeFitting')
        apply(prim, 'AecoPipeFittingAPI' if fitting else 'AecoPipeAPI')
        if fitting:
            prim.GetAttribute('aeco:pipeFitting:origin').Set('authored')
        dims = {}
        for field, name, fallback in [('NominalDiameter','nominalDiameter','NominalDiameter'),
                                      ('OuterDiameter','outerDiameter','OutsideDiameter'),
                                      ('InnerDiameter','innerDiameter','InsideDiameter')]:
            v = value(prim,PIPE_PSET,field)
            pset, source_field = PIPE_PSET, field
            if v is None and value(prim,'DC_Section',fallback) is not None:
                pset, source_field = 'DC_Section', fallback
                stats['sectionFallbacks'] += 1
            if fitting:
                v = value(prim,pset,source_field)
                dims[name] = None if v is None else float(v)*meters
            else:
                dims[name] = promote(prim,'aeco:pipe:'+name,pset,source_field,meters)
        nominal[prim.GetPath()] = dims['nominalDiameter']
        if not fitting:
            if dims['nominalDiameter'] is None:
                prim.GetAttribute('aeco:pipe:nominalDiameter').Block()
                stats['unknownNominal'] += 1
            elif dims['nominalDiameter'] > 0:
                prim.GetAttribute('aeco:pipe:sizeLabel').Set('DN%g' % (1000*dims['nominalDiameter']))
            if prim.HasAPI('AecoAxisAPI'):
                a,b = (prim.GetAttribute('aeco:axis:'+n).Get() for n in ('start','end'))
                if a is not None and b is not None:
                    m = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                    d=m.Transform(b)-m.Transform(a)
                    up=2 if UsdGeom.GetStageUpAxis(stage)=='Z' else 1
                    horizontal=math.sqrt(sum(d[i]**2 for i in range(3) if i!=up))
                    if horizontal>1e-12:
                        prim.GetAttribute('aeco:pipe:slope').Set(d[up]/horizontal)
                    else:
                        prim.GetAttribute('aeco:pipe:slope').Block()
        catalog = next((stage.GetPrimAtPath(p) for p in prim.GetInherits().GetAllDirectInherits()
                        if stage.GetPrimAtPath(p).IsAbstract() and stage.GetPrimAtPath(p).HasAPI('AecoTypeAPI')), None)
        if catalog is None and dims['nominalDiameter'] is not None:
            # A shared section catalog is a class, never a new referent or identity.
            key=hashlib.sha256(repr(tuple(dims.values())).encode()).hexdigest()[:12]
            catalog=stage.CreateClassPrim(_section_catalog(stage).AppendChild('PipeSection_'+key))
            catalog.ApplyAPI('AecoTypeAPI')
            catalog.GetAttribute('aeco:type:model').Set('Imported pipe section')
            prim.GetInherits().AddInherit(catalog.GetPath())
        if catalog:
            apply(catalog,'AecoPipeTypeAPI')
            for field,target in [('Reference','schedule'),('WorkingPressure','workingPressure')]:
                promote(catalog,'aeco:pipeType:'+target,PIPE_PSET,field)
            if all(v is not None and v > 0 for v in dims.values()):
                if dims['innerDiameter'] > dims['outerDiameter']:
                    raise ValueError('Bore exceeds outer diameter')
                row=tuple(dims.values())
                names=('nominalDiameters','outerDiameters','innerDiameters')
                rows=list(zip(*(catalog.GetAttribute('aeco:pipeType:'+n).Get() or [] for n in names)))
                match=[r for r in rows if abs(r[0]-row[0])<1e-8]
                if match and any(abs(a-b)>1e-8 for a,b in zip(match[0],row)):
                    raise ValueError('Conflicting pipe section rows')
                if not match: rows.append(row)
                for i,name in enumerate(names):
                    catalog.GetAttribute('aeco:pipeType:'+name).Set([r[i] for r in sorted(rows)])
    for prim in stage.Traverse():
        if prim.GetTypeName() == 'AecoPort':
            owner=prim.GetParent()
            while owner and not owner.IsPseudoRoot() and owner.GetPath() not in nominal:
                owner=owner.GetParent()
            if owner and owner.GetPath() in nominal:
                apply(prim,'AecoPipePortAPI')
                v=promote(prim,'aeco:pipePort:nominalDiameter','Pset_DistributionPortTypePipe','NominalDiameter',meters)
                if v is None and nominal[owner.GetPath()] is not None:
                    prim.GetAttribute('aeco:pipePort:nominalDiameter').Set(nominal[owner.GetPath()])
        elif prim.GetTypeName() == 'AecoSystem':
            members=Usd.CollectionAPI(prim,'members').GetIncludesRel().GetTargets()
            if any(p in nominal for p in members):
                apply(prim,'AecoPipeSystemAPI')
                promote(prim,'aeco:pipeSystem:fluid','Pset_PipeSystemCommon','Fluid')
                promote(prim,'aeco:pipeSystem:fluidTemperature','Pset_PipeSystemCommon','FluidTemperature')
    from . import size_table
    for p in stage.TraverseAll():
        if p.IsAbstract() and p.HasAPI('AecoPipeTypeAPI'):
            stats['incompleteTables'] += not bool(size_table(p))
    write_layers(stage,layer,output,[source])
    return dict(stats)
