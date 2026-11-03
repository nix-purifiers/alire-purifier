"""Exercise native Alire/GPR commands with immutable dependencies and mutable roots."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

repo = Path(__file__).resolve().parent.parent
sdk = Path(
    subprocess.check_output(
        ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True
    ).strip()
)


def call(root, *args, env=None, expected=0):
    print("native", root, args, flush=True)
    result = subprocess.run(
        [sdk / "bin" / args[0], *args[1:]],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert result.returncode == expected, (args, result)
    return result


with tempfile.TemporaryDirectory(prefix="alire proof with spaces ") as temporary:
    temp = Path(temporary)
    root = temp / "project"
    shutil.copytree(
        repo / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns(
            "alire", "config", "obj", "bin", ".alire-purifier"
        ),
    )
    poison = temp / "poison"
    poison.mkdir()
    (poison / "settings.toml").write_text("[index]\nauto_community=true\n")
    env = dict(
        os.environ,
        ALIRE_SETTINGS_DIR=str(poison),
        GPR_PROJECT_PATH="/missing/host-projects",
        ADA_INCLUDE_PATH="/missing/ada",
    )
    assert call(root, "alr", "run", env=env).stdout.rstrip().endswith("42")
    source = root / "src/purifierproof.adb"
    original = source.read_text()
    source.write_text(original.replace('"42"', '"43"'))
    assert call(root, "alr", "run", env=env).stdout.rstrip().endswith("43")
    source.write_text(original)
    call(root, "alr", "clean", env=env)
    assert call(root, "alr", "run", env=env).stdout.rstrip().endswith("42")
    # Native GPR inspection locates dependency projects in the installed Nix SDK.
    exports = call(root, "alr", "printenv", env=env).stdout
    assert "/nix/store/" in exports and "GPR_PROJECT_PATH" in exports
    call(root, "gprbuild", "-P", "purifierproof.gpr", env=env)
    profiles = list((root / ".alire-purifier").glob("*/environment-profile"))
    assert len(profiles) == 1
    profile = json.loads(profiles[0].resolve().read_text())
    manifest = json.loads((Path(profile["output"]) / "manifest.json").read_text())
    artifact = manifest["artifacts"]["libhello"]
    assert (Path(artifact["prefix"]) / "share/gpr/libhello.gpr").is_file()
    sources = call(root, "gprls", "-P", "purifierproof.gpr", "-U", "-s", env=env).stdout
    assert artifact["prefix"] + "/include/libhello/libhello.adb" in sources, sources
    alias = root / "alire/cache/dependencies/libhello_1.0.1_external"
    assert alias.is_symlink() and alias.resolve() == Path(artifact["prepared"])
    refs = subprocess.check_output(
        ["nix-store", "-q", "--requisites", str(profiles[0].resolve())], text=True
    )
    assert (
        str(sdk) in refs and artifact["prefix"] in refs and artifact["prepared"] in refs
    )
    assert (
        call(temp, "alr", "-C", str(root), "run", env=env)
        .stdout.rstrip()
        .endswith("42")
    )
    subdir = root / "subdir"
    subdir.mkdir()
    assert call(subdir, "alr", "run", env=env).stdout.rstrip().endswith("42")
    for args in [
        ("update",),
        ("pin",),
        ("index", "--add", "https://invalid.example"),
        ("settings", "--set", "dependencies.shared", "true"),
    ]:
        call(root, "alr", *args, env=env, expected=1)
    changed = dict(env, LIBHELLO_LIBRARY_TYPE="static")
    assert (
        "build setting changed"
        in call(root, "alr", "run", env=changed, expected=1).stderr
    )
    manifest_file = root / "alire.toml"
    before = manifest_file.read_text()
    manifest_file.write_text(before + "\n# stale selection input\n")
    assert (
        "Selection inputs changed"
        in call(root, "alr", "run", env=env, expected=1).stderr
    )
    manifest_file.write_text(before)
    companion = temp / "external.json"
    (root / "alire-purifier.lock.json").rename(companion)
    external = dict(
        env, ALIRE_PURIFIER_PROJECT=str(root), ALIRE_PURIFIER_LOCK=str(companion)
    )
    assert call(subdir, "alr", "run", env=external).stdout.rstrip().endswith("42")
    archive = Path(
        call(root, "alire-purifier", "bundle", "--lock", str(companion)).stdout.strip()
    )
    fake_gh = temp / "fake-gh"
    fake_gh.write_text(
        "#!/usr/bin/env python3\nimport pathlib,sys\n"
        "assert sys.argv[1:4]==['release','upload','v0.1.0']\n"
        "pathlib.Path(__file__).with_suffix('.uploaded').write_bytes(pathlib.Path(sys.argv[4]).read_bytes())\n"
    )
    fake_gh.chmod(0o755)
    call(
        root,
        "alire-purifier",
        "publish",
        "--lock",
        str(companion),
        "--tag",
        "v0.1.0",
        env=dict(os.environ, ALIRE_PURIFIER_GH=str(fake_gh)),
    )
    assert fake_gh.with_suffix(".uploaded").read_bytes() == archive.read_bytes()
    consumer = temp / "consumer"
    consumer.mkdir()
    with tarfile.open(archive) as tar:
        tar.extractall(consumer, filter="data")
    assert (consumer / "project/src/purifierproof.adb").read_text() == original
    # Original Alire consumes the native release, using native provided-package metadata.
    settings = profiles[0].parent / "settings"
    native_root = consumer / "project"
    (native_root / "alire").mkdir()
    shutil.copyfile(root / "alire/alire.lock", native_root / "alire/alire.lock")
    native = call(
        native_root,
        "alr",
        "-s",
        str(settings),
        "run",
        env=dict(
            os.environ,
            XDG_RUNTIME_DIR=str(temp),
            PATH=manifest["nativePath"] + os.pathsep + os.environ["PATH"],
        ),
    )
    assert "ordinary impure" in native.stderr and native.stdout.rstrip().endswith(
        "42"
    ), native
    fallback = temp / "fallback"
    fallback.mkdir()
    fake = temp / "fake-native"
    fake.write_text("#!/bin/sh\nprintf native-out\nprintf native-err >&2\nexit 7\n")
    fake.chmod(0o755)
    registry = temp / "programs.json"
    registry.write_text(json.dumps({"alr": str(fake)}))
    direct = dict(
        os.environ,
        PYTHONPATH=str(sdk / "lib/alire-purifier"),
        ALIRE_PURIFIER_PROGRAMS=str(registry),
    )
    result = subprocess.run(
        [
            next(
                str(Path(p) / "bin/python3")
                for p in refs.splitlines()
                if "-python3-" in p and p.endswith("-env")
            ),
            "-m",
            "alire_purifier.cli",
            "--native=alr",
        ],
        cwd=fallback,
        env=direct,
        text=True,
        capture_output=True,
    )
    assert (
        result.returncode == 7
        and result.stdout == "native-out"
        and result.stderr.endswith("native-err")
    ), result
    assert "ordinary impure" in result.stderr

print(
    "Native Alire/GPR, mutable roots, readonly dependencies, private settings, GC and fallback passed"
)
