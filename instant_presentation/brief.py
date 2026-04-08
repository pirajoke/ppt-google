"""Deck brief generation from structured summaries."""

from __future__ import annotations

import os
import re
from pathlib import Path

from .i18n import localize_audience, normalize_language
from .models import DeckBriefDocument, SlidePlan, SummaryDocument


def build_brief_file(
    input_path: Path,
    output_dir: Path,
    style: str = "editorial",
) -> Path:
    """Generate a deck brief from a summary note and write it to disk."""
    from .render import parse_summary_note

    summary = parse_summary_note(input_path.read_text(encoding="utf-8"))
    brief = build_deck_brief(summary, style=style, source_summary=input_path.name)
    markdown = render_brief_markdown(brief)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / build_brief_filename(brief)
    output_path.write_text(markdown, encoding="utf-8")
    return output_path


def build_deck_brief(
    summary: SummaryDocument,
    style: str = "editorial",
    source_summary: str | None = None,
) -> DeckBriefDocument:
    """Create the intermediate slide plan from the summary."""
    slide_titles, slide_goals = choose_slide_plan(summary)
    section_inputs = build_section_inputs(summary, slide_titles)

    if adaptive_slide_plan_enabled() and summary.slide_plan is not None:
        normalized_plan = normalize_adaptive_slide_plan(
            plan=summary.slide_plan,
            fallback_titles=slide_titles,
            fallback_goals=slide_goals,
            fallback_sections=section_inputs,
        )
        if normalized_plan is not None:
            slide_titles = normalized_plan.slide_titles
            slide_goals = normalized_plan.slide_goals
            section_inputs = normalized_plan.section_inputs
    context_items, pains, decisions, objections, next_steps = choose_brief_inputs(summary)
    evidence = choose_evidence_inputs(summary)
    quotes = choose_quote_inputs(summary, decisions=decisions, next_steps=next_steps, pains=pains, evidence=evidence)
    audience = infer_audience(summary)

    return DeckBriefDocument(
        title=summary.title,
        date=summary.date,
        project=summary.project,
        source_summary=source_summary or build_summary_reference(summary),
        deck_style=style,
        slide_count=len(slide_titles),
        deck_mode=summary.deck_mode,
        meeting_type=summary.meeting_type,
        audience=audience,
        language=normalize_language(summary.language),
        presentation_goal=summary.presentation_goal,
        tone=summary.tone,
        slide_titles=slide_titles,
        slide_goals=slide_goals,
        topic_summaries=summary.topic_summaries,
        section_inputs=section_inputs,
        context_items=context_items,
        pains=pains,
        decisions=decisions,
        objections=objections,
        quotes=quotes,
        evidence=evidence,
        next_steps=next_steps,
    )


