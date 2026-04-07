from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LogicalSource:
    source: str
    reference_formulation: str
    iterator: str | None = None
    query: str | None = None


@dataclass(slots=True)
class FnmlCall:
    function_iri: str
    parameters: list[tuple[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class TermMap:
    constant: Any | None = None
    template: str | None = None
    reference: str | None = None
    term_type: str | None = None
    datatype: str | None = None
    language: str | None = None
    language_map: "TermMap | None" = None
    function_call: FnmlCall | None = None


@dataclass(slots=True)
class JoinCondition:
    child: str
    parent: str


@dataclass(slots=True)
class ObjectMapSpec:
    term_map: TermMap | None = None
    parent_triples_map: str | None = None
    join_conditions: list[JoinCondition] = field(default_factory=list)


@dataclass(slots=True)
class PredicateObjectMap:
    predicate_maps: list[TermMap] = field(default_factory=list)
    object_maps: list[ObjectMapSpec] = field(default_factory=list)
    condition: FnmlCall | None = None


@dataclass(slots=True)
class TriplesMap:
    identifier: str
    logical_source: LogicalSource
    subject_map: TermMap
    class_iris: list[str] = field(default_factory=list)
    has_named_graphs: bool = False
    po_maps: list[PredicateObjectMap] = field(default_factory=list)


@dataclass(slots=True)
class MappingDocument:
    prefixes: dict[str, str]
    base: str | None
    triples_maps: list[TriplesMap]
