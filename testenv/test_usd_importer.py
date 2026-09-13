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


@pytest.mark.parametrize('project_root', ['/Campus', '/RenamedProject'])
@pytest.mark.parametrize('existing_catalog', [True, False])
def test_project_catalog_survives_reference(tmp_path, monkeypatch, project_root, existing_catalog):
    monkeypatch.setenv('AECO_STUDY_ROOT', '/Studies/pipe')
    source = tmp_path / 'source.usda'
    fixture(source)
    stage = Usd.Stage.CreateNew(str(tmp_path / 'project.usda'))
    UsdGeom.SetStageMetersPerUnit(stage, 1)
    project = stage.DefinePrim(project_root, 'Xform')
    project.ApplyAPI('AecoProjectAPI')
    stage.SetDefaultPrim(project)
    pipe = stage.DefinePrim(project_root + '/Pipe')
    pipe.GetReferences().AddReference(str(source))
    catalog_root = project_root + '/_TypeCatalog'
    if existing_catalog:
        stage.CreateClassPrim(catalog_root)
        existing = stage.CreateClassPrim(catalog_root + '/Existing')
        existing.ApplyAPI('AecoTypeAPI')
    stage.GetRootLayer().Save()
    before = {p: p.read_bytes() for p in [source, tmp_path / 'project.usda']}
    output = tmp_path / 'pipe.usda'
    import_stage(tmp_path / 'project.usda', output)
    composed = Usd.Stage.Open(str(output))
    catalog = pipe_type_of(composed.GetPrimAtPath(project_root + '/Pipe'))
    assert catalog.GetPath().GetParentPath() == Sdf.Path(catalog_root)
    assert composed.GetRootLayer().GetPrimAtPath(catalog.GetPath()).specifier == Sdf.SpecifierClass
    assert not composed.GetPrimAtPath('/_TypeCatalog')
    assert not composed.GetPrimAtPath('/Studies')
    assert [p.GetPath() for p in composed.GetPseudoRoot().GetAllChildren()] == [Sdf.Path(project_root)]
    if existing_catalog:
        assert composed.GetPrimAtPath(catalog_root + '/Existing').HasAPI('AecoTypeAPI')
    # Referencing only the default project must carry both the inherit and table.
    referenced = Usd.Stage.CreateInMemory()
    referenced.DefinePrim('/Delivered').GetReferences().AddReference(str(output))
    delivered_pipe = referenced.GetPrimAtPath('/Delivered/Pipe')
    assert pipe_type_of(delivered_pipe).GetPath().GetParentPath() == Sdf.Path('/Delivered/_TypeCatalog')
    assert size_table(pipe_type_of(delivered_pipe)) == [(0.05, 0.0603, 0.0543)]
    assert not referenced.GetCompositionErrors()
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.mark.parametrize('has_default_prim', [True, False])
def test_standalone_catalog_parent_is_class(tmp_path, monkeypatch, has_default_prim):
    monkeypatch.setenv('AECO_STUDY_ROOT', '/Studies/pipe')
    source = tmp_path / 'source.usda'
    stage = fixture(source)
    if not has_default_prim:
        stage.ClearDefaultPrim()
        stage.GetRootLayer().Save()
    before = source.read_bytes()
    output = tmp_path / 'pipe.usda'
    import_stage(source, output)
    composed = Usd.Stage.Open(str(output))
    catalog = pipe_type_of(composed.GetPrimAtPath('/Pipe'))
    assert catalog.GetPath().GetParentPath() == Sdf.Path('/_TypeCatalog')
    for path in [Sdf.Path('/_TypeCatalog'), catalog.GetPath()]:
        assert composed.GetRootLayer().GetPrimAtPath(path).specifier == Sdf.SpecifierClass
    assert not composed.GetPrimAtPath('/Studies')
    assert size_table(catalog) == [(0.05, 0.0603, 0.0543)]
    assert source.read_bytes() == before