def adaptive_slide_plan_enabled() -> bool:
    """Enable adaptive slide plans only when explicitly requested via env."""
    return os.environ.get("INSTANT_PRESENTATION_ENABLE_ADAPTIVE_SLIDE_PLAN", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def normalize_adaptive_slide_plan(
    plan: SlidePlan,
    fallback_titles: list[str],
    fallback_goals: list[str],
    fallback_sections: dict[str, list[str]],
) -> SlidePlan | None:
    """Validate and sanitize a model-proposed slide plan before using it."""
    if not plan.slide_titles or not plan.slide_goals:
        return None
    if len(plan.slide_titles) != len(plan.slide_goals):
        return None
    if not (3 <= len(plan.slide_titles) <= 8):
        return None

    titles: list[str] = []
    goals: list[str] = []
    seen_titles: set[str] = set()
    for index, raw_title in enumerate(plan.slide_titles):
        title = " ".join(raw_title.split()).strip()
        if not title:
            return None
        fingerprint = re.sub(r"[\W_]+", "", title.lower())
        if not fingerprint or fingerprint in seen_titles:
            return None
        seen_titles.add(fingerprint)
        titles.append(title[:72])

        goal = " ".join(plan.slide_goals[index].split()).strip()
        if not goal:
            goal = fallback_goals[index] if index < len(fallback_goals) else ""
        if not goal:
            return None
        goals.append(goal[:180])

    sections: dict[str, list[str]] = {}
    for index, title in enumerate(titles):
        fallback_key = fallback_titles[index] if index < len(fallback_titles) else ""
        raw_items = plan.section_inputs.get(plan.slide_titles[index], []) if isinstance(plan.section_inputs, dict) else []
        compact_items = choose_compact_items(raw_items, fallback_sections.get(fallback_key, []), limit=4)
        if not compact_items:
            compact_items = fallback_sections.get(fallback_key, [])
        sections[title] = compact_items[:4]

    return SlidePlan(slide_titles=titles, slide_goals=goals, section_inputs=sections)


def build_section_inputs(summary: SummaryDocument, slide_titles: list[str]) -> dict[str, list[str]]:
    """Build per-slide inputs aligned with the active slide plan."""
    sections: list[list[str]]
    if summary.meeting_type == "research":
        sections = [
            section_or_fallback(summary, "Corpus Overview", summary.goals, summary.context_signals),
            section_or_fallback(summary, "Repeated Pain Points", summary.pain_points, summary.themes),
            section_or_fallback(summary, "Tool Signals", summary.themes, summary.context_signals),
            section_or_fallback(summary, "Direction Patterns", summary.decisions, summary.action_items),
            section_or_fallback(summary, "Evidence Highlights", summary.evidence_trails, summary.narrative),
            section_or_fallback(summary, "Next Slice", summary.action_items, summary.narrative),
        ]
    elif summary.meeting_type == "business":
        if summary.presentation_goal == "decision":
            sections = [
                section_or_fallback(summary, "Conversation Context", summary.goals, summary.context_signals, summary.themes),
                choose_decision_inputs(summary),
                choose_compact_items(
                    section_or_fallback(summary, "Risks and Blockers", summary.objections, summary.pain_points),
                    section_or_fallback(summary, "Open Questions", summary.objections),
                    limit=5,
                ),
                section_or_fallback(summary, "Action Grid", summary.action_items, summary.narrative),
                section_or_fallback(summary, "Open Questions", summary.objections, summary.pain_points),
            ]
        elif summary.presentation_goal == "follow_up":
            sections = [
                section_or_fallback(summary, "Conversation Context", summary.context_signals, summary.goals, summary.themes),
                choose_decision_inputs(summary),
                section_or_fallback(summary, "Action Grid", summary.action_items, summary.narrative),
                section_or_fallback(summary, "Risks and Blockers", summary.objections, summary.pain_points),
                section_or_fallback(summary, "Open Questions", summary.objections, summary.pain_points),
            ]
        else:
            sections = [
                section_or_fallback(summary, "Conversation Context", summary.context_signals, summary.goals, summary.themes),
                choose_decision_inputs(summary),
                section_or_fallback(summary, "Risks and Blockers", summary.objections, summary.pain_points),
                section_or_fallback(summary, "Action Grid", summary.action_items, summary.narrative),
                section_or_fallback(summary, "Open Questions", summary.objections, summary.pain_points),
            ]
    elif summary.meeting_type == "trading":
        sections = [
            section_or_fallback(summary, "Market Context", summary.context_signals, summary.themes),
            section_or_fallback(summary, "Trade Ideas / Setups", summary.decisions, summary.themes),
            section_or_fallback(summary, "Risk Management", summary.objections, summary.pain_points),
            section_or_fallback(summary, "Macro and Catalysts", summary.objections, summary.context_signals),
            section_or_fallback(summary, "Watchlist / Actions", summary.action_items, summary.narrative),
        ]
    elif summary.meeting_type == "lecture":
        thesis_items = section_or_fallback(summary, "Topic and Main Thesis", summary.goals, summary.themes)
        key_object_items = section_or_fallback(summary, "Key Facts", summary.themes)
        explanation_items = section_or_fallback(summary, "Links Between Ideas", summary.context_signals, summary.themes)
        insight_items = section_or_fallback(summary, "Insights", summary.decisions, summary.themes)
        memory_items = choose_compact_items(
            section_or_fallback(summary, "Further Study", summary.action_items),
            thesis_items,
            insight_items,
            limit=4,
        )
        sections = [
            thesis_items,
            explanation_items,
            key_object_items,
            insight_items,
            memory_items,
        ]
    elif summary.meeting_type == "ideas":
        if summary.presentation_goal == "pitch":
            sections = [
                section_or_fallback(summary, "Project: What and Why", summary.goals, summary.themes),
                choose_compact_items(summary.themes, summary.context_signals, summary.pain_points, limit=4),
                section_or_fallback(summary, "Current State", summary.context_signals, summary.themes),
                section_or_fallback(summary, "Design Decisions", summary.decisions, summary.themes),
                section_or_fallback(summary, "Next: Path to MVP", summary.action_items, summary.narrative),
            ]
        else:
            sections = [
                section_or_fallback(summary, "Project: What and Why", summary.goals, summary.themes),
                section_or_fallback(summary, "Current State", summary.context_signals, summary.themes),
                section_or_fallback(summary, "Design Decisions", summary.decisions, summary.themes),
                section_or_fallback(summary, "Deferred / Cut", summary.objections, summary.pain_points),
                section_or_fallback(summary, "Next: Path to MVP", summary.action_items, summary.narrative),
            ]
    else:
        sections = [
            section_or_fallback(summary, "What We Talked About", summary.themes, summary.goals),
            section_or_fallback(summary, "Their News", summary.context_signals, summary.themes),
            section_or_fallback(summary, "Recommendations", summary.decisions, summary.objections, summary.themes),
            section_or_fallback(summary, "Agreements", summary.decisions, summary.action_items),
            section_or_fallback(summary, "Follow-up", summary.action_items, summary.narrative),
        ]

    return {
        title: sections[index] if index < len(sections) else []
        for index, title in enumerate(slide_titles)
    }


def choose_brief_inputs(summary: SummaryDocument) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """Map summary content into renderer inputs with talk-type awareness."""
    if summary.presentation_goal == "follow_up":
        return choose_follow_up_inputs(summary)
    if summary.presentation_goal == "decision":
        return choose_decision_goal_inputs(summary)
    if summary.presentation_goal == "pitch":
        return choose_pitch_inputs(summary)

    sections = summary.type_sections
    if summary.meeting_type == "research":
        return (
            section_or_fallback(summary, "Corpus Overview", summary.goals, summary.context_signals),
            section_or_fallback(summary, "Repeated Pain Points", summary.pain_points, summary.themes),
            section_or_fallback(summary, "Direction Patterns", summary.decisions, summary.action_items),
            section_or_fallback(summary, "Audience / Talk Mix", summary.objections, summary.context_signals),
            section_or_fallback(summary, "Evidence Highlights", summary.action_items, summary.narrative),
        )
    if summary.meeting_type == "business":
        return (
            section_or_fallback(summary, "Conversation Context", summary.context_signals, summary.themes),
            section_or_fallback(summary, "Risks and Blockers", summary.pain_points, summary.objections),
            choose_decision_inputs(summary),
            section_or_fallback(summary, "Risks and Blockers", summary.objections, summary.pain_points),
            section_or_fallback(summary, "Action Grid", summary.action_items, summary.narrative),
        )
    if summary.meeting_type == "trading":
        return (
            section_or_fallback(summary, "Market Context", summary.context_signals, summary.themes),
            section_or_fallback(summary, "Risk Management", summary.pain_points, summary.objections),
            section_or_fallback(summary, "Trade Ideas / Setups", summary.decisions, summary.themes),
            section_or_fallback(summary, "Macro and Catalysts", summary.objections, summary.context_signals),
            section_or_fallback(summary, "Watchlist / Actions", summary.action_items, summary.narrative),
        )
    if summary.meeting_type == "lecture":
        return (
            section_or_fallback(summary, "Topic and Main Thesis", summary.goals, summary.themes),
            section_or_fallback(summary, "Key Facts", summary.themes),
            section_or_fallback(summary, "Insights", summary.decisions, summary.themes),
            section_or_fallback(summary, "Links Between Ideas", summary.context_signals, summary.themes),
            section_or_fallback(summary, "Further Study", summary.action_items, summary.themes),
        )
    if summary.meeting_type == "ideas":
        return (
            section_or_fallback(summary, "Project: What and Why", summary.goals, summary.themes),
            section_or_fallback(summary, "Deferred / Cut", summary.pain_points, summary.objections),
            section_or_fallback(summary, "Design Decisions", summary.decisions, summary.themes),
            section_or_fallback(summary, "Deferred / Cut", summary.objections, summary.pain_points),
            section_or_fallback(summary, "Next: Path to MVP", summary.action_items, summary.narrative),
        )
    return (
        section_or_fallback(summary, "What We Talked About", summary.themes, summary.goals),
        section_or_fallback(summary, "Their News", summary.themes, summary.context_signals),
        section_or_fallback(summary, "Agreements", summary.decisions, summary.action_items),
        section_or_fallback(summary, "Recommendations", summary.objections, summary.context_signals),
        section_or_fallback(summary, "Follow-up", summary.action_items, summary.narrative),
    )


def choose_follow_up_inputs(summary: SummaryDocument) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """Select warmer, sendable inputs for post-call follow-up decks."""
    if summary.meeting_type == "business":
        return (
            section_or_fallback(summary, "Conversation Context", summary.context_signals, summary.themes),
            section_or_fallback(summary, "Risks and Blockers", summary.objections, summary.pain_points),
            choose_compact_items(summary.decisions, summary.action_items, summary.themes, limit=4),
            choose_compact_items(
                section_or_fallback(summary, "Open Questions", summary.objections),
                section_or_fallback(summary, "Risks and Blockers", summary.objections, summary.pain_points),
                limit=4,
            ),
            section_or_fallback(summary, "Action Grid", summary.action_items, summary.narrative),
        )
    if summary.meeting_type == "social":
        return (
            section_or_fallback(summary, "What We Talked About", summary.themes, summary.goals),
            section_or_fallback(summary, "Recommendations", summary.decisions, summary.action_items),
            section_or_fallback(summary, "Agreements", summary.decisions, summary.action_items),
            section_or_fallback(summary, "Recommendations", summary.objections, summary.context_signals),
            section_or_fallback(summary, "Follow-up", summary.action_items, summary.narrative),
        )
    return (
        choose_compact_items(summary.context_signals, summary.themes, limit=4),
        choose_compact_items(summary.objections, summary.pain_points, limit=4),
        choose_compact_items(summary.decisions, summary.action_items, limit=4),
        choose_compact_items(summary.objections, summary.themes, limit=4),
        choose_compact_items(summary.action_items, summary.narrative, limit=4),
    )


def choose_decision_goal_inputs(summary: SummaryDocument) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """Select sharper decision-oriented inputs."""
    if summary.meeting_type == "business":
        return (
            section_or_fallback(summary, "Conversation Context", summary.goals, summary.context_signals),
            section_or_fallback(summary, "Risks and Blockers", summary.pain_points, summary.objections),
            choose_decision_inputs(summary),
            choose_compact_items(
                section_or_fallback(summary, "Open Questions", summary.objections),
                section_or_fallback(summary, "Risks and Blockers", summary.objections, summary.pain_points),
                limit=4,
            ),
            section_or_fallback(summary, "Action Grid", summary.action_items, summary.narrative),
        )
    if summary.meeting_type == "trading":
        return (
            section_or_fallback(summary, "Market Context", summary.context_signals, summary.themes),
            section_or_fallback(summary, "Risk Management", summary.objections, summary.pain_points),
            section_or_fallback(summary, "Trade Ideas / Setups", summary.decisions, summary.themes),
            section_or_fallback(summary, "Macro and Catalysts", summary.objections, summary.context_signals),
            section_or_fallback(summary, "Watchlist / Actions", summary.action_items, summary.narrative),
        )
    return (
        choose_compact_items(summary.goals, summary.context_signals, limit=4),
        choose_compact_items(summary.pain_points, summary.objections, limit=4),
        choose_compact_items(summary.decisions, summary.action_items, limit=4),
        choose_compact_items(summary.objections, summary.themes, limit=4),
        choose_compact_items(summary.action_items, summary.narrative, limit=4),
    )


def choose_pitch_inputs(summary: SummaryDocument) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """Select persuasive inputs for idea/pitch decks."""
    if summary.meeting_type == "ideas":
        return (
            section_or_fallback(summary, "Project: What and Why", summary.goals, summary.themes),
            choose_compact_items(summary.pain_points, summary.context_signals, limit=4),
            section_or_fallback(summary, "Design Decisions", summary.decisions, summary.themes),
            section_or_fallback(summary, "Deferred / Cut", summary.objections, summary.pain_points),
            section_or_fallback(summary, "Next: Path to MVP", summary.action_items, summary.narrative),
        )
    return (
        choose_compact_items(summary.goals, summary.themes, limit=4),
        choose_compact_items(summary.pain_points, summary.objections, limit=4),
        choose_compact_items(summary.decisions, summary.action_items, limit=4),
        choose_compact_items(summary.objections, summary.context_signals, limit=4),
        choose_compact_items(summary.action_items, summary.narrative, limit=4),
    )


def choose_quote_inputs(
    summary: SummaryDocument,
    decisions: list[str],
    next_steps: list[str],
    pains: list[str],
    evidence: list[str],
) -> list[str]:
    """Select quote/evidence blocks appropriate for the deck type."""
    if summary.meeting_type == "research":
        return section_or_fallback(summary, "Tool Signals", summary.themes, summary.context_signals)
    ranked: list[tuple[int, str]] = []
    anchors = " ".join([*decisions[:3], *next_steps[:3], *pains[:2], *evidence[:2]]).lower()
    for quote in summary.quotes:
        lowered = quote.lower()
        score = 0
        if summary.presentation_goal == "follow_up":
            score += sum(token in lowered for token in ("next step", "follow up", "send", "let's", "great", "help"))
        elif summary.presentation_goal == "decision":
            score += sum(token in lowered for token in ("should", "need", "cannot", "risk", "priority", "decision"))
        elif summary.presentation_goal == "pitch":
            score += sum(token in lowered for token in ("build", "opportunity", "mvp", "why", "project"))
        if any(fragment and fragment in anchors for fragment in lowered.split()[:8]):
            score += 2
        if "—" in quote:
            score += 1
        ranked.append((score, quote))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    ordered = [quote for _, quote in ranked]
    return ordered[:3] or summary.quotes[:3]


def choose_evidence_inputs(summary: SummaryDocument) -> list[str]:
    """Select evidence trails that best match the deck goal."""
    if summary.meeting_type == "research":
        return summary.evidence_trails[:6]

    preferred_labels = {
        "decision": ("Decisions", "Action Items", "Open Questions", "Objections", "Pain Points"),
        "follow_up": ("Action Items", "Decisions", "Recommendations", "Open Questions", "Goals"),
        "pitch": ("Goals", "Decisions", "Action Items", "Pain Points"),
        "recap": ("Goals", "Pain Points", "Action Items", "Decisions"),
        "research": ("Evidence Highlights", "Pain Points", "Tool Signals"),
    }.get(summary.presentation_goal, ("Goals", "Pain Points", "Action Items", "Decisions"))

    ranked: list[tuple[int, str]] = []
    for trail in summary.evidence_trails:
        score = 0
        for index, label in enumerate(preferred_labels):
            if trail.startswith(f"{label}:"):
                score += 10 - index
        if summary.presentation_goal == "follow_up" and any(token in trail.lower() for token in ("next step", "follow up", "send", "recommend")):
            score += 2
        if summary.presentation_goal == "decision" and any(token in trail.lower() for token in ("cannot", "risk", "should", "priority", "question")):
            score += 2
        if summary.presentation_goal == "pitch" and any(token in trail.lower() for token in ("mvp", "build", "opportunity", "project")):
            score += 2
        ranked.append((score, trail))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    ordered = [trail for _, trail in ranked]
    return ordered[:6] or summary.evidence_trails[:6]


def choose_decision_inputs(summary: SummaryDocument) -> list[str]:
    """Prefer explicit decisions; otherwise fall back to stronger directional inputs."""
    fallback_section = filter_placeholder_items(section_or_fallback(summary, "Key Decisions", summary.decisions))
    explicit = [
        item for item in summary.decisions
        if item != "None identified in the current heuristic pass."
    ] or fallback_section
    if explicit:
        return explicit

    candidates = [
        *summary.action_items,
        *summary.context_signals,
        *summary.themes,
    ]
    ranked: list[tuple[int, str]] = []
    seen: set[str] = set()
    for item in candidates:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        score = 0
        lowered = normalized.lower()
        if "next step" in lowered or "action items" in lowered:
            score += 4
        if "should" in lowered or "priority" in lowered or "for v1" in lowered:
            score += 3
        if "same day" in lowered or "client-ready" in lowered:
            score += 2
        if normalized.endswith("?"):
            score -= 3
        if lowered.startswith("thanks "):
            score -= 3
        ranked.append((score, normalized))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item for _, item in ranked[:4]] or summary.themes[:4]


