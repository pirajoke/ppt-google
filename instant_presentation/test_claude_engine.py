"""Tests for Claude engine integration."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from .brief import build_deck_brief
from .claude_engine import _extract_json, claude_available
from .llm import resolve_summary_engine
from .models import SlidePlan, SummaryDocument


# --- Engine resolution tests ---


def test_resolve_engine_explicit_claude():
    assert resolve_summary_engine("claude") == "claude"


def test_resolve_engine_explicit_heuristic():
    assert resolve_summary_engine("heuristic") == "heuristic"


def test_resolve_engine_explicit_openai():
    assert resolve_summary_engine("openai") == "openai"


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"})
@patch("importlib.util.find_spec", return_value=MagicMock())
def test_resolve_engine_auto_prefers_claude(mock_spec):
    assert resolve_summary_engine("auto") == "claude"


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test", "OPENAI_API_KEY": "sk-openai"})
@patch("importlib.util.find_spec", return_value=MagicMock())
def test_resolve_engine_auto_prefers_openai_when_both_keys_present(mock_spec):
    assert resolve_summary_engine("auto") == "openai"


@patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False)
@patch("instant_presentation.llm.claude_available", return_value=False)
def test_resolve_engine_auto_falls_back_to_openai(mock_claude):
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        assert resolve_summary_engine("auto") == "openai"


@patch("instant_presentation.llm.claude_available", return_value=False)
def test_resolve_engine_auto_falls_back_to_heuristic(mock_claude):
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        assert resolve_summary_engine("auto") == "heuristic"


# --- claude_available tests ---


@patch.dict(os.environ, {}, clear=True)
def test_claude_not_available_no_key():
    assert claude_available() is False


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"})
@patch("importlib.util.find_spec", return_value=None)
def test_claude_not_available_no_sdk(mock_spec):
    assert claude_available() is False


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"})
@patch("importlib.util.find_spec", return_value=MagicMock())
def test_claude_available_with_key_and_sdk(mock_spec):
    assert claude_available() is True


# --- JSON extraction tests ---


def test_extract_json_plain():
    result = _extract_json('{"key": "value"}')
    assert result == {"key": "value"}


def test_extract_json_with_fences():
    result = _extract_json('```json\n{"key": "value"}\n```')
    assert result == {"key": "value"}


def test_extract_json_invalid_raises():
    with pytest.raises(Exception):
        _extract_json("not json at all")


# --- SlidePlan passthrough in brief ---


def _make_summary(**kwargs) -> SummaryDocument:
    defaults = dict(
        title="Test Meeting",
        date="2026-03-20",
        project="test",
        source_note="test.md",
        meeting_type="business",
        deck_mode="client-followup",
        participants=["Alice", "Bob"],
        language="en",
        goals=["goal1"],
        themes=["theme1"],
        pain_points=["pain1"],
        decisions=["decision1"],
        action_items=["action1"],
        quotes=["quote1"],
        evidence_trails=["evidence1"],
    )
    defaults.update(kwargs)
    return SummaryDocument(**defaults)


def test_brief_uses_slide_plan_when_present():
    plan = SlidePlan(
        slide_titles=["Overview", "Key Findings", "Next Steps"],
        slide_goals=["Set context", "Share findings", "Align on actions"],
        section_inputs={
            "Overview": ["bullet1", "bullet2"],
            "Key Findings": ["finding1", "finding2"],
            "Next Steps": ["step1", "step2"],
        },
    )
    summary = _make_summary(slide_plan=plan)
    with patch.dict(os.environ, {"INSTANT_PRESENTATION_ENABLE_ADAPTIVE_SLIDE_PLAN": "1"}):
        brief = build_deck_brief(summary)

    assert brief.slide_titles == ["Overview", "Key Findings", "Next Steps"]
    assert brief.slide_goals == ["Set context", "Share findings", "Align on actions"]
    assert brief.section_inputs == plan.section_inputs
    assert brief.slide_count == 3


def test_brief_ignores_slide_plan_by_default():
    plan = SlidePlan(
        slide_titles=["Overview", "Key Findings", "Next Steps"],
        slide_goals=["Set context", "Share findings", "Align on actions"],
        section_inputs={"Overview": ["bullet1"]},
    )
    summary = _make_summary(slide_plan=plan)
    with patch.dict(os.environ, {}, clear=False):
        brief = build_deck_brief(summary)

    assert brief.slide_titles != plan.slide_titles
    assert brief.slide_count == len(brief.slide_titles)


def test_brief_falls_back_without_slide_plan():
    summary = _make_summary(slide_plan=None)
    brief = build_deck_brief(summary)

    # Should use choose_slide_plan() — exact titles depend on meeting_type
    assert len(brief.slide_titles) > 0
    assert brief.slide_count == len(brief.slide_titles)


# --- Response parsing test ---


def test_summary_from_llm_payload_with_slide_plan():
    from .llm import summary_from_llm_payload
    from .models import TranscriptDocument, TranscriptSegment

    transcript = TranscriptDocument(
        title="Test",
        source="krisp",
        date="2026-03-20",
        participants=["Alice"],
        language="en",
        origin_file="test.md",
        project="test",
        segments=[TranscriptSegment(timestamp="00:00", speaker="Alice", text="Hello")],
    )

    payload = {
        "meeting_type": "business",
        "deck_mode": "client-followup",
        "goals": ["Launch product"],
        "themes": ["product"],
        "pain_points": [],
        "decisions": ["Go with option A"],
        "action_items": ["Send proposal"],
        "quotes": [],
        "narrative": [],
        "topic_summaries": [],
        "topic_categories": {},
        "type_sections": {},
        "evidence_trails": [],
        "slide_plan": {
            "slide_titles": ["Context", "Decision", "Actions"],
            "slide_goals": ["Set scene", "Review", "Plan"],
            "section_inputs": {
                "Context": ["bullet"],
                "Decision": ["option A chosen"],
                "Actions": ["send proposal"],
            },
        },
    }

    summary = summary_from_llm_payload(
        transcript=transcript,
        context_notes=[],
        context_signals=[],
        presentation_goal=None,
        audience=None,
        tone=None,
        payload=payload,
    )

    # summary_from_llm_payload doesn't parse slide_plan — that's done in claude_engine
    # Verify the base fields are populated correctly
    assert summary.meeting_type == "business"
    assert summary.goals == ["Launch product"]
    assert summary.decisions == ["Go with option A"]
