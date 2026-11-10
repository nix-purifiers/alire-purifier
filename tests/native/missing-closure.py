import json
from pathlib import Path
import shutil
import subprocess
import sys

prefix, output = map(Path, sys.argv[1:])
original = prefix / "lib/answer/libanswer.so"
needed = subprocess.check_output(["patchelf", "--print-needed", str(original)], text=True).splitlines()
receipts = {}
for label, substring in (("gnat-runtime", "libgnat"), ("locked-dependency", "Libhello")):
    selection = [name for name in needed if substring in name]
    assert len(selection) == 1, needed
    broken = Path(label + ".so")
    shutil.copyfile(original, broken)
    missing = "/missing-alire-native-control/" + selection[0]
    subprocess.run(["patchelf", "--replace-needed", selection[0], missing, str(broken)], check=True)
    code = "import ctypes,sys; ctypes.CDLL(sys.argv[1])"
    result = subprocess.run([sys.executable, "-c", code, str(broken.resolve())], text=True, capture_output=True)
    assert result.returncode and missing in result.stderr
    receipts[label] = {"exit": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
(output / "missing-closure.json").write_text(json.dumps(receipts, indent=2) + "\n")
