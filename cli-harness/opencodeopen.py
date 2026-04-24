#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cli_harness_shim import load_cli_harness_module, reexport_public

_module = load_cli_harness_module("opencodeopen.py", "_cli_harness_opencodeopen")
reexport_public(_module, globals())

if __name__ == "__main__":
    raise SystemExit(_module.main())
