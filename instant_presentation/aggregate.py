"""Aggregate research deck generation across multiple transcript notes."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .brief import build_brief_file
from .i18n import detect_language_from_parts, normalize_language
from .llm import resolve_summary_engine, summarize_with_openai
from .models import SummaryDocument, TranscriptDocument
from .render import render_summary_file
from .summary import (
    build_summary_filename,
    extract_context_signals,
    infer_tone,
    parse_normalized_note,
    render_summary_markdown,
    summarize_transcript,
)

RESEARCH_SECTION_TITLES = [
    "Corpus Overview",
    "Repeated Pain Points",
    "Tool Signals",
    "Direction Patterns",
    "Audience / Talk Mix",
    "Evidence Highlights",
]

TOOL_PATTERNS = {
    "Obsidian": ("obsidian",),
    "Krisp": ("krisp",),
    "Claude Code": ("claude code",),
    "Claude": ("claude",),
    "ChatGPT": ("chatgpt",),
    "Cursor": ("cursor",),
    "Perplexity": ("perplexity",),
    "MCP": ("mcp",),
    "n8n": ("n8n",),
    "Granola": ("granola",),
    "Plaud": ("plaud",),
    "Zoom": ("zoom",),
    "Teams": ("teams", "microsoft teams"),
}


def build_research_from_notes(
    input_paths: list[Path],
    output_dir: Path,
    style: str = "editorial",
    project: str = "instant",
    context_notes: list[Path] | None = None,
    summary_engine: str = "auto",
    audience: str | None = None,
    tone: str | None = None,
) -> dict[str, Path]:
    """Build a corpus-level research deck from multiple transcript notes."""
    context_notes = context_notes or []
    summaries = summarize_note_paths(
        input_paths=input_paths,
        project=project,
        context_notes=context_notes,
        summary_engine=summary_engine,
        audience=audience,
        tone=tone,
    )
    aggregate_summary = aggregate_summaries(
        summaries=summaries,
        project=project,
        context_notes=context_notes,
        audience=audience,
        tone=tone,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / build_summary_filename(aggregate_summary)
    summary_path.write_text(render_summary_markdown(aggregate_summary), encoding="utf-8")
    brief_path = build_brief_file(
        input_path=summary_path,
        output_dir=output_dir,
        style=style,
    )
    deck_path = render_summary_file(
        input_path=brief_path,
        output_dir=output_dir,
        style=style,
    )
    manifest_path = write_research_manifest(
        output_dir=output_dir,
        input_paths=input_paths,
        summary_path=summary_path,
        brief_path=brief_path,
        deck_path=deck_path,
        style=style,
        context_notes=context_notes,
        summary_engine=summary_engine,
    )
    return {
        "summary": summary_path,
        "brief": brief_path,
        "deck": deck_path,
        "manifest": manifest_path,
    }


def summarize_note_paths(
    input_paths: list[Path],
    project: str,
    context_notes: list[Path],
    summary_engine: str,
    audience: str | None,
    tone: str | None,
) -> list[SummaryDocument]:
    """Summarize many normalized transcript notes into in-memory summary docs."""
    context_sources, context_signals = extract_context_signals(context_notes)
    engine = resolve_summary_engine(summary_engine)
    summaries: list[SummaryDocument] = []
    for input_path in input_paths:
        note_text = input_path.read_text(encoding="utf-8")
        transcript = parse_normalized_note(note_text=note_text, origin_file=input_path.name, project=project)
        if engine == "openai":
            try:
                summary = summarize_with_openai(
                    transcript=transcript,
                    context_notes=context_sources,
                    context_signals=context_signals,
                    presentation_goal="research",
                    audience=audience,
                    tone=tone,
                )
            except Exception:
                summary = summarize_transcript(
                    transcript,
                    context_notes=context_sources,
                    context_signals=context_signals,
                    presentation_goal="research",
                    audience=audience,
                    tone=tone,
                )
        else:
            summary = summarize_transcript(
                transcript,
                context_notes=context_sources,
                context_signals=context_signals,
                presentation_goal="research",
                audience=audience,
                tone=tone,
            )
        summaries.append(summary)
    return summaries


def aggregate_summaries(
    summaries: list[SummaryDocument],
    project: str,
    context_notes: list[Path],
    audience: str | None,
    tone: str | None,
) -> SummaryDocument:
    """Aggregate many summary docs into one research-style summary."""
    if not summaries:
        raise ValueError("aggregate_summaries requires at least one summary")

    language = normalize_language(
        detect_language_from_parts(
            *[summary.title for summary in summaries],
            *[item for summary in summaries for item in summary.themes[:3]],
        )
    )
    title = build_research_title(summaries)
    all_context = dedupe_items([item for summary in summaries for item in summary.context_signals])
    all_goals = dedupe_items([item for summary in summaries for item in summary.goals])
    all_themes = dedupe_items([item for summary in summaries for item in summary.themes])
    all_pains = [item for summary in summaries for item in summary.pain_points]
    all_decisions = [item for summary in summaries for item in summary.decisions]
    all_actions = [item for summary in summaries for item in summary.action_items]
    all_quotes = [item for summary in summaries for item in summary.quotes]

    meeting_counts = Counter(summary.meeting_type for summary in summaries)
    pain_counts = count_items(all_pains)
    decision_counts = count_items(all_decisions + all_actions)
    tool_counts = count_tool_mentions(summaries)

    overview = [
        f"Corpus size: {len(summaries)} notes",
        f"Date range: {min(summary.date for summary in summaries)} to {max(summary.date for summary in summaries)}",
        f"Distinct participants: {count_distinct_participants(summaries)}",
    ]
    repeated_pains = format_counter_items(pain_counts, fallback=all_themes[:4], limit=5)
    tool_signals = format_counter_items(tool_counts, fallback=all_context[:4], limit=5, value_suffix=" notes")
    direction_patterns = format_counter_items(decision_counts, fallback=all_goals[:4], limit=5)
    talk_mix = format_counter_items(meeting_counts, fallback=["business: no classified data"], limit=5, value_suffix=" notes")
    evidence_highlights = build_research_evidence(summaries)

    type_sections = {
        RESEARCH_SECTION_TITLES[0]: overview,
        RESEARCH_SECTION_TITLES[1]: repeated_pains,
        RESEARCH_SECTION_TITLES[2]: tool_signals,
        RESEARCH_SECTION_TITLES[3]: direction_patterns,
        RESEARCH_SECTION_TITLES[4]: talk_mix,
        RESEARCH_SECTION_TITLES[5]: evidence_highlights,
    }

    return SummaryDocument(
        title=title,
        date=max(summary.date for summary in summaries),
        project=project,
        source_note=f"{len(summaries)} notes",
        meeting_type="research",
        deck_mode="research-insights",
        participants=dedupe_items([participant for summary in summaries for participant in summary.participants])[:12],
        language=language,
        presentation_goal="research",
        audience=audience.strip() if audience else "internal product or strategy team",
        tone=tone.strip() if tone else infer_tone("research", "research"),
        context_notes=[path.name for path in context_notes],
        context_signals=all_context[:6],
        goals=overview,
        themes=all_themes[:6],
        pain_points=repeated_pains,
        objections=talk_mix[:4],
        decisions=direction_patterns,
        action_items=build_research_actions(summaries),
        quotes=all_quotes[:4] or evidence_highlights[:3],
        narrative=[
            "Frame the deck as corpus-level insight, not a recap of one conversation.",
            "Use repeated patterns only when they appear across multiple notes.",
            "Keep evidence visible so the audience can trust the aggregate claims.",
            "End with actions or hypotheses worth testing on the next corpus slice.",
        ],
        type_sections=type_sections,
        evidence_trails=evidence_highlights,
    )


def build_research_title(summaries: list[SummaryDocument]) -> str:
    """Build a compact title for the aggregate research summary."""
    projects = dedupe_items([summary.project for summary in summaries])
    if len(projects) == 1 and projects[0].lower() not in {"research", "instant"}:
        return f"{projects[0].title()} research digest"
    return "Research digest"


def dedupe_items(items: list[str]) -> list[str]:
    """Keep order while removing duplicates and blanks."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = " ".join(str(item).split()).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def normalize_counter_key(text: str) -> str:
    """Normalize extracted text before frequency counting."""
    cleaned = re.sub(r"\[[^\]]+\]\s*", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > 72:
        cleaned = cleaned[:69].rstrip() + "..."
    return cleaned


def count_items(items: list[str]) -> Counter[str]:
    """Count repeated extracted signals."""
    counter: Counter[str] = Counter()
    seen_in_doc: set[str] = set()
    for item in items:
        normalized = normalize_counter_key(item)
        if not normalized or normalized in seen_in_doc:
            continue
        counter[normalized] += 1
        seen_in_doc.add(normalized)
    return counter


def count_tool_mentions(summaries: list[SummaryDocument]) -> Counter[str]:
    """Count tool mentions across summaries using a small curated lexicon."""
    counter: Counter[str] = Counter()
    for summary in summaries:
        haystack = " ".join([
            summary.title,
            *summary.themes,
            *summary.context_signals,
            *summary.decisions,
            *summary.action_items,
            *summary.quotes,
        ]).lower()
        for label, patterns in TOOL_PATTERNS.items():
            if any(pattern in haystack for pattern in patterns):
                counter[label] += 1
    return counter


def format_counter_items(
    counter: Counter[str],
    fallback: list[str],
    limit: int,
    value_suffix: str = "",
) -> list[str]:
    """Format top counter entries into deck-safe bullets."""
    items = [f"{label} — {count}{value_suffix}" for label, count in counter.most_common(limit)]
    if items:
        return items
    return dedupe_items(fallback)[:limit] or ["None identified."]


def build_research_evidence(summaries: list[SummaryDocument]) -> list[str]:
    """Collect evidence trails with source-note labels."""
    evidence: list[str] = []
    seen: set[str] = set()
    for summary in summaries:
        source = summary.source_note
        for trail in summary.evidence_trails[:2]:
            item = f"{source}: {trail}"
            if item not in seen:
                evidence.append(item)
                seen.add(item)
            if len(evidence) >= 8:
                return evidence
    return evidence


def build_research_actions(summaries: list[SummaryDocument]) -> list[str]:
    """Suggest next research steps from the current corpus slice."""
    actions = [
        f"Review the {len(summaries)}-note slice with the strongest repeated pain points first.",
        "Validate whether the top recurring patterns hold on a larger corpus before turning them into strategy.",
        "Use the evidence highlights to pick 2-3 concrete slides worth sharing immediately.",
    ]
    return actions


def count_distinct_participants(summaries: list[SummaryDocument]) -> int:
    """Count unique named participants across summaries."""
    return len({participant for summary in summaries for participant in summary.participants})


def write_research_manifest(
    output_dir: Path,
    input_paths: list[Path],
    summary_path: Path,
    brief_path: Path,
    deck_path: Path,
    style: str,
    context_notes: list[Path],
    summary_engine: str,
) -> Path:
    """Write a manifest for the aggregate research build."""
    manifest_path = output_dir / "research-build-manifest.md"
    lines = [
        "# Research Build Manifest",
        "",
        f"- Input notes: `{len(input_paths)}`",
        f"- Aggregate summary note: `{summary_path}`",
        f"- Deck brief: `{brief_path}`",
        f"- Deck: `{deck_path}`",
        f"- Style: `{style}`",
        f"- Summary engine: `{summary_engine}`",
        "",
        "## Notes",
        "",
    ]
    lines.extend(f"- `{path}`" for path in input_paths)
    lines.extend(["", "## Context Notes", ""])
    if context_notes:
        lines.extend(f"- `{path}`" for path in context_notes)
    else:
        lines.append("- None")
    manifest_path.write_text("\n".join(lines), encoding="utf-8")
    return manifest_path
