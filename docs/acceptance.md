# Acceptance evidence

Target: usdAecoPipe 0.2.6. Dependency pins remain core 0.9.5, axis 0.1.5,
toolchain 0.3.10, data centre 0.4.8 and IFC 0.2.2. Tests run from source on
USD 26.8. The v0.5.2 full data-centre delivery is an additional compatibility
probe; it does not replace the example's pinned clash source.

| Acceptance | Measured result |
|---|---|
| Full check.py, including explicit project delivery | **89 checks, 0 failed, 0 not run** |
| Pytest from source | **29 passed** |
| Structure | **29/29 PASS**, including result freshness, relocation and independent rendering |
| Core UsdValidation registry | **8/8 loaded** |
| Minimal pipe/core/built-in validation | **0 errors, 0 warnings** |
| Minimal fixture and generated schema | **Byte-identical to v0.2.5** |
| Schema contract | **5 APIs, 18 properties, 9 derived flags**, unchanged |
| Project catalog regression | **2 classes moved, 6 inherits retargeted**, no root catalog |
| Standalone regression | Root catalog and generated children are **class specs** |
| Project reference regression | Catalog and SI size table survive a renamed project reference |
| Study-setting regression | Unset, `/Studies/pipe`, `/Studies/RenamedPipe`: **identical authored USDA bytes**, with and without a project |
| Full v0.5.2 hook | **1 root**, 2 new section classes, 6 inherits in the project catalog |
| Full v0.5.2 reference | **482 pipe catalogs carried**; 0 composition errors |
| Full v0.5.2 source preservation | **28/28 layers byte-identical** |
| Full v0.5.2 guides | **1,813**, all under elements; pipe validation clean |
| Pinned example runtime | **28.971 seconds** / 180-second budget |
| Published result | **14 files, 5,614,756 bytes** / 10,000,000-byte cap |
| Flattened crate | **1,784,228 bytes; 14,152 prims**, 0 composition errors |
| Own USDA layers | **10/11 byte-identical**; only `pipe.usda` changes |
| Vanilla render | **1280 × 800; 168,976 bytes**, independently rendered and non-uniform |
| Source transforms in pinned example | **12,279 identical** in a plugin-free process |
| Pipe promotion | **482 segments, 238 fittings, 1,650 ports, 17 types, 5 systems** |
| Required DN50 cases | **5/5**, nominal 0.05 m, OD 0.0603 m, two ports and inherited catalogs |
| Pinned pipe-validator findings | **0 errors, 0 warnings**, expected findings unchanged |
| Publication content scan | **71 text/decoded files, 0 findings**, including the USD crate |
| Offline Nix attempt | **1 attempt**, 5 Darwin derivations evaluated; timed out at **180.062 seconds** during prerequisites |

[Machine-readable gate](acceptance.json) records all checks.
[Byte-comparison receipt](stage-tidiness.json) records comparison with v0.2.5.
The [example manifest](../examples/datacentre/manifest.json) records published
bytes, hashes, dependency pins and source evidence.

## Catalog and study placement

The USD importer resolves the catalog from the default prim. Existing inherited
types are reused. Generated section types join that prim's `_TypeCatalog`; an
`AecoProjectAPI` default prim receives its own class catalog when missing.
Standalone stages without either retain a root-level class catalog. The new
parent is explicitly a class, preventing USD from creating an implicit `def`.

The hook creates no standalone looks, materials, findings prims or guides.
Axis guides are children of their source elements; presentation changes edit
existing geometry. `AECO_STUDY_ROOT` passes through to child tools and requires
no new scope or path remapping in this library. Regression tests compare all
authored USDA bytes with the setting unset and with two study paths. No empty
`/Studies` is created. The catalog always stays with the project.

The published crate matches v0.2.5 exactly after moving its two generated
section classes into the project catalog and removing the old root catalog.
No other composed opinions change. The editable import layer also retargets
six inherits. Ten other archived layers and the expected findings are unchanged.
Both committed PNGs were freshly rendered. Historical public re-pin and
relocation receipts remain evidence for their original releases.

## Reproduction

Use the [README source environment](../README.md#build-and-check) with the exact
release checkouts in `dependencies.json`. Select committed resource directories
for `CORE_PLUGIN_DIR` and `AXIS_PLUGIN_DIR`; installed copies may have stale
metadata. Run Python with `PYTHONPATH` unset. Set `AECO_DC_FULL_ROOT` to the
v0.5.2 delivery checkout for the additional probe.

```sh
env -u PYTHONPATH "$AECO_PYTHON" examples/datacentre/run.py --publish
env -u PYTHONPATH AECO_STUDY_ROOT=/Studies/pipe "$AECO_PYTHON" check.py \
  --project-stage "$AECO_DC_FULL_ROOT/dist/full/dc.usda" --report out/tidy-check.json
env -u PYTHONPATH "$AECO_PYTHON" -m pytest -q
```

The ordinary gate omits only the five optional full-delivery checks when
`--project-stage` is absent. Source checkouts remain read-only; the pinned IFC
revision was exported locally into ignored `out/pins/` for this run.

## Deviations

- Pipe has no standalone study content to relocate. `AECO_STUDY_ROOT` is tested
  as a compatible setting without adding a redundant empty study scope.
- One `nix flake check --offline --no-write-lock-file` attempt used five local
  source overrides, disabled substituters/builders and one build job. It
  evaluated five Darwin derivations and began prerequisite builds, then reached
  its 180-second limit during `bash53-014`. No second attempt ran and no lockfile
  was written. Nix packaging and Linux execution remain unproven.
- The pinned toolchain v0.3.10 discovers cameras only as direct children of
  `/Renders`, in both ordinary and independent vanilla rendering. The committed
  example therefore retains `/Renders/l01_void`. The hook authors no cameras;
  nesting this input under `/Renders/pipe` needs a shared renderer update.
- The committed minimal example retains its historical axis producer stamps
  and exact bytes. Rebuilding with the current pinned axis library changes
  four stamps from 0.1.1 to 0.1.3; that pre-existing regeneration difference is
  outside this catalog change.
- Existing source limitations remain: two core classification warnings on
  utility-intake proxies, 476 segments without nominal values, 17 incomplete
  catalogs and first-leg axes on the chilled-water pair. Native body regeneration,
  live round trips and exact/mesh clash verdicts remain unproven.
