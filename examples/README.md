# A pipe run with an elbow and a tee

Open [pipe_run.usda](../usdAecoPipe/examples/minimal.usda). It contains four straight pipe occurrences,
a generated elbow, an authored tee, thirteen ports and a water system. Five
port pairs are connected in both directions. All connections coincide in world
space. The pipe, core and built-in validators report **0 errors, 0 warnings**.

The level is under the facility; system membership is a collection. Each pipe
inherits `/_TypeCatalog/SteelPipe`, whose three aligned rows describe DN50,
DN65 and DN80. Nominal, outer and inner diameter are deliberately different.
All four occurrences currently use DN50.

```text
Inlet ── Elbow
            │
          Middle
            │
           Tee ── Branch
            │
          Outlet
```

Turn on guide geometry in a viewer to see the run. Its six `BasisCurves`
children use standard USD geometry and carry `AecoDerivedGeometryAPI`.
The elbow is a segmented arc; all other guides are linear. There is no mesh
or render-material dependency. Authored fallback types let a plugin-free
runtime preserve the port, facility and level transforms, and display the
system as a Scope.

To reproduce the file after following the [root setup](../README.md):

```sh
env -u PYTHONPATH "$AECO_PYTHON" tools/build_example.py
env -u PYTHONPATH "$AECO_PYTHON" check.py
```

For an edit, change `aeco:axis:end` or `aeco:pipe:nominalDiameter` on an
occurrence in a stronger layer. A length control keeps the start fixed and
changes the end. Outer diameter, bore, label, slope and catalog size arrays
are derived values; a host or catalog publisher supplies them. This example
does not solve geometry when a driver changes.

`check.py` edits anonymous copies: removing an axis produces
`pipeMissingAxis`; setting 0.033 m produces `pipeSizeNotInTable`; translating
`Middle/In` by 0.5 m produces `pipeGap`. The committed example stays valid.
