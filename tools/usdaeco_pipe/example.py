"""The pinned clash stage: promote facts, derive guides, retain mesh evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
from pxr import Sdf, Usd, UsdGeom
from . import APIS, iter_pipes, pipe_type_of

CASE_IDS = ('pipe.clash.hard','pipe.clash.near','pipe.clash.tangent','pipe.chw.void.f','pipe.chw.void.r')
COLORS = ((.95,.15,.12),(.98,.60,.08),(.08,.80,.52),(.08,.38,.95),(.08,.38,.95))


def split_axis_layer(path):
    """Archive the full derivation in stable batches below the per-layer cap."""
    layer = Sdf.Layer.FindOrOpen(str(path))
    def opinions():
        flattened = Usd.Stage.Open(layer).Flatten(addSourceFileComment=False)
        paths = []
        flattened.Traverse(Sdf.Path.absoluteRootPath, paths.append)
        return {str(p): {key: flattened.GetObjectAtPath(p).GetInfo(key)
                         for key in flattened.GetObjectAtPath(p).ListInfoKeys()} for p in paths}
    before = opinions()
    owners = []
    def collect(p):
        if p.IsPrimPath() and p.name == 'Axis':
            owners.append(p.GetParentPath())
    layer.Traverse(Sdf.Path.absoluteRootPath, collect)
    parts = []
    (path.parent / 'axis').mkdir()
    for offset in range(0, len(owners), 500):
        relative = 'axis/part-%03d.usda' % (offset // 500)
        part = Sdf.Layer.CreateNew(str(path.parent / relative))
        part.customLayerData = layer.customLayerData
        for owner in sorted(owners)[offset:offset + 500]:
            for ancestor in owner.GetParentPath().GetPrefixes():
                source = layer.GetPrimAtPath(ancestor)
                target = Sdf.CreatePrimInLayer(part, ancestor)
                for key in source.ListInfoKeys():
                    target.SetInfo(key, source.GetInfo(key))
            Sdf.CopySpec(layer, owner, part, owner)
        part.Save()
        parts.append(relative)
    metadata = layer.customLayerData
    layer.Clear()
    layer.customLayerData = metadata
    layer.subLayerPaths = parts
    layer.Save()
    after = opinions()
    if before != after:
        changed = [(p, k) for p in sorted(before.keys() | after.keys())
                   for k in before.get(p, {}).keys() | after.get(p, {}).keys()
                   if before.get(p, {}).get(k) != after.get(p, {}).get(k)]
        raise ValueError('Splitting the axis archive changed its composed opinions: ' + str(changed[:8]))


def library_hook(stage, out_dir):
    root=stage.GetRootLayer()
    root.Save()
    # The CLI gets a snapshot of the input stack, never its future composed root.
    snapshot=Sdf.Layer.CreateNew(str(out_dir/'source.usda'))
    snapshot.TransferContent(root)
    snapshot.Save()
    repo=Path(__file__).resolve().parents[2]
    env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'}
    result=subprocess.run([sys.executable,str(repo/'tools/aeco-pipe'),'import',str(out_dir/'source.usda'),
                           '--out',str(out_dir/'pipe.usda')],env=env,text=True,capture_output=True,check=True)
    stats=json.loads(result.stdout)
    (out_dir/'import.json').write_text(json.dumps(stats,indent=2,sort_keys=True)+'\n')
    root.subLayerPaths.insert(0,'pipe.usda')
    root.Save()
    axis=Path(os.environ.get('AECO_AXIS_ROOT',repo.parent/'usdaeco-axis'))
    kit=Path(os.environ.get('TOOLCHAIN_DIR',repo.parent/'usdaeco-toolchain'))
    code="import runpy,sys; sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)]; runpy.run_module('usdaeco_axis.cli',run_name='__main__')"
    result=subprocess.run([sys.executable,'-c',code,str(axis/'tools'),str(kit/'tools'),'derive',str(out_dir/'example.usda'),
                           '--out',str(out_dir/'axis.derived.usda')],env=env,text=True,capture_output=True,check=True)
    axis_stats=json.loads(result.stdout)
    split_axis_layer(out_dir/'axis.derived.usda')
    root.subLayerPaths.insert(0,'axis.derived.usda')
    # Camera presentation is isolated from both imported drivers and readback.
    presentation=Sdf.Layer.CreateNew(str(out_dir/'presentation.usda'))
    root.subLayerPaths.insert(0,'presentation.usda')
    index={p.GetAttribute('aeco:props:DC_Identity:Id').Get():p for p in stage.Traverse()
           if p.GetAttribute('aeco:props:DC_Identity:Id').Get()}
    bounds=UsdGeom.BBoxCache(Usd.TimeCode.Default(),["default","guide","proxy","render"])
    with Usd.EditContext(stage,presentation):
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Gprim):
                box=bounds.ComputeWorldBound(prim).ComputeAlignedRange()
                if prim.GetAttribute('aeco:derived:role').Get()=='extent' or (not box.IsEmpty() and (box.GetMin()[2]>=6.95 or box.GetMax()[2]<6.65)):
                    UsdGeom.Imageable(prim).CreateVisibilityAttr('invisible')
        for key,color in zip(CASE_IDS,COLORS):
            if key not in index:
                raise ValueError('Missing example identity: '+key)
            for child in Usd.PrimRange(index[key]):
                if child.IsA(UsdGeom.Gprim):
                    child.CreateRelationship('material:binding').SetTargets([])
                    UsdGeom.Gprim(child).CreateDisplayColorAttr([color])
    presentation.Save()
    root.Save()
    rows=[{'name':'PublishedCounts','elements':sum(p.HasAPI('AecoElementAPI') for p in stage.Traverse()),
           'spaces':sum(p.GetTypeName()=='AecoSpace' for p in stage.Traverse()),
           'levels':sum(p.GetTypeName()=='AecoLevel' for p in stage.Traverse()),
           'ports':sum(p.GetTypeName()=='AecoPort' for p in stage.Traverse())},
          {'name':'PipePromotion','segments':stats['AecoPipeAPI'],'fittings':stats['AecoPipeFittingAPI']}]
    for key in CASE_IDS:
        p=index[key]
        rows.append({'name':'DN50Promotion','id':key,'nominal_m':p.GetAttribute('aeco:pipe:nominalDiameter').Get(),
                     'outer_m':p.GetAttribute('aeco:pipe:outerDiameter').Get(),
                     'ports':sum(c.HasAPI('AecoPipePortAPI') for c in p.GetChildren()),
                     'catalog':bool(pipe_type_of(p)), 'axis':p.HasAPI('AecoAxisAPI')})
    (out_dir/'axis.json').write_text(json.dumps({'axes':axis_stats['axes']},indent=2)+'\n')
    return rows
