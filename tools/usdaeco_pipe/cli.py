"""Promote a published USD stage or validate pipe semantics."""
import argparse
import json
from . import register_plugins


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aeco-pipe", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("import")
    command.add_argument("stage")
    command.add_argument("--ifc", help="optional IFC source; otherwise promote USD property sets")
    command.add_argument("-o", "--out", required=True)
    command = commands.add_parser("check")
    command.add_argument("stage")
    args = parser.parse_args(argv)
    register_plugins()
    if args.command == "import":
        if args.ifc:
            from .importer import import_pipe
            result = import_pipe(args.stage, args.ifc, args.out)
        else:
            from .usd_importer import import_stage
            result = import_stage(args.stage, args.out)
    else:
        from pxr import Usd
        from usdaeco_check.validation import run
        stage = Usd.Stage.Open(args.stage)
        if not stage or stage.GetCompositionErrors():
            parser.error("stage does not compose")
        result = [{"name": e.GetName(), "severity": str(e.GetType()).split(".")[-1].lower(),
                   "message": e.GetMessage(), "paths": [str(s.GetPath()) for s in e.GetSites()]}
                  for e in run(stage, ["UsdAecoPipeValidators"])]
    print(json.dumps(result, indent=2, sort_keys=True))
    return int(args.command == "check" and any(e["severity"] == "error" for e in result))


if __name__ == "__main__":
    raise SystemExit(main())
