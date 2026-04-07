from __future__ import annotations

import argparse
import sys
from pathlib import Path

from worph.core.config import parse_runtime_config
from worph.materializer import materialize_from_config

_FORMAT_TO_EXTENSION = {
    "N-TRIPLES": ".nt",
    "NTRIPLES": ".nt",
    "NT": ".nt",
    "N-QUADS": ".nq",
    "NQUADS": ".nq",
    "NQ": ".nq",
    "TURTLE": ".ttl",
    "TTL": ".ttl",
    "JSON-LD": ".jsonld",
    "JSONLD": ".jsonld",
    "JELLY": ".jelly",
}

_FORMAT_TO_RDFLIB = {
    "N-TRIPLES": "nt",
    "NTRIPLES": "nt",
    "NT": "nt",
    "N-QUADS": "nquads",
    "NQUADS": "nquads",
    "NQ": "nquads",
    "TURTLE": "turtle",
    "TTL": "turtle",
    "JSON-LD": "json-ld",
    "JSONLD": "json-ld",
    "JELLY": "jelly",
}


def _default_output_path(output_format: str) -> Path:
    fmt = output_format.upper().strip()
    extension = _FORMAT_TO_EXTENSION.get(fmt, ".nt")
    return Path(f"kg{extension}")


def _rdflib_format(output_format: str) -> str:
    fmt = output_format.upper().strip()
    return _FORMAT_TO_RDFLIB.get(fmt, "nt")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="worph", description="Materialize mappings into RDF outputs.")
    parser.add_argument("config", help="Path to a .ini configuration file")
    parser.add_argument("-o", "--output", help="Optional output file path (overrides config output_file)")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Configuration file not found: {config_path}", file=sys.stderr)
        return 2

    runtime = parse_runtime_config(config_path)
    graph = materialize_from_config(config_path)

    output_path = Path(args.output) if args.output else Path(runtime.output_file) if runtime.output_file else _default_output_path(runtime.output_format)
    out_format = _rdflib_format(runtime.output_format)

    graph.serialize(destination=output_path.as_posix(), format=out_format)
    print(output_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
