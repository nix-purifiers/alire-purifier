{ nixpkgsSrc, alire }:
builtins.hashString "sha256" (
  builtins.toJSON {
    nixpkgs = toString nixpkgsSrc;
    resolver = toString alire.src;
    toolchain = builtins.hashFile "sha256" ./toolchain.nix;
    provider = builtins.hashFile "sha256" ../../alire_purifier/provider.py;
    compilerIndex = [
      (builtins.hashFile "sha256" ../../native/compiler-index/gn/gnat_external/gnat_external-external.toml)
      (builtins.hashFile "sha256" ../../native/compiler-index/gp/gprbuild/gprbuild-external.toml)
    ];
  }
)
