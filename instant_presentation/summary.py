"""Summary generation from normalized transcript notes."""

from __future__ import annotations

import re
from pathlib import Path

from .i18n import detect_language_from_parts, normalize_language
from .llm import resolve_summary_engine, summarize_with_openai
from .models import SummaryDocument, TranscriptDocument, TranscriptSegment

GOAL_KEYWORDS = ("want", "goal", "outcome", "need", "looking for", "хочу", "цель", "ищу", "нужен")
PAIN_KEYWORDS = (
    "pain",
    "problem",
    "slow",
    "lose",
    "manual",
    "hours",
    "friction",
    "проблем",
    "лагает",
    "боятся",
    "долг",
    "хаос",
)
OBJECTION_KEYWORDS = ("concern", "accuracy", "risk", "cannot", "can't", "worry", "style", "страх", "риск", "не могу")
DECISION_KEYWORDS = ("agreed", "we should", "for v1", "priority", "preferred", "decided", "приоритет", "будем", "план")
ACTION_KEYWORDS = ("next step", "test", "will", "follow up", "compare", "need to", "action item", "скинуть", "оформить", "проверить", "сделать")
DECISION_STRONG_KEYWORDS = (
    "we should",
    "for v1",
    "priority",
    "agreed",
    "html is enough",
    "keep the pipeline generic",
    "support krisp first",
)
ACTION_STRONG_KEYWORDS = (
    "next step",
    "test on",
    "compare output",
    "follow-up",
    "action items",
    "same day",
)
QUESTION_STARTERS = ("what ", "why ", "how ", "when ", "where ", "who ")
OPEN_QUESTION_KEYWORDS = ("question", "unknown", "unclear", "need to understand", "нужно понять", "непонятно", "вопрос", "надо разобраться")
RECOMMENDATION_KEYWORDS = ("recommend", "suggest", "intro", "should talk", "совет", "рекомен", "интро", "стоит")
NEWS_KEYWORDS = ("now", "currently", "recently", "update", "news", "сейчас", "недавно", "обнов", "новост")
DEFERRED_KEYWORDS = ("later", "not now", "defer", "cut", "out of scope", "потом", "отлож", "вырез", "не сейчас")
FACT_KEYWORDS = ("fact", "history", "stat", "example", "because", "means", "например", "факт", "значит", "поэтому")
LINK_KEYWORDS = ("because", "therefore", "means", "so that", "если", "значит", "поэтому", "связ")
MARKET_KEYWORDS = ("market", "macro", "flow", "liquidity", "range", "рын", "макро", "ликвид", "волат", "контекст")
SETUP_KEYWORDS = ("setup", "ticker", "entry", "trade", "long", "short", "тикер", "сетап", "вход", "лонг", "шорт")
CATALYST_KEYWORDS = ("catalyst", "earnings", "fed", "data", "event", "катализ", "отчёт", "ставк", "событ")
KEY_POINT_GOAL_KEYWORDS = (
    "строит",
    "создаю",
    "собираю",
    "операционную систему",
    "переход",
    "подписку",
    "возможность",
    "набор",
)
KEY_POINT_PAIN_KEYWORDS = (
    "долг",
    "нужны",
    "нуждается",
    "нет таких специалистов",
    "боятся",
    "хаос",
    "закрыт",
    "приоритет",
)
KEY_POINT_DIRECTION_KEYWORDS = (
    "проект",
    "создание сайта",
    "цифровой двойник",
    "оптимизация",
    "перспективный рынок",
    "потенциал",
    "стоимость",
    "alchemist",
    "акселератор",
    "клиент",
    "работы",
    "интервью",
)
TYPE_SECTION_TITLES = {
    "research": [
        "Corpus Overview",
        "Repeated Pain Points",
        "Tool Signals",
        "Direction Patterns",
        "Audience / Talk Mix",
        "Evidence Highlights",
    ],
    "business": [
        "Conversation Context",
        "Key Decisions",
        "Risks and Blockers",
        "Action Grid",
        "Open Questions",
    ],
    "trading": [
        "Market Context",
        "Trade Ideas / Setups",
        "Risk Management",
        "Macro and Catalysts",
        "Watchlist / Actions",
    ],
    "lecture": [
        "Topic and Main Thesis",
        "Key Facts",
        "Links Between Ideas",
        "Insights",
        "Further Study",
    ],
    "ideas": [
        "Project: What and Why",
        "Current State",
        "Design Decisions",
        "Deferred / Cut",
        "Next: Path to MVP",
    ],
    "social": [
        "What We Talked About",
        "Their News",
        "Recommendations",
        "Agreements",
        "Follow-up",
    ],
}
TOPIC_CATEGORY_TEMPLATES = {
    "business": {
        "Context & Goals": ("goals", "context_signals", "themes"),
        "Problems & Constraints": ("pain_points", "objections"),
        "Decisions & Direction": ("decisions", "type:Key Decisions", "themes"),
        "Actions & Open Questions": ("action_items", "type:Open Questions"),
    },
    "trading": {
        "Market Context": ("type:Market Context", "themes", "context_signals"),
        "Trade Setups": ("type:Trade Ideas / Setups", "decisions"),
        "Risk & Watchouts": ("type:Risk Management", "pain_points", "objections"),
        "Catalysts & Watchlist": ("type:Macro and Catalysts", "type:Watchlist / Actions", "action_items"),
    },
    "lecture": {
        "Thesis": ("type:Topic and Main Thesis", "goals"),
        "Facts & Examples": ("type:Key Facts", "themes"),
        "Links Between Ideas": ("type:Links Between Ideas", "context_signals"),
        "Insights & Further Study": ("type:Insights", "type:Further Study", "action_items"),
    },
    "ideas": {
        "Project & Opportunity": ("type:Project: What and Why", "goals", "themes"),
        "Current State": ("type:Current State", "context_signals"),
        "Design Decisions": ("type:Design Decisions", "decisions"),
        "MVP Path & Cuts": ("type:Deferred / Cut", "type:Next: Path to MVP", "action_items"),
    },
    "social": {
        "What Came Up": ("type:What We Talked About", "themes"),
        "Personal Updates": ("type:Their News", "context_signals"),
        "Recommendations & Agreements": ("type:Recommendations", "type:Agreements", "decisions"),
        "Follow-up": ("type:Follow-up", "action_items"),
    },
    "research": {
        "Corpus Overview": ("type:Corpus Overview", "goals"),
        "Repeated Pain Points": ("type:Repeated Pain Points", "pain_points"),
        "Direction Patterns": ("type:Direction Patterns", "decisions"),
        "Evidence Highlights": ("type:Evidence Highlights", "evidence_trails"),
    },
}

VALID_PRESENTATION_GOALS = {"recap", "follow_up", "decision", "pitch", "research"}
VALID_TONES = {"clear", "sharp", "persuasive", "insightful", "warm"}


def summarize_note_file(
    input_path: Path,
    output_dir: Path,
    project: str = "instant",
    context_notes: list[Path] | None = None,
    summary_engine: str = "auto",
    presentation_goal: str | None = None,
    audience: str | None = None,
    tone: str | None = None,
) -> Path:
    """Read a normalized transcript note, generate a structured summary, and write it to disk."""
    note_text = input_path.read_text(encoding="utf-8")
    transcript = parse_normalized_note(note_text=note_text, origin_file=input_path.name, project=project)
    context_sources, context_signals = extract_context_signals(context_notes or [])
    engine = resolve_summary_engine(summary_engine)
    if engine == "claude":
        try:
            from .claude_engine import summarize_with_claude

            summary = summarize_with_claude(
                transcript=transcript,
                context_notes=context_sources,
                context_signals=context_signals,
                presentation_goal=presentation_goal,
                audience=audience,
                tone=tone,
            )
        except Exception:
            summary = summarize_transcript(
                transcript,
                context_notes=context_sources,
                context_signals=context_signals,
                presentation_goal=presentation_goal,
                audience=audience,
                tone=tone,
            )
    elif engine == "openai":
        try:
            summary = summarize_with_openai(
                transcript=transcript,
                context_notes=context_sources,
                context_signals=context_signals,
                presentation_goal=presentation_goal,
                audience=audience,
                tone=tone,
            )
        except Exception:
            summary = summarize_transcript(
                transcript,
                context_notes=context_sources,
                context_signals=context_signals,
                presentation_goal=presentation_goal,
                audience=audience,
                tone=tone,
            )
    else:
        summary = summarize_transcript(
            transcript,
            context_notes=context_sources,
            context_signals=context_signals,
            presentation_goal=presentation_goal,
            audience=audience,
            tone=tone,
        )
    markdown = render_summary_markdown(summary)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / build_summary_filename(summary)
    output_path.write_text(markdown, encoding="utf-8")
    return output_path


def parse_normalized_note(note_text: str, origin_file: str, project: str) -> TranscriptDocument:
    """Parse a normalized transcript markdown note back into a transcript document."""
    frontmatter, body = split_frontmatter(note_text)
    metadata = parse_frontmatter(frontmatter)
    segments = parse_rendered_segments(body)
    key_points = parse_markdown_bullets_section(body, "Key Points")
    next_actions = parse_markdown_bullets_section(body, "Next actions")

    participants = metadata.get("participants_list", [])
    if not participants:
        participants = sorted({segment.speaker for segment in segments if segment.speaker})

    language = metadata.get("language", "unknown")
    if language == "unknown":
        language = detect_language_from_parts(
            metadata.get("title", ""),
            "\n".join(key_points),
            "\n".join(next_actions),
            "\n".join(segment.text for segment in segments),
        )

    return TranscriptDocument(
        title=metadata.get("title", origin_file),
        source=metadata.get("source", "generic"),
        date=metadata.get("date", "1970-01-01"),
        participants=participants,
        language=normalize_language(language),
        origin_file=metadata.get("origin_file", origin_file),
        project=metadata.get("project", project),
        status=metadata.get("status", "normalized"),
        segments=segments,
        key_points=key_points,
        next_actions=next_actions,
    )


def split_frontmatter(note_text: str) -> tuple[str, str]:
    """Split markdown content into frontmatter and body."""
    if not note_text.startswith("---\n"):
        return "", note_text
    parts = note_text.split("---\n", 2)
    if len(parts) < 3:
        return "", note_text
    _, frontmatter, body = parts
    return frontmatter, body


