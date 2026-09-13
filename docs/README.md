# usdAecoPipe schema reference

Version **0.2.6**, kind tier, requires `usdAeco >=0.9,<1.0` and
`usdAecoAxis >=0.1.1,<0.2`; checked against core v0.9.5 and axis v0.1.5.
The authoritative source is [schema.usda](../usdAecoPipe/schema.usda).
All five schemas are single-apply APIs. The published per-API namespaces are
preserved, including `aeco:pipeType:` and `aeco:pipeFitting:`.

Pipe dimensions are **SI metres**, pressure is **Pa**, temperature is **K**,
bend angle is **radians** and slope is dimensionless. Geometry and transforms
use the stage's `metersPerUnit`; the gap validator converts world distances
to metres. In the tables, D means driver and R means derived/readback.
Every R property has `aecoDerived = true` in the schema, never in `customData`
or authored stage data. OpenUSD 26.8 retains brief user documentation in the
generated registry; full documentation lives in the source schema and here.

## Occurrences: `AecoPipeAPI`

Applies to `Imageable`, beside core `AecoElementAPI` and the separate `AecoAxisAPI`.
Classification is `IfcPipeSegment.*` or `IfcPipeFitting.*`; a fitting need
only carry `AecoPipeFittingAPI` unless it also has a meaningful single axis
and nominal section.

| Property | Type · fallback | D/R | Source meaning |
|---|---|---|---|
| `aeco:pipe:nominalDiameter` | double · 0.05 | D | Size-table key in m; `RBS_PIPE_DIAMETER_PARAM` / `MEPCurve.Diameter`; `Pset_PipeSegmentTypeCommon.NominalDiameter` |
| `aeco:pipe:outerDiameter` | double · 0 | R | Outer diameter in m; `RBS_PIPE_OUTER_DIAMETER`; twice `IfcCircleHollowProfileDef.Radius` |
| `aeco:pipe:innerDiameter` | double · 0 | R | Bore in m; `RBS_PIPE_INNER_DIAM_PARAM`; twice `(Radius - WallThickness)` |
| `aeco:pipe:sizeLabel` | string · `""` | R | Display text; `RBS_PIPE_SIZE_PARAM`; `IfcProfileDef.ProfileName` |
| `aeco:pipe:slope` | double · 0 | R | Signed rise/run; `RBS_PIPE_SLOPE`; `Pset_PipeSegmentOccurrence.Gradient`, otherwise world-axis slope |

Zero derived dimensions mean unavailable. A vertical axis has no finite slope;
the importer blocks an unavailable slope instead of claiming a measured zero.
The nominal schema fallback is a default choice, not evidence of an IFC value;
the importer blocks it when neither a profile nor a nominal property exists.

## Catalogs: `AecoPipeTypeAPI`

No mechanical prim-type restriction; author it beside `AecoTypeAPI` on an
abstract catalog class. Occurrences use native `inherits`. No `aeco:id` is
authored on catalog types.

| Property | Type · fallback | D/R | Source meaning |
|---|---|---|---|
| `aeco:pipeType:material` | string · `""` | D | `PipeSegment` material; associated profile `IfcMaterial.Name`; not a render binding |
| `aeco:pipeType:schedule` | string · `""` | D | `PipeSegment` schedule/type; pipe-common `Reference` |
| `aeco:pipeType:workingPressure` | double · 0 | D | Type working-pressure parameter; pipe-common `WorkingPressure`, Pa |
| `aeco:pipeType:nominalDiameters` | double[] · [] | R | Unique nominal keys, m; `PipeSegment.GetSizes()` or known IFC profiles |
| `aeco:pipeType:outerDiameters` | double[] · [] | R | Outer diameter for each aligned key, m |
| `aeco:pipeType:innerDiameters` | double[] · [] | R | Bore for each aligned key, m |

The three arrays must have equal lengths. Dimensions must be finite and
positive, inner ≤ outer; nominal keys must be unique within `1e-8 m`.
An empty table means unknown catalog data. To extend a table, a catalog
publisher adds corresponding entries to **all three arrays** in the catalog
layer, or supplies additional named hollow-circle material profiles in IFC
and reruns the importer to a new output. An intent editor changes the nominal
key; it does not add its own derived catalog rows.

## Fittings: `AecoPipeFittingAPI`

Applies to `Imageable`, beside `AecoElementAPI`. Bend, tee and transition
roles remain classification (`IfcPipeFitting.BEND`, `.JUNCTION`, `.TRANSITION`).

| Property | Type · fallback | D/R | Source meaning |
|---|---|---|---|
| `aeco:pipeFitting:origin` | uniform token · authored | D | `authored` or `generated`; adapter provenance, not an IFC kind |
| `aeco:pipeFitting:angle` | double · 0 | R | Family bend deflection or revolved fitting geometry, rad |
| `aeco:pipeFitting:bendRadius` | double · 0 | R | Family centreline bend radius or fitting geometry, m |

