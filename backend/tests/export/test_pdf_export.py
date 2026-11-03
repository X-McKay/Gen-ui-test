"""The HTML form shows labels and display values only; the PDF is a real PDF document."""

from __future__ import annotations

import re

import pytest

from app.export.pdf_export import (
    TIER_INFO,
    build_form_context,
    export_pdf_bytes,
    render_form_html,
)
from app.intake.question_bank import QUESTIONS_BY_FIELD
from app.intake.schema import EuAiActClassification, IntakeRecord


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


def test_html_never_shows_provenance(high_risk_record: IntakeRecord) -> None:
    html = render_form_html(high_risk_record).lower()
    assert "confidence" not in html
    assert "confirmed" not in html
    assert "repo:requirements.txt" not in html
    assert "inferred" not in html
    assert "0.95" not in html


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
