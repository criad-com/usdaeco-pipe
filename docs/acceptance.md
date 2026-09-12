# Acceptance evidence

Target: usdAecoPipe 0.2.5, core 0.9.5, axis 0.1.5, toolchain 0.3.10,
data centre 0.4.8, IFC 0.2.2. [dependencies.json](../dependencies.json) records
the five release tags and checked source revisions. All five revisions were
resolved from the source forge and matched the clean sibling checkouts.
Library requirement ranges are unchanged. Python tests run directly from source
on USD 26.8, without setuptools or package installation.

| Acceptance | Measured result |
|---|---|
| Full check.py | **82 checks, 0 failed, 0 not run** |
| Pytest from source | **20 passed** |
| Structure from toolchain v0.3.10 | **29/29 PASS**, including S05 tag refs and package versions; no exception applied |
| Core UsdValidation registry | **8/8 loaded**, with the missing-tolerance regression detected |
| Minimal pipe/core/built-in validation | **0 errors, 0 warnings** |
| Schema compatibility | **5 APIs, 18 properties, 9 derived flags**, unchanged from the declared v0.1.2 fixture |
| S27 standalone result and freshness | **14,153 prims, 0 composition errors**, fresh result matches |
| S28 independent plugin-free render | **PASS**, fresh stock Embree render, non-uniform |
| Fresh example runtime | **28.659 seconds** / 180-second budget |
| Result inventory | **14 files, 5,614,609 bytes** / 10,000,000-byte cap |
| Flattened crate | **1,784,659 bytes; 14,153 prims** |
| Own USDA layers | **11 files; largest 847,944 bytes** / 2,000,000-byte cap |
| Vanilla render | **1280 × 800; 168,537 bytes** / 400,000-byte cap |
| Required DN50 cases | **5/5**, nominal 0.05 m, OD 0.0603 m, two ports and inherited catalogs |
| Pipe promotion | **482 segments, 238 fittings, 1,650 ports, 17 types, 5 systems** |
| Axis guides | **1,794**, in four deterministic text batches |
| Source transforms | **12,279 identical** in the plugin-free comparison |
| Pinned example pipe-validator findings | **0 errors, 0 warnings** |
| Offline Nix flake check | **1 attempt**, 5 Darwin derivations evaluated; stopped after 180 seconds, exit 1; build unproven |
| Public tag lookups without credentials | **2/5 resolved**; three authentication errors, detailed below |
| Publication sweep | **73 files, 0 findings**, including decoded USD crates |
| Whitespace and old public-org references | **git diff --check PASS; 0 obsolete org refs** |

[Machine-readable checks](acceptance.json) record the complete gate.
The [example manifest](../examples/datacentre/manifest.json) records every result
file's bytes and hashes, normalized crate hash, source evidence and dependency pins.
[Re-pin comparisons](public-repin.json) record the byte comparisons, render hashes,
source revisions and anonymous public-tag results.

## Republished result

