"""Rebuild every output of the actual compiled Alire dependencies."""

import json
from pathlib import Path
import subprocess

repo = Path(__file__).resolve().parent.parent
system = subprocess.check_output(
    ["nix", "eval", "--impure", "--raw", "--expr", "builtins.currentSystem"], text=True
).strip()
output = subprocess.check_output(
    [
        "nix",
        "build",
        "--no-link",
        "--print-out-paths",
        str(repo) + "#checks." + system + ".environment",
    ],
    text=True,
).strip()
manifest = json.loads((Path(output) / "manifest.json").read_text())
assert set(manifest["artifacts"]) == {"libhello"}
for artifact in manifest["artifacts"].values():
    drv = subprocess.check_output(
        ["nix-store", "-q", "--deriver", artifact["prefix"]], text=True
    ).strip()
    subprocess.run(["nix-store", "--realise", drv, "--check"], check=True)
print("Installed and prepared native Alire dependencies rebuilt identically")
