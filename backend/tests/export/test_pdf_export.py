"""The HTML form shows labels and display values only; the PDF is a real PDF document."""

from __future__ import annotations

import re

import pytest

from app.export.pdf_export import (
    CONTROL_STATUS_LABELS,
    RISK_TIER_CSS_CLASS,
    TIER_INFO,
    build_form_context,
    control_label,
    export_pdf_bytes,
    render_form_html,
    risk_lens_rows,
)
from app.intake.question_bank import QUESTIONS_BY_FIELD
from app.intake.schema import (
    ControlEffect,
    EuAiActClassification,
    IntakeRecord,
    RiskDriver,
    RiskLens,
    RiskProfile,
    RiskTier,
)


def risk_section(html: str) -> str:
    return html.split("Inherent and residual risk</h2>", 1)[1].split(">Project</h2>", 1)[0]


def test_html_header_and_classification(high_risk_record: IntakeRecord) -> None:
    html = render_form_html(high_risk_record)
    assert html.startswith("<!DOCTYPE html>")
    assert '<html lang="en">' in html
    assert "Candidate summary assistant" in html
    assert high_risk_record.meta.intake_id in html
    assert "Existing project" in html
    assert "https://github.com/example/candidate-screener" in html
    assert "Questions asked" in html
    assert "EU AI Act: High risk" in html
    assert 'data-tier="high_risk"' in html
    assert "4. Employment and workers management" in html
    assert 'data-risk-tier="high"' in html
    assert "EU AI Act, GDPR" in html


def test_html_contains_labels_and_display_values(high_risk_record: IntakeRecord) -> None:
    html = render_form_html(high_risk_record)
    for section in ("Project", "AI system", "Data", "Use case"):
        assert f">{section}</h2>" in html
    assert "Project name" in html
    assert "Talent Ops" in html
    assert "Lifecycle stage" in html and ">Pilot<" in html
    assert "Model source" in html and "Third-party API" in html
    assert "Recommends, a person decides" in html
    assert "Employees or candidates, Minors" in html
    assert "HR and employment" in html
    assert "Interacts with people" in html and ">No<" in html
    # The raw enum values never leak into the form.
    assert "third_party_api" not in html
    assert "hr_employment" not in re.sub(r"data-field=\"[^\"]*\"", "", html)


def test_html_answers_include_controls_section_as_labels(
    high_risk_record: IntakeRecord,
) -> None:
    html = render_form_html(high_risk_record)
    assert ">Controls</h2>" in html
    controls = html.split(">Controls</h2>", 1)[1].split("Why this classification", 1)[0]
    assert "Controls in place" in controls
    assert "Access controls, Input and output guardrails" in controls
    assert "access_controls" not in re.sub(r"data-[a-z]+=\"[^\"]*\"", "", controls)
    sections = build_form_context(high_risk_record)["sections"]
    assert isinstance(sections, list)
    assert [section["key"] for section in sections][-1] == "controls"


def test_html_never_shows_provenance(high_risk_record: IntakeRecord) -> None:
    rendered = render_form_html(high_risk_record)
    html = rendered.lower()
    assert "confidence" not in html
    assert "repo:requirements.txt" not in html
    assert "repo:app/auth.py" not in html
    assert "inferred" not in html
    assert "0.95" not in html and "0.7" not in html
    # Only the risk section says whether a control is confirmed; that is an assessment
    # outcome, not a field's provenance. The rest of the form body never carries it.
    body = rendered.split("<body>", 1)[1]
    assert "confirmed" not in body.replace(risk_section(body), "").lower()


def test_html_skips_unset_fields_and_marks_unknown(high_risk_record: IntakeRecord) -> None:
    html = render_form_html(high_risk_record)
    assert "Retention policy" not in html
    assert "Business unit" not in html
    assert 'class="unknown">Not sure<' in html


def test_html_appendix_lists_unknown_fields(high_risk_record: IntakeRecord) -> None:
    html = render_form_html(high_risk_record)
    appendix = html.split("Appendix: Open questions", 1)[1]
    assert "Special-category data" in appendix
    assert "data.special_category_data" in appendix
    assert QUESTIONS_BY_FIELD["data.special_category_data"].prompt in appendix