def parse_frontmatter(frontmatter: str) -> dict[str, object]:
    """Parse the small subset of YAML used in generated notes."""
    metadata: dict[str, object] = {}
    current_list_key: str | None = None
    list_values: list[str] = []

    for raw_line in frontmatter.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if re.match(r"^[A-Za-z_]+:\s*$", line):
            if current_list_key is not None:
                metadata[f"{current_list_key}_list"] = list_values
            current_list_key = line[:-1]
            list_values = []
            continue
        if line.startswith("  - ") and current_list_key is not None:
            list_values.append(line[4:].strip())
            continue
        if current_list_key is not None:
            metadata[f"{current_list_key}_list"] = list_values
            current_list_key = None
            list_values = []
        if ": " in line:
            key, value = line.split(": ", 1)
            metadata[key] = value.strip().strip('"')

    if current_list_key is not None:
        metadata[f"{current_list_key}_list"] = list_values

    return metadata


def parse_rendered_segments(body: str) -> list[TranscriptSegment]:
    """Parse transcript lines from the normalized markdown body."""
    segments: list[TranscriptSegment] = []
    inline_ts_first = re.compile(r"^\*\*(?P<ts>\d{1,2}:\d{2}(?::\d{2})?) \| (?P<speaker>.+?)\*\*: (?P<text>.+)$")
    inline_speaker_first = re.compile(r"^\*\*(?P<speaker>.+?) \| (?P<ts>\d{1,2}:\d{2}(?::\d{2})?)\*\*: (?P<text>.+)$")
    block_speaker_first = re.compile(r"^\*\*(?P<speaker>.+?) \| (?P<ts>\d{1,2}:\d{2}(?::\d{2})?)\*\*$")
    lines = body.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        match = inline_ts_first.match(line) or inline_speaker_first.match(line)
        if not match:
            block_match = block_speaker_first.match(line)
            if not block_match:
                index += 1
                continue
            text_lines: list[str] = []
            index += 1
            while index < len(lines):
                candidate = lines[index].strip()
                if not candidate:
                    index += 1
                    continue
                if candidate.startswith("## ") or candidate.startswith("**"):
                    break
                text_lines.append(candidate)
                index += 1
            if text_lines:
                segments.append(
                    TranscriptSegment(
                        timestamp=block_match.group("ts"),
                        speaker=block_match.group("speaker").strip(),
                        text=" ".join(text_lines).strip(),
                    )
                )
            continue
        segments.append(
            TranscriptSegment(
                timestamp=match.group("ts"),
                speaker=match.group("speaker").strip(),
                text=match.group("text").strip(),
            )
        )
        index += 1
    return segments


def parse_markdown_bullets_section(body: str, heading: str) -> list[str]:
    """Extract bullet lines from a named markdown section."""
    lines = body.splitlines()
    target = heading.lower()
    in_section = False
    items: list[str] = []

    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("## "):
            in_section = stripped[3:].strip().lower() == target
            continue
        if not in_section:
            continue
        if not stripped:
            continue
        if stripped.startswith("- [ ] "):
            items.append(stripped[6:].strip())
            continue
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
            continue
        if stripped.startswith("## "):
            break

    return items


def summarize_transcript(
    transcript: TranscriptDocument,
    context_notes: list[str] | None = None,
    context_signals: list[str] | None = None,
    presentation_goal: str | None = None,
    audience: str | None = None,
    tone: str | None = None,
) -> SummaryDocument:
    """Extract a first-pass structured summary from transcript utterances."""
    context_notes = context_notes or []
    context_signals = context_signals or []
    fallback_items = transcript.key_points + transcript.next_actions
    goal_fallback = select_key_points_by_keywords(transcript.key_points, KEY_POINT_GOAL_KEYWORDS, limit=3)
    pain_fallback = select_key_points_by_keywords(transcript.key_points, KEY_POINT_PAIN_KEYWORDS, limit=4)
    decision_fallback = select_key_points_by_keywords(transcript.key_points, KEY_POINT_DIRECTION_KEYWORDS, limit=4)
    meeting_type = infer_meeting_type(transcript)
    deck_mode = infer_deck_mode(meeting_type)
    resolved_goal = infer_presentation_goal(
        meeting_type=meeting_type,
        transcript=transcript,
        context_signals=context_signals,
        requested_goal=presentation_goal,
    )
    resolved_audience = infer_audience_label(
        meeting_type=meeting_type,
        deck_mode=deck_mode,
        requested_audience=audience,
    )
    resolved_tone = infer_tone(
        meeting_type=meeting_type,
        presentation_goal=resolved_goal,
        requested_tone=tone,
    )

    goal_segments = select_segment_records(
        transcript.segments,
        GOAL_KEYWORDS,
        limit=3,
        strong_keywords=("want", "outcome", "looking for"),
        question_penalty=True,
    )
    pain_segments = select_segment_records(
        transcript.segments,
        PAIN_KEYWORDS,
        limit=4,
        strong_keywords=("main pain", "lose context", "manual", "hours"),
    )
    objection_segments = select_segment_records(
        transcript.segments,
        OBJECTION_KEYWORDS,
        limit=3,
        strong_keywords=("accuracy", "style", "cannot", "risk"),
        exclude_questions=True,
    )
    decision_segments = select_segment_records(
        transcript.segments,
        DECISION_KEYWORDS,
        limit=4,
        strong_keywords=DECISION_STRONG_KEYWORDS,
        exclude_questions=True,
    )
    action_segments = select_segment_records(
        transcript.segments,
        ACTION_KEYWORDS,
        limit=4,
        strong_keywords=ACTION_STRONG_KEYWORDS,
        exclude_questions=True,
    )
    open_question_segments = select_segment_records(
        transcript.segments,
        OPEN_QUESTION_KEYWORDS,
        limit=3,
        strong_keywords=("need to understand", "need to figure out", "вопрос", "непонятно"),
        question_penalty=False,
    )
    recommendation_segments = select_segment_records(
        transcript.segments,
        RECOMMENDATION_KEYWORDS,
        limit=3,
        strong_keywords=("recommend", "suggest", "intro", "совет", "рекомен"),
    )
    news_segments = select_segment_records(
        transcript.segments,
        NEWS_KEYWORDS,
        limit=3,
        strong_keywords=("currently", "recently", "сейчас", "недавно"),
    )
    deferred_segments = select_segment_records(
        transcript.segments,
        DEFERRED_KEYWORDS,
        limit=3,
        strong_keywords=("later", "out of scope", "потом", "отлож", "не сейчас"),
    )
    fact_segments = select_segment_records(
        transcript.segments,
        FACT_KEYWORDS,
        limit=4,
        strong_keywords=("means", "because", "example", "значит", "поэтому", "например"),
    )
    link_segments = select_segment_records(
        transcript.segments,
        LINK_KEYWORDS,
        limit=3,
        strong_keywords=("because", "therefore", "значит", "поэтому"),
    )
    market_segments = select_segment_records(
        transcript.segments,
        MARKET_KEYWORDS,
        limit=3,
        strong_keywords=("market", "macro", "range", "рын", "макро"),
    )
    setup_segments = select_segment_records(
        transcript.segments,
        SETUP_KEYWORDS,
        limit=4,
        strong_keywords=("ticker", "setup", "entry", "trade", "тикер", "сетап"),
    )
    catalyst_segments = select_segment_records(
        transcript.segments,
        CATALYST_KEYWORDS,
        limit=3,
        strong_keywords=("catalyst", "earnings", "fed", "катализ", "отчёт"),
    )
    goals = choose_compact_items([segment.text for segment in goal_segments], limit=3)
    pain_points = choose_compact_items([segment.text for segment in pain_segments], limit=4)
    objections = choose_compact_items([segment.text for segment in objection_segments], limit=4)
    decisions = choose_compact_items([segment.text for segment in decision_segments], limit=4)
    action_items = choose_compact_items([segment.text for segment in action_segments], limit=4)
    goals = apply_fallback_items(goals, goal_fallback or transcript.key_points[:3], limit=3)
    pain_points = apply_fallback_items(pain_points, pain_fallback, limit=4)
    decisions = apply_fallback_items(decisions, decision_fallback, limit=4)
    action_items = apply_fallback_items(action_items, transcript.next_actions, limit=4)
    themes = build_themes(goals, pain_points, context_signals, objections, decisions, action_items, fallback_items)
    quotes = build_quotes(
        transcript.segments,
        pain_points,
        objections,
        goals,
        decisions=decisions,
        action_items=action_items,
        fallback_quotes=transcript.key_points,
    )
    type_sections = build_type_sections(
        meeting_type=meeting_type,
        transcript=transcript,
        goals=goals,
        themes=themes,
        pain_points=pain_points,
        objections=objections,
        decisions=decisions,
        action_items=action_items,
        context_signals=context_signals,
        news_items=[segment.text for segment in news_segments],
        recommendation_items=[segment.text for segment in recommendation_segments],
        open_questions=extract_open_questions(transcript, open_question_segments),
        deferred_items=[segment.text for segment in deferred_segments],
        fact_items=[segment.text for segment in fact_segments],
        link_items=[segment.text for segment in link_segments],
        market_items=[segment.text for segment in market_segments],
        setup_items=[segment.text for segment in setup_segments],
        catalyst_items=[segment.text for segment in catalyst_segments],
    )
    narrative = build_narrative(
        meeting_type,
        pain_points,
        objections,
        decisions,
        action_items,
        context_signals,
    )
    topic_categories = build_topic_categories(
        meeting_type=meeting_type,
        goals=goals,
        themes=themes,
        pain_points=pain_points,
        objections=objections,
        decisions=decisions,
        action_items=action_items,
        context_signals=context_signals,
        type_sections=type_sections,
    )
    topic_summaries = build_topic_summaries(topic_categories)
    evidence_trails = build_evidence_trails(
        meeting_type=meeting_type,
        grouped_segments=[
            ("Goals", goal_segments),
            ("Pain Points", pain_segments),
            ("Objections", objection_segments),
            ("Decisions", decision_segments),
            ("Action Items", action_segments),
            ("Recommendations", recommendation_segments),
            ("Open Questions", open_question_segments),
            ("Key Facts", fact_segments),
            ("Market Context", market_segments),
            ("Trade Ideas / Setups", setup_segments),
        ],
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
        goals=goals,
        themes=themes,
        pain_points=pain_points,
        objections=objections,
        decisions=decisions,
        action_items=action_items,
        quotes=quotes,
        narrative=narrative,
        topic_summaries=topic_summaries,
        topic_categories=topic_categories,
        type_sections=type_sections,
        evidence_trails=evidence_trails,
    )


