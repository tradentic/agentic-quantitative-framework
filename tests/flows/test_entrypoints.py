"""Tests that Prefect deployment entrypoints resolve to real flows."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import yaml
from prefect.flows import Flow

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _iter_deployment_entrypoints():
    prefect_yaml = Path("prefect.yaml")
    data = yaml.safe_load(prefect_yaml.read_text())
    for deployment in data.get("deployments", []):
        entrypoint = deployment.get("entrypoint")
        if not entrypoint:
            continue
        module_spec, sep, attr = entrypoint.partition(":")
        if not sep:
            raise AssertionError(f"Invalid entrypoint format for deployment {deployment.get('name')!r}")
        yield deployment.get("name"), module_spec, attr, deployment.get("flow_name")


def _import_entrypoint_module(module_spec: str):
    module_name = module_spec.replace("/", ".")
    if module_name.endswith(".py"):
        module_name = module_name[:-3]
    module_name = module_name.rstrip(".")
    return importlib.import_module(module_name)


def test_prefect_deployment_entrypoints_resolve_to_flows():
    for deployment_name, module_spec, attr, flow_name in _iter_deployment_entrypoints():
        module = _import_entrypoint_module(module_spec)
        flow_obj = getattr(module, attr)
        assert isinstance(flow_obj, Flow), (
            f"Deployment {deployment_name!r} entrypoint {module_spec} is not a Prefect Flow"
        )
        if flow_name:
            assert (
                flow_obj.name == flow_name
            ), f"Deployment {deployment_name!r} flow name mismatch: expected {flow_name!r}, got {flow_obj.name!r}"