def test_html_appendix_says_none_when_nothing_is_unknown(empty_record: IntakeRecord) -> None:
    html = render_form_html(empty_record)
    appendix = html.split("Appendix: Open questions", 1)[1]
    assert "<p>None</p>" in appendix
    assert "Untitled project" in html
    assert "No answers recorded for this section." in html


def test_html_rationale_obligations_and_next_steps(high_risk_record: IntakeRecord) -> None:
    html = render_form_html(high_risk_record)
    assert "Why this classification" in html
    assert "Recruitment and worker-management systems are high-risk." in html
    assert "EU AI Act Art. 6(2), Annex III 4" in html
    assert "Based on: Domains — HR and employment" in html
    obligations = html.split("Obligations</h2>", 1)[1].split("Recommended next steps", 1)[0]
    assert obligations.index("<h3>EU AI Act</h3>") < obligations.index("<h3>GDPR</h3>")
    assert "Register the system in the EU database before deployment." in obligations
    assert "Art. 49" in obligations and ">provider<" in obligations
    assert "Book a review with the governance team." in html


def test_html_escapes_user_text(empty_record: IntakeRecord) -> None:
    empty_record.set_field(
        "project.name", "<script>alert(1)</script>", source="user", confidence=1.0, confirmed=True
    )
    html = render_form_html(empty_record)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_risk_profile_context_with_drivers_and_mixed_controls(
    high_risk_record: IntakeRecord,
) -> None:
    context = build_form_context(high_risk_record)
    assert context["inherent_risk"] == {
        "key": "inherent",
        "label": "Inherent risk",
        "tier": "high",
        "tier_label": "High",
        "css_class": "tier-high-risk",
        "score": 10,
        "floor": None,
        "floor_reason": None,
    }
    assert context["residual_risk"] == {
        "key": "residual",
        "label": "Residual risk",
        "tier": "medium",
        "tier_label": "Medium",
        "css_class": "tier-limited",
        "score": 8,
        "floor": "medium",
        "floor_reason": "Annex III obligations remain whatever controls are in place",
    }
    drivers = context["risk_drivers"]
    assert isinstance(drivers, list)
    assert [driver["points"] for driver in drivers] == [1, 2, 2, 3, 2]
    assert drivers[0] == {
        "field": "ai_system.autonomy_level",
        "label": "Autonomy",
        "value": "Recommends, a person decides",
        "category": "Autonomy",
        "points": 1,
        "text": "It recommends; a person decides",
    }
    assert drivers[2]["value"] == "Employees or candidates, Minors"
    assert drivers[4]["label"] == "Domains" and drivers[4]["value"] == "HR and employment"
    controls = context["risk_controls"]
    assert isinstance(controls, list)
    assert [(row["label"], row["status_label"], row["points"]) for row in controls] == [
        ("Human oversight", "Confirmed", 2),
        ("Input and output guardrails", "Claimed, not confirmed", 0),
        ("Personal data minimisation", "Not in place", 0),
        ("Access controls", "Claimed, not confirmed", 0),
        ("Vendor data protections", "Not answered", 0),
    ]
    assert controls[0]["text"] == "A person reviews or can override outputs"
    assert {row["status"] for row in controls} == set(CONTROL_STATUS_LABELS)


def test_risk_profile_context_for_record_without_profiles(empty_record: IntakeRecord) -> None:
    context = build_form_context(empty_record)
    inherent = context["inherent_risk"]
    residual = context["residual_risk"]
    assert isinstance(inherent, dict) and isinstance(residual, dict)
    for profile in (inherent, residual):
        assert profile["tier"] == "low"
        assert profile["tier_label"] == "Low"
        assert profile["css_class"] == RISK_TIER_CSS_CLASS[RiskTier.LOW]
        assert profile["score"] == 0
        assert profile["floor"] is None and profile["floor_reason"] is None
    assert context["risk_drivers"] == []
    assert context["risk_controls"] == []
    assert context["risk_lenses"] == []


