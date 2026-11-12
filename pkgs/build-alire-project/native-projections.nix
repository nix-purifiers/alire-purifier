{
  lib,
  stdenv,
  runCommand,
  writeText,
  python,
  binutils,
  toolchain,
  purifier,
}:
{
  nativeLibraries,
  project,
  source,
  dependencyPrefixes,
}:
let
  names = builtins.attrNames nativeLibraries;
  path =
    p:
    builtins.isString p
    && p != ""
    && !(lib.hasPrefix "/" p)
    && builtins.all (s: s != "" && s != "." && s != "..") (lib.splitString "/" p);
  symbol = s: builtins.isString s && builtins.match "[A-Za-z_][A-Za-z0-9_]*" s != null;
  valid =
    p:
    builtins.isAttrs p
    &&
      builtins.attrNames p == [
        "exports"
        "headers"
        "library"
        "project"
        "runtime"
      ]
    && path p.project
    && lib.hasSuffix ".gpr" p.project
    && path p.library
    && lib.hasSuffix ".so" p.library
    && builtins.isList p.headers
    && p.headers != [ ]
    && builtins.all path p.headers
    && builtins.isList p.exports
    && p.exports != [ ]
    && builtins.all symbol p.exports
    && lib.unique p.exports == p.exports
    &&
      p.runtime == {
        kind = "gnat";
        initialization = "linker-constructor";
        lifecycle = "process-lifetime";
        threading = "single-foreign-thread";
      };
  spec = writeText "alire-native-libraries.json" (
    builtins.toJSON {
      products = nativeLibraries;
      inherit dependencyPrefixes;
      compiler = {
        path = toString toolchain.gnat;
        version = toolchain.gnat.version;
      };
      system = stdenv.hostPlatform.system;
    }
  );
  producer =
    runCommand "alire-native-libraries"
      {
        nativeBuildInputs = [
          python
          binutils
        ];
      }
      ''
        ${python}/bin/python3 ${./native-output.py} ${project} ${source} ${spec} "$out" ${lib.getBin stdenv.cc.libc}/bin/ldd
      '';
in
assert lib.assertMsg
  (
    names != [ ]
    && builtins.all (
      n: builtins.match "[A-Za-z_][A-Za-z0-9_-]*" n != null && valid nativeLibraries.${n}
    ) names
  )
  "alire-purifier: nativeLibraries needs installed shared libraries, owning GPR projects, public headers, C exports, and explicit process-lifetime/single-foreign-thread GNAT constructor runtime";
assert lib.assertMsg (
  stdenv.hostPlatform.isLinux && stdenv.buildPlatform == stdenv.hostPlatform
) "alire-purifier: nativeLibraries requires a native Linux build";
{
  validated = true;
  inherit producer;
  projections = purifier.nativeProjections {
    inherit producer runCommand;
    python3 = python;
    system = stdenv.hostPlatform.system;
    libraries = lib.mapAttrs (n: _: "lib/${n}/lib${n}.so") nativeLibraries;
    includeDirectories = [ "include" ];
    targetMetadata = lib.mapAttrs (
      _: p:
      p
      // {
        type = "shared-library";
        nativeModel = "${producer}/native-libraries.json";
        compiler = {
          name = "gnat";
          version = toolchain.gnat.version;
          path = toString toolchain.gnat;
        };
      }
    ) nativeLibraries;
  };
}
