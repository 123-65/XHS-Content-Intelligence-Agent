from collections.abc import Mapping
from typing import Any


COMMENT_RULES: dict[str, tuple[str, ...]] = {
    "ROUTE": ("route", "roadmap", "\u8def\u7ebf", "\u987a\u5e8f", "\u600e\u4e48\u5b66"),
    "RESOURCE": ("resource", "template", "\u8d44\u6599", "\u8d44\u6e90", "\u6e05\u5355"),
    "PROJECT": ("project", "portfolio", "\u9879\u76ee", "\u5b9e\u6218", "\u6848\u4f8b"),
    "SOURCE_CODE": ("source code", "github", "\u6e90\u7801", "\u4ee3\u7801", "\u4ed3\u5e93"),
    "PRICE": ("price", "cost", "\u4ef7\u683c", "\u591a\u5c11\u94b1", "\u8d39\u7528"),
    "COURSE": ("course", "lesson", "\u8bfe\u7a0b", "\u6559\u5b66", "\u8bad\u7ec3\u8425"),
    "CONSULTATION": ("consult", "\u54a8\u8be2", "\u79c1\u4fe1", "\u8054\u7cfb"),
    "ANXIETY": ("anxious", "too late", "\u7126\u8651", "\u6765\u5f97\u53ca", "\u96f6\u57fa\u7840"),
    "MARKETING_RESISTANCE": ("scam", "ad", "\u5e7f\u544a", "\u9a97\u4eba", "\u5957\u8def"),
}

COMMENT_PRIORITY: tuple[str, ...] = (
    "SOURCE_CODE",
    "PRICE",
    "CONSULTATION",
    "COURSE",
    "RESOURCE",
    "ROUTE",
    "PROJECT",
    "ANXIETY",
    "MARKETING_RESISTANCE",
)

RISK_PHRASES: tuple[str, ...] = (
    "\u4fdd offer",
    "\u4fdd\u8bc1\u6da8\u7c89",
    "\u4fdd\u8bc1\u6210\u4ea4",
    "\u7a33\u8d5a",
    "\u6708\u5165",
    "\u5fc5\u987b\u8bc4\u8bba",
    "\u8bc4\u8bba\u533a\u6263",
    "\u771f\u5b9e\u5b66\u5458\u6848\u4f8b",
)

MCP_DENY_ACTIONS: tuple[str, ...] = (
    "auto_like",
    "auto_comment",
    "auto_follow",
    "auto_dm",
    "bypass_captcha",
    "risk_control_bypass",
    "account_pool",
    "proxy_pool",
)


def classify_comment(text: str) -> str:
    """Classify one comment with deterministic keyword rules."""
    normalized = text.lower()
    return next(
        (
            demand_type
            for demand_type in COMMENT_PRIORITY
            for keywords in [COMMENT_RULES[demand_type]]
            if any(keyword.lower() in normalized for keyword in keywords)
        ),
        "UNKNOWN",
    )


def find_risk_phrases(payload: Any) -> list[str]:
    """Find prohibited risk phrases in a nested payload."""
    text = _flatten_text(payload).lower()
    return [phrase for phrase in RISK_PHRASES if phrase.lower() in text]


def is_mcp_action_allowed(tool_name: str, action: str, payload: Mapping[str, Any] | None = None) -> tuple[bool, str | None]:
    """Check whether an MCP tool action stays inside the allowed boundary."""
    text = " ".join([tool_name, action, _flatten_text(payload or {})]).lower()
    denied = [item for item in MCP_DENY_ACTIONS if item in text]
    if denied:
        return False, f"Denied MCP action: {', '.join(denied)}"
    return True, None


def validate_min_json_schema(instance: Any, schema: Mapping[str, Any]) -> list[str]:
    """Validate the common JSON Schema subset used by prompt outputs."""
    return _validate_node(instance, schema, "$", schema)


def _flatten_text(payload: Any) -> str:
    """Flatten nested text-like payload values into one searchable string."""
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, Mapping):
        return " ".join(_flatten_text(value) for value in payload.values())
    if isinstance(payload, list | tuple | set):
        return " ".join(_flatten_text(value) for value in payload)
    return str(payload)


def _validate_node(value: Any, schema: Mapping[str, Any], path: str, root_schema: Mapping[str, Any]) -> list[str]:
    """Recursively validate a JSON Schema node."""
    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], root_schema)

    if "anyOf" in schema:
        nested_errors = [_validate_node(value, item, path, root_schema) for item in schema["anyOf"]]
        if any(not errors for errors in nested_errors):
            return []
        return [f"{path} did not match anyOf"]

    expected_type = schema.get("type")
    type_errors = _validate_type(value, expected_type, path)
    if type_errors:
        return type_errors

    enum_values = schema.get("enum")
    if enum_values is not None and value not in enum_values:
        return [f"{path} must be one of {enum_values}"]

    errors: list[str] = []
    if expected_type == "object" and isinstance(value, Mapping):
        required = schema.get("required", [])
        errors.extend(f"{path}.{field} is required" for field in required if field not in value)
        properties = schema.get("properties", {})
        for key, child_schema in properties.items():
            if key in value:
                errors.extend(_validate_node(value[key], child_schema, f"{path}.{key}", root_schema))

    if expected_type == "array" and isinstance(value, list):
        min_items = schema.get("minItems")
        if min_items is not None and len(value) < min_items:
            errors.append(f"{path} must contain at least {min_items} items")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                errors.extend(_validate_node(item, item_schema, f"{path}[{index}]", root_schema))

    min_length = schema.get("minLength")
    if isinstance(value, str) and min_length is not None and len(value) < min_length:
        errors.append(f"{path} length must be >= {min_length}")

    return errors


def _resolve_ref(ref: str, root_schema: Mapping[str, Any]) -> Mapping[str, Any]:
    """Resolve a local JSON Schema reference."""
    if not ref.startswith("#/"):
        return {}
    node: Any = root_schema
    for part in ref[2:].split("/"):
        node = node.get(part, {}) if isinstance(node, Mapping) else {}
    return node if isinstance(node, Mapping) else {}


def _validate_type(value: Any, expected_type: str | None, path: str) -> list[str]:
    """Validate a JSON Schema primitive type."""
    validators = {
        "object": lambda item: isinstance(item, Mapping),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, int | float) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    if expected_type is None:
        return []
    validator = validators.get(expected_type)
    if validator is None or validator(value):
        return []
    return [f"{path} must be {expected_type}"]
