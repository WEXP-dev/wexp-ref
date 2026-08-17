"""A deliberately small JSON Schema subset validator.

Classification: **SHARED-INFRASTRUCTURE-SAFE**

Profile data carries semantic variation, so it must be validated before any
engine reads it. Validation runs in the portable environment, which is
stdlib-only by design, so this implements exactly the subset the qualification
schemas use rather than taking a dependency:

``type``, ``properties``, ``required``, ``additionalProperties`` (boolean or
schema), ``items``, ``enum``, ``const``, ``pattern``, ``minItems``,
``maxItems``, ``uniqueItems``, ``minimum``, ``maximum``, ``propertyNames``,
``patternProperties``, ``$ref`` to ``#/$defs/<name>``.

Anything else in a schema is an error, not an ignored hint: silently skipping
an unrecognised keyword would make a schema look stricter than it is. Unknown
keywords therefore fail closed.
"""

from __future__ import annotations

import re
from typing import Any

SUPPORTED_KEYWORDS = frozenset(
    {
        "$defs",
        "$id",
        "$ref",
        "$schema",
        "additionalProperties",
        "const",
        "description",
        "enum",
        "items",
        "maxItems",
        "maximum",
        "minItems",
        "minimum",
        "patternProperties",
        "pattern",
        "properties",
        "propertyNames",
        "required",
        "title",
        "type",
        "uniqueItems",
    }
)

TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


class SchemaError(ValueError):
    """Raised when a schema itself is unusable."""


class ValidationError(ValueError):
    """Raised when an instance does not satisfy its schema."""


def _resolve(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    reference = schema.get("$ref")
    if reference is None:
        return schema
    if not isinstance(reference, str) or not reference.startswith("#/$defs/"):
        raise SchemaError(f"only #/$defs/<name> references are supported: {reference!r}")
    name = reference[len("#/$defs/") :]
    defs = root.get("$defs")
    if not isinstance(defs, dict) or name not in defs:
        raise SchemaError(f"unresolved reference: {reference}")
    resolved = defs[name]
    if not isinstance(resolved, dict):
        raise SchemaError(f"reference target is not a schema: {reference}")
    return resolved


def _check_keywords(schema: dict[str, Any], location: str) -> None:
    unknown = sorted(set(schema) - SUPPORTED_KEYWORDS)
    if unknown:
        raise SchemaError(f"{location}: unsupported schema keyword(s): {', '.join(unknown)}")


def _type_matches(value: Any, expected: str) -> bool:
    python_type = TYPE_MAP.get(expected)
    if python_type is None:
        raise SchemaError(f"unsupported type: {expected!r}")
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return isinstance(value, python_type)


def validate(instance: Any, schema: dict[str, Any], *, root: dict[str, Any] | None = None, location: str = "$") -> None:
    """Validate ``instance``; raise ``ValidationError`` on the first problem."""

    root = schema if root is None else root
    schema = _resolve(schema, root)
    _check_keywords(schema, location)

    if "type" in schema:
        expected = schema["type"]
        types = expected if isinstance(expected, list) else [expected]
        if not any(_type_matches(instance, item) for item in types):
            raise ValidationError(f"{location}: expected type {expected!r}, got {type(instance).__name__}")

    if "const" in schema and instance != schema["const"]:
        raise ValidationError(f"{location}: expected constant {schema['const']!r}")

    if "enum" in schema and instance not in schema["enum"]:
        raise ValidationError(f"{location}: {instance!r} is not one of {schema['enum']!r}")

    if isinstance(instance, str) and "pattern" in schema:
        if not re.fullmatch(schema["pattern"], instance):
            raise ValidationError(f"{location}: {instance!r} does not match {schema['pattern']!r}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise ValidationError(f"{location}: {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            raise ValidationError(f"{location}: {instance} > maximum {schema['maximum']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise ValidationError(f"{location}: expected at least {schema['minItems']} item(s)")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise ValidationError(f"{location}: expected at most {schema['maxItems']} item(s)")
        if schema.get("uniqueItems"):
            seen: list[Any] = []
            for item in instance:
                if item in seen:
                    raise ValidationError(f"{location}: duplicate item {item!r}")
                seen.append(item)
        if "items" in schema:
            for index, item in enumerate(instance):
                validate(item, schema["items"], root=root, location=f"{location}[{index}]")

    if isinstance(instance, dict):
        for name in schema.get("required", []):
            if name not in instance:
                raise ValidationError(f"{location}: missing required property {name!r}")
        properties = schema.get("properties", {})
        pattern_properties = schema.get("patternProperties", {})
        for name, value in instance.items():
            child = f"{location}.{name}"
            if "propertyNames" in schema:
                validate(name, schema["propertyNames"], root=root, location=f"{location} key {name!r}")
            if name in properties:
                validate(value, properties[name], root=root, location=child)
                continue
            matched = False
            for expression, subschema in pattern_properties.items():
                if re.fullmatch(expression, name):
                    validate(value, subschema, root=root, location=child)
                    matched = True
                    break
            if matched:
                continue
            additional = schema.get("additionalProperties", True)
            if additional is False:
                raise ValidationError(f"{location}: unexpected property {name!r}")
            if isinstance(additional, dict):
                validate(value, additional, root=root, location=child)