def infer_meeting_type(transcript: TranscriptDocument) -> str:
    """Infer the talk type using title, speaker distribution, and semantic hints."""
    utterances = [segment.text for segment in transcript.segments]
    title_haystack = " ".join([
        transcript.title,
        transcript.project,
        transcript.origin_file,
    ]).lower()
    haystack = " ".join([
        transcript.title,
        transcript.project,
        transcript.origin_file,
        *transcript.key_points,
        *transcript.next_actions,
        *utterances,
    ]).lower()
    dominant_share = dominant_speaker_share(transcript.segments)
    lecture_keywords = ("lecture", "workshop", "excursion", "tour", "экскурс", "лекц", "семинар")

    if dominant_share >= 0.8 and len(transcript.segments) >= 6:
        if any(keyword in title_haystack for keyword in lecture_keywords):
            return "lecture"

    trading_keywords = ("trading", "ticker", "tickers", "market", "macro", "setup", "watchlist", "рын", "тикер", "сетап", "лонг", "шорт", "катализ")
    strong_trading_keywords = ("ticker", "tickers", "тикер", "setup", "сетап", "лонг", "шорт", "watchlist")
    trading_hits = sum(keyword in haystack for keyword in trading_keywords)
    strong_trading_hits = sum(keyword in haystack for keyword in strong_trading_keywords)
    if strong_trading_hits >= 1 and trading_hits >= 2:
        return "trading"
    if trading_hits >= 3:
        return "trading"
    if any(keyword in title_haystack for keyword in lecture_keywords):
        return "lecture"
    if any(keyword in haystack for keyword in ("discovery", "client", "customer", "stakeholder", "sprint", "strategy", "reporting", "roadmap", "product", "команд", "клиент", "стратег", "спринт", "продукт", "отчёт")):
        return "business"
    if any(keyword in haystack for keyword in ("brainstorm", "idea", "mvp", "feature", "prototype", "ai", "product", "дизайн", "mvp", "иде", "проект", "фич", "архитект")):
        return "ideas"
    if any(keyword in haystack for keyword in ("friend", "catch up", "coffee", "личн", "семь", "новости", "созвон", "поговорили", "recommend", "intro", "moved", "new role", "moved to", "переех", "новая роль", "интро")):
        return "social"
    return "business"


def infer_deck_mode(meeting_type: str) -> str:
    """Map meeting type to the most likely deck mode."""
    mapping = {
        "business": "internal-decision",
        "trading": "research-insights",
        "lecture": "research-insights",
        "ideas": "internal-decision",
        "social": "client-followup",
    }
    return mapping.get(meeting_type, "internal-decision")


