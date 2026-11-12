{
  root,
  lockFile,
  sdk,
}:
let
  nixpkgsSrc = /. + "@nixpkgs@";
  pkgs = import nixpkgsSrc { };
  scope = import ../default.nix {
    inherit pkgs nixpkgsSrc;
    purifierSrc = /. + "@purifier@";
  };
  lock = scope.purifier.checkLock (
    import ../../lib-overlays/default/read-lock.nix { inherit (pkgs) lib; } {
      src = /. + root;
      lockFile = /. + lockFile;
    }
  );
  environment = scope.callPackage ./environment.nix { } { inherit lock; };
in
assert pkgs.lib.assertMsg (
  lock.data.sdk == scope.sdkVersion
) "Alire frontend SDK changed; update the lock";
pkgs.writeText "alire-environment-profile.json" (
  builtins.toJSON {
    output = environment.output;
    sdk = builtins.storePath sdk;
  }
)
