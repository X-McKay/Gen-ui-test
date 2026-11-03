"""The render repair restores the plan but respects the model's intro and foreign surfaces."""

from __future__ import annotations

import copy

from app.agents.render_repair import repair_operations
from app.agents.surface_plan import Step, build_operations, build_step
from app.intake.record_service import FieldUpdate, apply_updates, create_intake


def _step() -> Step:
    record = create_intake()
    apply_updates(
        record,
        [
            FieldUpdate(
                path="ai_system.uses_ai",
                value=True,
                source="inferred",
                confidence=0.9,
                confirmed=False,
            ),
            FieldUpdate(
                path="data.processes_personal_data",
                value=False,
                source="inferred",
                confidence=0.9,
                confirmed=False,
            ),
        ],
        policy="inferred",
    )
    return build_step(record, step_number=1, previous_surface_id=None)


def test_dropped_children_are_restored_and_intro_kept() -> None:
    step = _step()
    planned = build_operations(step)
    mangled = copy.deepcopy(planned)
    mangled[0]["createSurface"]["components"][0]["intro"] = "Here is what we found. Confirm it."
    mangled.pop()  # the model forgot updateComponents
    repaired = repair_operations({"target": "interview", "operations": mangled}, step)
    assert repaired is not None
    assert len(repaired["operations"]) == len(planned)
    assert (
        repaired["operations"][0]["createSurface"]["components"][0]["intro"]
        == "Here is what we found. Confirm it."
    )
    assert repaired["operations"][1] == planned[1]


def test_long_or_chatty_intro_falls_back_to_the_plan() -> None:
    step = _step()
    mangled = copy.deepcopy(build_operations(step))
    mangled[0]["createSurface"]["components"][0]["intro"] = "One. Two. Three sentences is too many."
    repaired = repair_operations({"target": "interview", "operations": mangled[:1]}, step)
    assert repaired is not None
    assert repaired["operations"][0]["createSurface"]["components"][0]["intro"] == step.intro


def test_identical_plan_needs_no_repair() -> None:
    step = _step()
    assert (
        repair_operations({"target": "interview", "operations": build_operations(step)}, step)
        is None
    )


def test_foreign_surfaces_and_targets_are_left_alone() -> None:
    step = _step()
    fixture = [
        {
            "version": "1.0",
            "createSurface": {
                "surfaceId": "step-1-invalid",
                "components": [{"id": "root", "component": "Marquee"}],
            },
        }
    ]
    assert repair_operations({"target": "interview", "operations": fixture}, step) is None
    assert (
        repair_operations({"target": "chat", "operations": build_operations(step)[:1]}, step)
        is None
    )
    assert repair_operations({"target": "interview", "operations": "nope"}, step) is None


def test_empty_operations_ask_the_server_to_render_the_plan() -> None:
    step = _step()
    repaired = repair_operations({"target": "interview", "operations": []}, step)
    assert repaired == {"target": "interview", "operations": build_operations(step)}
