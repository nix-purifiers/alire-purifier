"""Create a native, offline build context for one source package."""

import json
from pathlib import Path
import os
import sys

import tomli_w

from common import alr, command, native_environment, setup, shell_environment, write
from provider import provide, catalog

manifest_file, root, context, *installation = sys.argv[1:]
manifest = json.loads(Path(manifest_file).read_text())
root = Path(root).resolve()
context = Path(context).resolve()
programs = manifest["programs"]
os.environ["ALIRE_PURIFIER_PROGRAMS"] = str(Path(manifest_file).resolve())
# Native helpers expect a program registry; keep it separate from the build data.
registry = context / "programs.json"
write(registry, json.dumps(programs))
os.environ["ALIRE_PURIFIER_PROGRAMS"] = str(registry)
os.environ["ALIRE_PURIFIER_NATIVE_PATH"] = manifest["nativePath"]
provided = provide(
    manifest["native"], manifest["artifacts"], programs, manifest["names"]
)
index = context / "index"
catalog(index, provided, manifest["compilerIndex"])
env = native_environment(context)
for name, value in manifest["externals"].items():
    if value["set"]:
        env[name] = value["value"]
    else:
        env.pop(name, None)
settings = setup(root, context, env, [("locked", str(index))])
write(root / "alire/alire.lock", tomli_w.dumps(provided))
exports = shell_environment(alr(root, settings, env, "printenv"), env)
for name, artifact in manifest["artifacts"].items():
    key = name.upper() + "_ALIRE_PREFIX"
    if key not in exports:
        continue
    alias = Path(exports[key])
    alias.parent.mkdir(parents=True, exist_ok=True)
    if not alias.exists():
        alias.symlink_to(artifact["prepared"], target_is_directory=True)
# This command does all source generation without invoking the compiler.
alr(root, settings, env, "build", "--release", "--stop-after=generation")
for file in root.rglob("*"):
    if file.is_file() and not file.is_symlink():
        os.utime(file, (1, 1))
alr(root, settings, env, "build", "--release")
if installation:
    prefix, *projects = installation
    # Installation must see the same captured scenario variables and native
    # dependency projects as the build. Re-entering gprinstall with the outer
    # builder environment can select a different library kind.
    install_env = shell_environment(alr(root, settings, env, "printenv"), env)
    for project in projects:
        print(command(
            [programs["gprinstall"], "-P", project, "--prefix=" + prefix, "-p", "-f"],
            cwd=root,
            env=install_env,
        ), end="")