def test_risk_lens_context_rows(high_risk_record: IntakeRecord) -> None:
    rows = build_form_context(high_risk_record)["risk_lenses"]
    assert isinstance(rows, list)
    assert [row["lens"] for row in rows] == ["data_privacy", "financial", "regulatory"]
    assert [row["label"] for row in rows] == ["Data and privacy", "Financial", "Regulatory"]
    assert rows[0]["inherent"] == {
        "key": "data_privacy-inherent",
        "label": "Inherent",
        "tier": "medium",
        "tier_label": "Medium",
        "css_class": "tier-limited",
        "score": 4,
        "floor": None,
        "floor_reason": None,
    }
    assert rows[0]["drivers"] == "It processes personal data; Minors are among the data subjects"
    # A lens nothing counts towards: low, zero, and an em dash instead of an empty cell.
    assert rows[1]["inherent"]["tier"] == "low" and rows[1]["residual"]["score"] == 0
    assert rows[1]["drivers"] == "\u2014"
    assert rows[2]["inherent"]["tier"] == "high" and rows[2]["inherent"]["score"] == 7
    assert rows[2]["residual"]["tier"] == "medium" and rows[2]["residual"]["score"] == 5
    assert rows[2]["residual"]["floor"] == "medium"
    assert rows[2]["drivers"].count(";") == 2
    assert [row["residual"]["key"] for row in rows] == [
        "data_privacy-residual",
        "financial-residual",
        "regulatory-residual",
    ]


def test_risk_lens_rows_directly() -> None:
    assert risk_lens_rows([]) == []
    lens = RiskLens(
        lens="operational",
        label="Operational",
        inherent=RiskProfile(
            lens="operational",
            tier=RiskTier.CRITICAL,
            score=12,
            drivers=[
                RiskDriver(
                    field="ai_system.autonomy_level",
                    value="acts",
                    category="autonomy",
                    points=12,
                    text="It acts without a person in the loop",
                    lenses=["operational"],
                )
            ],
        ),
    )
    (row,) = risk_lens_rows([lens])
    assert row["inherent"]["css_class"] == RISK_TIER_CSS_CLASS[RiskTier.CRITICAL]
    assert row["inherent"]["tier_label"] == "Critical"
    assert row["residual"]["tier"] == "low" and row["residual"]["score"] == 0
    assert row["drivers"] == "It acts without a person in the loop"


def test_control_label_falls_back_for_unknown_controls() -> None:
    effect = ControlEffect(
        field="controls.in_place", control="not_an_option", status="absent", points=0, text="x"
    )
    assert control_label(effect) == "Not an option"
    orphan = ControlEffect(
        field="nowhere.at_all", control="nothing", status="unknown", points=0, text="x"
    )
    assert control_label(orphan) == "Nothing"


def test_html_risk_section_follows_classification(high_risk_record: IntakeRecord) -> None:
    html = render_form_html(high_risk_record)
    classification_end = html.index("</section>", html.index('id="classification-heading"'))
    risk_start = html.index("Inherent and residual risk</h2>")
    assert classification_end < risk_start < html.index(">Project</h2>")
    section = risk_section(html)
    assert 'data-risk-profile="inherent"' in section and 'data-risk-profile="residual"' in section
    inherent, residual = section.split('data-risk-profile="residual"', 1)
    assert 'data-risk-tier="high"' in inherent and "Score <strong>10</strong>" in inherent
    assert "Floor:" not in inherent
    assert 'data-risk-tier="medium"' in residual and "Score <strong>8</strong>" in residual
    assert 'data-risk-floor="medium"' in residual
    assert "Floor: Annex III obligations remain whatever controls are in place." in residual
    panels = section.split("By lens</h3>", 1)[0]
    assert panels.count("risk-pill") == 2


