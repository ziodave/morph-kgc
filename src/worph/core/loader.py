from __future__ import annotations

import os

from .config import RuntimeConfig
from .model import MappingDocument
from .rml_parser import parse_rml
from .yarrrml import parse_yarrrml


YARRRML_EXTENSIONS = {".yml", ".yaml", ".yarrrml"}


def _resolve_mapping_path(mapping_path: str) -> str:
    if os.path.exists(mapping_path):
        return mapping_path
    raise FileNotFoundError(mapping_path)


def load_mapping(mapping_path: str, config: RuntimeConfig) -> MappingDocument:
    resolved = _resolve_mapping_path(mapping_path)
    ext = os.path.splitext(resolved)[1].lower()
    if ext in YARRRML_EXTENSIONS:
        return parse_yarrrml(resolved, file_path_override=config.file_path)
    return parse_rml(resolved, file_path_override=config.file_path, db_url=config.db_url)
