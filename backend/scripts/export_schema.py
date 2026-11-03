"""Write ``schema/intake.schema.json`` from the Pydantic model. Used by ``make export-schema``."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.intake.schema import IntakeRecord

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "schema" / "intake.schema.json"


def _require_all_properties(schema: dict[str, object]) -> None:
    """Serialisation always emits every key, so the schema requires every property."""
    definitions = schema.get("$defs")
    targets: list[dict[str, object]] = [schema]
    if isinstance(definitions, dict):
        targets.extend(value for value in definitions.values() if isinstance(value, dict))
    for target in targets:
        properties = target.get("properties")
        if isinstance(properties, dict) and properties:
            target["required"] = list(properties)


def render() -> str:
    schema = IntakeRecord.model_json_schema()
    _require_all_properties(schema)
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://intake.local/schema/intake.schema.json"
    schema["title"] = "IntakeRecord"
    # Exports carry a "$schema" pointer; allow it without requiring it.
    schema["properties"] = {"$schema": {"type": "string"}, **schema["properties"]}
    return json.dumps(schema, indent=2, sort_keys=False) + "\n"


def main(check: bool = False) -> int:
    content = render()
    if check:
        if not TARGET.exists() or TARGET.read_text() != content:
            print(f"{TARGET} is stale; run `make export-schema`", file=sys.stderr)
            return 1
        print("schema is fresh")
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(content)
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
