"""Data-only immutable Python artifacts. Execution belongs exclusively to Worker."""

import ast
from copy import deepcopy
import hashlib
import json
import re

CONTRACT = "catos.python-strategy.v1"
TOKEN = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


def data(value, depth=0):
    if depth > 2:
        raise ValueError("strategy_data_depth")
    if value is None or type(value) in (bool, str):
        if type(value) is str and len(value) > 4096:
            raise ValueError("strategy_data_size")
    elif type(value) is int:
        if abs(value) > 2**63 - 1:
            raise ValueError("strategy_integer_range")
    elif type(value) in (dict, list):
        if len(value) > 64:
            raise ValueError("strategy_data_size")
        for key, item in (value.items() if type(value) is dict else enumerate(value)):
            if type(value) is dict and (type(key) is not str or len(key) > 64):
                raise ValueError("strategy_data_key")
            data(item, depth + 1)
    else:
        raise ValueError("strategy_data_no_float")
    return value


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def artifact(value):
    keys = {"contract", "strategy_id", "version", "name", "description", "source", "defaults", "warmup_bars"}
    if type(value) is not dict or set(value) != keys or value["contract"] != CONTRACT:
        raise ValueError("strategy_manifest_contract")
    for key in ("strategy_id", "version"):
        if type(value[key]) is not str or not TOKEN.fullmatch(value[key]):
            raise ValueError("strategy_identity")
    for key, maximum in (("name", 120), ("description", 2000), ("source", 12000)):
        if type(value[key]) is not str or not 0 < len(value[key].encode("utf-8")) <= maximum:
            raise ValueError("strategy_text_size")
    if type(value["defaults"]) is not dict:
        raise ValueError("strategy_parameters_object")
    data(value["defaults"])
    if len(canonical(value["defaults"]).encode("utf-8")) > 4096:
        raise ValueError("strategy_parameters_size")
    if type(value["warmup_bars"]) is not int or not 1 <= value["warmup_bars"] <= 16:
        raise ValueError("strategy_warmup_range")
    # Parsing is validation, never imports or evaluates user code in this process.
    tree = ast.parse(value["source"])
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Strategy"]
    if len(classes) != 1:
        raise ValueError("strategy_entrypoint_required")
    methods = {node.name for node in classes[0].body if isinstance(node, ast.FunctionDef)}
    if not {"__init__", "update_indicators", "on_bar", "snapshot_state", "restore_state"} <= methods:
        raise ValueError("strategy_hooks_required")
    return deepcopy(value)


def binding(value):
    if type(value) is not dict or set(value) != {"artifact", "artifact_hash", "parameters"}:
        raise ValueError("strategy_binding_contract")
    manifest = artifact(value["artifact"])
    if value["artifact_hash"] != digest(manifest):
        raise ValueError("strategy_artifact_hash_mismatch")
    if type(value["parameters"]) is not dict:
        raise ValueError("strategy_parameters_object")
    data(value["parameters"])
    if len(canonical(value["parameters"]).encode("utf-8")) > 4096:
        raise ValueError("strategy_parameters_size")
    return deepcopy(value)


def state(value):
    data(value)
    if len(canonical(value).encode("utf-8")) > 4096:
        raise ValueError("strategy_state_size")
    return deepcopy(value)
