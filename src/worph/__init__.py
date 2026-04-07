"""worph v2 rewrite package."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pyoxigraph import Store

from worph.materializer import materialize_from_config



def materialize(config, python_source=None):
    return materialize_from_config(config)



def materialize_oxigraph(config, python_source=None):
    graph = materialize(config, python_source=python_source)
    store = Store()
    with tempfile.NamedTemporaryFile("w+", suffix=".nt", encoding="utf-8") as tmp:
        tmp.write(graph.serialize(format="nt"))
        tmp.flush()
        store.bulk_load(tmp.name, "application/n-triples")
    return store



def materialize_set(config, python_source=None):
    graph = materialize(config, python_source=python_source)
    return {f"{s.n3()} {p.n3()} {o.n3()} " for s, p, o in graph}



def materialize_kafka(config, python_source=None):
    raise NotImplementedError("Kafka output is not implemented in v2 rewrite yet")



def translate_to_rml(mapping_path):
    # For compatibility this returns the same path until explicit translation pipeline lands.
    return str(Path(mapping_path))