An imported fitting is `authored`. Only an adapter that creates a fitting to
satisfy intent should mark it `generated`. IFC geometry represented as an
`IfcRevolvedAreaSolid` supplies angle and radius. Other representations retain
the unavailable fallbacks; the importer does not fit curves to a mesh.

## Ports: `AecoPipePortAPI`

Mechanically restricted to `AecoPort`; a Mesh is refused by `CanApplyAPI`.
The owning element is its nearest ancestor with `AecoElementAPI`.

| Property | Type · fallback | D/R | Source meaning |
|---|---|---|---|
| `aeco:pipePort:nominalDiameter` | double · 0 | conditional | Twice `Connector.Radius`; `Pset_DistributionPortTypePipe.NominalDiameter`, m |
| `aeco:pipePort:connectionType` | uniform token · undefined | D | Family connector description; `Pset_DistributionPortTypePipe.ConnectionType` |

Connection tokens: `undefined`, `threaded`, `flanged`, `welded`, `pushFit`,
`compression`, `solvent`, `grooved`, `other`. The importer normalizes case,
spaces and punctuation; unrecognized text becomes `other`.

Port diameter is a driver on equipment, but readback on segments/fittings.
It intentionally has **no global derived flag**, following design §12.3.
An editor/adapter must consult the owner before allowing a port-size edit.
Zero means unknown and is excluded from diameter mismatch comparisons.
Connectivity is always `aeco:connectedPorts`, authored symmetrically.

## Systems: `AecoPipeSystemAPI`

Mechanically restricted to `AecoSystem`; a plain Scope is refused.
Membership is the core `CollectionAPI:members`; system kind is classification.

| Property | Type · fallback | D/R | Source meaning |
|---|---|---|---|
| `aeco:pipeSystem:fluid` | string · `""` | D | `PipingSystemType` fluid name |
| `aeco:pipeSystem:fluidTemperature` | double · 0 | D | `PipingSystemType` fluid temperature, K |

IFC defines no standard equivalents for these fields. The importer accepts
the optional exchange convention `Pset_PipeSystemCommon.Fluid` and
`.FluidTemperature`. Explicit units and project temperature units are honored,
including Celsius offsets; unspecified temperature units mean K. It never
guesses fluid or temperature from a system classification.

## Queries and validators

The optional [`usdaeco_pipe`](../tools/usdaeco_pipe/__init__.py) companion
uses string schema identifiers; there are no generated Python API classes.

| Query | Result |
|---|---|
| `iter_pipes(stage)` | Active, defined, non-abstract occurrences with `AecoPipeAPI` |
| `pipe_type_of(prim)` | First inherited pipe catalog class in inheritance strength order, or `None` |
| `size_table(type_prim)` | Ordered `(nominal, outer, inner)` tuples in m; `[]` if unknown; `ValueError` if malformed |
| `size_in_table(prim)` | `True`/`False` for a known table; `None` if unknown; malformed tables raise `ValueError` |

[`validators.register()`](../tools/usdaeco_pipe/validators.py) registers five
rules under keyword **`AecoPipeValidators`**, with names `aecoPipe:<rule>`.
`validate_stage(stage)` returns `UsdValidation.ValidationError` objects and
includes USD's built-in core rules by default. Use `include_core=True` with
the core `tools/` directory on `sys.path` to include usdAeco rules too.

| Rule / error name | Severity | Condition |
|---|---|---|
| `pipeKindMismatch` | Warn | Pipe/fitting API with absent or incompatible IFC classification; entity prefix must equal `IfcPipeSegment` or `IfcPipeFitting` |
| `pipeMissingAxis` | Error | `AecoPipeAPI` without `AecoAxisAPI` |
| `pipeSizeNotInTable` | Warn | Nominal key absent from a known catalog; malformed table also warns |
| `pipePortSizeMismatch` | Warn | Connected pipe ports have known differing nominal sizes, with neither owner a fitting |
| `pipeGap` | Error | Connected port origins differ by **more than `1e-4 m` in world space** |

Pair rules emit one finding per undirected connection, with both port paths
as validation sites. One-way edges are checked too; symmetry, dangling
targets, flow and medium are the core validators' responsibility. The rules
evaluate default-time data; they do not inspect animated geometry. Missing
catalogs do not claim that an unknown size is valid or invalid. Sync intent
rules, including rejection of derived edits, belong to the separate sync tier.

## Importer