def section_or_fallback(summary: SummaryDocument, section: str, *fallbacks: list[str]) -> list[str]:
    """Return a type-specific section when present, otherwise merge fallbacks."""
    if summary.type_sections.get(section):
        return filter_placeholder_items(summary.type_sections[section])
    merged: list[str] = []
    seen: set[str] = set()
    for group in fallbacks:
        for item in group:
            normalized = item.strip()
            if normalized == "None identified in the current heuristic pass.":
                continue
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
            if len(merged) >= 4:
                return merged
    return merged


def choose_compact_items(*groups: list[str], limit: int) -> list[str]:
    """Merge several lists into a compact deduplicated set."""
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            normalized = item.strip()
            if not normalized or normalized == "None identified in the current heuristic pass.":
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
            if len(merged) >= limit:
                return merged
    return merged


def filter_placeholder_items(items: list[str]) -> list[str]:
    """Remove placeholder bullets from extracted content."""
    return [item for item in items if item != "None identified in the current heuristic pass."]


def infer_audience(summary: SummaryDocument) -> str:
    """Infer a rough deck audience from the deck mode."""
    if summary.audience.strip():
        return summary.audience
    language = normalize_language(summary.language)
    if summary.meeting_type == "social" and summary.deck_mode == "client-followup":
        return localize_audience("relationship_follow_up", language)
    mapping = {
        "sales-recap": "client_or_prospect",
        "client-followup": "client_stakeholder",
        "research-insights": "internal_product_or_strategy_team",
        "internal-decision": "internal_decision_makers",
    }
    return localize_audience(mapping.get(summary.deck_mode, "mixed_stakeholders"), language)


