"""Claude API-backed summary engine with adaptive slide planning."""

from __future__ import annotations

import importlib.util
import json
import os

from .i18n import normalize_language
from .llm import (
    build_source_note_name,
    coerce_string_list,
    coerce_string_map,
    format_list_block,
    summary_from_llm_payload,
)
from .models import SlidePlan, SummaryDocument, TranscriptDocument


def claude_available() -> bool:
    """Return whether Claude API credentials and SDK are available."""
    return bool(
        os.environ.get("ANTHROPIC_API_KEY")
        and importlib.util.find_spec("anthropic")
    )


def summarize_with_claude(
    transcript: TranscriptDocument,
    context_notes: list[str],
    context_signals: list[str],
    presentation_goal: str | None = None,
    audience: str | None = None,
    tone: str | None = None,
) -> SummaryDocument:
    """Call Claude API and return a SummaryDocument with an adaptive slide plan."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    model = os.environ.get("INSTANT_PRESENTATION_CLAUDE_MODEL", "claude-opus-4-6")
    prompt = _build_claude_prompt(
        transcript,
        context_notes,
        context_signals,
        presentation_goal=presentation_goal,
        audience=audience,
        tone=tone,
    )

    client = anthropic.Anthropic(api_key=api_key)

    with client.messages.stream(
        model=model,
        max_tokens=16000,
        thinking={"type": "enabled", "budget_tokens": 8000},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()

    output_text = ""
    for block in response.content:
        if block.type == "text":
            output_text += block.text

    if not output_text:
        raise RuntimeError("Claude response contained no text output")

    parsed = _extract_json(output_text)

    summary = summary_from_llm_payload(
        transcript=transcript,
        context_notes=context_notes,
        context_signals=context_signals,
        presentation_goal=presentation_goal,
        audience=audience,
        tone=tone,
        payload=parsed,
    )

    slide_plan_data = parsed.get("slide_plan")
    if isinstance(slide_plan_data, dict):
        summary.slide_plan = SlidePlan(
            slide_titles=coerce_string_list(slide_plan_data.get("slide_titles")),
            slide_goals=coerce_string_list(slide_plan_data.get("slide_goals")),
            section_inputs=coerce_string_map(slide_plan_data.get("section_inputs")),
        )

    return summary


def _extract_json(text: str) -> dict:
    """Extract JSON from Claude's response, handling markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.index("\n")
        text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[:-3].strip()
    return json.loads(text)


def _build_claude_prompt(
    transcript: TranscriptDocument,
    context_notes: list[str],
    context_signals: list[str],
    presentation_goal: str | None = None,
    audience: str | None = None,
    tone: str | None = None,
) -> str:
    """Build the two-phase extraction + slide planning prompt."""
    transcript_lines = []
    for segment in transcript.segments:
        speaker = segment.speaker or "Unknown"
        timestamp = segment.timestamp or "--:--"
        transcript_lines.append(f"[{timestamp}] {speaker}: {segment.text}")

    language = normalize_language(transcript.language)

    return f"""You are extracting a presentation-ready meeting summary from a transcript.
You will perform TWO tasks in a single JSON response.

Return JSON only. No markdown fences. No commentary outside JSON.

## TASK 1: Extract meeting content

Required JSON fields:
{{
  "meeting_type": "business|trading|lecture|ideas|social",
  "deck_mode": "client-followup|sales-recap|research-insights|internal-decision",
  "presentation_goal": "recap|follow_up|decision|pitch|research",
  "audience": "...",
  "tone": "clear|sharp|persuasive|insightful|warm",
  "goals": ["..."],
  "themes": ["..."],
  "pain_points": ["..."],
  "objections": ["..."],
  "decisions": ["..."],
  "action_items": ["..."],
  "topic_summaries": ["Category — concise takeaway"],
  "topic_categories": {{
    "Category": ["..."]
  }},
  "type_sections": {{
    "Section Title": ["..."]
  }},
  "evidence_trails": ["Section: [timestamp speaker] short supporting reference"],
  "quotes": ["\\"...\\" — speaker (timestamp)"],
  "narrative": ["..."]
}}

Extraction rules:
- Keep bullets concise: one idea per bullet, 8-18 words, <= 140 chars.
- Never truncate with ellipsis or half-sentences.
- Classify the conversation type by analyzing the actual discussion flow, not just keyword presence.
- If a person shares a personal story as context for a business point, classify as business, not social.
- Use only information supported by the transcript or provided context.
- Prefer concrete statements over abstract summaries.
- Do not output metadata lines (date/source/path/audience) as content bullets.
- Do not repeat near-identical bullets across arrays.
- Extract real decisions when present. Do not invent them.
- Quotes must be verbatim and include speaker plus timestamp when available.
- Fill type_sections with the 5 section blocks that match the detected talk type:
  - business: context, key decisions, blockers, action items, open questions
  - trading: market context, trade ideas/setups/tickers, risk management, macro/catalysts, watchlist/actions
  - lecture: topic/thesis, key facts, idea links, insights, further study
  - ideas: project intent, current state, design decisions, deferred/cut scope, path to MVP
  - social: what was discussed, news from the other person, recommendations, agreements, follow-up

## TASK 2: Plan adaptive slides

Add a "slide_plan" object to the JSON:
{{
  "slide_plan": {{
    "slide_titles": ["Title 1", "Title 2", ...],
    "slide_goals": ["Goal sentence for slide 1", ...],
    "section_inputs": {{
      "Title 1": ["grounded bullet 1", "grounded bullet 2", ...],
      "Title 2": ["...", "..."]
    }}
  }}
}}

Slide planning rules:
- Use 3 to 8 slides based on content density.
- Short focused call with 1-2 topics → 3 slides.
- Dense multi-topic session → 6-8 slides.
- Each slide title: 2-5 words.
- Each slide goal: 1 sentence describing what the audience should take away.
- Each slide: 2-6 grounded bullets in section_inputs, referencing actual transcript content.
- First slide = context/overview. Last slide = forward-looking actions or open questions.
- slide_titles and slide_goals arrays must have the same length.
- section_inputs keys must match slide_titles exactly.

## Metadata

Meeting title: {transcript.title}
Meeting date: {transcript.date}
Participants: {", ".join(transcript.participants) if transcript.participants else "unknown"}
Transcript source: {transcript.source}
Detected transcript language: {language}
Context note names: {", ".join(context_notes) if context_notes else "none"}
Requested presentation goal: {presentation_goal or "infer from transcript"}
Requested audience: {audience or "infer from transcript"}
Requested tone: {tone or "infer from transcript"}
Context signals:
{format_list_block(context_signals)}

## Language

Respond with all array items and slide content in the dominant transcript language: {language}.

## Transcript

{chr(10).join(transcript_lines)}""".strip()
