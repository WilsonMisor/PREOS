#!/usr/bin/env python3
"""Dependency-free validator for the JSON-Schema subset used by PREOS runtime files.

PREOS runtime recovery must validate persisted JSON against its owned schemas
without requiring a network/package install during an interrupted-session drill.
This intentionally supports the schema keywords PREOS uses: type, required,
properties, enum, pattern, minimum, items, uniqueItems, additionalProperties,
$ref into local #/$defs, oneOf, and anyOf.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


class SchemaValidationError(ValueError):
    pass


def _type_ok(value: Any, kind: str) -> bool:
    if kind == "object": return isinstance(value, dict)
    if kind == "array": return isinstance(value, list)
    if kind == "string": return isinstance(value, str)
    if kind == "integer": return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number": return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "boolean": return isinstance(value, bool)
    if kind == "null": return value is None
    return True


def _resolve_ref(root: dict, ref: str) -> dict:
    if not ref.startswith("#/"):
        raise SchemaValidationError(f"unsupported external schema reference: {ref}")
    node: Any = root
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or token not in node:
            raise SchemaValidationError(f"unresolvable schema reference: {ref}")
        node = node[token]
    if not isinstance(node, dict):
        raise SchemaValidationError(f"schema reference does not resolve to object: {ref}")
    return node


def validate_instance(instance: Any, schema: dict, *, root_schema: dict | None = None, path: str = "$") -> None:
    root = root_schema or schema
    if "$ref" in schema:
        validate_instance(instance, _resolve_ref(root, str(schema["$ref"])), root_schema=root, path=path)
        return
    if "oneOf" in schema:
        matches = 0
        failures = []
        for option in schema["oneOf"]:
            try:
                validate_instance(instance, option, root_schema=root, path=path)
                matches += 1
            except SchemaValidationError as exc:
                failures.append(str(exc))
        if matches != 1:
            raise SchemaValidationError(f"{path}: oneOf matched {matches} schemas")
        return
    if "anyOf" in schema:
        for option in schema["anyOf"]:
            try:
                validate_instance(instance, option, root_schema=root, path=path)
                return
            except SchemaValidationError:
                pass
        raise SchemaValidationError(f"{path}: anyOf matched no schema")

    if "enum" in schema and instance not in schema["enum"]:
        raise SchemaValidationError(f"{path}: {instance!r} is not in enum {schema['enum']!r}")

    types = schema.get("type")
    if types is not None:
        allowed = [types] if isinstance(types, str) else list(types)
        if not any(_type_ok(instance, str(kind)) for kind in allowed):
            raise SchemaValidationError(f"{path}: wrong type; expected {allowed}")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < int(schema["minLength"]):
            raise SchemaValidationError(f"{path}: string shorter than minLength")
        if "maxLength" in schema and len(instance) > int(schema["maxLength"]):
            raise SchemaValidationError(f"{path}: string longer than maxLength")
        if "pattern" in schema and not re.search(str(schema["pattern"]), instance):
            raise SchemaValidationError(f"{path}: string does not match pattern")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise SchemaValidationError(f"{path}: value below minimum")
        if "maximum" in schema and instance > schema["maximum"]:
            raise SchemaValidationError(f"{path}: value above maximum")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < int(schema["minItems"]):
            raise SchemaValidationError(f"{path}: too few items")
        if "maxItems" in schema and len(instance) > int(schema["maxItems"]):
            raise SchemaValidationError(f"{path}: too many items")
        if schema.get("uniqueItems"):
            fingerprints = [json.dumps(v, sort_keys=True, ensure_ascii=False) for v in instance]
            if len(fingerprints) != len(set(fingerprints)):
                raise SchemaValidationError(f"{path}: duplicate array items")
        if isinstance(schema.get("items"), dict):
            for idx, value in enumerate(instance):
                validate_instance(value, schema["items"], root_schema=root, path=f"{path}[{idx}]")

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                raise SchemaValidationError(f"{path}: missing required property {key}")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, value in instance.items():
                if key in properties:
                    validate_instance(value, properties[key], root_schema=root, path=f"{path}.{key}")
                elif schema.get("additionalProperties") is False:
                    raise SchemaValidationError(f"{path}: unexpected property {key}")
                elif isinstance(schema.get("additionalProperties"), dict):
                    validate_instance(value, schema["additionalProperties"], root_schema=root, path=f"{path}.{key}")


def load_schema(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SchemaValidationError(f"schema is not an object: {path}")
    return data


def validate_file(path: Path, schema_path: Path) -> Any:
    try:
        instance = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(f"invalid JSON {path}: {exc}") from exc
    schema = load_schema(schema_path)
    validate_instance(instance, schema, root_schema=schema, path=str(path))
    return instance