Run the [README build setup](../README.md#build-and-check), then:

```sh
env -u PYTHONPATH PYTHONPATH="$AECO_CORE_ROOT:$(pwd)" "$AECO_PYTHON" examples/datacentre/run.py --publish
env -u PYTHONPATH PYTHONPATH="$AECO_CORE_ROOT:$(pwd)" "$AECO_PYTHON" check.py --report out/public-check.json
env -u PYTHONPATH "$AECO_PYTHON" -m pytest -q
```

The gate used the committed `usdAeco/` and `usdAecoAxis/` resource directories
from the exact tagged sources. Their installed `out/` copies had older metadata;
no dependency checkout was rebuilt or changed.

The published data-centre source inventory, source manifest hash and expected
findings hash match v0.2.4 exactly. Six editable layers are byte-identical.
The other five contain exactly 1,799 replacements of `aeco-axis 0.1.2` with
`aeco-axis 0.1.3`: 1,794 guide stamps and five layer producer strings. Reversing
only that string replacement reproduces every previous layer byte and every
previous flattened-crate byte. No geometry, driver, transform or other field
changed. The generated schema is also byte-identical; plugin metadata advances
to 0.2.5.

[Axis CHANGELOG 0.1.3](https://github.com/criad-com/usdaeco-axis/blob/v0.1.5/CHANGELOG.md)
records the producer-stamp refresh; 0.1.5 explicitly retains that stamp because
derivation is unchanged. The generated result notice changes only its source
tag, v0.4.5 to v0.4.8; manifest changes record pins, revisions and updated hashes.

Both preview images were rendered by the publication step. The committed PNGs
were then restored from v0.2.4 and their original manifest hashes retained, as
S28 does not compare pixels across renders. Fresh and retained images differ
by mean absolute RGB channel values of 0.177 and 0.178 on the 0–255 scale.
Their fresh hashes are recorded in the comparison receipt. The full gate
subsequently rendered the committed crate independently and passed S27/S28.

## Offline Nix attempt

Exactly one `nix flake check --offline --no-write-lock-file` invocation used ten
local overrides. It evaluated five Darwin derivations (the default package,
plugin set, two checks and development shell), inspected both apps, and reported
`running 867 flake checks`. The attempt was deliberately bounded to 180 seconds
and interrupted during the `bash53-014` prerequisite build, exiting 1 after
180.04 seconds. No package or gate build completed; Linux and public resolution
were not proven. No lockfile was written and no retry ran.

The five direct overrides in the README select the target release checkouts.
The complete command also supplies nested source inputs. Set
`AECO_BUILD_TOOLCHAIN_ROOT` to the local aeco-toolchain v0.4.0 checkout and
`OPENUSD_ROOT` to a local Git clone containing the pinned upstream revision:

```sh
nix flake check --offline --no-write-lock-file --max-jobs 1 \
  --option substituters '' --option builders '' \
  --override-input toolchain "path:$TOOLCHAIN_DIR" \
  --override-input core "path:$AECO_CORE_ROOT" \
  --override-input axis "path:$AECO_AXIS_ROOT" \
  --override-input ifc "path:$AECO_IFC_ROOT" \
  --override-input datacentre "path:$AECO_DATACENTRE_ROOT" \
  --override-input core/datacentre "path:$AECO_DATACENTRE_ROOT" \
  --override-input axis/datacentre "path:$AECO_DATACENTRE_ROOT" \
  --override-input toolchain/core "git+file://$AECO_CORE_ROOT?ref=refs/tags/v0.9.2" \
  --override-input toolchain/aeco-toolchain "path:$AECO_BUILD_TOOLCHAIN_ROOT" \
  --override-input toolchain/aeco-toolchain/openusd "git+file://$OPENUSD_ROOT?rev=47154dc7b5e28df623745495a7a508b69535ba24"
```

## Deviations

- The single offline Nix attempt was interrupted at its 180-second execution
  limit during prerequisite builds. Packaging, Linux and online reproduction
  remain **not proven**; no second attempt was made.

- Anonymous GitHub lookups resolved toolchain v0.3.10 and core v0.9.5. Axis
  v0.1.5, IFC v0.2.2 and datacentre v0.4.8 requested authentication. The supplied
  target tags are retained, but their public availability is **not independently
  proven** here. Public orphan revisions are recorded separately from checked
  source revisions; source hashes are never substituted into flake URLs.
- The committed PNG bytes are retained after fresh rendering to avoid sampling
  churn. The crate and five axis layers change only the documented producer
  stamp, so raw byte identity is claimed only after that exact replacement.
- Historical v0.1.2 schema evidence and the v0.2.3 relocation receipt retain their
  original pins. They are historical evidence, not flake inputs or current gates.
- Existing source limitations remain: two core classification warnings on
  utility-intake proxies, 476 segments without nominal values, 17 incomplete
  catalogs and first-leg axes on the chilled-water pair. Native body regeneration,
  live round trips and exact/mesh clash verdicts remain unproven here.
