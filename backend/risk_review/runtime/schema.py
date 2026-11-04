"""JSON Schema (from Pydantic) to ``google.genai.types.Schema`` for explicit tool
declarations. Supports the subset the tool argument models use: objects, arrays, scalars,
enums, nullable unions and local ``$ref``s."""

from __future__ import annotations

from typing import Any

from google.genai import types

_TYPE_MAP: dict[str, types.Type] = {
    "object": types.Type.OBJECT,
    "array": types.Type.ARRAY,
    "string": types.Type.STRING,
    "integer": types.Type.INTEGER,
    "number": types.Type.NUMBER,
    "boolean": types.Type.BOOLEAN,
}


def _resolve(node: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        target = defs[ref.removeprefix("#/$defs/")]
        merged = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
        return _resolve(merged, defs)
    return node


def to_genai_schema(json_schema: dict[str, Any]) -> types.Schema:
    defs = dict(json_schema.get("$defs", {}))
    return _convert(json_schema, defs)


def _convert(node: dict[str, Any], defs: dict[str, Any]) -> types.Schema:
    node = _resolve(node, defs)
    nullable = False
    variants = node.get("anyOf") or node.get("oneOf")
    if isinstance(variants, list):
        non_null = [v for v in variants if v.get("type") != "null"]
        nullable = len(non_null) != len(variants)
        if len(non_null) == 1:
            inner = _convert({**non_null[0], "description": node.get("description")}, defs)
            inner.nullable = nullable
            return inner
        return types.Schema(
            type=types.Type.STRING, description=node.get("description"), nullable=nullable
        )
    type_name = node.get("type")
    if isinstance(type_name, list):
        nullable = "null" in type_name
        type_name = next((t for t in type_name if t != "null"), "string")
    schema = types.Schema(
        type=_TYPE_MAP.get(str(type_name), types.Type.STRING),
        description=node.get("description"),
        nullable=nullable or None,
    )
    if "enum" in node:
        schema.enum = [str(v) for v in node["enum"]]
        schema.type = types.Type.STRING
    if schema.type == types.Type.OBJECT:
        properties = node.get("properties", {})
        schema.properties = {name: _convert(sub, defs) for name, sub in properties.items()}
        required = node.get("required")
        if required:
            schema.required = list(required)
    if schema.type == types.Type.ARRAY and "items" in node:
        schema.items = _convert(node["items"], defs)
    return schema
