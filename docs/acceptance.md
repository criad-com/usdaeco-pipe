# Acceptance evidence

Target: usdAecoPipe 0.2.1, core 0.9.1, axis 0.1.1, toolchain 0.3.1,
data centre 0.4.1, IFC 0.1.0. Python tests run directly from source on USD 26.8.
The gate retains all 41 original checks. Sdf comparison still covers five APIs,
18 properties and nine derived flags, including names, types, defaults,
variability and allowed tokens.

| Acceptance | Measured result |
|---|---|
| Full check.py | **81 checks, 0 failed** |
| Pytest from source | **20 passed** |
| Minimal smoke | **21 checks, 0 failed**, all **8 core validators loaded** |
| Minimal pipe/core/built-in validation | **0 errors, 0 warnings** |
| Core E15 regression | Removing the tee tolerance produces `ExactWithoutTolerance` |
| S27 standalone result and freshness | **PASS: 14,153 prims, 0 composition errors; regenerated result matches** |
| S28 independent plugin-free render | **PASS: fresh stock Embree render, non-uniform** |
| Structure | **28/28 with family licence policy; raw upstream 26/28**, S01/S25 exceptions below |
| Term sweep | **Clean except required MIT copyright line; serialized crate clean** |
| Result inventory | **14 files, 5,614,113 bytes** / 10,000,000-byte cap |
| Flattened crate | **1,784,152 bytes; 14,153 prims** |
| Own USDA layers | **11 files; largest 847,944 bytes** / 2,000,000-byte cap |
| Vanilla render | **1280 × 800; 168,527 bytes** / 400,000-byte cap; visually inspected |
| Required DN50 cases | **5/5**, nominal 0.05 m, OD 0.0603 m, two ports and inherited catalogs |
| Pipe promotion | **482 segments, 238 fittings, 1,650 ports, 17 types, 5 systems** |
| Axis guides | **1,794**, in four deterministic text batches with composed Sdf fields unchanged |
| Pinned example pipe-validator findings | **0 errors, 0 warnings** |
| Pinned composed example core validation | **0 errors, 2 source classification warnings** on utility-intake proxies |
| Nix | **1 attempt**, stopped at public axis v0.1.1 source HTTP 404 |

[Machine-readable checks](acceptance.json) record each final gate result.
The [example manifest](../examples/datacentre/manifest.json) records every result
file's bytes and hashes, normalized crate hash, source evidence and dependency pins.
The minimal fixture's four driven guides use axis v0.1.1. Its two-branch tee has
no axis drivers; the known 0.2 m coordinates round to float32 with error below
1e-8 m, the declared generation tolerance. The segmented elbow also has no axis
drivers and retains its stored `arcSegmented` guide.

## Deviations

- The family licence is MIT with the required copyright holder. Toolchain v0.3.1 S01 still
  rejects it with `Apache-2.0 license text required`. The repo gate replaces only
  that exact failure with a full MIT-text hash and manifest-licence check;
  missing root files and every other lint failure remain failures. The raw
  upstream S01 rejection is retained here as a deviation, not reported as a pass.
  S25 also rejects the required copyright-holder line. Only `LICENSE:3` is
  accepted, with the same full-file hash; any additional term match fails.
- One `nix flake check --no-write-lock-file` attempt failed while resolving the
  public axis v0.1.1 source (HTTP 404). Nix builds are not proven; no retry ran.
- The default data-centre checkout has advanced. The existing runner exports the
  pinned v0.4.1 tag into ignored `out/pins/` without modifying that checkout;
  source mode remains `pinned`. Explicit source-root overrides stay strict.
- The 2,293,528-byte full axis derivation exceeds the individual USDA cap.
  It is archived as four deterministic batches plus a small sublayer wrapper;
  an Sdf field comparison rejects any change in composed opinions.
- The pinned composed data-centre stage retains two core `proxyClassified`
  warnings on utility-intake proxies. Its existing pipe-validator scope remains
  unchanged and clean. The minimal pipe fixture passes core, pipe and built-in
  validation with zero warnings; all eight core rules must load in the gate.
- The kit harness fixes proxy/render purposes. The existing second render call
  retains the guide view and refreshes its measured manifest; S28 independently
  renders the crate plugin-free with proxy/render purposes.
- Source catalog gaps remain: 476 segments lack nominal values and all 17 tables
  are incomplete. The chilled-water pair retains its first-leg axis limitation.
  Native body regeneration and exact/mesh clash verdicts are not proven here.
