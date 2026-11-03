import copy
import json
import os
from pathlib import Path
import re
import tempfile
import tomllib

import tomli_w

from .common import (
    alr,
    command,
    inputs,
    load,
    native_environment,
    normalise_native,
    setup,
    shell_environment,
    write,
)


def capture(root, companion, update=False, extra=(), indexes=()):
    if companion.exists() and not update:
        load(root, companion)
        return
    previous = json.loads(companion.read_text()) if companion.exists() else {}
    extra = list(extra or previous.get("extraInputs", []))
    indexes = list(
        indexes
        or previous.get(
            "indexes", ["git+https://github.com/alire-project/alire-index#stable-1.4.0"]
        )
    )
    root_manifest = tomllib.loads((root / "alire.toml").read_text())

    def check_arch(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key.startswith("case(") and ("arch" in key or "word-size" in key):
                    raise ValueError(
                        "Architecture-dependent selection needs a target-specific integration"
                    )
                check_arch(child)
        elif isinstance(value, list):
            for child in value:
                check_arch(child)

    check_arch(root_manifest)
    native_lock = root / "alire/alire.lock"
    saved = native_lock.read_bytes() if native_lock.exists() else None
    with tempfile.TemporaryDirectory(prefix="alire-capture-") as temporary:
        state = Path(temporary)
        env = native_environment(state)
        # Native GPR externals remain inputs to the Nix dependency builds.
        for key in os.environ:
            if re.fullmatch("[A-Z][A-Z0-9_]*", key) and key not in (
                "GPR_PROJECT_PATH",
                "ADA_PROJECT_PATH",
                "ADA_INCLUDE_PATH",
                "ADA_OBJECTS_PATH",
            ):
                if key.endswith("_LIBRARY_TYPE") or key in ("LIBRARY_TYPE", "ADAFLAGS"):
                    env[key] = os.environ[key]
        catalog = [("community" + str(i), url) for i, url in enumerate(indexes)]
        catalog.append(("sdk", os.environ["ALIRE_PURIFIER_COMPILER_INDEX"]))
        settings = setup(root, state, env, catalog, capture=True)
        if native_lock.exists():
            native_lock.unlink()
        try:
            alr(root, settings, env, "update")
            native = tomllib.loads(native_lock.read_text())
            selected = normalise_native(native)
            alr(root, settings, env, "build", "--stop-after=generation")
            exports = shell_environment(alr(root, settings, env, "printenv"), env)
            aliases = {
                s["crate"]: s["release"]["name"] for s in selected["solution"]["state"]
            }
            unique = {}
            entries = []
            externals = {}
            for state_record in selected["solution"]["state"]:
                release = state_record["release"]
                name = release["name"]
                if name in unique:
                    continue
                if not re.fullmatch("[a-z][a-z0-9_]*", name):
                    raise ValueError("Unsupported native Alire crate name")
                node = {
                    "name": name,
                    "version": release["version"],
                    "release": release,
                    "aliases": [k for k, v in aliases.items() if v == name],
                }
                if "sdk" in release["origin"]:
                    node["kind"] = "sdk"
                    node["dependencies"] = []
                    unique[name] = node
                    continue
                raw = json.loads(
                    alr(
                        root,
                        settings,
                        env,
                        "--format=JSON",
                        "show",
                        name + "=" + release["version"],
                    )
                )
                check_arch(raw)
                origin = release["origin"]
                url = origin.get("url", "")
                node["kind"] = "source"
                native_edges = {
                    key for group in release.get("depends-on", []) for key in group
                }
                node["dependencies"] = sorted({aliases[key] for key in native_edges})
                if not url.startswith("git+") or not re.fullmatch(
                    "[a-f0-9]{40}", origin.get("commit", "")
                ):
                    raise ValueError(
                        "The initial Alire integration supports exact Git source origins"
                    )
                fetched = json.loads(
                    command(
                        [
                            os.environ["ALIRE_PURIFIER_PREFETCH_GIT"],
                            "--url",
                            url[4:],
                            "--rev",
                            origin["commit"],
                        ]
                    )
                )
                entry = "sources/" + name
                entries.append(
                    {
                        "path": entry,
                        "hash": fetched["hash"],
                        "git": {
                            "url": url[4:],
                            "rev": origin["commit"],
                            "submodules": False,
                            "leaveDotGit": False,
                            "commitObject": None,
                        },
                    }
                )
                node["entry"] = entry
                node["subdir"] = origin.get("subdir", ".")
                if (
                    Path(node["subdir"]).is_absolute()
                    or ".." in Path(node["subdir"]).parts
                ):
                    raise ValueError("Unsafe source subdirectory")
                manifest = copy.deepcopy(release)
                manifest.pop("origin")
                node["manifest"] = tomli_w.dumps(manifest)
                node["projects"] = release.get("project-files", [name + ".gpr"])
                prefix = Path(exports[name.upper() + "_ALIRE_PREFIX"])
                hash_inputs = prefix / "alire/build_hash_inputs"
                if hash_inputs.exists():
                    for line in hash_inputs.read_text().splitlines():
                        if line.startswith("external:"):
                            key = line.removeprefix("external:").split("=", 1)[0]
                            externals[key] = {
                                "set": key in os.environ,
                                "value": os.environ.get(key, ""),
                            }
                unique[name] = node
            data = {
                "version": 1,
                "purifier": "alire",
                "sdk": os.environ["ALIRE_PURIFIER_SDK_VERSION"],
                "native": selected,
                "nodes": [unique[k] for k in sorted(unique)],
                "entries": entries,
                "inputs": inputs(root, ["alire.toml", *extra]),
                "extraInputs": extra,
                "indexes": indexes,
                "externals": externals,
            }
            write(companion, json.dumps(data, sort_keys=True, indent=2) + "\n")
        finally:
            if saved is not None:
                write(native_lock, saved)
            elif native_lock.exists():
                native_lock.unlink()
