#!/usr/bin/env python3
from __future__ import annotations

from cli_harness_shim import load_cli_harness_module, reexport_public

_module = load_cli_harness_module("codexopen.py", "_cli_harness_codexopen")
reexport_public(_module, globals())

if __name__ == "__main__":
    raise SystemExit(_module.main())
