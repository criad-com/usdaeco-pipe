"""Sdf comparison with the released source, independent of formatting/layout."""
import json
from pathlib import Path
from pxr import Sdf
ROOT=Path(__file__).resolve().parents[1]


def snapshot(layer):
    return {p.name:{a.name:{'type':str(a.typeName), 'default':str(a.default),
            'variability':str(a.variability), 'custom':a.custom,
            'derived':a.GetInfo('aecoDerived') is True,
            'allowedTokens':list(a.GetInfo('allowedTokens') or [])}
            for a in p.properties} for p in layer.rootPrims if p.name!='GLOBAL'}


def compare_schema():
    wanted=json.loads((ROOT/'testenv/baseline/schema-v0.1.2.json').read_text())
    actual=snapshot(Sdf.Layer.FindOrOpen(str(ROOT/'usdAecoPipe/schema.usda')))
    if actual!=wanted:
        raise AssertionError('Published pipe property contract changed')
    return len(actual),sum(map(len,actual.values())),sum(a['derived'] for p in actual.values() for a in p.values())