def test_html_risk_lens_table(high_risk_record: IntakeRecord) -> None:
    section = risk_section(render_form_html(high_risk_record))
    # Placed after the two overall panels and before the drivers table.
    assert (
        section.index('data-risk-profile="residual"')
        < section.index("By lens</h3>")
        < section.index("Drivers</h3>")
    )
    table = section.split("By lens</h3>", 1)[1].split("Drivers</h3>", 1)[0]
    assert 'class="answers risk-lenses" aria-labelledby="risk-lenses-heading"' in table
    assert table.count("<tr data-lens=") == 3
    assert (
        table.index('data-lens="data_privacy"')
        < table.index('data-lens="financial"')
        < table.index('data-lens="regulatory"')
    )
    assert table.count("risk-pill") == 6
    rows = table.split("<tr data-lens=")[1:]
    privacy, financial, regulatory = rows
    assert '<th scope="row" class="lens">Data and privacy</th>' in privacy
    assert 'data-lens-profile="data_privacy-inherent"' in privacy
    assert 'data-lens-profile="data_privacy-residual"' in privacy
    assert privacy.count('data-risk-tier="medium">Medium</span><span class="lens-score">4<') == 2
    assert (
        '<td class="lens-drivers">It processes personal data; '
        "Minors are among the data subjects</td>" in privacy
    )
    assert financial.count('data-risk-tier="low">Low</span><span class="lens-score">0<') == 2
    assert '<td class="lens-drivers">\u2014</td>' in financial
    assert 'data-risk-tier="high">High</span><span class="lens-score">7<' in regulatory
    assert 'data-risk-tier="medium">Medium</span><span class="lens-score">5<' in regulatory
    assert regulatory.count("; ") == 2
    # Raw lens keys and field paths never leak into the visible text.
    assert "data_privacy" not in re.sub(r"data-[a-z-]+=\"[^\"]*\"", "", table)
    assert "use_case." not in table


def test_html_risk_lens_table_absent_without_lenses(empty_record: IntakeRecord) -> None:
    section = risk_section(render_form_html(empty_record))
    assert "By lens" not in section
    assert "risk-lenses" not in section
    assert "data-lens=" not in section


def test_html_risk_tables(high_risk_record: IntakeRecord) -> None:
    section = risk_section(render_form_html(high_risk_record))
    drivers = section.split("Drivers</h3>", 1)[1].split("Controls</h3>", 1)[0]
    assert drivers.count("<tr data-field=") == 5
    assert "It recommends; a person decides" in drivers
    assert "Autonomy — Recommends, a person decides" in drivers
    assert "Data subjects — Employees or candidates, Minors" in drivers
    assert '<td class="points">+3</td>' in drivers
    controls = section.split("Controls</h3>", 1)[1]
    assert controls.count("<tr data-field=") == 5
    assert 'data-control="ai_system.human_oversight" data-status="applied"' in controls
    assert 'data-control="guardrails" data-status="unconfirmed"' in controls
    assert 'data-control="pii_minimisation" data-status="absent"' in controls
    assert 'data-control="vendor_data_protections" data-status="unknown"' in controls
    assert ">Human oversight<" in controls
    assert ">Input and output guardrails<" in controls
    for label in CONTROL_STATUS_LABELS.values():
        assert f'<td class="status">{label}</td>' in controls
    assert controls.count('<td class="points">\u22122</td>') == 1
    assert controls.count('<td class="points">0</td>') == 4
    # Raw ControlKind values never leak into the visible text.
    assert "pii_minimisation" not in re.sub(r"data-[a-z]+=\"[^\"]*\"", "", controls)


def test_html_risk_section_empty_states(empty_record: IntakeRecord) -> None:
    section = risk_section(render_form_html(empty_record))
    assert section.count('data-risk-tier="low"') == 2
    assert section.count("Score <strong>0</strong>") == 2
    assert "No risk drivers: the answers given add no points." in section
    assert "No controls assessed." in section
    assert "<tr data-field=" not in section


def test_css_tier_variables_are_defined(high_risk_record: IntakeRecord) -> None:
    html = render_form_html(high_risk_record)
    for name in ("--tier-prohibited", "--tier-high-risk", "--tier-limited", "--tier-minimal"):
        assert f"{name}:" in html
    assert "@page" in html and 'counter(page) " of " counter(pages)' in html
    assert "size: A4" in html and "margin: 18mm" in html


@pytest.mark.parametrize("classification", list(EuAiActClassification))
def test_every_tier_has_badge_and_explanation(
    empty_record: IntakeRecord, classification: EuAiActClassification
) -> None:
    empty_record.assessment.eu_ai_act.classification = classification
    context = build_form_context(empty_record)
    tier = context["tier"]
    assert tier == TIER_INFO[classification]
    html = render_form_html(empty_record)
    assert f'data-tier="{classification.value}"' in html
    assert TIER_INFO[classification]["explanation"] in html
    assert TIER_INFO[classification]["css_class"] in html


def test_pdf_bytes(high_risk_record: IntakeRecord) -> None:
    pdf = export_pdf_bytes(high_risk_record)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2048
    assert b"%%EOF" in pdf[-64:]
