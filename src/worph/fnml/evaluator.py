from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .registry import FunctionRegistry, get_default_registry

JsonValue = Any


@dataclass
class FunctionEvaluator:
    """Lightweight FNML evaluator wrapper for executor integration."""

    registry: FunctionRegistry

    @classmethod
    def with_default_registry(cls) -> "FunctionEvaluator":
        return cls(registry=get_default_registry())

    def evaluate(self, function_id: str, parameters: Mapping[str, JsonValue] | Iterable[tuple[str, JsonValue]]) -> JsonValue:
        return self.registry.evaluate(function_id, parameters)


def evaluate_function(
    function_id: str,
    parameters: Mapping[str, JsonValue] | Iterable[tuple[str, JsonValue]],
    registry: FunctionRegistry | None = None,
) -> JsonValue:
    active_registry = registry or get_default_registry()
    return active_registry.evaluate(function_id, parameters)
