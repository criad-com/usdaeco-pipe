"""Resolve the exact published example release without modifying a sibling."""
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile


def datacentre_root(repo):
    """Honor explicit roots; otherwise use the sibling or export its pinned tag.

    A moving main checkout never silently changes the example's source version.
    Export is local/read-only and contains only already-published release data.
    Nix's exact source and ordinary exact-tag checkouts need no Git invocation.
    """
    explicit=os.environ.get('AECO_DATACENTRE_ROOT')
    if explicit:
        return Path(explicit).resolve()
    pins=json.loads((repo/'dependencies.json').read_text())['repos']
    pin=next(p for p in pins.values() if p['repo']=='usdaeco-datacentre')
    sibling=repo.parent/'usdaeco-datacentre'
    if json.loads((sibling/'library.json').read_text())['version']==pin['ref'].removeprefix('v'):
        return sibling
    destination=repo/'out/pins'/('usdaeco-datacentre-'+pin['ref'])
    if not (destination/'library.json').is_file():
        destination.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
            archive=Path(temporary)/'release.tar'
            subprocess.run(['git','-C',str(sibling),'archive','--format=tar','--output',str(archive),pin['ref'],
                            'library.json','dist/clash','manifests/demo-datacentre-01.clash.json'],check=True,capture_output=True)
            extracted=Path(temporary)/'release'
            extracted.mkdir()
            with tarfile.open(archive) as package:
                package.extractall(extracted,filter='data')
            extracted.rename(destination)
    if json.loads((destination/'library.json').read_text())['version']!=pin['ref'].removeprefix('v'):
        raise ValueError('Exported data-centre release differs from pin')
    return destination
