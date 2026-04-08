"""Optional OpenAI-backed extraction helpers."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from .i18n import normalize_language
from .models import SummaryDocument, TranscriptDocument

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


def _resolve_openai_responses_url() -> str:
    base_url = os.environ.get("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL).strip()
    if not base_url:
        base_url = DEFAULT_OPENAI_BASE_URL
    if base_url.endswith("/responses"):
        return base_url
    return base_url.rstrip("/") + "/responses"


def resolve_summary_engine(requested: str = "auto") -> str:
    """Resolve the summary engine based on the request and environment."""
    if requested == "heuristic":
        return "heuristic"
    if requested == "openai":
        return "openai"
    if requested == "claude":
        return "claude"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if claude_available():
        return "claude"
    return "heuristic"


def claude_available() -> bool:
    """Return whether Claude API credentials and SDK are available."""
    import importlib.util

    return bool(
        os.environ.get("ANTHROPIC_API_KEY")
        and importlib.util.find_spec("anthropic")
    )


def openai_available() -> bool:
    """Return whether OpenAI API credentials are available."""
    return bool(os.environ.get("OPENAI_API_KEY"))


def summarize_with_openai(
    transcript: TranscriptDocument,
    context_notes: list[str],
    context_signals: list[str],
    presentation_goal: str | None = None,
    audience: str | None = None,
    tone: str | None = None,
) -> SummaryDocument:
    """Call the OpenAI Responses API and convert the JSON output into a SummaryDocument."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    model = (
        os.environ.get("INSTANT_PRESENTATION_OPENAI_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or "gpt-5-mini"
    )
    prompt = build_openai_prompt(
        transcript,
        context_notes,
        context_signals,
        presentation_goal=presentation_goal,
        audience=audience,
        tone=tone,
    )
    payload = {
        "model": model,
        "input": prompt,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    base_url = os.environ.get("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL)
    if "openrouter.ai" in (base_url or ""):
        referer = os.environ.get("OPENROUTER_REFERER")
        title = os.environ.get("OPENROUTER_TITLE")
        if referer:
            headers["HTTP-Referer"] = referer
        if title:
            headers["X-Title"] = title

    request = urllib.request.Request(
        _resolve_openai_responses_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI request failed with HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI request failed: {exc.reason}") from exc

    data = json.loads(raw)
    output_text = data.get("output_text")
    if not output_text:
        raise RuntimeError("OpenAI response did not include output_text")

    parsed = json.loads(output_text)
    return summary_from_llm_payload(
        transcript=transcript,
        context_notes=context_notes,
        context_signals=context_signals,
        presentation_goal=presentation_goal,
        audience=audience,
        tone=tone,
        payload=parsed,
    )


def build_openai_prompt(
    transcript: TranscriptDocument,
    context_notes: list[str],
    context_signals: list[str],
    presentation_goal: str | None = None,
    audience: str | None = None,
    tone: str | None = None,
) -> str:
    """Build a JSON-only extraction prompt for the model."""
    transcript_lines = []
    for segment in transcript.segments:
        speaker = segment.speaker or "Unknown"
        timestamp = segment.timestamp or "--:--"
        transcript_lines.append(f"[{timestamp}] {speaker}: {segment.text}")

    prompt = f"""
You are extracting a presentation-ready meeting summary from a transcript.

Return JSON only. No markdown. No commentary.

Required JSON shape:
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

Rules:
- Use only information supported by the transcript or provided context.
- Prefer concrete statements over abstract summaries.
- Keep each array item concise: one idea per bullet, 8-18 words, <= 140 chars.
- Do not output metadata lines (date/source/file path/audience labels) as content bullets.
- Do not repeat near-identical bullets across arrays.
- Avoid ellipsis or cut-off phrases.
- First classify the conversation into one of the five talk types.
- Respect the requested presentation framing when provided.
- Then extract content according to the correct talk type:
  - business: context, key decisions, blockers, action items, open questions
  - trading: market context, trade ideas/setups/tickers, risk management, macro/catalysts, watchlist/actions
  - lecture: topic/thesis, key facts, idea links, insights, further study
  - ideas: project intent, current state, design decisions, deferred/cut scope, path to MVP
  - social: what was discussed, news from the other person, recommendations, agreements, follow-up
- Extract real decisions when present. Do not invent them.
- Produce short topic summaries so each important topic gets a concise takeaway.
- Group topic items into meaningful categories using `topic_categories`.
- Also fill `type_sections` with the 5 section blocks that match the detected talk type.
- Add `evidence_trails` with short transcript-grounded references that help audit the deck later.
- Use the context signals only to sharpen interpretation, not to override the transcript.
- Quotes must be verbatim and include speaker plus timestamp when available.
- Return the array items in the dominant transcript language: {normalize_language(transcript.language)}.

Meeting title: {transcript.title}
Meeting date: {transcript.date}
Participants: {", ".join(transcript.participants) if transcript.participants else "unknown"}
Transcript source: {transcript.source}
Detected transcript language: {normalize_language(transcript.language)}
Context note names: {", ".join(context_notes) if context_notes else "none"}
Requested presentation goal: {presentation_goal or "infer from transcript"}
Requested audience: {audience or "infer from transcript"}
Requested tone: {tone or "infer from transcript"}
Context signals:
{format_list_block(context_signals)}

Transcript:
{chr(10).join(transcript_lines)}
""".strip()
    return prompt


def format_list_block(items: list[str]) -> str:
    """Render a list block for prompt input."""
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def summary_from_llm_payload(
    transcript: TranscriptDocument,
    context_notes: list[str],
    context_signals: list[str],
    presentation_goal: str | None,
    audience: str | None,
    tone: str | None,
    payload: dict[str, object],
) -> SummaryDocument:
    """Convert parsed LLM JSON into a SummaryDocument."""
    from .summary import infer_audience_label, infer_deck_mode, infer_presentation_goal, infer_tone

    meeting_type = str(payload.get("meeting_type", "other"))
    deck_mode = str(payload.get("deck_mode", infer_deck_mode(meeting_type)))
    resolved_goal = str(payload.get("presentation_goal", "")).strip() or infer_presentation_goal(
        meeting_type=meeting_type,
        transcript=transcript,
        context_signals=context_signals,
        requested_goal=presentation_goal,
    )
    resolved_audience = str(payload.get("audience", "")).strip() or infer_audience_label(
        meeting_type=meeting_type,
        deck_mode=deck_mode,
        requested_audience=audience,
    )
    resolved_tone = str(payload.get("tone", "")).strip() or infer_tone(
        meeting_type=meeting_type,
        presentation_goal=resolved_goal,
        requested_tone=tone,
    )

    return SummaryDocument(
        title=transcript.title,
        date=transcript.date,
        project=transcript.project,
        source_note=build_source_note_name(transcript),
        meeting_type=meeting_type,
        deck_mode=deck_mode,
        participants=transcript.participants,
        language=normalize_language(transcript.language),
        presentation_goal=resolved_goal,
        audience=resolved_audience,
        tone=resolved_tone,
        context_notes=context_notes,
        context_signals=context_signals,
        goals=coerce_string_list(payload.get("goals")),
        themes=coerce_string_list(payload.get("themes")),
        pain_points=coerce_string_list(payload.get("pain_points")),
        objections=coerce_string_list(payload.get("objections")),
        decisions=coerce_string_list(payload.get("decisions")),
        action_items=coerce_string_list(payload.get("action_items")),
        quotes=coerce_string_list(payload.get("quotes")),
        narrative=coerce_string_list(payload.get("narrative")),
        topic_summaries=coerce_string_list(payload.get("topic_summaries")),
        topic_categories=coerce_string_map(payload.get("topic_categories")),
        type_sections=coerce_string_map(payload.get("type_sections")),
        evidence_trails=coerce_string_list(payload.get("evidence_trails")),
    )


def coerce_string_list(value: object) -> list[str]:
    """Coerce a JSON field into a clean list of strings."""
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            normalized = normalize_payload_item(item)
            if not normalized:
                continue
            fingerprint = normalize_item_fingerprint(normalized)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            result.append(normalized)
    return result


def coerce_string_map(value: object) -> dict[str, list[str]]:
    """Coerce a JSON object with string-list values into a clean mapping."""
    if not isinstance(value, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, items in value.items():
        if not isinstance(key, str):
            continue
        normalized_items = coerce_string_list(items)
        if normalized_items:
            normalized_key = normalize_payload_item(key, max_chars=72)
            if normalized_key:
                result[normalized_key] = normalized_items
    return result


def normalize_payload_item(value: str, max_chars: int = 220) -> str:
    """Normalize one LLM payload bullet into concise deck-safe text."""
    normalized = " ".join(value.split()).strip(" -–—\t\n\r")
    if not normalized:
        return ""
    if is_metadata_like_item(normalized):
        return ""
    normalized = normalized.rstrip(";")
    if len(normalized) > max_chars:
        normalized = normalized[: max_chars - 1].rstrip() + "…"
    return normalized


def is_metadata_like_item(value: str) -> bool:
    """Filter out non-content payload lines that pollute slides."""
    lowered = value.lower()
    metadata_prefixes = (
        "date:",
        "source:",
        "summary:",
        "audience:",
        "meeting title:",
        "meeting date:",
        "participants:",
        "transcript source:",
        "detected transcript language:",
        "context note names:",
        "requested presentation goal:",
        "requested audience:",
        "requested tone:",
    )
    if any(lowered.startswith(prefix) for prefix in metadata_prefixes):
        return True
    if lowered.startswith("{") and lowered.endswith("}"):
        return True
    if "/users/" in lowered or ".md" in lowered:
        return True
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", lowered):
        return True
    return False


def normalize_item_fingerprint(value: str) -> str:
    """Build a stable fingerprint for deduplicating near-identical bullets."""
    return re.sub(r"[\W_]+", "", value.lower())


def build_source_note_name(transcript: TranscriptDocument) -> str:
    """Recreate the expected normalized transcript filename."""
    from .summary import sanitize_filename_part

    title = sanitize_filename_part(transcript.title.lower())
    return f"{{{transcript.project}}} {{transcript}} {title} – {transcript.date}.md"
