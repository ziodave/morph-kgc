from __future__ import annotations

import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from .built_in_functions import bif_dict

JsonValue = Any
FnHandler = Callable[[Iterable[tuple[str, JsonValue]]], JsonValue]

_UDF_DECORATOR = """
udf_dict = {}
def udf(fun_id, **params):
    def wrapper(funct):
        udf_dict[fun_id] = {}
        udf_dict[fun_id]['function'] = funct
        udf_dict[fun_id]['parameters'] = params
        return funct
    return wrapper
"""


class UnknownFunctionError(KeyError):
    """Raised when function id cannot be resolved."""


def _name_fragment(value: str) -> str:
    if "#" in value:
        return value.rsplit("#", 1)[1]
    if "/" in value:
        return value.rsplit("/", 1)[1]
    if ":" in value:
        return value.rsplit(":", 1)[1]
    return value


def normalize_function_id(function_id: str) -> str:
    return _name_fragment(function_id).strip().lower()


def normalize_parameter_name(name: str) -> str:
    return _name_fragment(name).strip().lower()


def _as_pairs(parameters: Mapping[str, JsonValue] | Iterable[tuple[str, JsonValue]]) -> list[tuple[str, JsonValue]]:
    if isinstance(parameters, Mapping):
        return [(str(k), v) for k, v in parameters.items()]
    return [(str(k), v) for k, v in parameters]


def _collect_values(parameters: Iterable[tuple[str, JsonValue]]) -> dict[str, list[JsonValue]]:
    grouped: dict[str, list[JsonValue]] = {}
    for raw_key, value in parameters:
        grouped.setdefault(raw_key, []).append(value)
        grouped.setdefault(normalize_parameter_name(raw_key), []).append(value)
    return grouped


def _unwrap(values: list[JsonValue]) -> JsonValue:
    if len(values) == 1:
        return values[0]
    return values


def _legacy_coerce(value: JsonValue) -> JsonValue:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return [_legacy_coerce(v) for v in value]
    return value


def _load_udfs(udf_paths: list[str]) -> dict[str, Any]:
    if not udf_paths:
        return {}

    merged: dict[str, Any] = {}
    for idx, udf_path in enumerate(udf_paths):
        if not Path(udf_path).exists():
            continue
        module_name = f"worph_udf_{idx}"
        code = Path(udf_path).read_text(encoding="utf-8")
        module = ModuleType(module_name)
        sys.modules[module_name] = module
        exec(f"{_UDF_DECORATOR}\n{code}", module.__dict__)
        merged.update(getattr(module, "udf_dict", {}))
    return merged


_PARAM_DEFAULTS: dict[str, JsonValue] = {
    "p_string_pattern": "%Y-%m-%d %H:%M:%S",
    "p_string_sep": ",",
    "modeparameter": "html",
    "param_int_i_from": 0,
    "param_int_i_opt_to": None,
    "any_true": "true",
}


def _build_decorated_handler(function: Callable[..., JsonValue], parameter_map: dict[str, str]) -> FnHandler:
    def _call(parameters: Iterable[tuple[str, JsonValue]]) -> JsonValue:
        values_by_key = _collect_values(parameters)
        kwargs: dict[str, JsonValue] = {}
        for arg_name, param_iri in parameter_map.items():
            values = values_by_key.get(param_iri) or values_by_key.get(normalize_parameter_name(param_iri))
            if values is not None:
                kwargs[arg_name] = _legacy_coerce(_unwrap(values))
                continue
            fallback = _PARAM_DEFAULTS.get(normalize_parameter_name(param_iri))
            if fallback is not None or normalize_parameter_name(param_iri) in _PARAM_DEFAULTS:
                kwargs[arg_name] = fallback
        try:
            return function(**kwargs)
        except Exception:
            return None

    return _call


@dataclass
class FunctionRegistry:
    _handlers: dict[str, FnHandler] = field(default_factory=dict)

    def register(self, function_id: str, handler: FnHandler) -> None:
        self._handlers[function_id] = handler
        self._handlers[normalize_function_id(function_id)] = handler

    def resolve(self, function_id: str) -> FnHandler:
        key = function_id if function_id in self._handlers else normalize_function_id(function_id)
        if key not in self._handlers:
            raise UnknownFunctionError(function_id)
        return self._handlers[key]

    def has(self, function_id: str) -> bool:
        return function_id in self._handlers or normalize_function_id(function_id) in self._handlers

    def evaluate(self, function_id: str, parameters: Mapping[str, JsonValue] | Iterable[tuple[str, JsonValue]]) -> JsonValue:
        handler = self.resolve(function_id)
        return handler(_as_pairs(parameters))

    def supported_functions(self) -> list[str]:
        return sorted(self._handlers)


def build_default_registry(udf_paths: list[str] | None = None) -> FunctionRegistry:
    reg = FunctionRegistry()

    # Legacy built-ins preserve FNML behavior used by the compatibility test suite.
    for function_id, meta in bif_dict.items():
        handler = _build_decorated_handler(meta["function"], meta["parameters"])
        reg.register(function_id, handler)

    for function_id, meta in _load_udfs(udf_paths or []).items():
        handler = _build_decorated_handler(meta["function"], meta["parameters"])
        reg.register(function_id, handler)

    return reg


_DEFAULT_REGISTRY: FunctionRegistry | None = None
_DEFAULT_UDFS: tuple[str, ...] = ()


def configure_default_registry(udf_paths: list[str] | None = None) -> None:
    global _DEFAULT_REGISTRY, _DEFAULT_UDFS
    normalized = tuple(str(Path(p)) for p in (udf_paths or []))
    if normalized == _DEFAULT_UDFS and _DEFAULT_REGISTRY is not None:
        return
    _DEFAULT_UDFS = normalized
    _DEFAULT_REGISTRY = build_default_registry(list(normalized))


def get_default_registry() -> FunctionRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = build_default_registry(list(_DEFAULT_UDFS))
    return _DEFAULT_REGISTRY
