"""Parsers for structured data formats: JSON, CSV, YAML, XML, TOML."""

from __future__ import annotations

import csv
import json
import re
from typing import Any

from ..exceptions import UnsafeContentRefusal
from .base import ParserAdapter

# A DTD or entity declaration in an XML document opens the door to unbounded
# internal-entity expansion ('billion laughs') under the stdlib ElementTree,
# which has no expansion limit. XMLParser refuses any document that has one.
_XML_DTD_PATTERN = re.compile(rb"<!DOCTYPE|<!ENTITY", re.IGNORECASE)

try:
    import yaml
except ImportError:  # pragma: no cover - exercised when PyYAML is absent
    yaml = None

try:
    from xml.etree import ElementTree as ET
except ImportError:  # pragma: no cover - ElementTree ships with CPython
    ET = None

try:
    import toml
except ImportError:  # pragma: no cover - exercised when toml is absent
    toml = None


class JSONParser(ParserAdapter):
    """Parse JSON files. No optional dependency required."""

    def can_parse(self) -> bool:
        """JSON parsing uses only the standard library."""
        return True

    def parse(self, file_path: str) -> dict[str, Any]:
        """Load JSON and derive a text rendering plus a field-path entity list."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "structured_data": data,
            "text_content": json.dumps(data, indent=2),
            "entities": self._extract_entities(data),
        }

    def get_schema(self) -> dict[str, Any]:
        """Declared output shape for JSON content."""
        return {"structured_data": "object", "text_content": "string", "entities": "array"}

    def _extract_entities(self, data: Any, path: str = "") -> list[dict[str, Any]]:
        """Walk the JSON structure, recording each key's path and type."""
        entities: list[dict[str, Any]] = []
        if isinstance(data, dict):
            for key, value in data.items():
                entities.append(
                    {
                        "name": key,
                        "type": type(value).__name__,
                        "path": f"{path}.{key}" if path else key,
                        "confidence": 0.95,
                    }
                )
                if isinstance(value, (dict, list)):
                    entities.extend(self._extract_entities(value, f"{path}.{key}"))
        elif isinstance(data, list):
            for idx, item in enumerate(data[: self.limits.max_json_list_items]):
                if isinstance(item, dict):
                    entities.extend(self._extract_entities(item, f"{path}[{idx}]"))
        return entities


class CSVParser(ParserAdapter):
    """Parse CSV files. No optional dependency required."""

    def can_parse(self) -> bool:
        """CSV parsing uses only the standard library."""
        return True

    def parse(self, file_path: str) -> dict[str, Any]:
        """Read all rows via `csv.DictReader` and summarize by column."""
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)

        return {
            "structured_data": {"headers": headers, "rows": rows, "row_count": len(rows)},
            "text_content": self._to_text(rows, headers),
            "entities": self._extract_entities(rows, headers),
        }

    def get_schema(self) -> dict[str, Any]:
        """Declared output shape for CSV content."""
        return {
            "structured_data": {"headers": "array", "rows": "array", "row_count": "number"},
            "text_content": "string",
            "entities": "array",
        }

    def _to_text(self, rows: list[dict[str, Any]], headers: list[str]) -> str:
        """Render a bounded plain-text preview of the CSV."""
        lines = [",".join(headers)]
        for row in rows[: self.limits.max_csv_preview_rows]:
            lines.append(",".join(str(row.get(h, "")) for h in headers))
        return "\n".join(lines)

    def _extract_entities(
        self, rows: list[dict[str, Any]], headers: list[str]
    ) -> list[dict[str, Any]]:
        """Summarize each column as an entity with its distinct-value count."""
        entities: list[dict[str, Any]] = []
        for header in headers:
            values = [row.get(header) for row in rows if row.get(header)]
            entities.append(
                {
                    "name": header,
                    "type": "column",
                    "value_count": len(set(values)) if values else 0,
                    "confidence": 0.95,
                }
            )
        return entities


