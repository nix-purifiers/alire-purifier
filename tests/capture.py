"""Capture selection through the original native Alire resolver."""

import json
import os
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
for fixture in ("minimal", "native-projection"):
    with tempfile.TemporaryDirectory(prefix="alire native capture ") as temporary:
        temp = Path(temporary)
        root = temp / "project"
        shutil.copytree(
            repo / "examples" / fixture,
            root,
            ignore=shutil.ignore_patterns(
                "alire", "config", "obj", "bin", ".alire-purifier"
            ),
        )
        original = json.loads((root / "alire-purifier.lock.json").read_text())
        env = dict(os.environ)
        for name, selection in original["externals"].items():
            if selection["set"]:
                env[name] = selection["value"]
            else:
                env.pop(name, None)
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
        subprocess.run(command, cwd=root, env=env, check=True, timeout=300)
        captured = json.loads(companion.read_text())
        assert captured["entries"] == original["entries"]
        assert {n["name"] for n in captured["nodes"]} == {
            n["name"] for n in original["nodes"]
        }
        assert captured["externals"] == original["externals"]
        before = companion.read_bytes()
        subprocess.run(command, cwd=root, env=env, check=True, timeout=300)
        assert companion.read_bytes() == before
        if fixture == "minimal":
            subprocess.run([sdk / "bin/alr", "run"], cwd=root, env=env, check=True, timeout=120)
        else:
            # Replay the fresh native capture through the actual Nix projection.
            command = ["nix", "build", "--impure", "--no-link", "--print-out-paths", "--expr",
                       '(import ' + str(repo / "tests/native-build.nix") + ' { projectRoot = '
                       + json.dumps(str(repo)) + '; src = ' + json.dumps(str(root)) + '; }).native']
            prefix = Path(subprocess.check_output(command, text=True).strip())
            code = 'import ctypes,sys; d=ctypes.CDLL(sys.argv[1]); d.purifier_answer.argtypes=[ctypes.c_int]; assert [d.purifier_answer(0),d.purifier_answer(1)]==[42,43]'
            result = subprocess.run(["python3", "-c", code, str(prefix / "lib/answer/libanswer.so")], text=True, capture_output=True, check=True)
            assert result.stdout.splitlines() == ["Hello, world!", "purifier finalized"] and not result.stderr
print("Original Alire resolver captures, immutable selections and executable/shared-library replay passed")
