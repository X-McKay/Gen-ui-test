"""JSON export for the planted fixture: only record and assessment."""

from __future__ import annotations

import json


def export_json(record: dict[str, object], assessment: dict[str, object]) -> str:
    return json.dumps({"record": record, "assessment": assessment}, indent=2)  # DECOY EXP-D1