def test_reuses_inherited_project_type(tmp_path):
    source = tmp_path / 'source.usda'
    stage = fixture(source)
    project = stage.DefinePrim('/Project', 'Xform')
    stage.SetDefaultPrim(project)
    Sdf.CopySpec(stage.GetRootLayer(), '/Pipe', stage.GetRootLayer(), '/Project/Pipe')
    stage.RemovePrim('/Pipe')
    stage.CreateClassPrim('/Project/_TypeCatalog')
    catalog = stage.CreateClassPrim('/Project/_TypeCatalog/Existing')
    catalog.ApplyAPI('AecoTypeAPI')
    stage.GetPrimAtPath('/Project/Pipe').GetInherits().AddInherit(catalog.GetPath())
    stage.GetRootLayer().Save()
    output = tmp_path / 'pipe.usda'
    stats = import_stage(source, output)
    composed = Usd.Stage.Open(str(output))
    assert stats['AecoPipeTypeAPI'] == 1
    assert pipe_type_of(composed.GetPrimAtPath('/Project/Pipe')).GetPath() == catalog.GetPath()
    assert not any(p.GetName().startswith('PipeSection_') for p in composed.TraverseAll())
    assert not composed.GetPrimAtPath('/_TypeCatalog')


@pytest.mark.parametrize('has_project', [True, False])
def test_hook_study_setting_keeps_guides_under_elements(tmp_path, monkeypatch, has_project):
    from usdaeco_pipe.example import CASE_IDS, library_hook

    source = tmp_path / 'element.usda'
    fixture(source)
    base = Usd.Stage.CreateNew(str(tmp_path / 'base.usda'))
    UsdGeom.SetStageMetersPerUnit(base, 1)
    UsdGeom.SetStageUpAxis(base, 'Z')
    base.SetMetadata('fallbackPrimTypes', {'AecoPort': Vt.TokenArray(['Xform'])})
    project = base.DefinePrim('/Building', 'Xform')
    base.SetDefaultPrim(project)
    if has_project:
        project.ApplyAPI('AecoProjectAPI')
        base.CreateClassPrim('/Building/_TypeCatalog')
    for i, identity in enumerate((*CASE_IDS, 'pipe.other')):
        pipe = base.DefinePrim('/Building/Pipe_%d' % i)
        pipe.GetReferences().AddReference(str(source))
        pipe.GetAttribute('aeco:id').Set('8a837b65-0221-4340-bcc5-bd8d11a0ee1%d' % i)
        pipe.CreateAttribute('aeco:props:DC_Identity:Id', Sdf.ValueTypeNames.String).Set(identity)
    base.GetRootLayer().Save()
    source_bytes = {p: p.read_bytes() for p in [source, tmp_path / 'base.usda']}
    expected = None
    for i, study_root in enumerate([None, '/Studies/pipe', '/Studies/RenamedPipe']):
        if study_root is None:
            monkeypatch.delenv('AECO_STUDY_ROOT', raising=False)
        else:
            monkeypatch.setenv('AECO_STUDY_ROOT', study_root)
        out = tmp_path / str(i)
        out.mkdir()
        stage = Usd.Stage.CreateNew(str(out / 'example.usda'))
        stage.GetRootLayer().subLayerPaths = [str(tmp_path / 'base.usda')]
        for key in ['defaultPrim', 'metersPerUnit', 'upAxis', 'fallbackPrimTypes']:
            stage.SetMetadata(key, base.GetMetadata(key))
        rows = library_hook(stage, out)
        assert sum(r['name'] == 'DN50Promotion' and r['catalog'] and r['axis'] for r in rows) == 5
        catalog_root = Sdf.Path('/Building/_TypeCatalog' if has_project else '/_TypeCatalog')
        assert all(pipe_type_of(p).GetPath().GetParentPath() == catalog_root
                   for p in stage.Traverse() if p.HasAPI('AecoPipeAPI'))
        assert set(p.GetPath() for p in stage.GetPseudoRoot().GetAllChildren()) == (
            {Sdf.Path('/Building')} if has_project else {Sdf.Path('/Building'), catalog_root})
        guides = [p for p in stage.Traverse() if p.GetAttribute('aeco:derived:role').Get() == 'axis']
        assert len(guides) == 6
        assert all(p.GetParent().HasAPI('AecoElementAPI') for p in guides)
        assert not stage.GetCompositionErrors()
        # There is no standalone study content: a setting must neither create
        # empty scopes nor change catalog, guide, relationship or metadata paths.
        authored = {str(p.relative_to(out)): p.read_bytes() for p in out.rglob('*.usda')}
        if expected is None:
            expected = authored
        else:
            assert authored == expected
    assert all(p.read_bytes() == data for p, data in source_bytes.items())


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
