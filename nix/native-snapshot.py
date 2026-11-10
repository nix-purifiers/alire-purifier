"""Retain semantic native exchange sections, then prune incremental caches."""
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
records = []
for exchange in sorted(root.rglob("*.lexch")):
    sections = {}
    section = None
    for line in exchange.read_text().splitlines():
        if line.startswith("[") and line.endswith("]"):
            section = line
            sections[section] = []
        elif section:
            sections[section].append(line)
    records.append({
        "exchangePath": str(exchange),
        "directory": str(exchange.parent),
        "libraryPaths": sections.get("[LIBRARY PATH]", []),
        "generatedSources": sections.get("[GENERATED SOURCE FILES]", []),
    })
(root / "native-library-build.json").write_text(json.dumps({
    "kind": "retained-native-gpr-exchange-sections",
    "records": records,
}, sort_keys=True, indent=2) + "\n")
# These disposable incremental caches contain wall-clock object/binder times.
# Keep actual generated binder sources, object code, and installed .ali files.
for file in root.rglob("*"):
    if file.is_file() and (file.suffix in (".cswi", ".lexch", ".bexch")
                          or (file.name.startswith("b__") and file.suffix == ".ali")):
        file.unlink()
