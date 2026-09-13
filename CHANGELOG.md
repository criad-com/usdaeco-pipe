# Changelog

## 0.2.6

- Put imported pipe section classes in the default project's `_TypeCatalog`
  and retarget their inherits, so referencing the project carries its catalog.
  Reuse existing types; create the catalog under `AecoProjectAPI` when needed.
  Stages without a project catalog or project API retain a root-level class
  catalog, with an explicit `class` parent instead of an implicit `def`.
- Verify the hook with `AECO_STUDY_ROOT` unset, `/Studies/pipe` and a renamed
  study root. All its guides remain under elements and presentation edits stay
  on existing geometry; there are no standalone study prims to relocate.
- Republish the pinned data-centre result: two section classes move and six
  inherits are retargeted. Preserve the minimal example and generated schema
  byte-for-byte; dependency pins and schema contracts are unchanged.
- Add project/reference, standalone and full-hook regressions (29 pytest tests),
  plus `check.py --project-stage` for an explicit delivery compatibility probe.
  Record v0.5.2 full-stage and packaging evidence in `docs/acceptance.md`.

## 0.2.5

- public re-pin: toolchain v0.3.10, core v0.9.5, axis v0.1.5, IFC v0.2.2,
  datacentre v0.4.8. Record the checked revisions alongside public release tags.
- Keep the library requirement ranges; require toolchain >=0.3.10,<0.4
  for the release-tag and package-version checks in S05.
- Republish the example; geometry and drivers are byte-identical. Only the
  axis producer stamp changes (0.1.2 to 0.1.3, retained by axis v0.1.5),
  alongside source-tag and manifest provenance. Retain the committed PNGs
  after fresh renders, whose sampling changes bytes.
- Verify 82 checks, 0 failed, 0 not run; all 29 structure rules, eight core
  validators and 20 pytest tests pass against the exact tagged sources.
- Record the single offline Nix attempt: five Darwin derivations evaluated,
  interrupted after 180 seconds during prerequisites; packaging remains unproven.
  Two public tags resolve anonymously; three lookups request authentication.

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
