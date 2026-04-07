from __future__ import annotations

from pathlib import Path

from rdflib import Graph
from rdflib.namespace import RDF

from worph.core.config import parse_runtime_config
from worph.core.emitter import emit_triple, render_node
from worph.core.loader import load_mapping
from worph.core.model import MappingDocument, ObjectMapSpec
from worph.core.sources import Record, iter_records, reference_value
from worph.core.term_map import render_term_map
from worph.fnml.engine import evaluate_fnml_call, configure_udfs



def materialize_from_mapping(mapping: MappingDocument, graph: Graph | None = None) -> Graph:
    rdf_graph = graph if graph is not None else Graph()
    tm_by_id = {tm.identifier: tm for tm in mapping.triples_maps}
    rows_by_tm: dict[str, list[Record]] = {}

    for triples_map in mapping.triples_maps:
        if triples_map.has_named_graphs:
            # Compatibility mode for this rewrite snapshot: named graph output is not materialized yet.
            continue
        formulation = triples_map.logical_source.reference_formulation
        rows = list(
            iter_records(
                formulation=formulation,
                source=triples_map.logical_source.source,
                iterator=triples_map.logical_source.iterator,
                query=triples_map.logical_source.query,
            )
        )
        rows_by_tm[triples_map.identifier] = rows

    parent_subjects: dict[str, list[tuple[Record, list]]] = {}
    for triples_map in mapping.triples_maps:
        if triples_map.identifier not in rows_by_tm:
            continue
        formulation = triples_map.logical_source.reference_formulation
        subject_entries: list[tuple[Record, list]] = []
        for record in rows_by_tm[triples_map.identifier]:
            subject_value = render_term_map(triples_map.subject_map, record, formulation)
            subject_values = subject_value if isinstance(subject_value, list) else [subject_value]
            subject_nodes = [
                render_node(current_subject_value, triples_map.subject_map, role="subject")
                for current_subject_value in subject_values
            ]
            subject_entries.append((record, [s for s in subject_nodes if s is not None]))
        parent_subjects[triples_map.identifier] = subject_entries

    for triples_map in mapping.triples_maps:
        if triples_map.identifier not in rows_by_tm:
            continue
        formulation = triples_map.logical_source.reference_formulation
        for record, subject_nodes in parent_subjects[triples_map.identifier]:
            for subject_node in subject_nodes:
                for class_iri in triples_map.class_iris:
                    emit_triple(
                        rdf_graph,
                        subject_node,
                        RDF.type,
                        render_node(class_iri, triples_map.subject_map, role="object"),
                    )

                for po_map in triples_map.po_maps:
                    if po_map.condition is not None:
                        cond_value = evaluate_fnml_call(
                            po_map.condition,
                            lambda ref: reference_value(record, formulation, ref),
                        )
                        if not _is_truthy(cond_value):
                            continue

                    predicate_nodes = []
                    for predicate_tm in po_map.predicate_maps:
                        p_value = render_term_map(predicate_tm, record, formulation)
                        p_node = render_node(p_value, predicate_tm, role="predicate")
                        if p_node is not None:
                            predicate_nodes.append(p_node)

                    object_nodes = []
                    for object_map in po_map.object_maps:
                        obj_nodes = _render_object_map(
                            object_map=object_map,
                            record=record,
                            formulation=formulation,
                            current_tm=triples_map,
                            tm_by_id=tm_by_id,
                            parent_subjects=parent_subjects,
                        )
                        object_nodes.extend(obj_nodes)

                    for p_node in predicate_nodes:
                        for o_node in object_nodes:
                            emit_triple(rdf_graph, subject_node, p_node, o_node)

    return rdf_graph


def _render_object_map(object_map: ObjectMapSpec, record: Record, formulation: str, current_tm, tm_by_id, parent_subjects):
    if object_map.parent_triples_map:
        parent_tm = tm_by_id.get(object_map.parent_triples_map)
        if parent_tm is None:
            return []
        matches = []
        parent_entries = parent_subjects.get(parent_tm.identifier, [])
        if object_map.join_conditions:
            for parent_record, parent_nodes in parent_entries:
                ok = True
                for jc in object_map.join_conditions:
                    child_val = reference_value(record, formulation, jc.child)
                    parent_val = reference_value(parent_record, parent_tm.logical_source.reference_formulation, jc.parent)
                    if child_val != parent_val:
                        ok = False
                        break
                if ok:
                    matches.extend(parent_nodes)
            return matches

        # No join condition: if same source, use current row for parent subject construction; otherwise fallback to all parent subjects.
        if parent_tm.logical_source.source == current_tm.logical_source.source:
            parent_subject_value = render_term_map(parent_tm.subject_map, record, current_tm.logical_source.reference_formulation)
            values = parent_subject_value if isinstance(parent_subject_value, list) else [parent_subject_value]
            nodes = [render_node(v, parent_tm.subject_map, role="object") for v in values]
            return [n for n in nodes if n is not None]

        for _, parent_nodes in parent_entries:
            matches.extend(parent_nodes)
        return matches

    if object_map.term_map is None:
        return []
    language = object_map.term_map.language
    if object_map.term_map.language_map is not None:
        lang_value = render_term_map(object_map.term_map.language_map, record, formulation)
        if isinstance(lang_value, list):
            language = str(lang_value[0]) if lang_value else None
        elif lang_value is not None:
            language = str(lang_value)

    term_map = object_map.term_map
    if language != term_map.language:
        term_map = object_map.term_map.__class__(
            constant=term_map.constant,
            template=term_map.template,
            reference=term_map.reference,
            term_type=term_map.term_type,
            datatype=term_map.datatype,
            language=language,
            language_map=term_map.language_map,
            function_call=term_map.function_call,
        )

    value = render_term_map(term_map, record, formulation)
    if isinstance(value, list):
        nodes = []
        for item in value:
            node = render_node(item, term_map, role="object")
            if node is not None:
                nodes.append(node)
        return nodes
    node = render_node(value, term_map, role="object")
    return [node] if node is not None else []


def materialize_from_config(config_input: str | Path) -> Graph:
    runtime_config = parse_runtime_config(config_input)
    configure_udfs(runtime_config.udfs)
    merged = Graph()
    for mapping_path in runtime_config.mappings:
        mapping_doc = load_mapping(mapping_path, runtime_config)
        materialize_from_mapping(mapping_doc, graph=merged)
    return merged


def _is_truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    return text not in {"", "0", "false", "no", "off", "none", "null"}