def choose_slide_plan(summary: SummaryDocument) -> tuple[list[str], list[str]]:
    """Choose slide titles/goals based on the meeting shape."""
    language = normalize_language(summary.language)
    goal = summary.presentation_goal
    plans = {
        "research": {
            "en": (
                ["Corpus Overview", "Repeated Pain Points", "Tool Signals", "Direction Patterns", "Evidence Highlights", "Next Slice"],
                [
                    "Open with the shape of the corpus before making any claims.",
                    "Show repeated pain points that appear across multiple notes.",
                    "Summarize tool and workflow signals that recur in the corpus.",
                    "Highlight repeated decisions, action patterns, and directional moves.",
                    "Close with grounded evidence and what to test on the next slice.",
                    "Translate the corpus read into the next review or product loop.",
                ],
            ),
            "ru": (
                ["Срез корпуса", "Повторяющиеся боли", "Сигналы по инструментам", "Повторяющиеся направления", "Evidence highlights", "Next slice"],
                [
                    "Открыть deck формой корпуса, а не выводами из одной заметки.",
                    "Показать боли, которые реально повторяются между notes.",
                    "Собрать recurring tool и workflow signals по корпусу.",
                    "Подсветить повторяющиеся решения, паттерны действий и направления.",
                    "Закрыть deck grounded evidence и тем, что проверять на следующем срезе.",
                    "Перевести срез корпуса в следующий исследовательский или продуктовый цикл.",
                ],
            ),
            "fr": (
                ["Vue corpus", "Douleurs récurrentes", "Signaux outils", "Directions récurrentes", "Evidence highlights", "Next slice"],
                [
                    "Ouvrir avec la forme du corpus avant toute conclusion.",
                    "Montrer les douleurs qui reviennent sur plusieurs notes.",
                    "Résumer les signaux outils et workflow récurrents.",
                    "Mettre en avant les décisions et directions qui se répètent.",
                    "Terminer avec des preuves concrètes et la prochaine tranche à tester.",
                    "Traduire la lecture du corpus en prochaine boucle d'analyse ou de produit.",
                ],
            ),
        },
        "business": {
            "en": (
                ["Context", "Key Decisions", "Risks and Blockers", "Action Items", "Open Questions"],
                [
                    "Clarify who was involved and why the conversation mattered.",
                    "Surface the decisions that actually move the work forward.",
                    "Show blockers, constraints, and risks without softening them.",
                    "Translate the conversation into accountable who/what/when items.",
                    "End with unresolved questions that still need owner attention.",
                ],
            ),
            "ru": (
                ["Контекст", "Ключевые решения", "Риски и блокеры", "Action items", "Открытые вопросы"],
                [
                    "Зафиксировать, кто участвовал и зачем был нужен разговор.",
                    "Подсветить решения, которые реально двигают работу вперёд.",
                    "Показать блокеры, ограничения и риски без сглаживания.",
                    "Перевести разговор в конкретные кто/что/когда.",
                    "Закрыть deck вопросами, которые ещё требуют владельца.",
                ],
            ),
            "fr": (
                ["Contexte", "Décisions clés", "Risques et blocages", "Actions", "Questions ouvertes"],
                [
                    "Clarifier qui était impliqué et pourquoi l'échange comptait.",
                    "Faire ressortir les décisions qui font avancer le travail.",
                    "Montrer les blocages et risques sans les adoucir.",
                    "Traduire l'appel en qui/quoi/quand actionnables.",
                    "Terminer avec les questions encore non résolues.",
                ],
            ),
        },
        "trading": {
            "en": (
                ["Market Context", "Trade Ideas / Setups", "Risk Management", "Macro and Catalysts", "Watchlist / Actions"],
                [
                    "Open with the market frame that shapes the discussion.",
                    "List setups, tickers, and trade ideas worth tracking.",
                    "Show the risk framework, invalidation logic, and sizing posture.",
                    "Capture macro drivers and catalysts behind the ideas.",
                    "Finish with watchlist updates and explicit next actions.",
                ],
            ),
            "ru": (
                ["Market context", "Trade ideas / setups", "Risk management", "Macro и catalysts", "Watchlist / actions"],
                [
                    "Открыть deck рыночным контекстом, в котором идёт разговор.",
                    "Собрать setups, тикеры и trade ideas, которые стоит отслеживать.",
                    "Показать risk framework, invalidation logic и sizing posture.",
                    "Зафиксировать макро-факторы и катализаторы за идеями.",
                    "Закрыть deck watchlist-ом и конкретными действиями.",
                ],
            ),
            "fr": (
                ["Contexte marché", "Idées de trade / setups", "Gestion du risque", "Macro et catalyseurs", "Watchlist / actions"],
                [
                    "Ouvrir avec le cadre de marché qui structure l'échange.",
                    "Lister les setups, tickers et idées de trade à suivre.",
                    "Montrer la logique de risque, d'invalidation et de sizing.",
                    "Capturer les moteurs macro et catalyseurs derrière les idées.",
                    "Terminer avec la watchlist et les actions à prendre.",
                ],
            ),
        },
        "lecture": {
            "en": (
                ["Main Thesis", "Analytical Frame", "Key Objects", "Historical Forces", "What to Remember"],
                [
                    "Open with the central idea of the lecture, not with scattered details.",
                    "Establish the conceptual frame through which the lecture should be read.",
                    "Name the main buildings, examples, or objects that carry the explanation.",
                    "Show the historical forces that explain why these monuments matter.",
                    "Close with the few things worth retaining after the lecture ends.",
                ],
            ),
            "ru": (
                ["Главный тезис", "Аналитическая рамка", "Ключевые объекты", "Исторические силы", "Что запомнить"],
                [
                    "Открыть deck центральной мыслью лекции, а не россыпью деталей.",
                    "Собрать концептуальную рамку, через которую читается материал лекции.",
                    "Назвать здания, примеры или объекты, через которые раскрывается тема.",
                    "Показать исторические силы, которые объясняют значимость памятников.",
                    "Закрыть deck несколькими мыслями, которые реально стоит унести с собой.",
                ],
            ),
            "fr": (
                ["Thèse principale", "Cadre analytique", "Objets clés", "Forces historiques", "À retenir"],
                [
                    "Ouvrir avec l'idée centrale plutôt qu'avec des détails dispersés.",
                    "Poser le cadre conceptuel à travers lequel la conférence doit être lue.",
                    "Nommer les bâtiments, exemples ou objets qui portent l'explication.",
                    "Montrer les forces historiques qui donnent leur portée aux monuments.",
                    "Terminer avec les quelques idées à garder en mémoire.",
                ],
            ),
        },
        "ideas": {
            "en": (
                ["Project: What and Why", "Current State", "Design Decisions", "Deferred / Cut", "Next: Path to MVP"],
                [
                    "Clarify what the project is and why it matters.",
                    "Show the actual current state rather than an aspirational vision.",
                    "Make design and architecture choices explicit.",
                    "Track what was postponed, cut, or intentionally excluded.",
                    "Finish with the shortest credible path to MVP.",
                ],
            ),
            "ru": (
                ["Проект: что и зачем", "Текущее состояние", "Решения по дизайну", "Отложено / вырезано", "Next: путь к MVP"],
                [
                    "Прояснить, что это за проект и зачем он нужен.",
                    "Показать реальное текущее состояние, а не только видение.",
                    "Сделать явными ключевые design и architecture choices.",
                    "Зафиксировать, что отложили или сознательно вырезали.",
                    "Закрыть deck кратчайшим реалистичным путём к MVP.",
                ],
            ),
            "fr": (
                ["Projet: quoi et pourquoi", "État actuel", "Décisions de design", "Reporté / coupé", "Suite: chemin vers le MVP"],
                [
                    "Clarifier ce qu'est le projet et pourquoi il compte.",
                    "Montrer l'état réel actuel, pas seulement la vision.",
                    "Rendre explicites les choix de design et d'architecture.",
                    "Tracer ce qui a été reporté ou retiré.",
                    "Terminer avec le plus court chemin crédible vers le MVP.",
                ],
            ),
        },
        "social": {
            "en": (
                ["What We Talked About", "Their News", "Recommendations", "Agreements", "Follow-up"],
                [
                    "Capture the main threads of the personal conversation.",
                    "Pull out updates, changes, and news from the other person.",
                    "List recommendations, suggestions, or introductions mentioned.",
                    "Make the actual agreements explicit.",
                    "Finish with warm but concrete follow-up actions.",
                ],
            ),
            "ru": (
                ["О чём поговорили", "Новости собеседника", "Рекомендации", "Договорённости", "Follow-up"],
                [
                    "Зафиксировать главные ветки личного разговора.",
                    "Вытащить обновления и новости от собеседника.",
                    "Собрать рекомендации, советы и возможные интро.",
                    "Сделать явными реальные договорённости.",
                    "Закрыть deck тёплым, но конкретным follow-up.",
                ],
            ),
            "fr": (
                ["De quoi on a parlé", "Nouvelles de l'interlocuteur", "Recommandations", "Accords", "Suivi"],
                [
                    "Capturer les fils principaux de l'échange personnel.",
                    "Faire ressortir les nouvelles et changements côté interlocuteur.",
                    "Lister les recommandations, conseils ou intros évoquées.",
                    "Rendre explicites les accords réels.",
                    "Terminer avec un suivi concret mais chaleureux.",
                ],
            ),
        },
    }
    overrides = build_goal_overrides(language)
    if (summary.meeting_type, goal) in overrides:
        return overrides[(summary.meeting_type, goal)]
    lang = plans.get(summary.meeting_type, plans["business"])
    return lang.get(language, lang["en"])


