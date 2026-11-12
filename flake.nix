{
  description = "Locked, Nix-built Ada dependencies for Alire";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        alire-purifier = import ./pkgs/default.nix {
          pkgs = final;
          nixpkgsSrc = nixpkgs;
          purifierSrc = purifier;
        };
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (system: {
        default = (pkgsFor system).alire-purifier.cli;
        cli = self.packages.${system}.default;
      });
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/alire-purifier";
          meta.description = "Lock native Alire dependencies";
        };
      });
      lib.alire-purifier = (nixpkgs.lib.extend (import ./lib-overlays/default)).alire-purifier;
      checks = forAll (
        system:
        let
          p = pkgsFor system;
          b = p.alire-purifier.buildAlireProject {
            src = ./examples/minimal;
            doCheck = true;
            checkCommand = ''test "$("$out/bin/purifierproof" | tail -n 1)" = 42'';
          };
          native = p.alire-purifier.buildAlireProject {
            src = ./examples/native-projection;
            nativeLibraries.answer = import ./tests/native/product.nix;
          };
        in
        {
          inherit (b.packages) environment project;
          release = b.release;
          cli = self.packages.${system}.default;
          native-project = native.packages.project;
          native-libraries = native.native;
          native-consumers = import ./tests/native-consumers.nix {
            pkgs = p;
            built = native;
          };
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
