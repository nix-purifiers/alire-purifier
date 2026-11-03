{
  lib,
  stdenvNoCC,
  makeWrapper,
  python,
  nix,
  gh,
  alire,
  toolchain,
  nativePath,
  programs,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
  nix-prefetch-git,
  git,
  cacert,
  writeText,
}:
let
  registry = writeText "alire-programs.json" (builtins.toJSON programs);
in
stdenvNoCC.mkDerivation {
  pname = "alire-purifier";
  version = "0.1.0";
  src = ../.;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/alire-purifier"
    cp -r alire_purifier nix native "$out/lib/alire-purifier/"
    install -m755 bin/alire-purifier "$out/bin/alire-purifier"
    for file in realize release; do
      substituteInPlace "$out/lib/alire-purifier/nix/$file.nix" --replace-fail '@nixpkgs@' '${nixpkgsSrc}' --replace-fail '@purifier@' '${purifierSrc}'
    done
    for binary in ${toolchain.gnat}/bin/* ${toolchain.gprbuild}/bin/*; do
      ln -sf "$binary" "$out/bin/$(basename "$binary")"
    done
    wrapProgram "$out/bin/alire-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python
          nix
          gh
          git
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default ALIRE_PURIFIER_GH ${gh}/bin/gh \
      --set ALIRE_PURIFIER_PROGRAMS ${registry} \
      --set ALIRE_PURIFIER_NATIVE_PATH ${lib.escapeShellArg nativePath} \
      --set ALIRE_PURIFIER_COMPILER_INDEX "$out/lib/alire-purifier/native/compiler-index" \
      --set ALIRE_PURIFIER_PREFETCH_GIT ${nix-prefetch-git}/bin/nix-prefetch-git \
      --set ALIRE_PURIFIER_SDK_VERSION ${sdkVersion} \
      --set ALIRE_PURIFIER_SDK "$out"
    for program in alr gprbuild gprclean gprinstall gprls gnatls gnatxref; do
      rm -f "$out/bin/$program"
      makeWrapper "$out/bin/alire-purifier" "$out/bin/$program" --add-flags "--native=$program"
    done
  '';
  meta = {
    description = "Native Alire with locked Nix-built Ada dependencies";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "alire-purifier";
  };
}
