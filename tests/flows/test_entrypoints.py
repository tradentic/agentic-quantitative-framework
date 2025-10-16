"""Ensure Prefect deployments reference importable flow entrypoints."""
from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path
from typing import Iterable

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _iter_entrypoints() -> Iterable[pytest.ParameterSet]:
    config_path = Path(__file__).resolve().parents[2] / "prefect.yaml"
    data = yaml.safe_load(config_path.read_text()) or {}
    deployments = data.get("deployments", [])

    for deployment in deployments:
        entrypoint = deployment.get("entrypoint")
        if not entrypoint:
            continue

        module_path, func_name = entrypoint.rsplit(":", 1)
        module_name = module_path.replace("/", ".")
        if module_name.endswith(".py"):
            module_name = module_name[:-3]

        deployment_name = deployment.get("name", entrypoint)
        yield pytest.param(module_name, func_name, id=deployment_name)


@pytest.mark.parametrize("module_name, attr", list(_iter_entrypoints()))
def test_prefect_entrypoint_importable(module_name: str, attr: str) -> None:
    module = import_module(module_name)
    assert hasattr(module, attr), f"{module_name} missing attribute {attr}"
