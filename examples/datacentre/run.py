#!/usr/bin/env python3
"""Run the pinned Route K example and publish its standalone USD result."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(Path(os.environ.get('TOOLCHAIN_DIR',ROOT.parent/'usdaeco-toolchain'))/'tools'),str(ROOT/'tools')]
from usdaeco_pipe import register_plugins
from usdaeco_pipe.example import library_hook
from usdaeco_pipe.validators import register_core_validators
from usdaeco_check.example import run_example
from usdaeco_render import render


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish',action='store_true')
    args=parser.parse_args()
    register_plugins()
    register_core_validators()
    from usdaeco_pipe.pinned import datacentre_root
    os.environ.setdefault('AECO_DATACENTRE_ROOT',str(datacentre_root(ROOT)))
    example=Path(__file__).parent
    # The shared harness refreshes ignored inputs/source from AECO_DATACENTRE_ROOT.
    manifest=run_example(example,library_hook,variant='clash',publish=args.publish)
    # Preserve the guide view beside the harness's independent plugin-free proof.
    manifest['renders']=render(example/'out/example.usda',output=example/'out/renders',purposes='guide,proxy,render')
    manifest['presentation']={'purposes':['guide','proxy','render'],'excluded_roles':['extent']}
    (example/'out/manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    if args.publish:
        for old in (example/'renders').glob('*.png'):
            old.unlink()
        for record in manifest['renders']:
            shutil.copyfile(example/'out'/record['path'],example/record['path'])
        shutil.copyfile(example/'out/manifest.json',example/'manifest.json')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
