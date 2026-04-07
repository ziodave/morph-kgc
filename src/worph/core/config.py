from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RuntimeConfig:
    parser: configparser.ConfigParser
    source_path: Path | None
    mappings: list[str]
    file_path: str | None
    db_url: str | None
    output_format: str
    output_file: str | None
    udfs: list[str]



def _split_mappings(raw: str) -> list[str]:
    return [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]


def parse_runtime_config(config: str | Path | None) -> RuntimeConfig:
    parser = configparser.ConfigParser(interpolation=None)
    source_path: Path | None = None

    if config is None:
        raise ValueError("Configuration is required")

    if isinstance(config, Path):
        parser.read(config, encoding="utf-8")
        source_path = config
    else:
        candidate_path = Path(config)
        if "\n" not in config and "[" not in config and candidate_path.exists():
            parser.read(candidate_path, encoding="utf-8")
            source_path = candidate_path
        else:
            parser.read_string(config)

    source_sections = [
        section
        for section in parser.sections()
        if section.lower().startswith("datasource")
    ]
    if not source_sections:
        raise ValueError("Configuration must include a [DataSource] or [DataSource1] section")

    mappings: list[str] = []
    file_path: str | None = None
    db_url: str | None = None
    for section in source_sections:
        ds = parser[section]
        mappings_raw = ds.get("mappings")
        if mappings_raw:
            mappings.extend(_split_mappings(mappings_raw))
        if file_path is None and ds.get("file_path"):
            file_path = ds.get("file_path")
        if db_url is None and ds.get("db_url"):
            db_url = ds.get("db_url")

    if not mappings:
        raise ValueError("DataSource.mappings is required")

    output_format = "N-TRIPLES"
    output_file = None
    udfs_raw = ""
    for section in parser.sections():
        if section.lower() == "configuration":
            output_format = parser[section].get("output_format", output_format)
            output_file = parser[section].get("output_file")
            udfs_raw = parser[section].get("udfs", "")
            break

    return RuntimeConfig(
        parser=parser,
        source_path=source_path,
        mappings=mappings,
        file_path=file_path,
        db_url=db_url,
        output_format=output_format,
        output_file=output_file,
        udfs=[p.strip() for p in udfs_raw.replace(";", ",").split(",") if p.strip()],
    )
