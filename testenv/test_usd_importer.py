"""Published-stage promotion: evidence, units, ownership and source preservation."""
import hashlib
from pathlib import Path
import subprocess
import sys
import pytest
from pxr import Sdf,Usd,UsdGeom,Vt
from usdaeco_pipe import register_plugins,pipe_type_of,size_table
from usdaeco_pipe.usd_importer import import_stage
register_plugins()


def fixture(path,meters=1,complete=True):
    s=Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageMetersPerUnit(s,meters)
    UsdGeom.SetStageUpAxis(s,'Z')
    s.SetMetadata('fallbackPrimTypes',{'AecoPort':Vt.TokenArray(['Xform'])})
    p=s.DefinePrim('/Pipe','Xform');s.SetDefaultPrim(p)
    p.ApplyAPI('AecoElementAPI');p.ApplyAPI('AecoClassificationAPI','ifc');p.ApplyAPI('AecoAxisAPI')
    p.GetAttribute('aeco:id').Set('8a837b65-0221-4340-bcc5-bd8d11a0ee13')
    p.GetAttribute('aeco:class:ifc:code').Set('IfcPipeSegment.RIGIDSEGMENT')
    p.GetAttribute('aeco:axis:start').Set((0,0,0));p.GetAttribute('aeco:axis:end').Set((2,0,0))
    for field,v in [('NominalDiameter',.05),('OuterDiameter',.0603),('InnerDiameter',.0543)] if complete else []:
        p.CreateAttribute('aeco:props:Pset_PipeSegmentTypeCommon:'+field,Sdf.ValueTypeNames.Double).Set(v/meters)
    p.CreateAttribute('aeco:props:Pset_PipeSegmentTypeCommon:Status',Sdf.ValueTypeNames.String).Set('NEW')
    s.DefinePrim('/Pipe/Port','AecoPort')
    s.GetRootLayer().Save()
    return s


@pytest.mark.parametrize('meters',[1,.001])
def test_si_separate_layers_and_source_bytes(tmp_path,meters):
    source=tmp_path/'source.usda';s=fixture(source,meters)
    original=source.read_bytes()
    target=tmp_path/'pipe.usda'
    stats=import_stage(source,target)
    assert source.read_bytes()==original
    composed=Usd.Stage.Open(str(target));p=composed.GetPrimAtPath('/Pipe')
    assert p.GetAttribute('aeco:pipe:nominalDiameter').Get()==.05
    assert p.GetAttribute('aeco:pipe:outerDiameter').Get()==pytest.approx(.0603)
    assert size_table(pipe_type_of(p))==[(.05,.0603,.0543)]
    assert p.GetAttribute('aeco:props:Pset_PipeSegmentTypeCommon:OuterDiameter').Get() is None
    assert p.GetAttribute('aeco:props:Pset_PipeSegmentTypeCommon:Status').Get()=='NEW'
    assert composed.GetPrimAtPath('/Pipe/Port').GetAttribute('aeco:pipePort:nominalDiameter').Get()==.05
    derived=Sdf.Layer.FindOrOpen(str(tmp_path/'pipe.derived.usda'))
    assert not composed.GetRootLayer().GetAttributeAtPath('/Pipe.aeco:pipe:outerDiameter')
    assert derived.GetAttributeAtPath('/Pipe.aeco:pipe:outerDiameter').default==pytest.approx(.0603)
    assert not derived.GetAttributeAtPath('/Pipe.aeco:pipe:nominalDiameter')
    assert stats['AecoPipeTypeAPI']==1
    with pytest.raises(ValueError):import_stage(source,target)
    assert source.read_bytes()==original


def test_unknown_values_stay_unknown(tmp_path):
    source=tmp_path/'source.usda';fixture(source,complete=False)
    target=tmp_path/'pipe.usda';stats=import_stage(source,target)
    p=Usd.Stage.Open(str(target))
    assert p.GetPrimAtPath('/Pipe').GetAttribute('aeco:pipe:nominalDiameter').Get() is None
    assert stats['unknownNominal']==1 and stats['AecoPipeTypeAPI']==0


def test_standard_property_wins_over_demo_fallback(tmp_path):
    source=tmp_path/'source.usda';s=fixture(source)
    p=s.GetPrimAtPath('/Pipe')
    p.CreateAttribute('aeco:props:DC_Section:NominalDiameter',Sdf.ValueTypeNames.Double).Set(.065)
    s.GetRootLayer().Save()
    target=tmp_path/'pipe.usda';import_stage(source,target)
    s2=Usd.Stage.Open(str(target));p=s2.GetPrimAtPath('/Pipe')
    assert p.GetAttribute('aeco:pipe:nominalDiameter').Get()==.05
    assert p.GetAttribute('aeco:props:DC_Section:NominalDiameter').Get()==.065


def test_demo_fallback_has_no_invented_bore(tmp_path):
    source=tmp_path/'source.usda';s=fixture(source,complete=False)
    p=s.GetPrimAtPath('/Pipe')
    for field,v in [('NominalDiameter',.05),('OutsideDiameter',.0603)]:
        p.CreateAttribute('aeco:props:DC_Section:'+field,Sdf.ValueTypeNames.Double).Set(v)
    s.GetRootLayer().Save()
    target=tmp_path/'pipe.usda';stats=import_stage(source,target)
    s2=Usd.Stage.Open(str(target));p=s2.GetPrimAtPath('/Pipe')
    assert p.GetAttribute('aeco:pipe:outerDiameter').Get()==.0603
    assert p.GetAttribute('aeco:pipe:innerDiameter').Get()==0
    assert not p.GetAttribute('aeco:pipe:innerDiameter').HasAuthoredValueOpinion()
    assert size_table(pipe_type_of(p))==[] and stats['incompleteTables']==1


def test_refuse_input_and_derived_output_alias(tmp_path):
    source=tmp_path/'source.usda';fixture(source)
    with pytest.raises(ValueError):import_stage(source,source)
    (tmp_path/'pipe.derived.usda').write_text('owned elsewhere')
    with pytest.raises(ValueError):import_stage(source,tmp_path/'pipe.usda')
    assert (tmp_path/'pipe.derived.usda').read_text()=='owned elsewhere'


def test_usd_cli_never_imports_ifcopenshell(tmp_path):
    source=tmp_path/'source.usda';fixture(source)
    code='''import sys
sys.path.insert(0,sys.argv.pop(1))
class RefuseIFC:
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0]=='ifcopenshell': raise AssertionError('USD promotion imported IFC')
sys.meta_path.insert(0,RefuseIFC())
from usdaeco_pipe.cli import main
raise SystemExit(main())
'''
    result=subprocess.run([sys.executable,'-c',code,str(Path(__file__).resolve().parents[1]/'tools'),
                           'import',str(source),'--out',str(tmp_path/'pipe.usda')],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
