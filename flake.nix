{
  description = "usdAecoPipe semantic library and example";
  inputs = {
    toolchain.url = "github:criad-com/usdaeco-toolchain?ref=v0.3.8";
    nixpkgs.follows = "toolchain/nixpkgs";
    core.url = "github:criad-com/usdaeco-core?ref=v0.9.2";
    core.inputs.toolchain.follows = "toolchain";
    core.inputs.nixpkgs.follows = "nixpkgs";
    axis.url = "github:criad-com/usdaeco-axis?ref=v0.1.2";
    axis.inputs.core.follows = "core";
    axis.inputs.toolchain.follows = "toolchain";
    axis.inputs.nixpkgs.follows = "nixpkgs";
    ifc.url = "github:criad-com/usdaeco-ifc?ref=v0.2.0";
    ifc.flake = false;
    datacentre.url = "github:criad-com/usdaeco-datacentre?ref=v0.4.5";
    datacentre.flake = false;
  };
  outputs = { self, nixpkgs, toolchain, core, axis, ifc, datacentre }:
    let
      eachSystem = nixpkgs.lib.genAttrs [ "aarch64-darwin" "x86_64-linux" ];
      forSystem = system:
        let
          kit = toolchain.lib.forSystem system;
          pkgs = nixpkgs.legacyPackages.${system};
          corePlugin = core.packages.${system}.default;
          axisPlugin = axis.packages.${system}.default;
          schema = kit.buildCodelessSchema { name = "usdAecoPipe"; src = self; deps = [ corePlugin axisPlugin ]; };
          plugins = kit.pluginSet { plugins = [ schema ]; };
          setup = ''
            export TOOLCHAIN_DIR=${toolchain}
            export AECO_CORE_ROOT=${core}
            export AECO_AXIS_ROOT=${axis}
            export AECO_IFC_ROOT=${ifc}
            export AXIS_PLUGIN_DIR=${axisPlugin}/plugins/usdAecoAxis/resources
            export CORE_PLUGIN_DIR=${corePlugin}/plugins/usdAeco/resources
            export AECO_DATACENTRE_ROOT=${datacentre}
            export PXR_PLUGINPATH_NAME=${plugins}
          '';
          example = pkgs.writeShellApplication {
            name = "example";
            runtimeInputs = [ kit.pythonEnv kit.usd-dev ];
            text = setup + ''
              cp -R ${self} example-work
              chmod -R u+w example-work
              env -u PYTHONPATH python example-work/examples/datacentre/run.py "$@"
            '';
          };
          render = pkgs.writeShellApplication {
            name = "render";
            runtimeInputs = [ kit.pythonEnv kit.usd-dev ];
            text = setup + ''
              cp -R ${self} render-work
              chmod -R u+w render-work
              env -u PYTHONPATH python render-work/tools/render_example.py
            '';
          };
        in { inherit kit pkgs schema plugins setup example render; };
    in {
      packages = eachSystem (system: let p = forSystem system; in {
        default = p.schema;
        pluginSet = p.plugins;
      });
      checks = eachSystem (system: let p = forSystem system; in {
        library = p.pkgs.runCommand "usdAecoPipe-check" {
          nativeBuildInputs = [ p.kit.pythonEnv p.kit.usd-dev ];
        } (p.setup + ''
          cp -R ${self} source
          chmod -R u+w source
          cd source
          env -u PYTHONPATH PYTHONPATH="$AECO_CORE_ROOT:$PWD" python check.py
          mkdir -p "$out"
        '');
        structure = p.pkgs.runCommand "usdAecoPipe-structure" {
          nativeBuildInputs = [ p.kit.pythonEnv ];
        } (p.setup + ''
          env -u PYTHONPATH usdaeco-check structure ${self} --dep "$CORE_PLUGIN_DIR" --dep "$AXIS_PLUGIN_DIR"
          mkdir -p "$out"
        '');
      });
      devShells = eachSystem (system: let p = forSystem system; in {
        default = p.pkgs.mkShell {
          packages = [ p.kit.pythonEnv p.kit.usd-dev ];
          shellHook = p.setup + "unset PYTHONPATH";
        };
      });
      apps = eachSystem (system: let p = forSystem system; in {
        example = { type = "app"; program = "${p.example}/bin/example"; };
        render = { type = "app"; program = "${p.render}/bin/render"; };
      });
    };
}
