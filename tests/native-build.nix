{
  projectRoot,
  src ? null,
  product ? import ./native/product.nix,
}:
let
  f = builtins.getFlake projectRoot;
  pkgs = import f.inputs.nixpkgs {
    system = builtins.currentSystem;
    overlays = [ f.overlays.default ];
  };
in
pkgs.alire-purifier.buildAlireProject {
  src = if src == null then ../examples/native-projection else /. + src;
  nativeLibraries.answer = product;
}
