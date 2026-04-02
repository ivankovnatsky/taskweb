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

        pythonEnv = pkgs.python312.withPackages (ps: (pythonPackages ps) ++ [ ps.playwright ]);

        rev = self.rev or "dirty";

        taskwebPackage = pkgs.python312Packages.buildPythonApplication {
          pname = "taskweb";
          version = "0.1.0";
          pyproject = true;

          src = ./.;

          build-system = with pkgs.python312Packages; [
            poetry-core
          ];

          dependencies = pythonPackages pkgs.python312Packages;

          postPatch = ''
            substituteInPlace taskweb/__init__.py \
              --replace-warn "@NIX_COMMIT@" "${rev}"
          '';

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
            pkgs.nixfmt
            pkgs.nodePackages.prettier
            pkgs.python312Packages.pre-commit-hooks
            pkgs.just
            pkgs.taskwarrior3
            pkgs.playwright-driver.browsers
          ];

          shellHook = ''
            export PLAYWRIGHT_BROWSERS_PATH="${pkgs.playwright-driver.browsers}"
            export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS="true"
            echo "taskweb dev shell"
            echo "  just serve        - start the server (local test data)"
            echo "  just serve-user   - start the server (user task data)"
            echo "  just test         - run tests"
            echo "  just format       - format code"
            echo "  just screenshots  - update screenshots"
          '';
        };
      }
    );
}
