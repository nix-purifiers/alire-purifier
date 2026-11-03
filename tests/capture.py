"""Capture selection through the original native Alire resolver."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
sdk = Path(
    subprocess.check_output(
        ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True
    ).strip()
)
with tempfile.TemporaryDirectory(prefix="alire native capture ") as temporary:
    temp = Path(temporary)
    root = temp / "project"
    shutil.copytree(
        repo / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns(
            "alire", "config", "obj", "bin", ".alire-purifier"
        ),
    )
    original = json.loads((root / "alire-purifier.lock.json").read_text())
    index = temp / "index"
    index.mkdir()
    (index / "index.toml").write_text('version = "1.4.0"\n')
    for node in original["nodes"]:
        if node["kind"] != "source":
            continue
        file = (
            index
            / node["name"][:2]
            / node["name"]
            / (node["name"] + "-" + node["version"] + ".toml")
        )
        file.parent.mkdir(parents=True, exist_ok=True)
        origin = node["release"]["origin"]
        file.write_text(
            node["manifest"]
            + "\n[origin]\nurl = "
            + json.dumps(origin["url"])
            + "\ncommit = "
            + json.dumps(origin["commit"])
            + "\n"
        )
    companion = root / "alire-purifier.lock.json"
    companion.unlink()
    command = [sdk / "bin/alire-purifier", "lock", "--index", str(index)]
    subprocess.run(command, cwd=root, check=True, timeout=300)
    captured = json.loads(companion.read_text())
    assert captured["entries"] == original["entries"]
    assert {n["name"] for n in captured["nodes"]} == {
        n["name"] for n in original["nodes"]
    }
    assert captured["externals"] == original["externals"]
    before = companion.read_bytes()
    subprocess.run(command, cwd=root, check=True, timeout=300)
    assert companion.read_bytes() == before
    subprocess.run([sdk / "bin/alr", "run"], cwd=root, check=True, timeout=120)
print("Original Alire resolver capture, immutable selection and native build passed")
