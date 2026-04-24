from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

CLI_HARNESS_DIR_ENV = "CLI_HARNESS_DIR"
DEFAULT_CLI_HARNESS_DIR = Path.home() / "dev" / "cli-harness"


def cli_harness_dir() -> Path:
    return Path(os.environ.get(CLI_HARNESS_DIR_ENV, str(DEFAULT_CLI_HARNESS_DIR))).expanduser()


def cli_harness_cmd(name: str) -> Path:
    return cli_harness_dir() / name


def load_cli_harness_module(script_name: str, module_name: str) -> ModuleType:
    root = cli_harness_dir()
    script_path = root / script_name
    if not script_path.exists():
        raise RuntimeError(
            f"Canonical cli-harness file not found: {script_path}. "
            f"Set {CLI_HARNESS_DIR_ENV} if cli-harness lives elsewhere."
        )

    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load canonical cli-harness module: {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def reexport_public(module: ModuleType, namespace: dict[str, object]) -> None:
    for name in dir(module):
        if not name.startswith("__"):
            namespace[name] = getattr(module, name)