[`aeco-pipe-import`](../tools/aeco-pipe-import)
`<core-stage.usda> <file.ifc> [-o kind.usda]` requires output from the core
reference converter. See the [setup and commands](../README.md#import-ifc-pipe-facts).

The pass joins occurrences, ports and systems by IFC GlobalId decoded into
the core's UUID `aeco:id`. Catalog identity comes from the occurrence's core
inheritance arc. It preserves axes, placements, geometry, classifications,
connections and collections, and authors only pipe APIs/properties and
value blocks for promoted quarantine attributes.

Nominal size uses pipe-common `NominalDiameter` first, then a full `DN<number>`
profile name (DN is millimetres), then outer diameter as an explicitly counted
fallback (`nominalFallbacks`). Physical diameter/bore comes from the selected
hollow-circle extrusion profile; associated material profiles contribute
additional catalog rows. With no profile, pipe-common `OuterDiameter` and
`InnerDiameter` are promoted if available. Duplicate identical rows collapse;
conflicting rows for one nominal key stop the import. No fixed DN50/DN65/DN80
table is imported from the prototype.

The pass applies fitting APIs to actual `IfcPipeFitting` entities; port APIs
to PIPE ports, pipe/fitting-owned ports, or ports with pipe property sets; and
system APIs to distribution systems containing pipes/fittings or carrying the
optional fluid property set. Missing core matches are counted as `unmatched`.
An incomplete reference conversion therefore cannot silently claim completeness.

Replaced pipe-common fields are `NominalDiameter`, `OuterDiameter`,
`InnerDiameter`, `Reference` and `WorkingPressure`, where the typed replacement
is available. Catalog drivers use the IFC type's values; distinct occurrence
schedule/pressure properties are retained because they are not represented by
that type driver. Other fields, such as `Status`, `Length` or `PressureRange`,
remain quarantined. Removing property definitions from a weaker layer is not
possible through an overlay, so the importer uses
[USD attribute value blocking](https://openusd.org/dev/api/class_usd_attribute.html).
Names remain discoverable; suppressed values resolve to `None`. Muting the
kind layer restores the original core data without editing the source files.

Lengths, pressure and temperature honor explicit property units, otherwise
project units, using the installed
[IfcOpenShell unit utilities](https://docs.ifcopenshell.org/autoapi/ifcopenshell/util/unit/index.html).
Unknown unit kinds fail rather than silently returning a mis-scaled value.
Mixed-material profiles do not invent a single material name. Fitting shapes
other than revolved solids and catalog availability beyond profiles actually
present in the IFC remain outside this initial importer.

## Verification and integration boundaries

[`check.py`](../check.py) runs the schema, importer, example, dependency and
hygiene gates; [acceptance](acceptance.md) records the current counts.
The reference baseline imports as
2 pipes, 2 types, 4 ports, 1 system and 0 fittings: it contains no fitting
or pipe property set. An augmented temporary baseline adds a real revolved
fitting and typed property sets to exercise all five APIs and suppression of
the replaced values. Independent millimetre fixtures distinguish nominal,
outer and inner diameter and verify pressure and temperature conversion.

The local example has 0 errors and 0 warnings. Seeded missing axis and a
0.5 m gap are errors; 0.033 m is a warning. A fresh process without AECO
plugins preserves all 28 example transforms and reads authored data through
the fallback types.

The shared toolchain v0.3.10 supplies the codeless builder, validation adapters,
structure lint, example harness and CPU renderer. Source generation writes beside
schema.usda; installation writes below out/plugins. The five plugin rules use
keyword `UsdAecoPipeValidators` and names `usdAecoPipeValidators:Pipe…Checker`.
Plugin errors capitalize the initial letter of legacy names. The existing
`validate_stage` function preserves legacy spellings and severity profiles.

## Published USD importer

`aeco-pipe import input.usda --out pipe.usda` promotes standard pipe property
sets without importing IfcOpenShell. Explicit DC_Section dimensions are a fallback
when a standard property is absent. Length properties are converted from stage
units to SI; pressure and temperature are already Pa and K. No body is inferred.
Unknown nominal values are blocked, and incomplete bore data never becomes an
invented catalog row. A catalog class may describe an imported known section
without asserting a complete manufacturing table.

Generated section classes live in `/<defaultPrim>/_TypeCatalog` when that
catalog exists or the default prim has `AecoProjectAPI`. Existing inherited
types are reused. Only stages without either use `class "_TypeCatalog"` at
the stage root. Queries and validators follow the actual inherits, including
after the project is referenced at another path.

Both import paths split schema-marked derived properties into a sibling
`pipe.derived.usda`. The root layers only imported drivers over readback and the
source. Existing output paths are refused. The
[data-centre example](../examples/datacentre/README.md) composes a pinned stage
without running the converter. Full results and limitations are in
[acceptance](acceptance.md).
