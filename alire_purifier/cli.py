import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .capture import capture
from .common import load, tools
from .runtime import prepare


def locate(project=None, companion=None):
    root = Path(
        project or os.environ.get("ALIRE_PURIFIER_PROJECT", Path.cwd())
    ).resolve()
    external = companion or os.environ.get("ALIRE_PURIFIER_LOCK")
    if external:
        return root, Path(external).resolve()
    if project or os.environ.get("ALIRE_PURIFIER_PROJECT"):
        return root, root / "alire-purifier.lock.json"
    for directory in [root, *root.parents]:
        if (directory / "alire-purifier.lock.json").exists():
            return directory, directory / "alire-purifier.lock.json"
    return root, root / "alire-purifier.lock.json"


def guard_alr(args):
    if any(
        a in ("-s", "--settings", "-c", "--config")
        or a.startswith(("--settings=", "--config="))
        or (not a.startswith("--") and a.startswith(("-s", "-c")))
        for a in args
    ):
        raise ValueError("The locked wrapper supplies its native settings directory")
    command = next((a for a in args if not a.startswith("-")), None)
    if command in ("update", "pin", "get", "init"):
        raise ValueError(
            "Change the native manifest and run alire-purifier lock --update for dependency selection"
        )
    if command == "with" and any(
        not a.startswith("-") for a in args[args.index(command) + 1 :]
    ):
        raise ValueError(
            "Change the native manifest and update the lock to add dependencies"
        )
    if command == "index" and any(
        a in ("--add", "--del", "--reset-community")
        or a.startswith(("--add=", "--del="))
        for a in args
    ):
        raise ValueError("The locked wrapper supplies the native index")
    if command == "toolchain" and any(
        a == "--select" or a.startswith("--select=") for a in args
    ):
        raise ValueError("The Nix SDK supplies the locked toolchain")
    if command in ("settings", "config") and any(
        a in ("--set", "--unset") for a in args
    ):
        protected = ("cache.", "dependencies.", "index.", "toolchain.", "update.")
        if any(a.startswith(protected) for a in args):
            raise ValueError(
                "The locked wrapper supplies dependency and toolchain settings"
            )
    if command == "clean" and any("cache" in a for a in args):
        raise ValueError(
            "Clean the root build normally; remove .alire-purifier to reset prepared sessions"
        )


def chdir_args(args):
    """Apply native global -C before finding the lock, preserving child arguments."""
    result = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-C", "--chdir"):
            i += 1
            if i == len(args):
                raise ValueError("The native chdir option requires a directory")
            os.chdir(args[i])
        elif arg.startswith("--chdir="):
            os.chdir(arg.split("=", 1)[1])
        elif arg.startswith("-C") and len(arg) > 2:
            os.chdir(arg[2:])
        elif not arg.startswith("-"):
            return [*result, *args[i:]]
        else:
            result.append(arg)
        i += 1
    return result


def main():
    args = sys.argv[1:]
    if args and args[0].startswith("--native="):
        name = args[0].split("=", 1)[1]
        rest = args[1:]
        if name == "alr":
            rest = chdir_args(rest)
        programs = tools()
        if name != "alr" and os.environ.get("ALIRE_PURIFIER_ACTIVE") == "1":
            os.execv(programs[name], [programs[name], *rest])
        root, companion = locate()
        if not companion.exists():
            if not os.environ.get("ALIRE_PURIFIER_IMPURE"):
                print(
                    "alire-purifier: no lockfile; using ordinary impure " + name,
                    file=sys.stderr,
                )
            env = dict(os.environ, ALIRE_PURIFIER_IMPURE="1")
            os.execve(programs[name], [programs[name], *rest], env)
        if name == "alr":
            guard_alr(rest)
        settings, env, exports = prepare(root, companion)
        if name == "alr":
            os.execve(programs[name], [programs[name], "-s", str(settings), *rest], env)
        env.update(exports)
        os.execve(programs[name], [programs[name], *rest], env)
    parser = argparse.ArgumentParser(
        description="Lock native Alire dependency solutions"
    )
    parser.add_argument(
        "action", choices=["lock", "prefetch", "exec", "bundle", "publish"]
    )
    parser.add_argument("--project", type=Path)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--index", action="append", default=[])
    parser.add_argument("--tag")
    opts, remaining = parser.parse_known_args(args)
    root, companion = locate(opts.project, opts.lock)
    if opts.action == "lock":
        if remaining:
            parser.error("Unexpected arguments: " + " ".join(remaining))
        capture(root, companion, opts.update, opts.input, opts.index)
    elif opts.action in ("prefetch", "exec"):
        settings, env, exports = prepare(root, companion)
        if opts.action == "exec":
            if remaining and remaining[0] == "--":
                remaining = remaining[1:]
            if not remaining:
                parser.error("exec requires a command")
            env.update(
                exports,
                ALIRE_PURIFIER_PROJECT=str(root),
                ALIRE_PURIFIER_LOCK=str(companion),
            )
            os.execvpe(remaining[0], remaining, env)
    else:
        load(root, companion)
        expression = (
            "import "
            + json.dumps(
                os.environ["ALIRE_PURIFIER_SDK"] + "/lib/alire-purifier/nix/release.nix"
            )
            + " {root="
            + json.dumps(str(root))
            + ";lockFile="
            + json.dumps(str(companion))
            + ";}"
        )
        result = subprocess.run(
            [
                "nix",
                "build",
                "--impure",
                "--expr",
                expression,
                "--no-link",
                "--print-out-paths",
            ],
            text=True,
            capture_output=True,
        )
        if result.returncode:
            raise ValueError(result.stdout + result.stderr)
        artifact = Path(result.stdout.strip()) / "alire-source.tar.gz"
        if opts.action == "bundle":
            print(artifact)
        else:
            if not opts.tag:
                parser.error("publish requires --tag")
            subprocess.run(
                [
                    os.environ.get("ALIRE_PURIFIER_GH", "gh"),
                    "release",
                    "upload",
                    opts.tag,
                    str(artifact),
                    "--clobber",
                ],
                cwd=root,
                check=True,
            )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print("alire-purifier: " + str(error), file=sys.stderr)
        raise SystemExit(1)
