# Changelog

## 0.2.4

- Public names → github.com/criad-com.
- Re-pin toolchain to v0.3.8 for public-name structure checks.
- Keep all other dependency pins and published example artifacts unchanged.

## 0.2.3

- Use toolchain v0.3.6 and S29 to route published review-layer sources through
  the example's ignored inputs/source link, independent of checkout layout.
- Republish the same composed example with portable source references.


## 0.2.2

- Re-pin to train aeco-0.7.0: core v0.9.2, axis v0.1.2, toolchain v0.3.5,
  data centre v0.4.5 and IFC v0.2.0. Keep supported requirement ranges.
- Declare the unchanged v0.1.2 schema snapshot as a historical fixture.
- Refresh the stale result for data-centre clash mesh/tolerance changes and
  axis v0.1.2 producer stamps; preserve pipe drivers and readback.
- Verify 81 checks, 0 failed, all 28 structure rules and 20 pytest tests.
  One restricted Nix attempt cannot access the daemon; packaging is not proven.

## 0.2.1

- Publish a flattened, self-contained example crate, editable own layers and
  plugin-free render with toolchain v0.3.1 (S27/S28).
- Require axis >=0.1.1 and regenerate driven guides with declared tolerances.
  The stored two-branch tee declares its 1e-8 m encoding tolerance.
- Require all core validators to load for example validation.
- License the repository under MIT.

## 0.2.0

- Adopt the flat schema module, Python UsdValidation plugin, source tests,
  shared example harness, Apache-2.0 license and exact family dependency pins.
- Require core >=0.9,<1.0 and axis >=0.1,<0.2. Preserve all five APIs and all
  18 property contracts, proved with an Sdf snapshot of v0.1.2.
- Add `aeco-pipe import` for published USD property sets, including the explicit
  DC_Section fallback. Keep the IFC importer and legacy Python error names.
- Separate imported drivers from derived readback; preserve source layers.
- Publish a Route K example on the v0.4.1 clash stage and two USD-rendered images.
- Document unknown catalog data, the source-axis correction, the multi-leg axis
  limit and the unmeasured clash/native-regeneration steps.

## 0.1.2

- Add conformance profile support to the original five-API pipe library.
