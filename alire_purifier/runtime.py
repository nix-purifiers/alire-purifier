import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess

from .common import alr, load, native_environment, setup, shell_environment, write


def prepare(root, companion):
    data = load(root, companion)
    generation = hashlib.sha256(
        companion.read_bytes() + os.environ["ALIRE_PURIFIER_SDK"].encode()
    ).hexdigest()[:20]
    state = root / ".alire-purifier" / generation
    state.mkdir(parents=True, exist_ok=True)
    expression = (
        "import "
        + json.dumps(
            os.environ["ALIRE_PURIFIER_SDK"] + "/lib/alire-purifier/pkgs/build-alire-project/realize.nix"
        )
        + " {root="
        + json.dumps(str(root))
        + ";lockFile="
        + json.dumps(str(companion))
        + ";sdk="
        + json.dumps(os.environ["ALIRE_PURIFIER_SDK"])
        + ";}"
    )
    result = subprocess.run(
        [
            "nix",
            "build",
            "--impure",
            "--expr",
            expression,
            "--out-link",
            str(state / "environment-profile"),
            "--print-out-paths",
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError(result.stdout + result.stderr)
    profile = json.loads(Path(result.stdout.strip()).read_text())
    manifest = json.loads((Path(profile["output"]) / "manifest.json").read_text())
    if manifest["sdk"] != data["sdk"]:
        raise ValueError("Prepared Alire SDK differs from the lock")
    base = native_environment(state)
    for name, value in data["externals"].items():
        if value["set"]:
            base[name] = value["value"]
        else:
            base.pop(name, None)
    with (state / "initialization.lock").open("a") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        ready = state / "ready"
        if not ready.exists():
            settings = setup(
                root,
                state,
                base,
                [("locked", str(Path(manifest["provided"]) / "index"))],
            )
            write(ready, "ready\n")
        else:
            settings = state / "settings"
        write(
            root / "alire/alire.lock",
            (Path(manifest["provided"]) / "alire.lock").read_bytes(),
        )
        exported = shell_environment(alr(root, settings, base, "printenv"), base)
        for name, artifact in manifest["artifacts"].items():
            key = name.upper() + "_ALIRE_PREFIX"
            if key not in exported:
                raise ValueError(
                    "Native Alire did not export the dependency prefix: " + name
                )
            alias = Path(exported[key])
            if not alias.is_relative_to(root / "alire/cache/dependencies"):
                raise ValueError(
                    "Unexpected dependency prefix outside the private project cache"
                )
            alias.parent.mkdir(parents=True, exist_ok=True)
            target = Path(artifact["prepared"])
            if alias.is_symlink() and alias.resolve() == target:
                continue
            if alias.is_symlink() and str(alias.resolve()).startswith("/nix/store/"):
                alias.unlink()
            if alias.is_dir() and not any(alias.iterdir()):
                alias.rmdir()
            if alias.exists() or alias.is_symlink():
                raise ValueError(
                    "Remove the old dependency cache before using the locked Nix environment: "
                    + str(alias)
                )
            try:
                alias.symlink_to(target, target_is_directory=True)
            except FileExistsError:
                if not alias.is_symlink() or alias.resolve() != target:
                    raise
    env = dict(
        base,
        ALIRE_PURIFIER_ACTIVE="1",
        ALIRE_PURIFIER_ACTIVE_ROOT=str(root),
        ALIRE_PURIFIER_ACTIVE_LOCK=str(companion),
    )
    env["PATH"] = (
        str(Path(os.environ["ALIRE_PURIFIER_SDK"]) / "bin") + os.pathsep + env["PATH"]
    )
    return settings, env, exported
