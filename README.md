# usdAecoPipe — pipe drivers, catalogs and connected fittings

## Use case

Route K describes a pipe by its axis and nominal size. The authoring tool resolves
its body and creates fittings as identified elements with ports. Read the
[use case](docs/usecase.md) for the editing contract and the clash trade-off.

## The schema on an index card

| Applied schema | Target | Facts |
|---|---|---|
| `AecoPipeAPI` | Imageable element | Nominal size; derived OD, bore, label and slope |
| `AecoPipeTypeAPI` | Untyped catalog class | Material, schedule, pressure; derived size table |
| `AecoPipeFittingAPI` | Imageable element | Authored/generated origin; derived angle and radius |
| `AecoPipePortAPI` | AecoPort | Nominal size and connection method |
| `AecoPipeSystemAPI` | AecoSystem | Fluid and temperature |

Five APIs, 18 properties, nine derived flags. Property names, types, defaults,
allowed tokens and variability match v0.1.2 by Sdf comparison. Dimensions are
SI metres; geometry uses stage units. Kind remains classification, identity
remains `aeco:id`, and connectivity remains the core port graph.

## The example

The pinned `usdaeco-datacentre` v0.4.5 clash stage supplies 482 pipe segments and
238 fittings. The importer promotes its property sets, `aeco-axis derive` writes
separate guides, and the Python validator plugin checks the composed stage.

```sh
env -u PYTHONPATH "$AECO_PYTHON" examples/datacentre/run.py
```

Open the committed [example crate](examples/datacentre/result/example.usdc) with
stock USD; it needs no family plugins or sibling checkouts:

```sh
usdview examples/datacentre/result/example.usdc
```

The [example](examples/datacentre/README.md) writes transient evidence under
`examples/datacentre/out/`. `run.py --publish` refreshes `result/example.usdc`,
its editable own layers, `result/vanilla.png`, renders and the measured manifest. All five named DN50 pipes have
OD 60.3 mm. Red, amber and green identify the three planted sweeps; blue identifies
the chilled-water pair. These are identity colors, not computed clash verdicts.

![L01 ceiling void from above](examples/datacentre/renders/l01_void.png)

## Build and check

Use sibling source checkouts at the refs in [dependencies.json](dependencies.json).
Set `AECO_PYTHON` to the Python environment providing USD 26.8, IfcOpenShell 0.8.5,
numpy, jinja2, packaging, pytest and Pillow. No editable install or setuptools is
needed to run the tools or tests. Core and axis plugins must already be built.

```sh
export PYTHON="$AECO_PYTHON"
export TOOLCHAIN_DIR="$(cd ../usdaeco-toolchain && pwd)"
export AECO_CORE_ROOT="$(cd ../usdaeco-core && pwd)"
export AECO_AXIS_ROOT="$(cd ../usdaeco-axis && pwd)"
export AECO_IFC_ROOT="$(cd ../usdaeco-ifc && pwd)"
export AECO_DATACENTRE_ROOT="$(cd ../usdaeco-datacentre && pwd)"
export CORE_PLUGIN_DIR="$AECO_CORE_ROOT/out/plugins/usdAeco/resources"
export AXIS_PLUGIN_DIR="$AECO_AXIS_ROOT/out/plugins/usdAecoAxis/resources"
export PXR_PLUGINPATH_NAME="$CORE_PLUGIN_DIR:$AXIS_PLUGIN_DIR:$(pwd)/usdAecoPipe:$(pwd)/usdAecoPipeValidators"
bash build.sh --generate-only
bash build.sh --install-root out
env -u PYTHONPATH PYTHONPATH="$AECO_CORE_ROOT:$(pwd)" "$AECO_PYTHON" check.py
env -u PYTHONPATH "$AECO_PYTHON" -m pytest -q
```

`check.py` prints `N checks, M failed`, runs every original acceptance check,
then `check_example()` (fresh-result comparison and independent vanilla render)
and S01–S29 structure lint from toolchain v0.3.8. `--without-importer`
explicitly omits IFC regression checks. `--baseline input.ifc` additionally
selects an external baseline; fixtures are generated in temporary directories.
Core loads first because it registers `aecoDerived`. All eight core validator
rules must load; a missing `usdAecoValidators` import fails the gate. `PIPE_PLUGIN_DIR` may select
an installed resource directory. `usdrecord` with the Embree renderer must be
on PATH; the shared renderer disables GPU and ambient occlusion.

