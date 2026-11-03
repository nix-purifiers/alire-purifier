{
  pkgs,
  nixpkgsSrc,
  purifierSrc,
}:
pkgs.lib.makeScope pkgs.newScope (scope: {
  buildTools = pkgs.lib.fileset.toSource {
    root = ../alire_purifier;
    fileset = pkgs.lib.fileset.unions [
      ../alire_purifier/common.py
      ../alire_purifier/provider.py
      ../alire_purifier/build-context.py
    ];
  };
  providerTools = pkgs.lib.fileset.toSource {
    root = ../alire_purifier;
    fileset = pkgs.lib.fileset.unions [
      ../alire_purifier/provider.py
      ../alire_purifier/make-provider.py
    ];
  };
  toolchain = pkgs.callPackage ./toolchain.nix { };
  python = pkgs.python3.withPackages (p: [ p.tomli-w ]);
  nativePath = pkgs.lib.makeBinPath [
    scope.toolchain.gnat
    scope.toolchain.gprbuild
    pkgs.git
    pkgs.curl
    pkgs.gnutar
    pkgs.gzip
    pkgs.unzip
    pkgs.coreutils
    pkgs.findutils
  ];
  programs = {
    alr = pkgs.lib.getExe pkgs.alire;
    gnat = pkgs.lib.getExe' scope.toolchain.gnat "gnat";
    gprbuild = pkgs.lib.getExe' scope.toolchain.gprbuild "gprbuild";
    gprclean = pkgs.lib.getExe' scope.toolchain.gprbuild "gprclean";
    gprinstall = pkgs.lib.getExe' scope.toolchain.gprbuild "gprinstall";
    gprls = pkgs.lib.getExe' scope.toolchain.gprbuild "gprls";
    gnatls = pkgs.lib.getExe' scope.toolchain.gnat "gnatls";
    gnatxref = pkgs.lib.getExe' scope.toolchain.gnat "gnatxref";
  };
  purifier = import (purifierSrc + "/nix/lib") { inherit (pkgs) lib; };
  sdkVersion = import ./sdk-version.nix {
    inherit nixpkgsSrc;
    inherit (pkgs) alire;
  };
  cli = scope.callPackage ./cli.nix { inherit nixpkgsSrc purifierSrc; };
  buildAlireProject = scope.callPackage ./build-project.nix { };
})
