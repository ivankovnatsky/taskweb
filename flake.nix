{
  description = "TaskWeb - Web interface for Taskwarrior";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      supportedSystems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
    in
    {
      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python312;
          pythonPackages = python.pkgs;
        in
        {
          default = pkgs.mkShell {
            buildInputs = [
              python
              pythonPackages.flask
              pythonPackages.click
              pythonPackages.pytest
              pythonPackages.pip
              pkgs.ruff
              pkgs.treefmt
              pkgs.nixfmt-rfc-style
              pkgs.nodePackages.prettier
              pkgs.task
            ];

            shellHook = ''
              echo "taskweb dev shell"
              echo "  make serve  - start the server"
              echo "  make test   - run tests"
              echo "  make format - format code"
            '';
          };
        }
      );
    };
}
