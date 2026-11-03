"""Reject stale and inconsistent native solutions without IFD."""

import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary) / "project"
    shutil.copytree(
        repo / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns(
            "alire", "config", "obj", "bin", ".alire-purifier"
        ),
    )
    companion = root / "alire-purifier.lock.json"
    original = json.loads(companion.read_text())

    def inspect():
        expression = f"let f=builtins.getFlake {json.dumps(str(repo))};lock=f.lib.alire-purifier.readLock {{src=/. + {json.dumps(str(root))};}};in {{inherit(lock)problems outputs;}}"
        return json.loads(
            subprocess.check_output(
                [
                    "nix",
                    "eval",
                    "--impure",
                    "--json",
                    "--option",
                    "allow-import-from-derivation",
                    "false",
                    "--expr",
                    expression,
                ],
                text=True,
            )
        )

    assert inspect()["problems"] == []
    assert inspect()["outputs"]["packages"] == ["default", "environment", "project"]
    companion.unlink()
    assert inspect()["problems"]
    for mutation in [
        lambda d: d.update(purifier="other"),
        lambda d: d["entries"][0].update(hash="invalid"),
        lambda d: d["nodes"][-1].update(manifest="name = 'tampered'"),
        lambda d: d["native"]["solution"]["state"][0]["release"].update(
            version="99.0.0"
        ),
        lambda d: d["nodes"][-1].update(subdir="../escape"),
        lambda d: d.update(sdk=None),
    ]:
        data = copy.deepcopy(original)
        mutation(data)
        companion.write_text(json.dumps(data))
        assert inspect()["problems"]
    companion.write_text(json.dumps(original))
    (root / "alire.toml").write_text("# stale\n")
    assert inspect()["problems"]
print("Native Alire lock validation passed without IFD")
