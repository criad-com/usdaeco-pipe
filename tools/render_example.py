#!/usr/bin/env python3
"""Render the pipe run with a separate analytic display layer over its guides."""
from pathlib import Path
import os
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(os.environ.get('TOOLCHAIN_DIR',ROOT.parent/'usdaeco-toolchain'))/'tools'))
from usdaeco_pipe import register_plugins
register_plugins()
from pxr import Gf,Sdf,Usd,UsdGeom
from usdaeco_render import render


def main():
    output=ROOT/'out/userDoc'
    output.mkdir(parents=True,exist_ok=True)
    source=ROOT/'usdAecoPipe/examples/minimal.usda'
    base=Usd.Stage.Open(str(source))
    layer=Sdf.Layer.CreateNew(str(output/'display.usda'))
    layer.subLayerPaths=[str(source)]
    stage=Usd.Stage.Open(layer)
    stage.SetDefaultPrim(stage.GetPrimAtPath('/PipeRun'))
    stage.SetMetadata('fallbackPrimTypes',base.GetMetadata('fallbackPrimTypes'))
    UsdGeom.SetStageMetersPerUnit(stage,1)
    UsdGeom.SetStageUpAxis(stage,'Z')
    for p in list(base.Traverse()):
        if not p.IsA(UsdGeom.BasisCurves):
            continue
        points=p.GetAttribute('points').Get()
        counts=p.GetAttribute('curveVertexCounts').Get()
        index=0
        for count in counts:
            for j in range(index,index+count-1):
                a,b=Gf.Vec3d(points[j]),Gf.Vec3d(points[j+1])
                delta=b-a
                cyl=UsdGeom.Cylinder.Define(stage,p.GetParent().GetPath().AppendChild('Display_'+str(j)))
                cyl.CreateHeightAttr(delta.GetLength())
                cyl.CreateRadiusAttr(.03015)
                cyl.CreateAxisAttr('Z')
                cyl.CreatePurposeAttr('proxy')
                cyl.CreateDisplayColorAttr([(.06,.36,.75) if p.GetParent().HasAPI('AecoPipeAPI') else (.9,.43,.08)])
                x=UsdGeom.Xformable(cyl)
                x.AddTranslateOp().Set((a+b)/2)
                x.AddOrientOp(UsdGeom.XformOp.PrecisionDouble).Set(Gf.Rotation(Gf.Vec3d(0,0,1),delta).GetQuat())
                prim=cyl.GetPrim();prim.ApplyAPI('AecoDerivedGeometryAPI')
                for key,value in {'source':p.GetParent().GetAttribute('aeco:id').Get(),'role':'proxy',
                                  'approx':'defaultDims','stamp':'pipe-run display 0.2.0'}.items():
                    prim.GetAttribute('aeco:derived:'+key).Set(value)
            index+=count
    layer.Save()
    records=render(output/'display.usda',cameras=ROOT/'usdAecoPipe/userDoc/cameras.usda',output=output/'renders',purposes='guide,proxy,render')
    shutil.copyfile(output/'renders/pipe_run.png',ROOT/'usdAecoPipe/userDoc/usdAecoPipeExample.png')
    print(records)


if __name__=='__main__':
    main()
