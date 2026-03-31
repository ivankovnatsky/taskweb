{
  description = "TaskWeb - Web interface for Taskwarrior";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ ];
        };

        pythonPackages =
          ps: with ps; [
            flask
            click
          ];

        pythonEnv = pkgs.python312.withPackages pythonPackages;

        taskwebPackage = pkgs.python312Packages.buildPythonApplication {
          pname = "taskweb";
          version = "0.1.0";
          pyproject = true;

          src = ./.;

          build-system = with pkgs.python312Packages; [
            poetry-core
          ];

          dependencies = pythonPackages pkgs.python312Packages;

          meta = with pkgs.lib; {
            description = "Web interface for Taskwarrior 3";
            homepage = "https://github.com/ivankovnatsky/taskweb";
            license = licenses.mit;
          };
        };
      in
      {
        packages = {
          taskweb = taskwebPackage;
          default = taskwebPackage;
        };

        devShells.default = pkgs.mkShell {
          buildInputs = [
            pythonEnv
            pkgs.python312Packages.pytest
            pkgs.ruff
            pkgs.treefmt
            pkgs.nixfmt-rfc-style
            pkgs.nodePackages.prettier
            pkgs.just
            pkgs.taskwarrior3
          ];

          shellHook = ''
            echo "taskweb dev shell"
            echo "  just serve  - start the server"
            echo "  just test   - run tests"
            echo "  just format - format code"
          '';
        };
      }
    );
}