def normalize_presentation_goal(value: str | None, default: str = "recap") -> str:
    """Clamp presentation goal values to the supported set."""
    normalized = (value or "").strip().lower().replace("-", "_")
    aliases = {
        "followup": "follow_up",
        "follow-up": "follow_up",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized in VALID_PRESENTATION_GOALS:
        return normalized
    return default


def normalize_tone(value: str | None, default: str = "clear") -> str:
    """Clamp tone values to the supported set."""
    normalized = (value or "").strip().lower().replace("-", "_")
    if normalized in VALID_TONES:
        return normalized
    return default


def infer_presentation_goal(
    meeting_type: str,
    transcript: TranscriptDocument,
    context_signals: list[str],
    requested_goal: str | None = None,
) -> str:
    """Infer the most likely presentation goal for the transcript."""
    explicit = normalize_presentation_goal(requested_goal, default="")
    if explicit:
        return explicit

    haystack = " ".join([
        transcript.title,
        transcript.origin_file,
        *transcript.key_points,
        *transcript.next_actions,
        *context_signals,
    ]).lower()
    if any(keyword in haystack for keyword in ("follow up", "follow-up", "send after", "отправить после", "скинуть", "follow up on")):
        return "follow_up"
    if any(keyword in haystack for keyword in ("decision", "approve", "выбрать", "решить", "приоритет")):
        return "decision"
    if any(keyword in haystack for keyword in ("pitch", "sell", "convince", "убедить", "презентовать")):
        return "pitch"
    if meeting_type == "social":
        return "follow_up"
    if meeting_type == "lecture":
        return "recap"
    if meeting_type == "ideas":
        return "pitch"
    if meeting_type == "trading":
        return "decision"
    return "decision" if meeting_type == "business" else "recap"


def infer_audience_label(
    meeting_type: str,
    deck_mode: str,
    requested_audience: str | None = None,
) -> str:
    """Infer a default audience label when none is provided."""
    if requested_audience and requested_audience.strip():
        return requested_audience.strip()
    if meeting_type == "social" and deck_mode == "client-followup":
        return "relationship follow-up"
    mapping = {
        "sales-recap": "client or prospect",
        "client-followup": "client stakeholder",
        "research-insights": "internal product or strategy team",
        "internal-decision": "internal decision makers",
    }
    return mapping.get(deck_mode, "mixed stakeholders")


def infer_tone(
    meeting_type: str,
    presentation_goal: str,
    requested_tone: str | None = None,
) -> str:
    """Infer a conservative presentation tone."""
    explicit = normalize_tone(requested_tone, default="")
    if explicit:
        return explicit
    if presentation_goal == "decision":
        return "sharp"
    if presentation_goal == "pitch":
        return "persuasive"
    if presentation_goal == "research" or meeting_type in {"lecture", "trading"}:
        return "insightful"
    if presentation_goal == "follow_up" or meeting_type == "social":
        return "warm"
    return "clear"


def dominant_speaker_share(segments: list[TranscriptSegment]) -> float:
    """Return the share of turns attributed to the most active speaker."""
    speaker_counts: dict[str, int] = {}
    total = 0
    for segment in segments:
        if not segment.speaker:
            continue
        total += 1
        speaker_counts[segment.speaker] = speaker_counts.get(segment.speaker, 0) + 1
    if total == 0:
        return 0.0
    return max(speaker_counts.values()) / total


def select_segment_records(
    segments: list[TranscriptSegment],
    keywords: tuple[str, ...],
    limit: int,
    strong_keywords: tuple[str, ...] = (),
    exclude_questions: bool = False,
    question_penalty: bool = False,
) -> list[TranscriptSegment]:
    """Select up to N high-signal transcript segments using lightweight scoring."""
    ranked: list[tuple[int, int, TranscriptSegment]] = []
    seen: set[str] = set()
    for index, segment in enumerate(segments):
        normalized = segment.text.strip()
        lowered = normalized.lower()
        score = score_utterance(
            lowered=lowered,
            keywords=keywords,
            strong_keywords=strong_keywords,
            exclude_questions=exclude_questions,
            question_penalty=question_penalty,
        )
        if score <= 0:
            continue
        if normalized in seen:
            continue
        ranked.append((score, index, segment))
        seen.add(normalized)

    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [segment for _, _, segment in ranked[:limit]]


def select_segment_texts(
    segments: list[TranscriptSegment],
    keywords: tuple[str, ...],
    limit: int,
    strong_keywords: tuple[str, ...] = (),
    exclude_questions: bool = False,
    question_penalty: bool = False,
) -> list[str]:
    """Select up to N high-signal utterances using lightweight scoring."""
    return [
        segment.text
        for segment in select_segment_records(
            segments,
            keywords,
            limit,
            strong_keywords=strong_keywords,
            exclude_questions=exclude_questions,
            question_penalty=question_penalty,
        )
    ]


def score_utterance(
    lowered: str,
    keywords: tuple[str, ...],
    strong_keywords: tuple[str, ...],
    exclude_questions: bool,
    question_penalty: bool,
) -> int:
    """Score one utterance for extraction relevance."""
    keyword_hits = sum(keyword in lowered for keyword in keywords)
    if keyword_hits == 0:
        return 0

    score = keyword_hits * 3
    score += sum(keyword in lowered for keyword in strong_keywords) * 2

    if question_penalty and any(lowered.startswith(prefix) for prefix in QUESTION_STARTERS):
        score -= 2
    if exclude_questions and lowered.endswith("?"):
        score -= 5
    if lowered.startswith("thanks"):
        score -= 2
    if len(lowered) < 28:
        score -= 1
    if "we " in lowered or "our " in lowered:
        score += 1
    if "client-ready" in lowered or "same day" in lowered:
        score += 1

    return score


def build_themes(*sections: list[str]) -> list[str]:
    """Build concise themes from the extracted summary sections."""
    themes: list[str] = []
    for section in sections:
        for item in section:
            condensed = condense_sentence(item)
            if condensed not in themes:
                themes.append(condensed)
            if len(themes) >= 4:
                return themes
    return themes


def build_type_sections(
    meeting_type: str,
    transcript: TranscriptDocument,
    goals: list[str],
    themes: list[str],
    pain_points: list[str],
    objections: list[str],
    decisions: list[str],
    action_items: list[str],
    context_signals: list[str],
    news_items: list[str],
    recommendation_items: list[str],
    open_questions: list[str],
    deferred_items: list[str],
    fact_items: list[str],
    link_items: list[str],
    market_items: list[str],
    setup_items: list[str],
    catalyst_items: list[str],
) -> dict[str, list[str]]:
    """Build talk-type-specific content sections for deck planning."""
    titles = TYPE_SECTION_TITLES.get(meeting_type, TYPE_SECTION_TITLES["business"])
    sections: dict[str, list[str]] = {}

    if meeting_type == "business":
        sections[titles[0]] = choose_compact_items(goals, themes, context_signals, limit=4)
        sections[titles[1]] = choose_compact_items(decisions, action_items, transcript.key_points, limit=4)
        sections[titles[2]] = choose_compact_items(objections, pain_points, limit=4)
        sections[titles[3]] = choose_compact_items(action_items, transcript.next_actions, limit=4)
        sections[titles[4]] = choose_compact_items(open_questions, limit=3)
    elif meeting_type == "trading":
        sections[titles[0]] = choose_compact_items(market_items, themes, context_signals, limit=4)
        sections[titles[1]] = choose_compact_items(setup_items, decisions, goals, limit=4)
        sections[titles[2]] = choose_compact_items(objections, pain_points, limit=4)
        sections[titles[3]] = choose_compact_items(catalyst_items, context_signals, limit=4)
        sections[titles[4]] = choose_compact_items(action_items, transcript.next_actions, limit=4)
    elif meeting_type == "lecture":
        sections.update(
            build_lecture_type_sections(
                transcript=transcript,
                titles=titles,
                goals=goals,
                themes=themes,
                fact_items=fact_items,
                link_items=link_items,
                context_signals=context_signals,
                action_items=action_items,
            )
        )
    elif meeting_type == "ideas":
        sections[titles[0]] = choose_compact_items(goals, themes, limit=4)
        sections[titles[1]] = choose_compact_items(context_signals, transcript.key_points, themes, limit=4)
        sections[titles[2]] = choose_compact_items(decisions, transcript.key_points, limit=4)
        sections[titles[3]] = choose_compact_items(deferred_items, objections, pain_points, limit=4)
        sections[titles[4]] = choose_compact_items(action_items, transcript.next_actions, decisions, limit=4)
    else:
        sections[titles[0]] = choose_compact_items(themes, goals, limit=4)
        sections[titles[1]] = choose_compact_items(news_items, transcript.key_points, limit=4)
        sections[titles[2]] = choose_compact_items(recommendation_items, decisions, limit=4)
        sections[titles[3]] = choose_compact_items(action_items, decisions, limit=4)
        sections[titles[4]] = choose_compact_items(transcript.next_actions, action_items, limit=4)

    return {title: items for title, items in sections.items() if items}


def build_lecture_type_sections(
    transcript: TranscriptDocument,
    titles: list[str],
    goals: list[str],
    themes: list[str],
    fact_items: list[str],
    link_items: list[str],
    context_signals: list[str],
    action_items: list[str],
) -> dict[str, list[str]]:
    """Build lecture sections from key points as an academic argument, not a fact dump."""
    language = normalize_language(transcript.language)
    key_points = [normalize_sentence(point) for point in transcript.key_points if normalize_sentence(point)]
    object_records = build_lecture_object_records(key_points, language)
    object_cards = [record["card"] for record in object_records]
    thesis_items = build_lecture_thesis_items(
        key_points=key_points,
        goals=goals,
        themes=themes,
        object_records=object_records,
        language=language,
    )
    explanation_items = build_lecture_explanation_items(
        key_points=key_points,
        object_records=object_records,
        link_items=link_items,
        context_signals=context_signals,
        language=language,
    )
    context_items = build_lecture_context_items(
        key_points=key_points,
        object_records=object_records,
        fact_items=fact_items,
        language=language,
    )
    memory_items = build_lecture_memory_items(
        object_cards=object_cards,
        thesis_items=thesis_items,
        insight_items=context_items,
        language=language,
    )
    return {
        titles[0]: thesis_items[:3],
        titles[1]: object_cards[:4],
        titles[2]: explanation_items[:4],
        titles[3]: context_items[:3],
        titles[4]: memory_items[:4],
    }


def build_lecture_object_records(key_points: list[str], language: str) -> list[dict[str, str]]:
    """Turn lecture key points into structured object records with takeaway lines."""
    ranked_cards: list[tuple[int, int, str, dict[str, str]]] = []
    for point in key_points:
        subject, detail = split_lecture_point(point)
        if not subject or not looks_like_lecture_subject(subject):
            continue
        normalized_subject = normalize_sentence(subject)
        canonical_subject = canonicalize_lecture_subject(normalized_subject)
        if not normalized_subject:
            continue
        clauses = split_lecture_detail(detail)
        if not clauses:
            continue
        observation = clauses[0]
        support = clauses[1] if len(clauses) > 1 else ""
        takeaway = infer_lecture_takeaway(
            subject=normalized_subject,
            observation=observation,
            support=support,
            language=language,
        )
        year = extract_year_badge_from_point(point)
        detail_parts = [observation]
        if support:
            detail_parts.append(support)
        if takeaway:
            detail_parts.append(takeaway)
        card = f"{normalized_subject}: " + ". ".join(detail_parts[:3])
        ranked_cards.append(
            (
                lecture_subject_priority(canonical_subject),
                len(ranked_cards),
                canonical_subject,
                {
                    "subject": normalized_subject,
                    "canonical_subject": canonical_subject,
                    "observation": observation,
                    "support": support,
                    "takeaway": takeaway,
                    "year": year,
                    "card": card,
                },
            )
        )
    if ranked_cards:
        cards: list[dict[str, str]] = []
        seen_subjects: set[str] = set()
        for _, _, canonical_subject, record in sorted(ranked_cards, key=lambda item: (item[0], item[1])):
            if canonical_subject in seen_subjects:
                continue
            cards.append(record)
            seen_subjects.add(canonical_subject)
            if len(cards) >= 4:
                return cards
        if cards:
            return cards
    return [
        {
            "subject": "",
            "canonical_subject": "",
            "observation": normalize_sentence(item),
            "support": "",
            "takeaway": "",
            "year": extract_year_badge_from_point(item),
            "card": normalize_sentence(item),
        }
        for item in choose_compact_items(key_points, limit=4)
    ]


def split_lecture_point(point: str) -> tuple[str, str]:
    """Split a lecture key point into a named object and the claim about it."""
    cleaned = normalize_sentence(point).rstrip(".")
    if " — " in cleaned:
        subject, detail = cleaned.split(" — ", 1)
        return subject.strip(), detail.strip()
    if ": " in cleaned:
        subject, detail = cleaned.split(": ", 1)
        if looks_like_lecture_subject(subject):
            return subject.strip(), detail.strip()
    lowered = cleaned.lower()
    markers = (
        " создают ",
        " создаёт ",
        " сохранил",
        " сохранилась ",
        " основан ",
        " основана ",
        " имеет ",
        " изображает ",
        " уничтожил ",
        " уничтожила ",
        " заложен ",
        " заложена ",
        " несёт ",
        " несет ",
        " меняется ",
        " привлекла ",
        " купил ",
        " купила ",
        " показывает ",
        " показывают ",
        " находится ",
        " находятся ",
    )
    for marker in markers:
        index = lowered.find(marker)
        if index > 0:
            return cleaned[:index].strip(" ,"), cleaned[index:].strip(" ,")
    return "", cleaned


def looks_like_lecture_subject(subject: str) -> bool:
    """Return whether a heading looks like a real lecture object rather than narration noise."""
    lowered = normalize_sentence(subject).lower()
    if len(lowered) < 3 or len(lowered) > 72:
        return False
    keywords = (
        "сент-",
        "шапель",
        "собор",
        "нотр-дам",
        "шартр",
        "реймс",
        "страсбург",
        "людовик",
        "терновый венец",
        "галерея королей",
        "песчаник",
        "скульптура",
        "лабиринт",
        "saint-",
        "cathedral",
        "chartres",
        "reims",
        "notre-dame",
        "couronne",
        "relic",
        "vitrail",
        "cathédrale",
        "sainte-",
    )
    return any(keyword in lowered for keyword in keywords) or any(char.isupper() for char in subject if char.isalpha())


def canonicalize_lecture_subject(subject: str) -> str:
    """Normalize closely related lecture subjects to the same bucket."""
    lowered = normalize_sentence(subject).lower()
    aliases = {
        "сент-шапель": ("сент-шапель", "сан-", "saint-chapelle", "sainte-chapelle"),
        "нотр-дам": ("нотр-дам", "notre-dame"),
        "шартр": ("шартр", "chartres"),
        "реймс": ("реймс", "reims"),
        "терновый венец": ("терновый венец", "couronne", "crown of thorns"),
        "людовик святой": ("людовик", "saint louis"),
        "галерея королей": ("галерея королей", "gallery of kings"),
        "песчаник": ("песчаник", "sandstone", "grès"),
        "скульптура": ("скульптура", "sculpture", "statue"),
    }
    for canonical, keywords in aliases.items():
        if any(keyword in lowered for keyword in keywords):
            return canonical
    return lowered


def lecture_subject_priority(subject: str) -> int:
    """Prefer architectural objects first, then political/economic supporting examples."""
    order = {
        "сент-шапель": 0,
        "нотр-дам": 1,
        "шартр": 2,
        "реймс": 3,
        "галерея королей": 4,
        "терновый венец": 5,
        "людовик святой": 6,
        "песчаник": 7,
        "скульптура": 8,
    }
    return order.get(subject, 20)


def split_lecture_detail(detail: str) -> list[str]:
    """Split a lecture claim into short conclusion-ready clauses."""
    normalized_detail = normalize_sentence(detail)
    parts = re.split(r";\s+|:\s+|(?<=[.!?])\s+", normalized_detail)
    clauses: list[str] = []
    for part in parts:
        base = normalize_sentence(part).rstrip(".")
        pivot_markers = (" в отличие от ", " but ", " mais ", " а ", " но ")
        lowered = base.lower()
        split_clauses = [base]
        for marker in pivot_markers:
            index = lowered.find(marker)
            if index > 0:
                head = base[:index].rstrip(" ,")
                tail = base[index:].lstrip(" ,")
                split_clauses = [head, tail]
                break
        for clause in split_clauses:
            normalized_clause = normalize_sentence(clause).rstrip(".")
            if len(normalized_clause) < 12:
                continue
            clauses.append(sentence_case(normalized_clause))
        if len(clauses) >= 3:
            return [condense_sentence(clause) for clause in dedupe_preserve_order(clauses)[:3]]
    return [condense_sentence(clause) for clause in dedupe_preserve_order(clauses)[:3]]


def build_lecture_thesis_items(
    key_points: list[str],
    goals: list[str],
    themes: list[str],
    object_records: list[dict[str, str]],
    language: str,
) -> list[str]:
    """Synthesize a few central lecture theses grounded in repeated key-point patterns."""
    haystack = " ".join(key_points).lower()
    items: list[str] = []
    if any(keyword in haystack for keyword in ("витраж", "свет", "цвет", "фиолет", "stained glass", "vitrail", "lumi")):
        items.append(localize_lecture_line(language, "light"))
    if any(keyword in haystack for keyword in ("тернов", "паломник", "коронац", "релик", "людовик", "венец", "relic", "pilgrim", "couronne")):
        items.append(localize_lecture_line(language, "power"))
    if any(keyword in haystack for keyword in ("шартр", "реймс", "нотр-дам", "переход", "лучист", "chartres", "reims", "notre-dame", "rayonnant")):
        items.append(localize_lecture_line(language, "evolution"))
    if not items:
        items = choose_compact_items(goals, themes, [record["card"] for record in object_records], limit=3)
    return items[:3]


def build_lecture_explanation_items(
    key_points: list[str],
    object_records: list[dict[str, str]],
    link_items: list[str],
    context_signals: list[str],
    language: str,
) -> list[str]:
    """Explain the lecture through recurring analytical lenses."""
    items = build_lecture_argument_items(object_records, key_points, language)
    if not items:
        items = choose_compact_items(link_items, context_signals, [record["card"] for record in object_records], limit=4)
    return items[:4]


def build_lecture_context_items(
    key_points: list[str],
    object_records: list[dict[str, str]],
    fact_items: list[str],
    language: str,
) -> list[str]:
    """Build coherent historical forces instead of a bag of isolated facts."""
    items = build_lecture_force_items(object_records, key_points, language)
    if not items:
        items = choose_compact_items([record["card"] for record in object_records], fact_items, limit=4)
    return items[:4]


def build_lecture_memory_items(
    object_cards: list[str],
    thesis_items: list[str],
    insight_items: list[str],
    language: str,
) -> list[str]:
    """Close the lecture deck with a few compact takeaways rather than raw note fragments."""
    items: list[str] = []
    subjects = [extract_lecture_card_subject(card) for card in object_cards]
    if any("сент" in subject.lower() or "sainte" in subject.lower() or "saint" in subject.lower() for subject in subjects):
        items.append(localize_lecture_line(language, "remember_sainte_chapelle"))
    if any("нотр" in subject.lower() or "notre" in subject.lower() for subject in subjects):
        items.append(localize_lecture_line(language, "remember_notre_dame"))
    if any("шартр" in subject.lower() or "chartres" in subject.lower() for subject in subjects):
        items.append(localize_lecture_line(language, "remember_chartres"))
    if any("реймс" in subject.lower() or "reims" in subject.lower() for subject in subjects):
        items.append(localize_lecture_line(language, "remember_reims"))
    if not items:
        items = choose_compact_items(thesis_items, insight_items, object_cards, limit=4)
    return items[:4]


def infer_lecture_takeaway(subject: str, observation: str, support: str, language: str) -> str:
    """Derive a short interpretive takeaway for a lecture object."""
    lowered = f"{subject} {observation} {support}".lower()
    localized = {
        "ru": {
            "light": "Показывает, что свет в готике заменяет стену как главный носитель пространства",
            "pilgrim": "Показывает, что план собора связан с движением паломников и ритуалом",
            "power": "Показывает, что архитектура обслуживает власть и публичную легитимность",
            "restoration": "Показывает, где проходит граница между средневековым ядром и поздними добавлениями",
            "style": "Показывает переход между фазами готики через сопоставление памятников",
            "material": "Показывает, что география и материал напрямую меняют стиль восприятия",
        },
        "en": {
            "light": "Shows that light replaces the wall as the main organizer of space",
            "pilgrim": "Shows that the plan is shaped by pilgrimage movement and ritual",
            "power": "Shows that architecture also serves power and public legitimacy",
            "restoration": "Shows where the line runs between the medieval core and later additions",
            "style": "Shows stylistic transition through comparison rather than isolated facts",
            "material": "Shows that geography and material directly change visual character",
        },
        "fr": {
            "light": "Montre que la lumière remplace le mur comme organisateur principal de l'espace",
            "pilgrim": "Montre que le plan répond au pèlerinage et au rituel",
            "power": "Montre que l'architecture sert aussi le pouvoir et la légitimité publique",
            "restoration": "Montre où passe la frontière entre noyau médiéval et ajouts tardifs",
            "style": "Montre la transition stylistique par comparaison, pas par faits isolés",
            "material": "Montre que géographie et matériau modifient directement le caractère visuel",
        },
    }
    copy = localized[language]
    if any(token in lowered for token in ("реймс", "коронац", "корол", "roi", "reims", "coronation", "людовик")):
        return copy["power"]
    if any(token in lowered for token in ("пожар", "революц", "виолле", "xix", "xx", "restaur", "новодел")):
        return copy["restoration"]
    if any(token in lowered for token in ("переход", "лучист", "цветущ", "шартр", "chartres", "style")):
        return copy["style"]
    if any(token in lowered for token in ("палом", "неф", "венец", "релик", "pilgrim", "nef", "relic")):
        return copy["pilgrim"]
    if any(token in lowered for token in ("песчаник", "sandstone", "grès", "розоват", "красн", "геолог")):
        return copy["material"]
    if any(token in lowered for token in ("витраж", "свет", "фиолет", "vitrail", "lumi")):
        return copy["light"]
    return ""


def build_lecture_argument_items(
    object_records: list[dict[str, str]],
    key_points: list[str],
    language: str,
) -> list[str]:
    """Build lecture frame items as thesis + example instead of generic labels."""
    haystack = " ".join(key_points).lower()
    items: list[str] = []
    local = lecture_argument_copy(language)

    sainte = find_lecture_record(object_records, "сент-шапель")
    notre = find_lecture_record(object_records, "нотр-дам")
    chartres = find_lecture_record(object_records, "шартр")
    reims = find_lecture_record(object_records, "реймс")

    if sainte and any(keyword in haystack for keyword in ("витраж", "свет", "цвет", "фиолет", "vitrail", "lumi")):
        items.append(f"{local['light_title']}: {sainte['subject']} показывает, что {local['light_body']}")
    if notre and any(keyword in haystack for keyword in ("паломник", "неф", "обход", "pilgrim", "nef", "relic")):
        items.append(f"{local['flow_title']}: {notre['subject']} объясняет, почему {local['flow_body']}")
    if reims and any(keyword in haystack for keyword in ("коронац", "корол", "реймс", "reims", "coronation", "roi")):
        items.append(f"{local['power_title']}: {reims['subject']} показывает, как {local['power_body']}")
    if chartres and any(keyword in haystack for keyword in ("переход", "лучист", "цветущ", "chartres", "шартр")):
        items.append(f"{local['style_title']}: {chartres['subject']} помогает увидеть, как {local['style_body']}")
    return items[:4]


def build_lecture_force_items(
    object_records: list[dict[str, str]],
    key_points: list[str],
    language: str,
) -> list[str]:
    """Build historical forces as cause-and-effect lines with concrete anchors."""
    haystack = " ".join(key_points).lower()
    items: list[str] = []
    local = lecture_force_copy(language)

    sainte = find_lecture_record(object_records, "сент-шапель")
    reims = find_lecture_record(object_records, "реймс")
    notre = find_lecture_record(object_records, "нотр-дам")

    if any(keyword in haystack for keyword in ("тернов", "релик", "паломник", "budget", "бюджет", "pilgrim", "couronne")):
        anchor = sainte["subject"] if sainte else local["paris_anchor"]
        items.append(f"{local['relics_title']}: {anchor} делает видимой логику, в которой реликвии и паломничество меняют экономику города." if language == "ru" else f"{local['relics_title']}: {anchor} makes visible how relics and pilgrimage reshape the city's economy.")
    if any(keyword in haystack for keyword in ("людовик", "коронац", "корол", "reims", "roi", "coronation", "реймс")):
        anchor = reims["subject"] if reims else local["power_anchor"]
        if language == "ru":
            items.append(f"{local['power_title']}: {anchor} показывает, что собор работает и как сцена власти, а не только как храм.")
        elif language == "fr":
            items.append(f"{local['power_title']}: {anchor} montre que la cathédrale agit aussi comme scène du pouvoir, pas seulement comme lieu de culte.")
        else:
            items.append(f"{local['power_title']}: {anchor} shows that the cathedral works as a stage of power, not only as a church.")
    if any(keyword in haystack for keyword in ("революц", "виолле", "пожар", "xix", "xx", "restaur", "новодел")):
        anchor = notre["subject"] if notre else local["restoration_anchor"]
        if language == "ru":
            items.append(f"{local['restoration_title']}: {anchor} показывает, почему в готике приходится отделять исходный памятник от поздних слоёв.")
        elif language == "fr":
            items.append(f"{local['restoration_title']}: {anchor} montre pourquoi il faut distinguer le monument d'origine de ses couches tardives.")
        else:
            items.append(f"{local['restoration_title']}: {anchor} shows why the original monument has to be separated from later layers.")
    if any(keyword in haystack for keyword in ("песчаник", "розоват", "красн", "геолог", "sandstone", "grès", "rose")):
        if language == "ru":
            items.append(f"{local['material_title']}: изменение камня от Парижа к Реймсу и Страсбургу объясняет, почему стиль зависит ещё и от географии.")
        elif language == "fr":
            items.append(f"{local['material_title']}: l'évolution de la pierre entre Paris, Reims et Strasbourg montre que le style dépend aussi de la géographie.")
        else:
            items.append(f"{local['material_title']}: the shift in stone from Paris to Reims and Strasbourg shows that style also depends on geography.")
    return items[:4]


def find_lecture_record(object_records: list[dict[str, str]], canonical_subject: str) -> dict[str, str] | None:
    """Find one lecture object record by canonical subject."""
    for record in object_records:
        if record.get("canonical_subject") == canonical_subject:
            return record
    return None


def lecture_argument_copy(language: str) -> dict[str, str]:
    """Localized copy for lecture analytical-frame lines."""
    localized = {
        "ru": {
            "light_title": "Свет вместо стены",
            "light_body": "свет и витраж перестраивают саму логику пространства",
            "flow_title": "Маршрут паломника",
            "flow_body": "план собора подчинён движению паломников и ритуалу",
            "power_title": "Собор как сцена власти",
            "power_body": "архитектура становится публичным ритуалом легитимности",
            "style_title": "Переход стиля",
            "style_body": "готика развивается последовательно, а не существует как один готовый канон",
        },
        "fr": {
            "light_title": "La lumière remplace le mur",
            "light_body": "la lumière et le vitrail réorganisent la logique même de l'espace",
            "flow_title": "Le parcours du pèlerin",
            "flow_body": "le plan répond au mouvement des pèlerins et au rituel",
            "power_title": "La cathédrale comme scène du pouvoir",
            "power_body": "l'architecture devient un rituel public de légitimation",
            "style_title": "La transition du style",
            "style_body": "le gothique se développe par étapes plutôt que comme un canon figé",
        },
        "en": {
            "light_title": "Light instead of wall",
            "light_body": "light and stained glass reorganize the logic of the space itself",
            "flow_title": "Pilgrim route",
            "flow_body": "the plan is shaped by pilgrimage movement and ritual",
            "power_title": "Cathedral as stage of power",
            "power_body": "architecture becomes a public ritual of legitimacy",
            "style_title": "Style in transition",
            "style_body": "Gothic develops step by step rather than existing as one fixed formula",
        },
    }
    return localized[language]


def lecture_force_copy(language: str) -> dict[str, str]:
    """Localized copy for lecture historical-force lines."""
    localized = {
        "ru": {
            "relics_title": "Реликвии и паломничество",
            "power_title": "Монархия как заказчик смысла",
            "restoration_title": "Реставрация меняет чтение",
            "material_title": "Материал формирует стиль",
            "paris_anchor": "Париж",
            "power_anchor": "Реймс",
            "restoration_anchor": "Нотр-Дам",
        },
        "fr": {
            "relics_title": "Les reliques comme moteur de croissance",
            "power_title": "La monarchie comme commanditaire de sens",
            "restoration_title": "La restauration change la lecture",
            "material_title": "Le matériau façonne le style",
            "paris_anchor": "Paris",
            "power_anchor": "Reims",
            "restoration_anchor": "Notre-Dame",
        },
        "en": {
            "relics_title": "Relics as a growth engine",
            "power_title": "Monarchy as a producer of meaning",
            "restoration_title": "Restoration changes how we read the monument",
            "material_title": "Material shapes style",
            "paris_anchor": "Paris",
            "power_anchor": "Reims",
            "restoration_anchor": "Notre-Dame",
        },
    }
    return localized[language]


def extract_year_badge_from_point(text: str) -> str:
    """Extract a compact year range from a lecture point when present."""
    match = re.search(r"\b(\d{4}(?:[–-]\d{4})?)\b", text)
    if match:
        return match.group(1).replace("-", "–")
    century_match = re.search(
        r"\b(X{0,3}(?:IX|IV|V?I{0,3})(?:[–-]X{0,3}(?:IX|IV|V?I{0,3}))?)\s+век",
        text,
        flags=re.IGNORECASE,
    )
    if century_match:
        return century_match.group(1).upper() + " век"
    return ""


def extract_lecture_card_subject(card: str) -> str:
    """Extract the leading object name from a generated lecture card."""
    if ": " in card:
        return card.split(": ", 1)[0].strip()
    return normalize_sentence(card)


def normalize_sentence(text: str) -> str:
    """Normalize whitespace without clipping the sentence."""
    return " ".join(text.split()).strip()


def localize_lecture_line(language: str, key: str) -> str:
    """Return one localized lecture synthesis line."""
    lines = {
        "ru": {
            "light": "Свет как конструкция: витраж и цвет в готике работают не как декор, а как часть самого пространства.",
            "power": "Собор как система власти: храм в лекции показан ещё и как инструмент паломничества, статуса и городской экономики.",
            "evolution": "Эволюция стиля: сравнение Шартра, Нотр-Дама и Реймса показывает движение от ранней готики к лучистой зрелости.",
            "explain_light": "Свет вместо стены: Сент-Шапель показывает, как витраж фактически меняет саму логику интерьера.",
            "explain_flow": "Маршрут паломника: реликвии, обходы и боковые нефы объясняют, почему план собора подчинён движению людей.",
            "explain_power": "Собор как сцена власти: Реймс показывает, что архитектура работала ещё и как публичный ритуал легитимности.",
            "explain_layers": "Слои времени: разрушения и реставрации объясняют, почему в готике нельзя смешивать средневековое и позднее.",
            "explain_style": "Переход стиля: сравнение Нотр-Дама, Шартра и Реймса помогает читать готику как последовательное развитие, а не как единый стиль.",
            "insight_economy": "Экономика реликвий: паломничество влияло не символически, а напрямую на богатство города и масштаб строительства.",
            "insight_restoration": "Ложная средневековость: часть того, что кажется подлинным, на деле относится к реставрациям XIX и XX веков.",
            "insight_material": "Геология как стиль: цвет песчаника меняется вместе с географией и влияет на визуальный характер собора.",
            "insight_antiquity": "Античность внутри готики: в Реймсе видно, как мастера впитывали и переосмысливали античные профили.",
            "context_relics": "Реликвии и паломничество: покупка Тернового венца превращает архитектуру в экономику потока, а Париж — в место притяжения паломников.",
            "context_power": "Монархия и легитимность: Сент-Шапель и Реймс важны не только как здания, но и как сцены королевской власти и сакрального статуса.",
            "context_restoration": "Разрушение и реставрация: революция, пожар 2019 года и вмешательства XIX века заставляют отделять средневековое ядро от поздних добавлений.",
            "context_material": "Материал и география: смена песчаника от Парижа к Реймсу и Страсбургу показывает, что стиль зависит не только от идеи, но и от камня.",
            "context_antiquity": "Античное наследие: в Реймсе готическая скульптура впитывает римские профили и показывает, что готика не отрывается от античной памяти.",
            "remember_sainte_chapelle": "Сент-Шапель: лучистая готика читается через свет, витраж и почти полное исчезновение стены.",
            "remember_notre_dame": "Нотр-Дам: планировка и фасад помогают читать собор как машину паломничества ранней готики.",
            "remember_chartres": "Шартр: удобная точка, чтобы увидеть переход между цветущей и лучистой готикой.",
            "remember_reims": "Реймс: собор важен не только архитектурой, но и своей ролью в коронационном ритуале Франции.",
        },
        "fr": {
            "light": "La lumière comme structure: le vitrail et la couleur participent à l'espace, pas seulement au décor.",
            "power": "La cathédrale comme système de pouvoir: le lieu sert aussi le pèlerinage, le prestige et l'économie urbaine.",
            "evolution": "Évolution du style: Chartres, Notre-Dame et Reims montrent le passage vers le gothique rayonnant.",
            "explain_light": "La lumière remplace le mur: la Sainte-Chapelle montre comment le vitrail transforme l'intérieur.",
            "explain_flow": "Le parcours du pèlerin: reliques, déambulatoires et bas-côtés expliquent le plan du bâtiment.",
            "explain_power": "La cathédrale comme scène de pouvoir: Reims montre l'architecture comme rituel public de légitimation.",
            "explain_layers": "Les couches du temps: destructions et restaurations obligent à distinguer le médiéval du tardif.",
            "explain_style": "Transition du style: Notre-Dame, Chartres et Reims permettent de lire le gothique comme une évolution, pas comme un bloc homogène.",
            "insight_economy": "Économie des reliques: le pèlerinage a influencé directement la richesse urbaine et l'ampleur du chantier.",
            "insight_restoration": "Fausse impression de Moyen Âge: une partie du visible relève des restaurations des XIXe et XXe siècles.",
            "insight_material": "La géologie comme style: la couleur du grès change avec la géographie et modifie la lecture du monument.",
            "insight_antiquity": "L'antique dans le gothique: à Reims, les profils montrent une réinterprétation des formes antiques.",
            "context_relics": "Reliques et pèlerinage: l'achat de la Couronne d'épines transforme l'architecture en économie du flux et fait de Paris un pôle d'attraction.",
            "context_power": "Monarchie et légitimation: la Sainte-Chapelle et Reims comptent autant comme scènes du pouvoir royal que comme monuments.",
            "context_restoration": "Destruction et restauration: révolution, incendie de 2019 et restaurations du XIXe siècle obligent à distinguer noyau médiéval et ajouts tardifs.",
            "context_material": "Matériau et géographie: du grès parisien au rose de Reims, le style dépend aussi de la pierre et du territoire.",
            "context_antiquity": "Mémoire antique: à Reims, la sculpture gothique réemploie des profils romains et conserve un dialogue avec l'Antiquité.",
            "remember_sainte_chapelle": "Sainte-Chapelle: le gothique rayonnant se lit par la lumière, le vitrail et la disparition presque totale du mur.",
            "remember_notre_dame": "Notre-Dame: le plan et la façade se comprennent comme une architecture pensée pour les pèlerins.",
            "remember_chartres": "Chartres: un bon point d'appui pour voir la transition entre gothique fleuri et gothique rayonnant.",
            "remember_reims": "Reims: la cathédrale compte autant pour son rôle dans le sacre que pour sa forme architecturale.",
        },
        "en": {
            "light": "Light as structure: stained glass and color shape Gothic space rather than merely decorating it.",
            "power": "The cathedral as a power system: the building also organizes pilgrimage, prestige, and urban economics.",
            "evolution": "Style in motion: Chartres, Notre-Dame, and Reims show the shift toward Rayonnant Gothic maturity.",
            "explain_light": "Light replacing the wall: Sainte-Chapelle shows how stained glass changes the logic of the interior.",
            "explain_flow": "Pilgrim circulation: relics, side aisles, and movement explain why the plan works the way it does.",
            "explain_power": "Architecture as public legitimacy: Reims turns the cathedral into a stage for coronation and power.",
            "explain_layers": "Layered time: destruction and restoration show why Gothic buildings cannot be read as untouched originals.",
            "explain_style": "Style as transition: Notre-Dame, Chartres, and Reims make Gothic legible as a sequence of developments rather than one static formula.",
            "insight_economy": "Relic economy: pilgrimage directly shaped urban wealth and the scale of construction.",
            "insight_restoration": "False medievality: some of what looks original is actually a product of nineteenth- and twentieth-century restoration.",
            "insight_material": "Geology as style: the stone's color shifts with geography and changes the monument's visual character.",
            "insight_antiquity": "Antiquity inside Gothic: Reims shows how sculptors absorbed and reworked antique profiles.",
            "context_relics": "Relics and pilgrimage: the Crown of Thorns turns architecture into a traffic economy and makes Paris a destination rather than a backdrop.",
            "context_power": "Monarchy and legitimacy: Sainte-Chapelle and Reims matter as stages for royal power as much as for architecture itself.",
            "context_restoration": "Destruction and restoration: revolution, the 2019 fire, and nineteenth-century intervention mean the visible building is layered rather than untouched.",
            "context_material": "Material and geography: stone color shifts from Paris to Reims and Strasbourg, so style is shaped by geology as well as design.",
            "context_antiquity": "Antique memory: Reims shows Gothic sculpture absorbing Roman profiles instead of breaking cleanly from them.",
            "remember_sainte_chapelle": "Sainte-Chapelle: Rayonnant Gothic is best remembered through light, stained glass, and the near-disappearance of the wall.",
            "remember_notre_dame": "Notre-Dame: plan and facade make sense when read as architecture for pilgrimage flow.",
            "remember_chartres": "Chartres: a useful reference point for the transition between earlier and more radiant Gothic forms.",
            "remember_reims": "Reims: the cathedral matters as much for coronation ritual as for architecture itself.",
        },
    }
    return lines[language].get(key, lines["en"][key])


def sentence_case(text: str) -> str:
    """Uppercase the first alphabetical character while preserving the rest."""
    if not text:
        return text
    for index, char in enumerate(text):
        if char.isalpha():
            return text[:index] + char.upper() + text[index + 1 :]
    return text


def dedupe_preserve_order(items: list[str]) -> list[str]:
    """Deduplicate strings while preserving the original order."""
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = normalize_sentence(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def choose_compact_items(*groups: list[str], limit: int) -> list[str]:
    """Merge several lists into a compact deduplicated set."""
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            condensed = condense_sentence(item)
            if not condensed or condensed in seen:
                continue
            seen.add(condensed)
            merged.append(condensed)
            if len(merged) >= limit:
                return merged
    return merged


def extract_open_questions(transcript: TranscriptDocument, matched_segments: list[TranscriptSegment]) -> list[str]:
    """Collect unresolved questions from explicit matches and transcript punctuation."""
    questions = [segment.text for segment in matched_segments]
    for segment in transcript.segments:
        text = segment.text.strip()
        if text.endswith("?"):
            questions.append(text)
    return choose_compact_items(questions, limit=3)


def build_evidence_trails(
    meeting_type: str,
    grouped_segments: list[tuple[str, list[TranscriptSegment]]],
) -> list[str]:
    """Build compact claim-to-transcript references for manual review."""
    trails: list[str] = []
    seen: set[str] = set()
    preferred_labels = {
        "business": {"Decisions", "Pain Points", "Action Items", "Open Questions"},
        "trading": {"Market Context", "Trade Ideas / Setups", "Action Items", "Pain Points"},
        "lecture": {"Goals", "Key Facts", "Action Items"},
        "ideas": {"Decisions", "Action Items", "Pain Points"},
        "social": {"Recommendations", "Action Items", "Goals"},
    }.get(meeting_type, set())

    def add_segment(label: str, segment: TranscriptSegment) -> None:
        condensed = condense_sentence(segment.text)
        if not condensed:
            return
        trail = f"{label}: {segment_ref(segment)} {condensed}"
        if trail not in seen:
            trails.append(trail)
            seen.add(trail)

    for label, segments in grouped_segments:
        if label in preferred_labels:
            for segment in segments[:2]:
                add_segment(label, segment)
    for label, segments in grouped_segments:
        for segment in segments[:1]:
            add_segment(label, segment)
        if len(trails) >= 8:
            break
    return trails[:8]


def segment_ref(segment: TranscriptSegment) -> str:
    """Render a compact transcript reference for a segment."""
    speaker = segment.speaker or "Unknown"
    timestamp = segment.timestamp or "--:--"
    return f"[{timestamp} {speaker}]"


def build_quotes(
    segments: list[TranscriptSegment],
    pain_points: list[str],
    objections: list[str],
    goals: list[str],
    decisions: list[str] | None = None,
    action_items: list[str] | None = None,
    fallback_quotes: list[str] | None = None,
) -> list[str]:
    """Promote a few high-signal utterances into quote blocks."""
    selected_texts = set(pain_points[:2] + objections[:1] + goals[:1] + (decisions or [])[:1] + (action_items or [])[:1])
    selected_fingerprints = {normalize_sentence(item).lower() for item in selected_texts}
    quotes: list[str] = []
    for segment in segments:
        segment_fingerprint = normalize_sentence(condense_sentence(segment.text)).lower()
        if (segment.text in selected_texts or segment_fingerprint in selected_fingerprints) and segment.speaker:
            prefix = f"{segment.speaker}"
            if segment.timestamp:
                prefix = f"{prefix} ({segment.timestamp})"
            quotes.append(f'"{compress_quote_text(segment.text)}" — {prefix}')
        if len(quotes) >= 3:
            break
    if not quotes:
        for item in fallback_quotes or []:
            quotes.append(f'"{compress_quote_text(item)}"')
            if len(quotes) >= 3:
                break
    return quotes


def apply_fallback_items(primary: list[str], fallback: list[str], limit: int) -> list[str]:
    """Use section bullets as a fallback when utterance extraction is weak."""
    if not fallback:
        return primary[:limit]

    merged: list[str] = []
    seen: set[str] = set()

    for source in (fallback, primary):
        for item in source:
            condensed = condense_sentence(item)
            if condensed in seen:
                continue
            merged.append(condensed)
            seen.add(condensed)
            if len(merged) >= limit:
                return merged

    return merged


def select_key_points_by_keywords(key_points: list[str], keywords: tuple[str, ...], limit: int) -> list[str]:
    """Select compact key points that match the target semantic bucket."""
    ranked: list[tuple[int, int, str]] = []
    for index, item in enumerate(key_points):
        lowered = item.lower()
        score = sum(keyword in lowered for keyword in keywords)
        if score <= 0:
            continue
        ranked.append((score, index, condense_sentence(item)))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item for _, _, item in ranked[:limit]]


def build_narrative(
    meeting_type: str,
    pain_points: list[str],
    objections: list[str],
    decisions: list[str],
    action_items: list[str],
    context_signals: list[str],
) -> list[str]:
    """Build a deck-friendly narrative skeleton."""
    type_narratives = {
        "business": "Frame the deck around context, decisions, blockers, actions, and open questions.",
        "trading": "Frame the deck around market context, setups, risk, catalysts, and watchlist actions.",
        "lecture": "Frame the deck around thesis, key facts, idea links, insights, and further study.",
        "ideas": "Frame the deck around the project intent, current state, design choices, cuts, and path to MVP.",
        "social": "Frame the deck around what was discussed, personal updates, recommendations, agreements, and follow-up.",
    }
    narrative = [type_narratives.get(meeting_type, "Frame the deck around the strongest supported signals from the transcript.")]
    if context_signals:
        narrative.append("Use context only to sharpen interpretation, not to override the transcript.")
    if pain_points and meeting_type in {"business", "ideas"}:
        narrative.append("Highlight blockers before proposing solutions.")
    if objections and meeting_type in {"business", "trading", "ideas"}:
        narrative.append("Keep risks explicit so the deck stays decision-useful.")
    if decisions and meeting_type in {"business", "ideas", "social"}:
        narrative.append("Present decisions and agreements as concrete commitments.")
    if action_items:
        narrative.append("Finish with next steps that can be sent immediately after the conversation.")
    return narrative


def build_topic_categories(
    meeting_type: str,
    goals: list[str],
    themes: list[str],
    pain_points: list[str],
    objections: list[str],
    decisions: list[str],
    action_items: list[str],
    context_signals: list[str],
    type_sections: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Group the conversation into a few high-signal topic categories."""
    sources = {
        "goals": goals,
        "themes": themes,
        "pain_points": pain_points,
        "objections": objections,
        "decisions": decisions,
        "action_items": action_items,
        "context_signals": context_signals,
        "evidence_trails": [],
    }
    categories: dict[str, list[str]] = {}
    template = TOPIC_CATEGORY_TEMPLATES.get(meeting_type, TOPIC_CATEGORY_TEMPLATES["business"])
    for label, descriptors in template.items():
        groups: list[list[str]] = []
        for descriptor in descriptors:
            if descriptor.startswith("type:"):
                groups.append(type_sections.get(descriptor[5:], []))
            else:
                groups.append(sources.get(descriptor, []))
        items = choose_compact_items(*groups, limit=3)
        if items:
            categories[label] = items
    return categories


def build_topic_summaries(topic_categories: dict[str, list[str]]) -> list[str]:
    """Create one concise takeaway per topic category."""
    summaries: list[str] = []
    for label, items in topic_categories.items():
        if not items:
            continue
        lead = condense_sentence(items[0])
        support = condense_sentence(items[1]) if len(items) > 1 else ""
        if support:
            summaries.append(f"{label} — {lead}; {support}")
        else:
            summaries.append(f"{label} — {lead}")
    return summaries


def extract_context_signals(context_notes: list[Path]) -> tuple[list[str], list[str]]:
    """Extract compact supporting signals from optional context notes."""
    sources: list[str] = []
    signals: list[str] = []
    seen: set[str] = set()

    for note_path in context_notes:
        sources.append(note_path.name)
        for candidate in iter_context_candidates(note_path.read_text(encoding="utf-8")):
            condensed = condense_sentence(candidate)
            if condensed not in seen:
                signals.append(condensed)
                seen.add(condensed)
            if len(signals) >= 5:
                return sources, signals

    return sources, signals


def iter_context_candidates(text: str) -> list[str]:
    """Return candidate lines from a free-form context note."""
    candidates: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped in {"---", "```"}:
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        if stripped.startswith("- "):
            stripped = stripped[2:].strip()
        if stripped.startswith("title:") or stripped.startswith("date:"):
            continue
        if re.match(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]", stripped):
            continue
        if re.match(r"^\d{1,2}:\d{2}(?::\d{2})?", stripped):
            continue
        if len(stripped) < 24:
            continue
        candidates.append(stripped)
    return prioritize_context_candidates(candidates)


def prioritize_context_candidates(candidates: list[str]) -> list[str]:
    """Sort candidate context lines by likely usefulness."""
    scored: list[tuple[int, str]] = []
    for candidate in candidates:
        lowered = candidate.lower()
        score = 0
        if any(keyword in lowered for keyword in GOAL_KEYWORDS):
            score += 3
        if any(keyword in lowered for keyword in PAIN_KEYWORDS):
            score += 3
        if any(keyword in lowered for keyword in DECISION_KEYWORDS):
            score += 2
        if any(keyword in lowered for keyword in ACTION_KEYWORDS):
            score += 2
        if "implementation" in lowered or "priority" in lowered or "trust" in lowered:
            score += 2
        score += min(len(candidate) // 40, 2)
        scored.append((score, candidate))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [candidate for _, candidate in scored]


def condense_sentence(text: str) -> str:
    """Turn a long spoken utterance into a concise deck-safe line."""
    normalized = normalize_sentence(text).strip(" ,;:-")
    if not normalized:
        return ""

    cleaned = strip_spoken_fillers(normalized)
    clauses = split_spoken_clauses(cleaned)
    if clauses:
        ranked = sorted(clauses, key=score_clause_for_deck, reverse=True)
        candidate = ranked[0]
    else:
        candidate = cleaned

    if is_low_signal_fragment(candidate):
        return ""

    if len(candidate) <= 110:
        return candidate
    clipped = candidate[:110].rstrip()
    for marker in (". ", "! ", "? ", ", ", "; ", " - "):
        index = clipped.rfind(marker)
        if index >= 48:
            clipped = clipped[:index].rstrip()
            break
    return clipped.rstrip(" ,;:-") + "..."


def strip_spoken_fillers(text: str) -> str:
    """Remove low-signal speech fillers from transcript text."""
    cleaned = text
    filler_patterns = (
        r"\bкак бы\b",
        r"\bтипа\b",
        r"\bкороче\b",
        r"\bну\b",
        r"\bвот\b",
        r"\bполучается\b",
        r"\bпо сути\b",
        r"\bто есть\b",
        r"\byou know\b",
        r"\bkind of\b",
        r"\bsort of\b",
        r"\bbasically\b",
        r"\bactually\b",
        r"\ben fait\b",
        r"\bdu coup\b",
        r"\balors\b",
    )
    for pattern in filler_patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"(?:\bда\b[,\s]*){2,}", "да ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:-")
    return cleaned


def split_spoken_clauses(text: str) -> list[str]:
    """Split spoken transcript text into candidate meaning clauses."""
    parts = re.split(r"(?<=[.!?])\s+|;\s+|,\s+", text)
    clauses: list[str] = []
    for part in parts:
        normalized = normalize_sentence(part).strip(" ,;:-")
        if len(normalized) < 18:
            continue
        clauses.append(normalized)
    return dedupe_preserve_order(clauses)


def score_clause_for_deck(clause: str) -> int:
    """Rank clause usefulness for deck bullets."""
    lowered = clause.lower()
    score = 0
    if any(keyword in lowered for keyword in GOAL_KEYWORDS):
        score += 3
    if any(keyword in lowered for keyword in DECISION_KEYWORDS):
        score += 4
    if any(keyword in lowered for keyword in ACTION_KEYWORDS):
        score += 4
    if any(keyword in lowered for keyword in PAIN_KEYWORDS):
        score += 3
    if any(keyword in lowered for keyword in OBJECTION_KEYWORDS):
        score += 2
    if clause.endswith("?"):
        score -= 2
    if len(clause) > 135:
        score -= 1
    score += min(len(clause) // 42, 2)
    return score


def is_low_signal_fragment(clause: str) -> bool:
    """Filter fragments that are too generic to be useful in slides."""
    lowered = clause.lower().strip(" ,;:-")
    if not lowered:
        return True
    weak_prefixes = (
        "а ",
        "в этом плане",
        "в целом",
        "ну и",
        "ну а",
        "то есть",
        "как бы",
        "короче",
        "я тебе",
        "который",
        "которая",
        "которые",
    )
    if any(lowered.startswith(prefix) for prefix in weak_prefixes) and len(lowered) < 56:
        return True

    signal_keywords = (
        *GOAL_KEYWORDS,
        *PAIN_KEYWORDS,
        *DECISION_KEYWORDS,
        *ACTION_KEYWORDS,
        *OBJECTION_KEYWORDS,
        *MARKET_KEYWORDS,
        *SETUP_KEYWORDS,
        *CATALYST_KEYWORDS,
    )
    if len(lowered) < 34 and not any(keyword in lowered for keyword in signal_keywords):
        return True
    return False


def compress_quote_text(text: str, max_chars: int = 150) -> str:
    """Compress transcript language into cleaner deck-safe quote snippets."""
    cleaned = " ".join(text.split()).strip()
    filler_patterns = (
        r"^(so|well|basically|actually|i think|you know|kind of|sort of)\s+",
        r"^(ну|короче|в общем|получается|как бы|на самом деле)\s+",
        r"^(alors|bon|du coup|en fait)\s+",
    )
    for pattern in filler_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]
    candidate = cleaned
    if sentences:
        candidate = sentences[0]
        if len(candidate) < 48 and len(sentences) > 1:
            candidate = f"{candidate} {sentences[1]}"
    if len(candidate) <= max_chars:
        return candidate

    clipped = candidate[:max_chars].rstrip()
    for marker in (". ", "! ", "? ", ", ", "; ", " - "):
        idx = clipped.rfind(marker)
        if idx >= int(max_chars * 0.55):
            clipped = clipped[:idx + 1].rstrip()
            break
    return clipped.rstrip(" ,;:-") + "…"


def build_source_note_name(transcript: TranscriptDocument) -> str:
    """Recreate the expected normalized transcript filename."""
    title = sanitize_filename_part(transcript.title.lower())
    return f"{{{transcript.project}}} {{transcript}} {title} – {transcript.date}.md"


def build_summary_filename(summary: SummaryDocument) -> str:
    """Build a predictable filename for the summary artifact."""
    title = sanitize_filename_part(summary.title.lower())
    return f"{{{summary.project}}} {{summary}} {title} – {summary.date}.md"


def sanitize_filename_part(value: str) -> str:
    """Keep filenames readable and stable."""
    cleaned = re.sub(r"[^0-9a-zа-яё\s-]+", "", value, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:60].rstrip() or "untitled summary"


def render_summary_markdown(summary: SummaryDocument) -> str:
    """Render the structured summary as markdown."""
    participants = (
        "\n".join(f"  - {participant}" for participant in summary.participants)
        if summary.participants
        else "  []"
    )
    context_notes = (
        "\n".join(f"  - {note}" for note in summary.context_notes)
        if summary.context_notes
        else ""
    )
    lines = [
        "---",
        f'title: "{escape_quotes(summary.title)}"',
        f"source_note: {summary.source_note}",
        "type: summary",
        f"date: {summary.date}",
        f"project: {summary.project}",
        f"language: {summary.language}",
        f"meeting_type: {summary.meeting_type}",
        f"deck_mode: {summary.deck_mode}",
        f"presentation_goal: {summary.presentation_goal}",
        f'audience: "{escape_quotes(summary.audience)}"',
        f"tone: {summary.tone}",
        "status: draft",
        "participants:",
        participants,
    ]
    if context_notes:
        lines.extend(["context_notes:", context_notes])
    lines.extend([
        "---",
        "",
        f"# Summary — {summary.title}",
        "",
        f"- Source note: `{summary.source_note}`",
        f"- Meeting type: `{summary.meeting_type}`",
        f"- Recommended deck mode: `{summary.deck_mode}`",
        f"- Presentation goal: `{summary.presentation_goal}`",
        f"- Audience: `{summary.audience}`",
        f"- Tone: `{summary.tone}`",
        "",
    ])

    lines.extend(render_bullet_section("Meeting Context", build_meeting_context(summary)))
    if summary.context_signals:
        lines.extend(render_bullet_section("Context Signals", summary.context_signals))
    lines.extend(render_bullet_section("Goals", summary.goals))
    lines.extend(render_bullet_section("Key Themes", summary.themes))
    lines.extend(render_bullet_section("Pain Points", summary.pain_points))
    lines.extend(render_bullet_section("Objections", summary.objections))
    lines.extend(render_bullet_section("Decisions", summary.decisions))
    lines.extend(render_bullet_section("Action Items", summary.action_items))
    if summary.topic_summaries:
        lines.extend(render_bullet_section("Topic Summaries", summary.topic_summaries))
    for title, items in summary.topic_categories.items():
        lines.extend(render_bullet_section(f"Topic Category: {title}", items))
    for title in TYPE_SECTION_TITLES.get(summary.meeting_type, []):
        if title in summary.type_sections:
            lines.extend(render_bullet_section(title, summary.type_sections[title]))
    if summary.evidence_trails:
        lines.extend(render_bullet_section("Evidence Trails", summary.evidence_trails))
    lines.extend(render_bullet_section("Notable Quotes", summary.quotes))
    lines.extend(render_bullet_section("Deck Narrative", summary.narrative))
    return "\n".join(lines)


def build_meeting_context(summary: SummaryDocument) -> list[str]:
    """Compose a compact context block for the summary."""
    participants = ", ".join(summary.participants) if summary.participants else "unknown participants"
    return [
        f"Date: {summary.date}",
        f"Participants: {participants}",
        f"Presentation goal: {summary.presentation_goal}",
        f"Audience: {summary.audience}",
        f"Tone: {summary.tone}",
        f"Summary derived from {summary.source_note}",
    ]


def render_bullet_section(title: str, items: list[str]) -> list[str]:
    """Render one markdown bullet section."""
    lines = [f"## {title}", ""]
    if items:
        lines.extend(f"- {item}" for item in items)
    else:
        lines.append("- None identified in the current heuristic pass.")
    lines.append("")
    return lines


def escape_quotes(value: str) -> str:
    """Escape double quotes for YAML string output."""
    return value.replace('"', '\\"')
