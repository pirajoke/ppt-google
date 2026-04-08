"""Core data models for transcript processing."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TranscriptSegment:
    """One transcript utterance with optional timestamp and speaker."""

    timestamp: str | None
    speaker: str | None
    text: str


@dataclass
class TranscriptDocument:
    """Canonical transcript representation used across the pipeline."""

    title: str
    source: str
    date: str
    participants: list[str]
    language: str
    origin_file: str
    project: str
    status: str = "normalized"
    segments: list[TranscriptSegment] = field(default_factory=list)
    key_points: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)


@dataclass
class SummaryDocument:
    """Structured summary derived from a normalized transcript."""

    title: str
    date: str
    project: str
    source_note: str
    meeting_type: str
    deck_mode: str
    participants: list[str]
    language: str = "en"
    presentation_goal: str = "recap"
    audience: str = "mixed stakeholders"
    tone: str = "clear"
    context_notes: list[str] = field(default_factory=list)
    context_signals: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)
    pain_points: list[str] = field(default_factory=list)
    objections: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    quotes: list[str] = field(default_factory=list)
    narrative: list[str] = field(default_factory=list)
    topic_summaries: list[str] = field(default_factory=list)
    topic_categories: dict[str, list[str]] = field(default_factory=dict)
    type_sections: dict[str, list[str]] = field(default_factory=dict)
    evidence_trails: list[str] = field(default_factory=list)
    slide_plan: SlidePlan | None = None


@dataclass
class SlidePlan:
    """Adaptive slide plan produced by an LLM engine."""

    slide_titles: list[str] = field(default_factory=list)
    slide_goals: list[str] = field(default_factory=list)
    section_inputs: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class DeckBriefDocument:
    """Intermediate deck brief used before final HTML rendering."""

    title: str
    date: str
    project: str
    source_summary: str
    deck_style: str
    slide_count: int
    deck_mode: str
    meeting_type: str
    audience: str
    language: str = "en"
    presentation_goal: str = "recap"
    tone: str = "clear"
    slide_titles: list[str] = field(default_factory=list)
    slide_goals: list[str] = field(default_factory=list)
    topic_summaries: list[str] = field(default_factory=list)
    section_inputs: dict[str, list[str]] = field(default_factory=dict)
    context_items: list[str] = field(default_factory=list)
    pains: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    objections: list[str] = field(default_factory=list)
    quotes: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