Source CLI usage (installed entry point: `aeco-pipe`):

```sh
env -u PYTHONPATH "$AECO_PYTHON" tools/aeco-pipe import input.usda --out pipe.usda
env -u PYTHONPATH "$AECO_PYTHON" tools/aeco-pipe check pipe.usda
env -u PYTHONPATH "$AECO_PYTHON" tools/aeco-pipe import input.usda --ifc input.ifc --out pipe.usda
```

The legacy `tools/aeco-pipe-import input.usda input.ifc -o pipe.usda` remains
available. Outputs must be new paths. Imported driver opinions and derived
readback occupy separate layers; neither source geometry nor source files change.
[Reference documentation](docs/README.md) explains promotion and legacy error names.

Nix inputs use public exact refs. A local checkout or private registry can supply
the sources without committing deployment addresses:

```sh
nix flake check --no-write-lock-file \
  --override-input toolchain path:../usdaeco-toolchain \
  --override-input core path:../usdaeco-core \
  --override-input axis path:../usdaeco-axis \
  --override-input ifc path:../usdaeco-ifc \
  --override-input datacentre path:../usdaeco-datacentre
```

See the [toolchain conventions](https://github.com/criad-com/usdaeco-toolchain/blob/v0.3.8/docs/repo-conventions.md)
for nested input overrides. `nix run .#example` runs the data-centre example;
`nix run .#render` renders the minimal pipe run with guides enabled.

## Family

Runtime requirements: `usdAeco >=0.9,<1.0`, `usdAecoAxis >=0.1.1,<0.2`.
Verified pins: core v0.9.2, axis v0.1.2, toolchain v0.3.8, data centre v0.4.5,
IFC v0.2.0 for synthetic regression conversion. The published data-centre stage
was produced against core v0.8.4; its stage vocabulary still composes on core v0.9.2.
There is no dependency on wall, clash, sync, or an authoring-tool integration.
The [family board](https://github.com/criad-com/usdaeco-board) consumes the same
metadata and evidence files.

## Layout

`usdAecoPipe/` contains source/generated schema, resource descriptor, user docs
and the minimal stage. `usdAecoPipeValidators/` is the Python UsdValidation plugin.
`tools/usdaeco_pipe/` holds CLI, importers and queries; `testenv/` holds source
regressions and the released schema snapshot. `docs/usecase.md` describes Route K;
`examples/datacentre/` contains pinned inputs, expected findings, renders and a standalone `result/`.
`out/` is transient; install resources are separate from the flat source module.

## Status

Version **0.2.4** uses public **github.com/criad-com** names and toolchain
**v0.3.8**. The full gate passes **82 checks, 0 failed, 0 not run** against
[the exact dependency pins](dependencies.json). All **29 structure rules**
pass, including S05 and S25; **20 pytest tests pass**. All eight core validators
load through UsdValidation.

The published result and renders remain byte-identical to v0.2.3. The result
totals **5,614,609 bytes**, within the 10 MB cap. S27/S28 and the fresh-result
comparison pass. Only the example manifest's toolchain pin changed; no result
was republished. Earlier [relocation verification](docs/relocation-verification.md)
records the portable source layout.

Nix remains unproven: the single offline flake-check attempt with exact local
source overrides failed while resolving axis v0.1.2's nested data-centre v0.4.2
input (HTTP 404). Native regeneration and live round trips were not run.
The source tessellation, findings and existing example limitations remain unchanged.

## Licence

MIT License. See [LICENSE](LICENSE).

Third-party code is not vendored. Runtime dependencies retain their licences:
OpenUSD uses the Apache-2.0-style TOST licence; numpy and jinja2 use BSD licences;
packaging uses Apache-2.0 or BSD-2-Clause; Pillow uses HPND. The optional IFC
importer imports IfcOpenShell (LGPL-3.0), whose OCCT dependency is dynamically
linked under LGPL-2.1. Pytest is a test-only MIT dependency.
