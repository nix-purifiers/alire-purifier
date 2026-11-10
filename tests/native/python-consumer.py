import ctypes
import hashlib
import json
from pathlib import Path
import sys

path = Path(sys.argv[1]).resolve(strict=True)
if sys.argv[2] == "ctypes":
    from purifier_native import load
    library = load("answer")
    library.purifier_answer.argtypes = [ctypes.c_int]
    library.purifier_answer.restype = ctypes.c_int
    values = [library.purifier_answer(0), library.purifier_answer(1)]
    class Info(ctypes.Structure):
        _fields_ = [("name", ctypes.c_char_p), ("base", ctypes.c_void_p),
                    ("symbol", ctypes.c_char_p), ("address", ctypes.c_void_p)]
    info = Info()
    host = ctypes.CDLL(None)
    assert host.dladdr(ctypes.cast(library.purifier_answer, ctypes.c_void_p), ctypes.byref(info))
    origin = Path(info.name.decode()).resolve(strict=True)
else:
    from cffi import FFI
    ffi = FFI()
    ffi.cdef("int purifier_answer(int); typedef struct { const char *name; void *base; const char *symbol; void *address; } Info; int dladdr(void *, Info *);")
    library = ffi.dlopen(str(path))
    values = [library.purifier_answer(0), library.purifier_answer(1)]
    info = ffi.new("Info *")
    assert ffi.dlopen(None).dladdr(ffi.cast("void *", library.purifier_answer), info)
    origin = Path(ffi.string(info.name).decode()).resolve(strict=True)
assert values == [42, 43] and origin == path
model = json.loads((path.parents[2] / "native-libraries.json").read_text())
product = model["products"]["answer"]
assert hashlib.sha256(path.read_bytes()).hexdigest() == product["sha256"]
loaded = {line.split()[-1] for line in Path("/proc/self/maps").read_text().splitlines() if "/nix/store/" in line}
Path(sys.argv[3]).write_text("\n".join(sorted(loaded)) + "\n")
for dependency in product["isolatedLoaderOrigins"]:
    actual = Path(dependency["path"])
    assert hashlib.sha256(actual.read_bytes()).hexdigest() == dependency["sha256"]
    if dependency["role"] != "host-support":
        assert str(actual) in loaded, actual
assert any("libgnat" in item for item in loaded)
assert any("alire-libhello" in item for item in loaded)
runtime = [{"path": name, "sha256": hashlib.sha256(Path(name).read_bytes()).hexdigest()}
           for name in sorted(loaded) if ".so" in Path(name).name]
print(json.dumps({"values": values, "origin": str(origin), "actualLoadedLibraries": runtime,
                  "isolatedLoaderOrigins": product["isolatedLoaderOrigins"]}), flush=True)
# Keep both handles alive through natural process exit, as declared by the API.
