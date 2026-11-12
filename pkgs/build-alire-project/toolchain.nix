{ gnat, gprbuild }:
{
  inherit gnat;
  gprbuild = gprbuild.overrideAttrs (old: {
    postPatch =
      (old.postPatch or "")
      + "\n"
      + ''
        substituteInPlace gpr/src/gpr-version.ads \
          --replace-fail 'Gpr_Version : constant String := "18.0w";' \
                         'Gpr_Version : constant String := "${gprbuild.version}";'
      '';
  });
}
