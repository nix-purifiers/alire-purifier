{ root, lockFile }:
let
  nixpkgsSrc = /. + "@nixpkgs@";
  pkgs = import nixpkgsSrc { };
  scope = import ../default.nix {
    inherit pkgs nixpkgsSrc;
    purifierSrc = /. + "@purifier@";
  };
in
(scope.buildAlireProject {
  src = /. + root;
  lockFile = /. + lockFile;
}).release
