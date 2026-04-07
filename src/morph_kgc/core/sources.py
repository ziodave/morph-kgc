from __future__ import annotations

import csv
import json
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

import elementpath
import pandas as pd


@dataclass(slots=True)
class Record:
    values: dict[str, Any]
    context: Any = None



def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {str(k): v for k, v in row.items()}


def iter_csv(path: str, delimiter: str = ",") -> Iterable[Record]:
    with open(path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        for row in reader:
            yield Record(values=_normalize_row(row))


def iter_tabular(path: str) -> Iterable[Record]:
    ext = Path(path).suffix.lower()
    if ext == ".tsv":
        yield from iter_csv(path, delimiter="\t")
        return
    if ext == ".parquet":
        frame = pd.read_parquet(path)
    elif ext == ".feather":
        frame = pd.read_feather(path)
    elif ext == ".dta":
        frame = pd.read_stata(path)
    elif ext in {".xlsx", ".xls"}:
        try:
            frame = pd.read_excel(path)
        except Exception:
            yield from _iter_xlsx_minimal(path)
            return
    elif ext == ".ods":
        try:
            frame = pd.read_excel(path, engine="odf")
        except Exception:
            yield from _iter_ods_minimal(path)
            return
    else:
        raise ValueError(f"Unsupported tabular source extension: {ext}")

    for _, row in frame.iterrows():
        values: dict[str, Any] = {}
        for col, value in row.to_dict().items():
            if pd.isna(value):
                values[str(col)] = None
            else:
                values[str(col)] = str(value)
        yield Record(values=values)


def _iter_xlsx_minimal(path: str) -> Iterable[Record]:
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as zf:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("x:si", ns):
                text = "".join(t.text or "" for t in si.findall(".//x:t", ns))
                shared_strings.append(text)

        sheet_name = "xl/worksheets/sheet1.xml"
        if sheet_name not in zf.namelist():
            sheet_name = next((n for n in zf.namelist() if n.startswith("xl/worksheets/") and n.endswith(".xml")), "")
        if not sheet_name:
            return
        sheet_root = ET.fromstring(zf.read(sheet_name))
        rows = []
        for row in sheet_root.findall(".//x:sheetData/x:row", ns):
            values = []
            for cell in row.findall("x:c", ns):
                tpe = cell.attrib.get("t")
                v = cell.find("x:v", ns)
                if tpe == "inlineStr":
                    t = cell.find("x:is/x:t", ns)
                    values.append((t.text if t is not None else None))
                    continue
                if v is None or v.text is None:
                    values.append(None)
                    continue
                raw = v.text
                if tpe == "s":
                    idx = int(raw)
                    values.append(shared_strings[idx] if idx < len(shared_strings) else raw)
                else:
                    values.append(raw)
            rows.append(values)

    if not rows:
        return
    headers = [str(h) for h in rows[0]]
    for data in rows[1:]:
        values = {headers[i]: (str(data[i]) if i < len(data) and data[i] is not None else None) for i in range(len(headers))}
        yield Record(values=values)


def _iter_ods_minimal(path: str) -> Iterable[Record]:
    ns = {
        "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
        "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    }
    with zipfile.ZipFile(path) as zf:
        if "content.xml" not in zf.namelist():
            return
        root = ET.fromstring(zf.read("content.xml"))

    table = root.find(".//table:table", ns)
    if table is None:
        return
    rows: list[list[str | None]] = []
    for row in table.findall("table:table-row", ns):
        cells: list[str | None] = []
        for cell in row.findall("table:table-cell", ns):
            repeat = int(cell.attrib.get(f"{{{ns['table']}}}number-columns-repeated", "1"))
            text_value = "".join((p.text or "") for p in cell.findall("text:p", ns))
            value = text_value if text_value != "" else None
            for _ in range(repeat):
                cells.append(value)
        if any(c is not None for c in cells):
            rows.append(cells)

    if not rows:
        return
    headers = [str(h) for h in rows[0]]
    for data in rows[1:]:
        values = {headers[i]: (str(data[i]) if i < len(data) and data[i] is not None else None) for i in range(len(headers))}
        yield Record(values=values)


def _sqlite_path(db_url: str) -> str:
    if db_url.startswith("sqlite:///"):
        return db_url[len("sqlite:///") :]
    return db_url


def iter_sqlite(db_url: str, query: str | None = None) -> Iterable[Record]:
    path = _sqlite_path(db_url)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        if query is None:
            tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
            if not tables:
                return
            query = f"SELECT * FROM {tables[0]['name']}"
        rows = connection.execute(query)
        for row in rows:
            yield Record(values={k: row[k] for k in row.keys()})
    finally:
        connection.close()


def _normalize_xpath(expr: str) -> str:
    if "@" in expr and "/@" not in expr and not expr.strip().startswith("@"):
        head, tail = expr.rsplit("@", 1)
        if head and not head.endswith("/"):
            return f"{head}/@{tail}"
    return expr


def _xpath_values(element: ET.Element, expr: str) -> list[str]:
    try:
        value = elementpath.select(element, _normalize_xpath(expr))
    except Exception:
        return []

    if isinstance(value, list):
        results: list[str] = []
        for item in value:
            if isinstance(item, ET.Element):
                results.append("".join(item.itertext()))
            elif item is not None:
                results.append(str(item))
        return results

    if isinstance(value, ET.Element):
        return ["".join(value.itertext())]

    if value is None:
        return []

    return [str(value)]


def iter_xml(path: str, iterator: str | None) -> Iterable[Record]:
    tree = ET.parse(path)
    root = tree.getroot()
    selected = elementpath.select(root, iterator or "/")
    if isinstance(selected, ET.Element):
        selected = [selected]

    for node in selected:
        if not isinstance(node, ET.Element):
            continue
        values: dict[str, Any] = {}
        for child in list(node):
            tag = child.tag.rsplit("}", 1)[-1]
            values[tag] = "".join(child.itertext())
        values.update({k.lstrip("@"): v for k, v in node.attrib.items()})
        yield Record(values=values, context=node)


def _json_expand_step(values: list[Any], part: str) -> list[Any]:
    expanded: list[Any] = []
    wildcard = part == "*"
    list_wildcard = part.endswith("[*]")
    key = part[:-3] if list_wildcard else part

    for value in values:
        if wildcard:
            if isinstance(value, dict):
                expanded.extend(value.values())
            elif isinstance(value, list):
                expanded.extend(value)
            continue

        current = value
        if key:
            if isinstance(current, dict):
                if key not in current:
                    continue
                current = current[key]
            else:
                continue

        if list_wildcard:
            if isinstance(current, list):
                expanded.extend(current)
            elif isinstance(current, dict):
                expanded.extend(current.values())
        else:
            expanded.append(current)
    return expanded


def _json_select(root: Any, path: str | None) -> list[Any]:
    if not path or path == "$":
        return [root]

    expr = path.strip()
    if expr.startswith("$."):
        expr = expr[2:]
    elif expr.startswith("$"):
        expr = expr[1:]
        if expr.startswith("."):
            expr = expr[1:]

    if expr == "":
        return [root]

    values: list[Any] = [root]
    for part in expr.split("."):
        if part == "":
            continue
        values = _json_expand_step(values, part)
        if not values:
            break
    return values


def iter_json(path: str, iterator: str | None) -> Iterable[Record]:
    with open(path, "r", encoding="utf-8") as handle:
        root = json.load(handle)

    selected = _json_select(root, iterator or "$")
    for node in selected:
        if isinstance(node, dict):
            yield Record(values=node, context=node)
        else:
            yield Record(values={"value": node}, context=node)


def _json_reference_values(node: Any, reference: str) -> list[Any]:
    # Compatibility: wildcard member access in references (e.g. "a.*.b") is not
    # supported by legacy behavior and should not materialize values.
    if reference and not reference.startswith("$") and ".*" in reference:
        return []
    expr = reference.strip()
    if expr.startswith("$"):
        return _json_select(node, expr)
    return _json_select(node, "$." + expr if expr else "$")


def reference_value(record: Record, formulation: str, reference: str) -> Any:
    form = formulation.lower()
    if form == "xpath":
        if record.context is not None:
            values = _xpath_values(record.context, reference)
            if not values:
                return None
            if len(values) == 1:
                return values[0]
            return values
        return record.values.get(reference)
    if form == "jsonpath":
        base = record.context if record.context is not None else record.values
        values = _json_reference_values(base, reference)
        if not values:
            return None
        normalized = [v for v in values if v is not None]
        if not normalized:
            return None
        normalized = [str(v) if not isinstance(v, (dict, list)) else v for v in normalized]
        if len(normalized) == 1:
            return normalized[0]
        return normalized
    value = record.values.get(reference)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "" or stripped.lower() == "nan":
            return None
    return value


def iter_records(formulation: str, source: str, iterator: str | None = None, query: str | None = None) -> Iterable[Record]:
    form = formulation.lower()
    suffix = Path(source).suffix.lower()
    if suffix in {".tsv", ".parquet", ".feather", ".dta", ".xlsx", ".xls", ".ods"}:
        yield from iter_tabular(source)
        return
    if form in {"csv"}:
        yield from iter_csv(source)
        return
    if form in {"xpath", "xml"}:
        yield from iter_xml(source, iterator)
        return
    if form in {"jsonpath", "json"}:
        yield from iter_json(source, iterator)
        return
    if form in {"sql2008", "sql2011", "sql2016", "rdb", "database", "sqlite"} or source.startswith("sqlite:///"):
        yield from iter_sqlite(source, query=query)
        return
    # default fallback behaves like csv for compatibility with simple tests
    yield from iter_csv(source)


def iter_source_rows(logical_source, base_path: Path | None = None) -> Iterator[dict[str, Any]]:
    source = str(logical_source.source)
    if base_path is not None:
        source_path = Path(source)
        if not source_path.is_absolute():
            source = str((base_path / source_path).resolve())

    rows = iter_records(
        formulation=logical_source.reference_formulation,
        source=source,
        iterator=logical_source.iterator,
        query=logical_source.query,
    )
    for record in rows:
        yield dict(record.values)
