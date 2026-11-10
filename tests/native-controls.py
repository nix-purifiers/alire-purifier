"""Actual native compiler controls, including a genuinely compiled replacement."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
native_python = subprocess.check_output([
    "nix", "eval", "--impure", "--raw", "--file", str(repo / "tests/native-python.nix"),
], text=True).strip()
product = {
    "project": "purifierprobe.gpr", "library": "lib/purifierprobe/libpurifier_probe.so",
    "headers": ["purifier_probe.h"], "exports": ["purifier_answer"],
    "runtime": {"kind": "gnat", "initialization": "linker-constructor",
                "lifecycle": "process-lifetime", "threading": "single-foreign-thread"},
}
receipts = {}
with tempfile.TemporaryDirectory(prefix="alire native controls ") as temporary:
    root = Path(temporary)
    def build(name, *, replacement=None, change=None, selected=None, expected=None, alias=False):
        source = root / name
        shutil.copytree(repo / "examples/native-projection", source)
        if alias:
            shutil.copyfile(source / "purifierprobe.gpr", source / "entry.gpr")
        if replacement:
            file = source / "src/probe.adb"
            file.write_text(file.read_text().replace("Value := 42", "Value := 99"))
        if change:
            file, old, new = change
            p = source / file
            assert old in p.read_text()
            p.write_text(p.read_text().replace(old, new))
        spec = root / (name + ".json")
        spec.write_text(json.dumps(selected or product))
        command = ["nix", "build", "--impure", "--no-link", "--print-out-paths", "--file",
                   str(repo / "tests/native-control-build.nix"), "--argstr", "projectRoot", str(repo),
                   "--argstr", "src", str(source), "--argstr", "specFile", str(spec)]
        result = subprocess.run(command, text=True, capture_output=True, timeout=600)
        receipts[name] = {"command": command, "exit": result.returncode,
                          "stdout": result.stdout, "stderr": result.stderr}
        if expected:
            assert result.returncode and expected in result.stderr, receipts[name]
            return None
        assert result.returncode == 0, receipts[name]
        return Path(result.stdout.strip())

    original = build("original")
    aliased = copy.deepcopy(product); aliased["project"] = "entry.gpr"
    alias = build("owning-project-filename-alias", selected=aliased, alias=True)
    alias_model = json.loads((alias / "native-libraries.json").read_text())["products"]["answer"]
    assert alias_model["project"] == "entry.gpr"
    assert Path(alias_model["installationManifest"]).name == "entry"
    replacement = build("replacement", replacement=True)
    old = original / "lib/answer/libanswer.so"
    new = replacement / "lib/answer/libanswer.so"
    assert hashlib.sha256(old.read_bytes()).digest() != hashlib.sha256(new.read_bytes()).digest()
    code = "import ctypes,sys; d=ctypes.CDLL(sys.argv[1]); d.purifier_answer.argtypes=[ctypes.c_int]; d.purifier_answer.restype=ctypes.c_int; assert [d.purifier_answer(0),d.purifier_answer(1)] == [99,100]"
    run = subprocess.run([native_python, "-c", code, str(new)], capture_output=True, text=True)
    assert run.returncode == 0, (run.returncode, run.stdout, run.stderr)
    assert run.stdout.splitlines() == ["Hello, world!", "purifier finalized"] and not run.stderr
    receipts["replacement-execution"] = {"stdout": run.stdout, "stderr": run.stderr, "values": [99, 100],
        "oldSha256": hashlib.sha256(old.read_bytes()).hexdigest(), "replacementSha256": hashlib.sha256(new.read_bytes()).hexdigest(),
        "byteGuardRejectedReplacement": True}
    build("missing-export", change=("src/probe.ads", '"purifier_answer"', '"purifier_other"'),
          expected="lacks declared C exports")
    build("manual-init", change=("purifierprobe.gpr", 'for Library_Auto_Init use "true";', 'for Library_Auto_Init use "false";'),
          expected="automatic elaboration/finalization binder")
    invalid = copy.deepcopy(product); invalid["headers"] = ["missing.h"]
    build("missing-header", selected=invalid, expected="nativeLibraries:")
    invalid = copy.deepcopy(product); invalid["library"] = "../outside.so"
    build("escaping-selector", selected=invalid, expected="nativeLibraries needs")
    invalid = copy.deepcopy(product); invalid["runtime"]["threading"] = "concurrent"
    build("unsupported-runtime", selected=invalid, expected="nativeLibraries needs")
    build("static-product", change=("purifierprobe.gpr", '"dynamic"', '"static"'),
          expected="nativeLibraries:")
    output = os.environ.get("ALIRE_NATIVE_CONTROL_REPORT")
    if output:
        Path(output).write_text(json.dumps(receipts, indent=2) + "\n")
print("Genuine compiled 99/100 replacement and six native/evaluation controls passed")
