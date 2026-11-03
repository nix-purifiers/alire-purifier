{
  lib,
  runCommand,
  fetchgit,
  fetchurl,
  python,
  buildTools,
  providerTools,
  writeText,
  callPackage,
  purifier,
  alire,
  toolchain,
  nativePath,
  programs,
  sdkVersion,
  gnutar,
  gzip,
}@scope:
{
  src,
  lockFile ? src + "/alire-purifier.lock.json",
  fetchers ? { },
  libraryOverrides ? { },
  nativeBuildInputs ? [ ],
  doCheck ? false,
  checkCommand ? "",
}:
let
  lock = purifier.checkLock (import ./read-lock.nix { inherit lib; } { inherit src lockFile; });
  prepared = import ./environment.nix (builtins.removeAttrs scope [
    "gnutar"
    "gzip"
  ]) { inherit lock fetchers libraryOverrides; };
  source = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        ".alire-purifier"
        "alire"
        "config"
        "obj"
        "bin"
        "result"
        "__pycache__"
      ]);
  };
  context = writeText "alire-root-context.json" (
    builtins.toJSON {
      native = lock.data.native;
      names = map (n: n.name) lock.data.nodes;
      artifacts = prepared.sourceArtifacts;
      inherit programs nativePath;
      compilerIndex = ../native/compiler-index;
      externals = lock.data.externals;
    }
  );
  project =
    runCommand "alire-project"
      {
        nativeBuildInputs = [
          alire
          toolchain.gnat
          toolchain.gprbuild
          python
        ]
        ++ nativeBuildInputs;
      }
      ''
        cp -pr ${source} source
        chmod -R u+w source
        cd source
        ${python}/bin/python3 ${buildTools}/build-context.py ${context} "$PWD" "$TMPDIR/context"
        mkdir -p "$out/bin" "$out/source"
        if [ -d bin ]; then cp -pr bin/. "$out/bin/"; fi
        ${lib.optionalString doCheck checkCommand}
        cp -pr ${source}/. "$out/source/"
      '';
  release =
    runCommand "alire-native-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        mkdir -p "$out" source/project
        cp -pr ${source}/. source/project/
        chmod -R u+rwX source
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -czf "$out/alire-source.tar.gz" -C source project
      '';
in
assert lib.assertMsg (lock.data.sdk == sdkVersion) "Alire frontend SDK changed; update the lock";
{
  packages = {
    default = project;
    inherit project;
    environment = prepared.output;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
