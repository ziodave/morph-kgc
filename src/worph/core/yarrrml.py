from __future__ import annotations

import os
import re
from typing import Any

import yaml

from .model import FnmlCall, LogicalSource, MappingDocument, ObjectMapSpec, PredicateObjectMap, TermMap, TriplesMap

_TEMPLATE_RE = re.compile(r"\$\(([^)]+)\)")


DEFAULT_PREFIXES = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "schema": "http://schema.org/",
}


def _parse_compact_source(value: str) -> dict[str, Any]:
    text = value.strip()
    if "~" in text:
        access, formulation = text.rsplit("~", 1)
        return {"access": access, "referenceFormulation": formulation.lower()}
    return {"access": text, "referenceFormulation": "csv"}


def _parse_source_item(item: Any, source_aliases: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if isinstance(item, str):
        if item in source_aliases:
            return dict(source_aliases[item])
        return _parse_compact_source(item)

    if isinstance(item, list):
        if not item:
            return None
        base = _parse_source_item(item[0], source_aliases)
        if base is None:
            return None
        if len(item) > 1 and "iterator" not in base:
            base["iterator"] = item[1]
        if len(item) > 2 and "query" not in base:
            base["query"] = item[2]
        return base

    if isinstance(item, dict):
        parsed = dict(item)
        table = parsed.pop("table", None)
        query_formulation = parsed.get("queryFormulation")
        if table is not None and "query" not in parsed:
            parsed["query"] = f"SELECT * FROM {table}"
        if query_formulation and "referenceFormulation" not in parsed:
            parsed["referenceFormulation"] = query_formulation
        return parsed

    return None


def _normalize_sources(raw: Any, source_aliases: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        result = []
        for item in raw:
            parsed = _parse_source_item(item, source_aliases)
            if parsed is not None:
                result.append(parsed)
        return result
    if isinstance(raw, dict):
        parsed = _parse_source_item(raw, source_aliases)
        return [parsed] if parsed is not None else []
    if isinstance(raw, str):
        parsed = _parse_source_item(raw, source_aliases)
        return [parsed] if parsed is not None else []
    return []


def _normalize_po_key(mapping: dict[str, Any]) -> list[dict[str, Any]]:
    if "predicateobjects" in mapping:
        raw = mapping["predicateobjects"]
    elif "predicateObjects" in mapping:
        raw = mapping["predicateObjects"]
    elif "po" in mapping:
        raw = mapping["po"]
    else:
        raw = []
    if isinstance(raw, list):
        normalized: list[dict[str, Any]] = []
        for x in raw:
            if isinstance(x, dict):
                normalized.append(x)
            elif isinstance(x, list) and len(x) >= 2:
                obj_value = x[1]
                if len(x) == 2:
                    normalized.append({"p": x[0], "o": obj_value})
                    continue

                obj_spec: dict[str, Any] = {"value": obj_value}
                third = x[2]
                if isinstance(third, str):
                    if third.lower() == "iri":
                        obj_spec["type"] = "iri"
                    elif ":" in third:
                        obj_spec["datatype"] = third
                normalized.append({"p": x[0], "o": obj_spec})
        return normalized
    return []


def _expand_prefixed(value: Any, prefixes: dict[str, str]) -> Any:
    if not isinstance(value, str):
        return value
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if value.startswith("<") and value.endswith(">"):
        return value[1:-1]
    if value.startswith("$"):
        return value
    if ":" in value:
        prefix, suffix = value.split(":", 1)
        if prefix in prefixes:
            return prefixes[prefix] + suffix
    return value


def _yarrrml_template_to_rr(template: str) -> str:
    return _TEMPLATE_RE.sub(lambda m: "{" + m.group(1).strip() + "}", template)


def _parse_function_call(obj: dict[str, Any], prefixes: dict[str, str], external_values: dict[str, Any]) -> FnmlCall:
    params: list[tuple[str, Any]] = []
    for p in obj.get("parameters", []):
        if not isinstance(p, dict):
            continue
        name = p.get("parameter")
        if not name:
            continue
        value = p.get("value")
        if isinstance(value, dict) and "function" in value:
            value = _term_map_from_object_spec(value, prefixes, external_values).function_call
        elif isinstance(value, str) and value.startswith("$(") and value.endswith(")"):
            raw_ref = value[2:-1]
            escaped = raw_ref.startswith("\\")
            ref_name = raw_ref.replace("\\", "")
            if ref_name in external_values:
                value = external_values[ref_name]
            elif escaped and ref_name.startswith("_") and ref_name[1:] in external_values:
                value = external_values[ref_name[1:]]
            else:
                value = {"reference": ref_name}
        elif isinstance(value, str) and "$(" in value:
            expanded_value = value
            if ":" in value and not value.startswith(("http://", "https://", "<")):
                prefix, suffix = value.split(":", 1)
                if prefix in prefixes:
                    expanded_value = prefixes[prefix] + suffix
            value = {"template": _yarrrml_template_to_rr(expanded_value)}
        else:
            value = _expand_prefixed(value, prefixes)
        if isinstance(value, bool):
            value = "true" if value else "false"
        elif isinstance(value, (int, float)):
            value = str(value)
        params.append((_expand_prefixed(name, prefixes), value))

    function_iri = _expand_prefixed(obj["function"], prefixes)
    return FnmlCall(function_iri=function_iri, parameters=params)


def _term_map_from_object_spec(obj: Any, prefixes: dict[str, str], external_values: dict[str, Any]) -> TermMap:
    if isinstance(obj, str):
        force_iri = False
        if obj.endswith("~iri"):
            obj = obj[:-4]
            force_iri = True

        if obj.startswith("$(") and obj.endswith(")"):
            raw_ref = obj[2:-1]
            escaped = raw_ref.startswith("\\")
            ref_name = raw_ref.replace("\\", "")
            if ref_name in external_values:
                return TermMap(constant=external_values[ref_name], term_type="iri" if force_iri else "literal")
            if escaped and ref_name.startswith("_") and ref_name[1:] in external_values:
                return TermMap(constant=external_values[ref_name[1:]], term_type="iri" if force_iri else "literal")
            return TermMap(reference=ref_name, term_type="iri" if force_iri else "literal")
        if "$(" in obj:
            expanded = obj
            if ":" in obj and not obj.startswith(("http://", "https://", "<")):
                prefix, suffix = obj.split(":", 1)
                if prefix in prefixes:
                    expanded = prefixes[prefix] + suffix
            return TermMap(template=_yarrrml_template_to_rr(expanded), term_type="iri" if force_iri else "literal")
        if obj.startswith("$"):
            return TermMap(template=_yarrrml_template_to_rr(obj), term_type="iri" if force_iri else "literal")
        expanded = _expand_prefixed(obj, prefixes)
        if force_iri or (isinstance(expanded, str) and expanded.startswith(("http://", "https://"))):
            return TermMap(constant=expanded, term_type="iri")
        return TermMap(constant=expanded, term_type="literal")

    if not isinstance(obj, dict):
        return TermMap(constant=obj, term_type="literal")

    if "function" in obj:
        fn_call = _parse_function_call(obj, prefixes, external_values)
        term_type = obj.get("type") or "literal"
        datatype = _expand_prefixed(obj.get("datatype"), prefixes)
        language = obj.get("language")
        return TermMap(
            function_call=fn_call,
            datatype=datatype,
            language=language,
            term_type=("iri" if term_type == "iri" else "literal"),
        )

    if "value" in obj:
        value = obj["value"]
        datatype = _expand_prefixed(obj.get("datatype"), prefixes)
        language = obj.get("language")
        term_type = obj.get("type")

        if isinstance(value, str) and value.startswith("$(") and value.endswith(")"):
            raw_ref = value[2:-1]
            escaped = raw_ref.startswith("\\")
            ref_name = raw_ref.replace("\\", "")
            if ref_name in external_values:
                return TermMap(
                    constant=external_values[ref_name],
                    datatype=datatype,
                    language=language,
                    term_type=(term_type or "literal"),
                )
            if escaped and ref_name.startswith("_") and ref_name[1:] in external_values:
                return TermMap(
                    constant=external_values[ref_name[1:]],
                    datatype=datatype,
                    language=language,
                    term_type=(term_type or "literal"),
                )
            return TermMap(
                reference=ref_name,
                datatype=datatype,
                language=language,
                term_type=(term_type or "literal"),
            )

        if isinstance(value, str) and "$(" in value:
            return TermMap(
                template=_yarrrml_template_to_rr(value),
                datatype=datatype,
                language=language,
                term_type=(term_type or "literal"),
            )

        const = _expand_prefixed(value, prefixes)
        guessed_term_type = term_type or ("iri" if isinstance(const, str) and const.startswith(("http://", "https://")) else "literal")
        return TermMap(
            constant=const,
            datatype=datatype,
            language=language,
            term_type=guessed_term_type,
        )

    return TermMap(constant=obj, term_type="literal")


def _build_po_map(po_entry: dict[str, Any], prefixes: dict[str, str], external_values: dict[str, Any]) -> PredicateObjectMap:
    predicates = po_entry.get("p") or po_entry.get("predicates")
    objects = po_entry.get("o") or po_entry.get("objects")

    pred_values = predicates if isinstance(predicates, list) else [predicates]
    obj_values = objects if isinstance(objects, list) else [objects]

    predicate_maps = [
        TermMap(constant=_expand_prefixed(p, prefixes), term_type="iri")
        for p in pred_values
        if p is not None
    ]
    object_maps = [
        ObjectMapSpec(term_map=_term_map_from_object_spec(o, prefixes, external_values))
        for o in obj_values
        if o is not None
    ]

    condition_obj = po_entry.get("condition")
    condition_call = None
    if isinstance(condition_obj, dict) and "function" in condition_obj:
        condition_call = _parse_function_call(condition_obj, prefixes, external_values)

    return PredicateObjectMap(predicate_maps=predicate_maps, object_maps=object_maps, condition=condition_call)


def parse_yarrrml(path: str, *, file_path_override: str | None = None, db_url_override: str | None = None) -> MappingDocument:
    with open(path, "r", encoding="utf-8") as handle:
        doc = yaml.safe_load(handle) or {}

    prefixes = dict(DEFAULT_PREFIXES)
    prefixes.update(doc.get("prefixes", {}))
    prefixes = {k: str(v) for k, v in prefixes.items()}

    base = doc.get("base")
    mappings = doc.get("mappings", {})
    external_values = dict(doc.get("external", {}))
    source_aliases_raw = doc.get("sources", {}) or {}
    source_aliases: dict[str, dict[str, Any]] = {}
    if isinstance(source_aliases_raw, dict):
        for name, descriptor in source_aliases_raw.items():
            parsed = _parse_source_item(descriptor, {})
            if parsed is not None:
                source_aliases[str(name)] = parsed

    triples_maps: list[TriplesMap] = []
    for map_name, map_spec in mappings.items():
        if not isinstance(map_spec, dict):
            continue

        sources = _normalize_sources(map_spec.get("sources"), source_aliases)
        source = sources[0] if sources else {}
        access = source.get("access")
        if file_path_override and (not access or os.path.basename(str(access)) == os.path.basename(file_path_override)):
            access = file_path_override
        elif db_url_override and not access:
            access = db_url_override
        elif access and not os.path.isabs(access):
            access_text = str(access)
            access = access_text if os.path.exists(access_text) else os.path.join(os.path.dirname(path), access_text)
        logical_source = LogicalSource(
            source=str(access or file_path_override or ""),
            reference_formulation=str(source.get("referenceFormulation", "csv")).lower(),
            iterator=source.get("iterator"),
            query=source.get("query"),
        )

        subjects = map_spec.get("subjects")
        if isinstance(subjects, list):
            subject_raw = subjects[0]
        else:
            subject_raw = subjects
        subject_term = _term_map_from_object_spec(subject_raw, prefixes, external_values)
        if subject_term.template and "$(" in subject_term.template:
            subject_term.template = _yarrrml_template_to_rr(subject_term.template)
        subject_term.term_type = "iri"

        po_maps = [_build_po_map(po, prefixes, external_values) for po in _normalize_po_key(map_spec)]

        triples_maps.append(
            TriplesMap(
                identifier=f"yarrrml:{map_name}",
                logical_source=logical_source,
                subject_map=subject_term,
                po_maps=po_maps,
            )
        )

    return MappingDocument(prefixes=prefixes, base=base, triples_maps=triples_maps)
