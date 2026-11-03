{ lib }:
{
  src,
  lockFile ? src + "/alire-purifier.lock.json",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  nodes = data.nodes or [ ];
  relative =
    s:
    builtins.isString s
    && s != ""
    && !(lib.hasPrefix "/" s)
    && !(builtins.elem ".." (lib.splitString "/" s));
  safe = s: builtins.isString s && builtins.match "[a-z][a-z0-9_]*" s != null;
  commit = s: builtins.isString s && builtins.match "[a-f0-9]{40}" s != null;
  shape =
    (data.version or null) == 1
    && (data.purifier or null) == "alire"
    && builtins.isString (data.sdk or null)
    && builtins.isAttrs (data.native or null)
    && builtins.isList nodes
    && builtins.all (
      n:
      builtins.isAttrs n
      && safe (n.name or null)
      && builtins.isString (n.version or null)
      && builtins.isAttrs (n.release or null)
      && (n.release.name or null) == n.name
      && (n.release.version or null) == n.version
      && builtins.isList (n.dependencies or null)
      && builtins.all safe n.dependencies
      && builtins.isList (n.aliases or null)
      && builtins.all safe n.aliases
      && (
        if (n.kind or null) == "sdk" then
          builtins.elem (n.release.origin.sdk or null) [
            "gnat"
            "gprbuild"
          ]
        else
          (n.kind or null) == "source"
          && relative (n.entry or null)
          && relative (n.subdir or null)
          && builtins.isString (n.manifest or null)
          && builtins.isList (n.projects or null)
          && builtins.all relative n.projects
      )
    ) nodes
    && builtins.isList entries
    && builtins.all (
      e:
      builtins.isAttrs e
      && relative (e.path or null)
      && builtins.isString (e.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" e.hash != null
      && builtins.isAttrs (e.git or null)
      && builtins.isString (e.git.url or null)
      && commit (e.git.rev or null)
      && (e.git.submodules or null) == false
      && (e.git.leaveDotGit or null) == false
      && (e.git.commitObject or null) == null
    ) entries
    && builtins.isAttrs (data.externals or null)
    && builtins.isList (data.extraInputs or null)
    && builtins.all relative data.extraInputs
    && builtins.isAttrs (data.inputs or null);
  names = map (n: n.name) nodes;
  states = data.native.solution.state or [ ];
  aliases = builtins.listToAttrs (
    map (s: {
      name = s.crate;
      value = s.release.name;
    }) states
  );
  nativeValid =
    builtins.isList states
    && builtins.all (
      s:
      builtins.isAttrs s
      && safe (s.crate or null)
      && (s.fulfilment or null) == "solved"
      && builtins.isAttrs (s.release or null)
      && builtins.elem (s.release.name or null) names
    ) states
    && builtins.length states == builtins.length (lib.unique (map (s: s.crate) states))
    && builtins.all (
      n:
      n.aliases == map (s: s.crate) (builtins.filter (s: s.release.name == n.name) states)
      && n.aliases != [ ]
      && builtins.all (s: s.release == n.release) (builtins.filter (s: s.release.name == n.name) states)
      && (
        n.kind == "sdk"
        || (
          builtins.fromTOML n.manifest == builtins.removeAttrs n.release [ "origin" ]
          && n.projects == (n.release.project-files or [ (n.name + ".gpr") ])
          && n.subdir == (n.release.origin.subdir or ".")
          &&
            n.dependencies == builtins.sort builtins.lessThan (
              lib.unique (
                map (name: aliases.${name}) (lib.concatMap builtins.attrNames (n.release.depends-on or [ ]))
              )
            )
        )
      )
    ) nodes;
  valid =
    shape
    && nativeValid
    && builtins.length names == builtins.length (lib.unique names)
    && builtins.all (n: builtins.all (name: builtins.elem name names) n.dependencies) nodes
    && !(lib.toposort (a: b: builtins.elem a.name b.dependencies) nodes ? cycle)
    && builtins.all (
      n:
      n.kind == "sdk"
      || builtins.any (
        e:
        e.path == n.entry
        && e.git.url == lib.removePrefix "git+" n.release.origin.url
        && e.git.rev == n.release.origin.commit
      ) entries
    ) nodes
    &&
      builtins.attrNames data.inputs
      == builtins.sort builtins.lessThan (lib.unique ([ "alire.toml" ] ++ data.extraInputs))
    && builtins.all (
      name:
      relative name
      && builtins.pathExists (src + "/${name}")
      && builtins.hashFile "sha256" (src + "/${name}") == (data.inputs.${name}.sha256 or null)
    ) (builtins.attrNames data.inputs);
in
{
  purifier = "alire";
  inherit data entries;
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
  problems = lib.optional (!valid) "Invalid or stale Alire lock; update the lock";
}