def build_goal_overrides(language: str) -> dict[tuple[str, str], tuple[list[str], list[str]]]:
    """Return goal-specific slide plan overrides."""
    overrides = {
        ("business", "decision"): {
            "en": (
                ["Decision Frame", "Key Decisions", "Risks and Tradeoffs", "Action Items", "Open Questions"],
                [
                    "Open with the decision context and what requires alignment now.",
                    "List the decisions that should shape execution.",
                    "Make tradeoffs and blockers explicit before commitment.",
                    "Translate decisions into owners and next moves.",
                    "Close with unresolved items that still block confidence.",
                ],
            ),
            "ru": (
                ["Decision frame", "Ключевые решения", "Риски и tradeoffs", "Action items", "Открытые вопросы"],
                [
                    "Открыть deck рамкой решения и тем, что нужно согласовать сейчас.",
                    "Собрать решения, которые должны определить исполнение.",
                    "Сделать явными tradeoffs и блокеры до коммита.",
                    "Перевести решения в owners и next moves.",
                    "Закрыть тем, что ещё мешает уверенному решению.",
                ],
            ),
            "fr": (
                ["Cadre de décision", "Décisions clés", "Risques et arbitrages", "Actions", "Questions ouvertes"],
                [
                    "Ouvrir avec le cadre de décision et ce qui doit être aligné maintenant.",
                    "Lister les décisions qui doivent guider l'exécution.",
                    "Rendre explicites les arbitrages et blocages avant engagement.",
                    "Traduire les décisions en owners et prochaines étapes.",
                    "Terminer avec ce qui bloque encore la confiance.",
                ],
            ),
        },
        ("business", "follow_up"): {
            "en": (
                ["Context", "Key Decisions", "Action Items", "Risks and Blockers", "Open Questions"],
                [
                    "Re-establish the conversation context for the recipient.",
                    "Restate the decisions worth remembering after the call.",
                    "Put follow-up actions before the deck loses urgency.",
                    "Capture blockers and risks that still matter.",
                    "End with the unresolved questions that need a reply.",
                ],
            ),
            "ru": (
                ["Контекст", "Ключевые решения", "Action items", "Риски и блокеры", "Открытые вопросы"],
                [
                    "Быстро вернуть получателя в контекст разговора.",
                    "Повторить решения, которые важно удержать после звонка.",
                    "Поставить follow-up действия раньше, пока deck не потерял срочность.",
                    "Зафиксировать блокеры и риски, которые ещё важны.",
                    "Закрыть открытыми вопросами, на которые нужен ответ.",
                ],
            ),
            "fr": (
                ["Contexte", "Décisions clés", "Actions", "Risques et blocages", "Questions ouvertes"],
                [
                    "Rappeler rapidement le contexte de l'échange.",
                    "Restituer les décisions à retenir après l'appel.",
                    "Faire remonter les actions pendant qu'elles sont encore fraîches.",
                    "Capturer les blocages et risques qui restent actifs.",
                    "Terminer avec les questions qui attendent une réponse.",
                ],
            ),
        },
        ("ideas", "pitch"): {
            "en": (
                ["Project Intent", "Why Now", "Current State", "Design Decisions", "Path to MVP"],
                [
                    "Open with the idea and the reason it deserves attention.",
                    "Explain why the timing or market pull matters now.",
                    "Show what already exists versus what is still conceptual.",
                    "Make the key product and architecture decisions explicit.",
                    "Finish with the shortest credible path to MVP.",
                ],
            ),
            "ru": (
                ["Project intent", "Почему сейчас", "Текущее состояние", "Решения по дизайну", "Путь к MVP"],
                [
                    "Открыть deck идеей и причиной, почему она заслуживает внимания.",
                    "Объяснить, почему timing или рыночный сигнал важен именно сейчас.",
                    "Показать, что уже существует, а что пока остаётся концептом.",
                    "Сделать явными ключевые product и architecture decisions.",
                    "Закрыть кратчайшим реалистичным путём к MVP.",
                ],
            ),
            "fr": (
                ["Intention du projet", "Pourquoi maintenant", "État actuel", "Décisions de design", "Chemin vers le MVP"],
                [
                    "Ouvrir avec l'idée et la raison pour laquelle elle mérite l'attention.",
                    "Expliquer pourquoi le timing ou le signal de marché compte maintenant.",
                    "Montrer ce qui existe déjà par rapport à ce qui reste conceptuel.",
                    "Rendre explicites les décisions produit et architecture.",
                    "Terminer avec le plus court chemin crédible vers le MVP.",
                ],
            ),
        },
    }
    return {key: value.get(language, value["en"]) for key, value in overrides.items()}


