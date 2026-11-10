import hashlib
import json
from pathlib import Path
import sys

prefix, output = map(Path, sys.argv[1:])
product = json.loads((prefix / "native-libraries.json").read_text())["products"]["answer"]
expected = {item["path"]: item["sha256"] for item in product["isolatedLoaderOrigins"]
            if item["role"] != "host-support"}
assert any("libgnat" in name for name in expected)
assert any("alire-libhello" in name for name in expected)
receipts = {}
for consumer in ("c", "ctypes", "cffi", "java"):
    loaded = {line.split()[-1] for line in (output / (consumer + ".maps")).read_text().splitlines()
              if "/nix/store/" in line}
    for name, checksum in expected.items():
        assert name in loaded, (consumer, name)
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == checksum
    receipts[consumer] = [{"path": name, "sha256": hashlib.sha256(Path(name).read_bytes()).hexdigest()}
                          for name in sorted(loaded) if ".so" in Path(name).name]
(output / "actual-process-origins.json").write_text(json.dumps(receipts, indent=2) + "\n")
