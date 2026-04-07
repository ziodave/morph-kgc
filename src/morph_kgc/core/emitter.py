from __future__ import annotations

from typing import Any
from urllib.parse import quote

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.term import Node

from .model import TermMap
from .term_map import is_probable_iri


def render_node(value: Any, term_map: TermMap, role: str) -> Node | None:
    if value is None:
        return None

    value_as_text = str(value)
    term_type = (term_map.term_type or "").strip()
    term_type_lower = term_type.lower()

    if role == "predicate":
        return URIRef(_encode_iri(value_as_text))

    if term_type in {"BlankNode", "BNode"} or term_type_lower.endswith("blanknode"):
        return BNode(value_as_text)

    if term_type == "IRI" or term_type_lower.endswith("iri"):
        return URIRef(_encode_iri(value_as_text))

    if role == "subject":
        return URIRef(_encode_iri(value_as_text))

    if term_type == "Literal" or term_type_lower.endswith("literal"):
        return _build_literal(value, term_map)

    if term_map.datatype or term_map.language:
        return _build_literal(value, term_map)

    if is_probable_iri(value_as_text):
        return URIRef(_encode_iri(value_as_text))

    return Literal(value)


def emit_triple(graph: Graph, subject: Node | None, predicate: Node | None, object_: Node | None) -> None:
    if subject is None or predicate is None or object_ is None:
        return
    graph.add((subject, predicate, object_))


def _build_literal(value: Any, term_map: TermMap) -> Literal:
    datatype = URIRef(term_map.datatype) if term_map.datatype else None
    if term_map.language:
        return Literal(value, lang=term_map.language)
    if datatype is not None:
        return Literal(value, datatype=datatype)
    return Literal(value)


def _encode_iri(iri: str) -> str:
    return quote(iri, safe=":/?#[]@!$&'*+;=%")
