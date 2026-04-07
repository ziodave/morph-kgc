from __future__ import annotations

import re
from typing import Any

from worph.core.model import FnmlCall

from .evaluator import FunctionEvaluator
from .registry import UnknownFunctionError, configure_default_registry

_TEMPLATE_PATTERN = re.compile(r"\{([^{}]+)\}")


def _resolve_param(param_value: Any, row_getter, evaluate_call):
    if isinstance(param_value, FnmlCall):
        return evaluate_call(param_value)
    if isinstance(param_value, dict) and "reference" in param_value:
        return row_getter(param_value["reference"])
    if isinstance(param_value, dict) and "template" in param_value:
        template = str(param_value["template"])
        return _TEMPLATE_PATTERN.sub(lambda m: str(row_getter(m.group(1)) or ""), template)
    return param_value


_DEFAULT_EVALUATOR = FunctionEvaluator.with_default_registry()


def configure_udfs(udf_paths: list[str] | None) -> None:
    global _DEFAULT_EVALUATOR
    configure_default_registry(udf_paths)
    _DEFAULT_EVALUATOR = FunctionEvaluator.with_default_registry()


def _normalize_fn_result(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return [_normalize_fn_result(v) for v in value]
    return value


def evaluate_fnml_call(call: FnmlCall, row_getter, evaluator: FunctionEvaluator | None = None) -> Any:
    active_evaluator = evaluator or _DEFAULT_EVALUATOR

    def _eval_nested(nested: FnmlCall) -> Any:
        return evaluate_fnml_call(nested, row_getter, evaluator=active_evaluator)

    parameters = [
        (name, _resolve_param(value, row_getter, _eval_nested))
        for name, value in call.parameters
    ]

    try:
        return _normalize_fn_result(active_evaluator.evaluate(call.function_iri, parameters))
    except UnknownFunctionError:
        return None
