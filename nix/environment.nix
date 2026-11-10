{
  lib,
  runCommand,
  fetchgit,
  fetchurl,
  python,
  buildTools,
  providerTools,
  writeText,
  purifier,
  alire,
  toolchain,
  nativePath,
  programs,
  sdkVersion,
  ...
}@scope:
{
  lock,
  fetchers ? { },
  libraryOverrides ? { },
}:
let
  data = lock.data;
  definitions = builtins.listToAttrs (
    map (n: {
      name = n.name;
      value = n;
    }) data.nodes
  );
  sourceTree =
    entry:
    purifier.tree (
      {
        name = "alire-fixed-source";
        entries = builtins.filter (e: e.path == entry) lock.entries;
        inherit
          runCommand
          fetchgit
          fetchurl
          writeText
          ;
        python3 = python;
      }
      // fetchers
    );
  dependencyNames =
    node:
    map (item: item.key) (
      builtins.genericClosure {
        startSet = map (name: { key = name; }) node.dependencies;
        operator = item: map (name: { key = name; }) definitions.${item.key}.dependencies;
      }
    );
  artifactFor = name: {
    prefix = "${packages.${name}}";
    prepared = "${packages.${name}.prepared}";
    projects = definitions.${name}.projects;
  };
  sourceNames = names: builtins.filter (n: definitions.${n}.kind == "source") names;
  packages = lib.mapAttrs (
    name: node:
    if node.kind == "sdk" then
      toolchain.${node.release.origin.sdk}
    else
      let
        source = sourceTree node.entry;
        deps = dependencyNames node;
        context = writeText "alire-build-context.json" (
          builtins.toJSON {
            inherit programs nativePath;
            native = data.native;
            names = deps;
            compilerIndex = ../native/compiler-index;
            artifacts = builtins.listToAttrs (
              map (name: {
                inherit name;
                value = artifactFor name;
              }) (sourceNames deps)
            );
            externals = data.externals;
          }
        );
      in
      (runCommand "alire-${name}-${node.version}"
        {
          outputs = [
            "out"
            "prepared"
          ];
          nativeBuildInputs = [
            alire
            toolchain.gnat
            toolchain.gprbuild
            python
          ];
        }
        ''
          cp -pr ${source}/${node.entry}/${node.subdir}/. source
          chmod -R u+w source
          cd source
          cp ${writeText "alire.toml" node.manifest} alire.toml
          mkdir -p "$out/share/gpr" "$prepared"
          ${python}/bin/python3 ${buildTools}/build-context.py ${context} "$PWD" "$TMPDIR/context" "$out" ${lib.escapeShellArgs node.projects}
          cp -pr . "$prepared/"
          # GPR's incremental-build exchange records contain wall-clock object
          # timestamps. Consumers use the installed, externally built GPR project;
          # these disposable records are not part of its source/configuration view.
          find "$prepared" -type f \( -name '*.cswi' -o -name '*.lexch' -o -name '*.bexch' \) -delete
        ''
      ).overrideAttrs
        (old: libraryOverrides.${name} or { })
  ) definitions;
  sourceArtifacts = builtins.listToAttrs (
    map (name: {
      inherit name;
      value = artifactFor name;
    }) (sourceNames (builtins.attrNames definitions))
  );
  provided = runCommand "alire-provided-catalog" { } ''
    mkdir -p "$out"
    ${python}/bin/python3 ${providerTools}/make-provider.py ${
      writeText "alire-native-provider.json" (
        builtins.toJSON {
          native = data.native;
          artifacts = sourceArtifacts;
          inherit programs;
          compilerIndex = ../native/compiler-index;
        }
      )
    } "$out"
  '';
  manifest = writeText "alire-environment.json" (
    builtins.toJSON {
      inherit provided programs nativePath;
      artifacts = sourceArtifacts;
      sdk = sdkVersion;
    }
  );
  output = runCommand "alire-locked-environment" { } ''
    mkdir -p "$out"
    ln -s ${manifest} "$out/manifest.json"
  '';
in
assert lib.assertMsg (builtins.all (
  n: n.kind != "sdk" || n.version == toolchain.${n.release.origin.sdk}.version
) data.nodes) "Alire compiler release differs from the Nix SDK; update the lock";
{
  inherit
    output
    packages
    provided
    sourceArtifacts
    ;
}
