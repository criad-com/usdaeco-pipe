#!/pxrpythonsubst
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'), str(ROOT)]
from pxr import Plug,Sdf,Usd,UsdValidation
from usdaeco_pipe import register_plugins
register_plugins()
Plug.Registry().RegisterPlugins(str(ROOT/'usdAecoPipeValidators'))
from usdaeco_check.validation import run


class TestValidators(unittest.TestCase):
    def fresh(self):
        layer=Sdf.Layer.CreateAnonymous('test.usda')
        layer.TransferContent(Sdf.Layer.FindOrOpen(str(ROOT/'usdAecoPipe/examples/minimal.usda')))
        return Usd.Stage.Open(layer)

    def codes(self,stage):
        return [e.GetName() for e in run(stage,['UsdAecoPipeValidators'])]

    def test_PipeKindMismatch(self):
        stage=self.fresh()
        stage.GetPrimAtPath('/PipeRun/Facility/Level/Inlet').GetAttribute('aeco:class:ifc:code').Set('IfcDuctSegment')
        self.assertEqual(self.codes(stage),['PipeKindMismatch'])

    def test_PipeMissingAxis(self):
        stage=self.fresh()
        stage.GetPrimAtPath('/PipeRun/Facility/Level/Inlet').RemoveAPI('AecoAxisAPI')
        self.assertEqual(self.codes(stage),['PipeMissingAxis'])

    def test_PipeSizeNotInTable(self):
        stage=self.fresh()
        stage.GetPrimAtPath('/PipeRun/Facility/Level/Inlet').GetAttribute('aeco:pipe:nominalDiameter').Set(.033)
        self.assertEqual(self.codes(stage),['PipeSizeNotInTable'])

    def test_PipePortSizeMismatch(self):
        stage=self.fresh()
        a=stage.GetPrimAtPath('/PipeRun/Facility/Level/Inlet/Out')
        b=stage.GetPrimAtPath('/PipeRun/Facility/Level/Middle/In')
        a.GetRelationship('aeco:connectedPorts').SetTargets([b.GetPath()])
        b.GetRelationship('aeco:connectedPorts').SetTargets([a.GetPath()])
        b.GetAttribute('aeco:pipePort:nominalDiameter').Set(.065)
        self.assertIn('PipePortSizeMismatch',self.codes(stage))

    def test_PipeGap(self):
        stage=self.fresh()
        port=stage.GetPrimAtPath('/PipeRun/Facility/Level/Middle/In')
        port.GetAttribute('xformOp:translate').Set((.5,0,0))
        self.assertEqual(self.codes(stage),['PipeGap'])
        port.GetAttribute('xformOp:translate').Set((0,0,0))
        self.assertEqual(self.codes(stage),[])


if __name__ == '__main__':
    unittest.main()
