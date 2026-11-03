import json
from pathlib import Path
import sys

import tomli_w

from provider import provide, catalog

input_file, destination = sys.argv[1:]
data = json.loads(Path(input_file).read_text())
output = Path(destination)
native = provide(data["native"], data["artifacts"], data["programs"])
(output / "alire.lock").write_text(tomli_w.dumps(native))
catalog(output / "index", native, data["compilerIndex"])
