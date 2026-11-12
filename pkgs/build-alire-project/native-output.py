"""Select unchanged installed GPR libraries and retain their native evidence."""

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


def digest(path, algorithm="sha256"):
    return hashlib.new(algorithm, path.read_bytes()).hexdigest()


def run(*args):
    result = subprocess.run(args, text=True, capture_output=True, check=True)
    if result.stderr:
        raise ValueError("native inspection emitted diagnostics: " + result.stderr)
    return result.stdout


def inside(base, relative):
    result = (base / relative).resolve(strict=True)
    if not result.is_relative_to(base.resolve()) or not result.is_file():
        raise ValueError("selected native file escapes its producer: " + relative)
    return result


def select(project, source, spec, out, ldd):
    model = {k: spec[k] for k in ("compiler", "system")}
    model["products"] = {}
    prefix = project / "native"
    for name, product in spec["products"].items():
        library = inside(prefix, product["library"])
        if library.read_bytes()[:4] != b"\x7fELF":
            raise ValueError("selected installed product is not ELF")
        elf = run("readelf", "--file-header", str(library))
        if "DYN (Shared object file)" not in elf:
            raise ValueError("selected product is not a shared library")
        symbols = run("readelf", "--dyn-syms", "--wide", str(library))
        defined = set()
        for line in symbols.splitlines():
            fields = line.split()
            if len(fields) >= 8 and fields[4] in ("GLOBAL", "WEAK") and fields[5] in ("DEFAULT", "PROTECTED") and fields[6] != "UND":
                defined.add(fields[7].split("@")[0])
        if not set(product["exports"]).issubset(defined):
            raise ValueError("selected native library lacks declared C exports")
        installations = json.loads((prefix / "native-installations.json").read_text())
        owners = [record for record in installations if record["project"] == product["project"]]
        if len(owners) != 1:
            raise ValueError("selected GPR project has no unique native installation")
        matches = []
        for emitted in owners[0]["manifests"]:
            manifest = inside(prefix, "share/gpr/manifests/" + emitted["name"])
            if digest(manifest) != emitted["sha256"]:
                raise ValueError("native GPR installation manifest changed after installation")
            installed = {}
            for line in manifest.read_text().splitlines()[1:]:
                checksum, relative = line.split(" ", 1)
                file = (manifest.parent / relative).resolve(strict=True)
                if not file.is_relative_to(prefix.resolve()) or digest(file, "md5") != checksum:
                    raise ValueError("native GPR installation manifest mismatch")
                installed[str(file)] = checksum
            if str(library) in installed:
                matches.append(manifest)
        if len(matches) != 1:
            raise ValueError("selected library is not installed by its owning GPR project")
        manifest = matches[0]
        # The exchange record is compiler output. Join its exact compiled bytes
        # to the installed selection before accepting the generated binder.
        binders = []
        snapshot = project / "build/native-library-build.json"
        for record in json.loads(snapshot.read_text())["records"]:
            paths = record["libraryPaths"]
            if len(paths) != 1:
                continue
            original = Path(paths[0]).resolve(strict=True)
            if not original.is_relative_to(project / "build") or digest(original) != digest(library):
                continue
            for generated in record["generatedSources"]:
                if not generated.endswith(".ads"):
                    continue
                directory = Path(record["directory"]).resolve(strict=True)
                if not directory.is_relative_to(project / "build"):
                    raise ValueError("native binder directory escapes build")
                binder = inside(directory, generated)
                text = binder.read_text()
                constructors = re.findall(r"pragma Linker_Constructor \((\w+)\);", text)
                destructors = re.findall(r"pragma Linker_Destructor \((\w+)\);", text)
                exports = dict(re.findall(r'pragma Export \(C, (\w+), "([^"]+)"\);', text))
                if len(constructors) != 1 or len(destructors) != 1:
                    continue
                init, term = exports.get(constructors[0]), exports.get(destructors[0])
                if init not in defined or term not in defined:
                    raise ValueError("native binder entry points are absent from library")
                binders.append({"source": str(binder), "sha256": digest(binder), "init": init, "term": term,
                                "nativeExchangeSections": str(snapshot), "compiledLibrary": str(original)})
        if len(binders) != 1:
            raise ValueError("selection needs one native automatic elaboration/finalization binder")
        origins = []
        ldd_output = run(ldd, str(library))
        if "not found" in ldd_output:
            raise ValueError("native runtime closure is incomplete")
        for line in ldd_output.splitlines():
            match = re.search(r"(?:=> )?(/\S+)\s+\(", line)
            if match:
                dependency = Path(match[1]).resolve(strict=True)
                if not str(dependency).startswith("/nix/store/"):
                    raise ValueError("native dependency is outside the locked store closure")
                role = "host-support"
                if dependency.name.startswith(("libgnat", "libgnarl")):
                    role = "gnat-runtime"
                elif any(dependency.is_relative_to(Path(p)) for p in spec["dependencyPrefixes"]):
                    role = "locked-dependency"
                origins.append({"path": str(dependency), "sha256": digest(dependency), "role": role})
        target = out / "lib" / name / ("lib" + name + ".so")
        target.parent.mkdir(parents=True)
        shutil.copyfile(library, target)
        headers = []
        for relative in product["headers"]:
            header = inside(source, relative)
            destination = out / "include" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and destination.read_bytes() != header.read_bytes():
                raise ValueError("conflicting public headers")
            shutil.copyfile(header, destination)
            headers.append({"path": relative, "source": str(header), "sha256": digest(header)})
        model["products"][name] = {**product, "installedLibrary": str(library), "sha256": digest(library),
                                  "installationManifest": str(manifest),
                                  "installationInvocation": str(prefix / "native-installations.json"), "binder": binders[0],
                                  "headersProof": headers, "isolatedLoaderOrigins": origins, "elfHeader": elf}
    (out / "native-libraries.json").write_text(json.dumps(model, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    try:
        project, source, spec, out, ldd = sys.argv[1:]
        select(Path(project), Path(source), json.loads(Path(spec).read_text()), Path(out), ldd)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit("alire-purifier: nativeLibraries: " + str(error))
