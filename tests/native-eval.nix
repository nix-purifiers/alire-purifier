{ pkgs }:
let
  build = pkgs.alire-purifier.buildAlireProject;
  src = ../examples/native-projection;
  product = import ./native/product.nix;
  bad = [
    (product // { exports = [ ]; })
    (
      product
      // {
        exports = [
          "purifier_answer"
          "purifier_answer"
        ];
      }
    )
    (product // { project = "../escape.gpr"; })
    (product // { library = "/absolute.so"; })
    (product // { headers = [ "../outside.h" ]; })
    (
      product
      // {
        runtime = product.runtime // {
          lifecycle = "manual";
        };
      }
    )
    (
      product
      // {
        runtime = product.runtime // {
          threading = "concurrent";
        };
      }
    )
  ];
  rejected =
    p:
    !(builtins.tryEval
      (build {
        inherit src;
        nativeLibraries.answer = p;
      }).projections.native.drvPath
    ).success;
  defaults = build { inherit src; };
  cross =
    if pkgs.stdenv.buildPlatform.isAarch64 then
      pkgs.pkgsCross.gnu64
    else
      pkgs.pkgsCross.aarch64-multiplatform;
  crossBuild = build.override { stdenv = cross.stdenv; };
in
assert builtins.all rejected bad;
assert defaults.projections == { } && defaults.native == null;
assert cross.stdenv.buildPlatform != cross.stdenv.hostPlatform;
assert
  !(builtins.tryEval
    (crossBuild {
      inherit src;
      nativeLibraries.answer = product;
    }).packages.project.drvPath
  ).success;
true