def build_summary_reference(summary: SummaryDocument) -> str:
    """Recreate the expected summary filename."""
    title = sanitize_filename_part(summary.title.lower())
    return f"{{{summary.project}}} {{summary}} {title} – {summary.date}.md"


def build_brief_filename(brief: DeckBriefDocument) -> str:
    """Build a predictable filename for the deck brief artifact."""
    title = sanitize_filename_part(brief.title.lower())
    return f"{{{brief.project}}} {{brief}} {title} – {brief.date}.md"


def sanitize_filename_part(value: str) -> str:
    """Keep filenames readable and stable."""
    cleaned = re.sub(r"[^0-9a-zа-яё\s-]+", "", value, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:60].rstrip() or "untitled brief"


def render_brief_markdown(brief: DeckBriefDocument) -> str:
    """Render the deck brief as markdown with frontmatter."""
    slide_titles = "\n".join(f"  - {title}" for title in brief.slide_titles)
    slide_goals = "\n".join(f"  - {goal}" for goal in brief.slide_goals)
    lines = [
        "---",
        f'title: "{escape_quotes(brief.title)}"',
        f"source_summary: {brief.source_summary}",
        "type: brief",
        f"date: {brief.date}",
        f"project: {brief.project}",
        f"language: {brief.language}",
        f"deck_style: {brief.deck_style}",
        f"slide_count: {brief.slide_count}",
        f"deck_mode: {brief.deck_mode}",
        f"meeting_type: {brief.meeting_type}",
        f'audience: "{escape_quotes(brief.audience)}"',
        f"presentation_goal: {brief.presentation_goal}",
        f"tone: {brief.tone}",
        "slide_titles:",
        slide_titles,
        "slide_goals:",
        slide_goals,
        "---",
        "",
        f"# Deck Brief — {brief.title}",
        "",
        f"- Source summary: `{brief.source_summary}`",
        f"- Audience: `{brief.audience}`",
        f"- Presentation goal: `{brief.presentation_goal}`",
        f"- Tone: `{brief.tone}`",
        f"- Deck style: `{brief.deck_style}`",
        f"- Deck mode: `{brief.deck_mode}`",
        "",
    ]
    lines.extend(render_bullet_section("Context Items", brief.context_items))
    lines.extend(render_bullet_section("Pain Inputs", brief.pains))
    lines.extend(render_bullet_section("Decision Inputs", brief.decisions))
    lines.extend(render_bullet_section("Objection Inputs", brief.objections))
    lines.extend(render_bullet_section("Quote Inputs", brief.quotes))
    lines.extend(render_bullet_section("Evidence Inputs", brief.evidence))
    lines.extend(render_bullet_section("Next Step Inputs", brief.next_steps))
    lines.extend(render_bullet_section("Topic Summaries", brief.topic_summaries))
    for title, items in brief.section_inputs.items():
        lines.extend(render_bullet_section(f"Section Input: {title}", items))
    return "\n".join(lines)


def render_bullet_section(title: str, items: list[str]) -> list[str]:
    """Render one markdown bullet section."""
    lines = [f"## {title}", ""]
    if items:
        lines.extend(f"- {item}" for item in items)
    else:
        lines.append("- None identified.")
    lines.append("")
    return lines


def escape_quotes(value: str) -> str:
    """Escape double quotes for YAML string output."""
    return value.replace('"', '\\"')
