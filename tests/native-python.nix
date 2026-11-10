let
  f = builtins.getFlake (toString ../.);
  pkgs = import f.inputs.nixpkgs {
    system = builtins.currentSystem;
    overlays = [ f.overlays.default ];
  };
in
pkgs.alire-purifier.python.interpreter
