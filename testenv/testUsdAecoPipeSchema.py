#!/pxrpythonsubst
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT)]
from pxr import Plug, Usd
from usdaeco_pipe import APIS, register_plugins
register_plugins()
Plug.Registry().RegisterPlugins(str(ROOT/'usdAecoPipe'))


class TestSchema(unittest.TestCase):
    def test_registry(self):
        self.assertTrue(all(Usd.SchemaRegistry().FindAppliedAPIPrimDefinition(api) for api in APIS))

    def test_catalog_is_untyped(self):
        stage=Usd.Stage.CreateInMemory()
        catalog=stage.CreateClassPrim('/Catalog')
        self.assertTrue(catalog.CanApplyAPI('AecoPipeTypeAPI'))
        self.assertEqual(catalog.GetTypeName(),'')
        self.assertFalse(stage.DefinePrim('/Mesh','Mesh').CanApplyAPI('AecoPipePortAPI'))

    def test_published_properties_unchanged(self):
        from schema_contract import compare_schema
        self.assertEqual(compare_schema(), (5,18,9))


if __name__ == '__main__':
    unittest.main()
