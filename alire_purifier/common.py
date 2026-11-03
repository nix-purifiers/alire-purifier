import copy
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

import tomli_w


def command(args, **kwargs):
    result = subprocess.run(args, text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise ValueError(result.stdout + result.stderr)
    return result.stdout


def write(path, content):
    path = Path(path)
    content = content.encode() if isinstance(content, str) else content
    if path.is_file() and path.read_bytes() == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def tools():
    return json.loads(Path(os.environ["ALIRE_PURIFIER_PROGRAMS"]).read_text())


def native_environment(state):
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("ALIRE_", "GPR_", "GNAT_"))
        and k
        not in (
            "ADAFLAGS",
            "ADA_PROJECT_PATH",
            "ADA_INCLUDE_PATH",
            "ADA_OBJECTS_PATH",
            "LIBRARY_TYPE",
        )
    }
    for name in ("config", "cache", "data", "run"):
        (state / name).mkdir(parents=True, exist_ok=True)
    env.update(
        XDG_CONFIG_HOME=str(state / "config"),
        XDG_CACHE_HOME=str(state / "cache"),
        XDG_DATA_HOME=str(state / "data"),
        XDG_RUNTIME_DIR=str(state / "run"),
    )
    env["PATH"] = os.environ["ALIRE_PURIFIER_NATIVE_PATH"] + os.pathsep + env["PATH"]
    return env


def alr(root, settings, env, *args):
    return command(
        [tools()["alr"], "-n", "--no-color", "--no-tty", "-s", str(settings), *args],
        cwd=root,
        env=env,
    )


def setup(root, state, env, indexes, capture=False):
    settings = state / "settings"
    settings.mkdir(parents=True, exist_ok=True)
    data = {
        "index": {"auto_community": False, "auto_update": 0},
        "distribution": {"disable_detection": True},
        "toolchain": {"assistant": False},
        "dependencies": {"shared": capture},
        "update": {"manually_only": not capture},
    }
    write(settings / "settings.toml", tomli_w.dumps(data))
    registry = settings / "indexes"
    if registry.exists():
        import shutil

        shutil.rmtree(registry)
    for name, url in indexes:
        alr(root, settings, env, "index", "--add", url, "--name", name)
    alr(root, settings, env, "toolchain", "--select", "gnat_external", "gprbuild")
    return settings


def inputs(root, names):
    result = {}
    for name in sorted(set(names)):
        path = root / name
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or not path.is_file()
            or path.is_symlink()
        ):
            raise ValueError("Selection inputs must be regular project files")
        result[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return result


def normalise_native(native):
    result = copy.deepcopy(native)
    programs = tools()
    for state in result["solution"]["state"]:
        if state.get("fulfilment") != "solved" or "release" not in state:
            raise ValueError("Alire must solve every dependency to a release")
        release = state["release"]
        origin = release["origin"]
        url = origin.get("url", "")
        if url.startswith("external:path "):
            provider = {"gnat_external": "gnat", "gprbuild": "gprbuild"}.get(
                release["name"]
            )
            if (
                not provider
                or Path(url.removeprefix("external:path ")).resolve()
                != Path(programs[provider]).resolve()
            ):
                raise ValueError(
                    "External dependencies require an explicit Nix SDK provider"
                )
            release["origin"] = {"sdk": provider}
            release.pop("notes", None)
    return result


def shell_environment(text, base):
    env = dict(base)
    for line in text.splitlines():
        parts = shlex.split(line)
        if not parts:
            continue
        if len(parts) != 2 or parts[0] != "export" or "=" not in parts[1]:
            raise ValueError("Unsupported native Alire environment output")
        name, value = parts[1].split("=", 1)
        env[name] = value
    return env


def load(root, companion):
    data = json.loads(companion.read_text())
    if data.get("version") != 1 or data.get("purifier") != "alire":
        raise ValueError("Unsupported Alire lock")
    if data["sdk"] != os.environ["ALIRE_PURIFIER_SDK_VERSION"]:
        raise ValueError("Alire frontend SDK changed; update the lock")
    if inputs(root, ["alire.toml", *data["extraInputs"]]) != data["inputs"]:
        raise ValueError("Selection inputs changed; update the lock")
    for name, value in data["externals"].items():
        actual = {"set": name in os.environ, "value": os.environ.get(name, "")}
        if actual != value:
            raise ValueError(
                "Dependency build setting changed: " + name + "; update the lock"
            )
    return data
