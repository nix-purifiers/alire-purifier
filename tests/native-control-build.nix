{
  projectRoot,
  src,
  specFile,
}:
(import ./native-build.nix {
  inherit projectRoot src;
  product = builtins.fromJSON (builtins.readFile specFile);
}).native