class YAMLParser(ParserAdapter):
    """Parse YAML files. Requires the optional `PyYAML` dependency."""

    def can_parse(self) -> bool:
        """Only usable when PyYAML is installed."""
        return yaml is not None

    def parse(self, file_path: str) -> dict[str, Any]:
        """Load YAML via `yaml.safe_load` and re-render it as text."""
        if yaml is None:
            raise ImportError(
                "PyYAML not installed. Install with: pip install 'nlke-universal-parser[yaml]'"
            )
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return {
            "structured_data": data or {},
            "text_content": yaml.dump(data, default_flow_style=False),
            "entities": self._extract_entities(data),
        }

    def get_schema(self) -> dict[str, Any]:
        """Declared output shape for YAML content."""
        return {"structured_data": "object", "text_content": "string", "entities": "array"}

    def _extract_entities(self, data: Any) -> list[dict[str, Any]]:
        """Record each top-level key as a field entity."""
        entities: list[dict[str, Any]] = []
        if isinstance(data, dict):
            for key in data.keys():
                entities.append({"name": key, "type": "field", "confidence": 0.95})
        return entities


class XMLParser(ParserAdapter):
    """Parse XML files. Uses the standard library's `xml.etree`."""

    def can_parse(self) -> bool:
        """`xml.etree.ElementTree` ships with CPython; this is effectively always True."""
        return ET is not None

    def parse(self, file_path: str) -> dict[str, Any]:
        """Parse the XML tree into a nested dict plus a bounded tag entity list.

        Refuses any document that declares a DTD or entities: the standard
        library's ElementTree expands internal entities without limit, so a
        crafted file ('billion laughs') could exhaust memory. Refusing is
        on-brand for this package -- it never trades safety for a guess.
        """
        if ET is None:
            raise ImportError("XML parsing not available in this Python build")

        with open(file_path, "rb") as f:
            raw = f.read()
        if _XML_DTD_PATTERN.search(raw):
            raise UnsafeContentRefusal(
                "XML declares a DTD or entities (<!DOCTYPE/<!ENTITY>); refusing to "
                "parse it to avoid unbounded entity expansion ('billion laughs') "
                "resource exhaustion."
            )

        root = ET.fromstring(raw)
        return {
            "structured_data": self._element_to_dict(root),
            "text_content": ET.tostring(root, encoding="unicode"),
            "entities": self._extract_entities(root)[: self.limits.max_xml_entities],
        }

    def get_schema(self) -> dict[str, Any]:
        """Declared output shape for XML content."""
        return {"structured_data": "object", "text_content": "string", "entities": "array"}

    def _element_to_dict(self, element: Any) -> dict[str, Any]:
        """Recursively convert an XML element into a plain dict."""
        return {
            "tag": element.tag,
            "attributes": element.attrib,
            "text": element.text.strip() if element.text else None,
            "children": [self._element_to_dict(child) for child in element],
        }

    def _extract_entities(self, element: Any, path: str = "") -> list[dict[str, Any]]:
        """Record each element tag, path, and attribute names as an entity."""
        current_path = f"{path}/{element.tag}"
        entities = [
            {
                "name": element.tag,
                "type": "element",
                "path": current_path,
                "attributes": list(element.attrib.keys()),
                "confidence": 0.95,
            }
        ]
        for child in element:
            entities.extend(self._extract_entities(child, current_path))
        return entities


class TOMLParser(ParserAdapter):
    """Parse TOML files. Requires the optional `toml` dependency."""

    def can_parse(self) -> bool:
        """Only usable when the `toml` package is installed."""
        return toml is not None

    def parse(self, file_path: str) -> dict[str, Any]:
        """Load TOML and re-render it as text."""
        if toml is None:
            raise ImportError(
                "toml not installed. Install with: pip install 'nlke-universal-parser[toml]'"
            )
        with open(file_path, "r", encoding="utf-8") as f:
            data = toml.load(f)
        return {
            "structured_data": data,
            "text_content": toml.dumps(data),
            "entities": self._extract_entities(data),
        }

    def get_schema(self) -> dict[str, Any]:
        """Declared output shape for TOML content."""
        return {"structured_data": "object", "text_content": "string", "entities": "array"}

    def _extract_entities(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Record each top-level key as a section or key entity."""
        entities: list[dict[str, Any]] = []
        for key, value in data.items():
            entities.append(
                {
                    "name": key,
                    "type": "section" if isinstance(value, dict) else "key",
                    "confidence": 0.95,
                }
            )
        return entities
