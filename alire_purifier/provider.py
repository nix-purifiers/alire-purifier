"""Represent compiled Nix artifacts through Alire's native external releases."""

import copy
from pathlib import Path

import tomli_w


def provide(native, artifacts, programs, names=None):
    result = copy.deepcopy(native)
    if names is not None:
        result["solution"]["state"] = [
            s for s in result["solution"]["state"] if s["release"]["name"] in names
        ]
    for state in result["solution"]["state"]:
        release = state["release"]
        origin = release["origin"]
        if "sdk" in origin:
            release["origin"] = {"url": "external:path " + programs[origin["sdk"]]}
            continue
        artifact = artifacts[release["name"]]
        prefix = artifact["prefix"]
        source = artifact["prepared"]
        release["origin"] = {"url": "external:path " + prefix}
        release["notes"] = "Provided by the locked Nix environment"
        release.pop("actions", None)
        config = release.setdefault("configuration", {})
        config.update(generate_ada=False, generate_c=False, generate_gpr=False)
        env = release.setdefault("environment", {})
        for setting in env.values():
            for key, value in setting.items():
                if isinstance(value, str):
                    setting[key] = value.replace("${CRATE_ROOT}", source)
        env["GPR_PROJECT_PATH"] = {"prepend": prefix + "/share/gpr"}
        # The native release keeps its package names and dependency constraints.
        release["project-files"] = artifact["projects"]
    return result


def catalog(directory, native, compiler_index):
    import shutil

    directory = Path(directory)
    shutil.copytree(compiler_index, directory, dirs_exist_ok=True)
    for item in [directory, *directory.rglob("*")]:
        if not item.is_symlink():
            item.chmod(item.stat().st_mode | 0o200)
    seen = set()
    for state in native["solution"]["state"]:
        release = state["release"]
        if release["name"] in ("gnat_external", "gprbuild"):
            continue
        identity = (release["name"], release["version"])
        if identity in seen:
            continue
        seen.add(identity)
        file = (
            directory
            / release["name"][:2]
            / release["name"]
            / (release["name"] + "-" + release["version"] + ".toml")
        )
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(tomli_w.dumps(release))
