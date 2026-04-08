"""HTML deck rendering from structured summary notes."""

from __future__ import annotations

import html
import re
from pathlib import Path

from .brief import build_deck_brief
from .i18n import deck_copy, detect_language_from_parts, localize_deck_mode, localize_meeting_type, normalize_language
from .models import DeckBriefDocument, SummaryDocument

GENERIC_SUMMARY_SECTIONS = {
    "Meeting Context",
    "Context Signals",
    "Goals",
    "Key Themes",
    "Pain Points",
    "Objections",
    "Decisions",
    "Action Items",
    "Topic Summaries",
    "Notable Quotes",
    "Deck Narrative",
    "Evidence Trails",
}


def render_summary_file(input_path: Path, output_dir: Path, style: str = "editorial") -> Path:
    """Render a summary or brief note into a single-file HTML presentation."""
    note_text = input_path.read_text(encoding="utf-8")
    note_type = detect_note_type(note_text)
    if note_type == "brief":
        brief = parse_brief_note(note_text)
    else:
        summary = parse_summary_note(note_text)
        brief = build_deck_brief(summary, style=style, source_summary=input_path.name)
    deck_html = render_html_deck(brief=brief, style=style)

    deck_dir = output_dir / slugify(brief.title)
    deck_dir.mkdir(parents=True, exist_ok=True)
    output_path = deck_dir / "index.html"
    output_path.write_text(deck_html, encoding="utf-8")
    return output_path


def detect_note_type(note_text: str) -> str:
    """Detect the artifact type from frontmatter."""
    frontmatter, _ = split_frontmatter(note_text)
    metadata = parse_frontmatter(frontmatter)
    return str(metadata.get("type", "summary"))


def parse_summary_note(note_text: str) -> SummaryDocument:
    """Parse a generated summary markdown note back into a structured object."""
    frontmatter, body = split_frontmatter(note_text)
    metadata = parse_frontmatter(frontmatter)
    sections = parse_sections(body)

    topic_categories = {
        title.removeprefix("Topic Category: ").strip(): items
        for title, items in sections.items()
        if title.startswith("Topic Category: ")
    }
    type_sections = {
        title: items
        for title, items in sections.items()
        if title not in GENERIC_SUMMARY_SECTIONS and not title.startswith("Topic Category: ")
    }

    return SummaryDocument(
        title=str(metadata.get("title", "Untitled Summary")),
        date=str(metadata.get("date", "1970-01-01")),
        project=str(metadata.get("project", "instant")),
        source_note=str(metadata.get("source_note", "")),
        meeting_type=str(metadata.get("meeting_type", "other")),
        deck_mode=str(metadata.get("deck_mode", "client-followup")),
        participants=list(metadata.get("participants_list", [])),
        language=normalize_language(
            str(metadata.get("language", detect_language_from_parts(str(metadata.get("title", "")), body)))
        ),
        presentation_goal=str(metadata.get("presentation_goal", "recap")),
        audience=str(metadata.get("audience", "mixed stakeholders")),
        tone=str(metadata.get("tone", "clear")),
        context_notes=list(metadata.get("context_notes_list", [])),
        context_signals=sections.get("Context Signals", []),
        goals=sections.get("Goals", []),
        themes=sections.get("Key Themes", []),
        pain_points=sections.get("Pain Points", []),
        objections=sections.get("Objections", []),
        decisions=sections.get("Decisions", []),
        action_items=sections.get("Action Items", []),
        quotes=sections.get("Notable Quotes", []),
        narrative=sections.get("Deck Narrative", []),
        topic_summaries=sections.get("Topic Summaries", []),
        topic_categories=topic_categories,
        type_sections=type_sections,
        evidence_trails=sections.get("Evidence Trails", []),
    )


def parse_brief_note(note_text: str) -> DeckBriefDocument:
    """Parse a generated brief markdown note back into a structured object."""
    frontmatter, body = split_frontmatter(note_text)
    metadata = parse_frontmatter(frontmatter)
    sections = parse_sections(body)
    section_inputs = {
        title.removeprefix("Section Input: ").strip(): items
        for title, items in sections.items()
        if title.startswith("Section Input: ")
    }

    return DeckBriefDocument(
        title=str(metadata.get("title", "Untitled Brief")),
        date=str(metadata.get("date", "1970-01-01")),
        project=str(metadata.get("project", "instant")),
        source_summary=str(metadata.get("source_summary", "")),
        deck_style=str(metadata.get("deck_style", "editorial")),
        slide_count=int(metadata.get("slide_count", 0) or 0),
        deck_mode=str(metadata.get("deck_mode", "client-followup")),
        meeting_type=str(metadata.get("meeting_type", "other")),
        audience=str(metadata.get("audience", "mixed stakeholders")),
        language=normalize_language(
            str(metadata.get("language", detect_language_from_parts(str(metadata.get("title", "")), body)))
        ),
        presentation_goal=str(metadata.get("presentation_goal", "recap")),
        tone=str(metadata.get("tone", "clear")),
        slide_titles=list(metadata.get("slide_titles_list", [])),
        slide_goals=list(metadata.get("slide_goals_list", [])),
        topic_summaries=sections.get("Topic Summaries", []),
        section_inputs=section_inputs,
        context_items=sections.get("Context Items", []),
        pains=sections.get("Pain Inputs", []),
        decisions=sections.get("Decision Inputs", []),
        objections=sections.get("Objection Inputs", []),
        quotes=sections.get("Quote Inputs", []),
        evidence=sections.get("Evidence Inputs", []),
        next_steps=sections.get("Next Step Inputs", []),
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
    """Parse the small subset of YAML emitted by the summary generator."""
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


def parse_sections(body: str) -> dict[str, list[str]]:
    """Parse markdown bullet sections from the generated summary body."""
    sections: dict[str, list[str]] = {}
    current_section: str | None = None

    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            current_section = line[3:].strip()
            sections[current_section] = []
            continue
        if current_section and line.startswith("- "):
            sections[current_section].append(line[2:].strip())

    return sections


def render_html_deck(brief: DeckBriefDocument, style: str) -> str:
    """Render a deck brief into a single-file HTML deck."""
    language = normalize_language(brief.language)
    context_items = build_context_items(brief)
    evidence_items = choose_items(brief.evidence, brief.context_items)
    action_items = choose_items(brief.next_steps, brief.decisions[:3], brief.context_items[:3])
    support_items = build_support_items(brief)
    if brief.meeting_type == "research":
        overview_metrics = build_overview_metrics(brief, language)
        slides = [
            render_title_slide(brief),
            render_dashboard_slide(
                title_for(brief, 0, default_title("snapshot", language)),
                overview_metrics,
                context_items,
                evidence_items,
                goal_for(brief, 0, default_goal("snapshot", language)),
                language=language,
            ),
            render_research_bar_slide(
                title_for(brief, 1, "Repeated Pain Points"),
                primary_items=brief.pains,
                secondary_items=brief.quotes,
                primary_label=local_label(language, "pain_chart"),
                secondary_label=local_label(language, "tool_chart"),
                lead=goal_for(brief, 1, default_goal("signals", language)),
                language=language,
            ),
            render_research_distribution_slide(
                title_for(brief, 3, "Direction Patterns"),
                primary_items=brief.decisions,
                secondary_items=brief.objections,
                primary_label=local_label(language, "direction_chart"),
                secondary_label=local_label(language, "mix_chart"),
                lead=goal_for(brief, 3, default_goal("direction", language)),
                language=language,
            ),
            render_evidence_highlights_slide(
                title_for(brief, 4, "Evidence Highlights"),
                evidence_items,
                lead=goal_for(brief, 4, default_goal("quotes", language)),
                language=language,
            ),
            render_action_plan_slide(
                title_for(brief, 5, "Next Slice"),
                action_items,
                evidence_items,
                goal_for(brief, 5, default_goal("actions", language)),
                language=language,
            ),
        ]
    elif brief.meeting_type == "lecture":
        slides = render_lecture_slides(brief, language, support_items)
    else:
        slides = [render_title_slide(brief)]
        for index, title in enumerate(brief.slide_titles):
            items = section_items_for(brief, index)
            lead = goal_for(brief, index, default_goal("snapshot", language))
            if index == 0:
                slides.append(
                    render_contextual_overview_slide(
                        title=title,
                        items=items,
                        topic_summaries=support_items,
                        lead=lead,
                        language=language,
                    )
                )
                continue
            if is_memory_slide(title):
                slides.append(
                    render_contextual_summary_slide(
                        title=title,
                        items=items,
                        supporting_items=support_items,
                        lead=lead,
                        language=language,
                    )
                )
                continue
            if is_action_slide(title, brief.meeting_type):
                slides.append(
                    render_contextual_action_slide(
                        title=title,
                        items=items,
                        supporting_items=support_items,
                        lead=lead,
                        language=language,
                    )
                )
                continue
            slides.append(
                render_contextual_focus_slide(
                    title=title,
                    items=items,
                    supporting_items=support_items,
                    lead=lead,
                    language=language,
                )
            )
    theme = build_theme(style)

    return f"""<!DOCTYPE html>
<html lang="{escape(language)}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(brief.title)} — INSTANT PRESENTATION</title>
  <style>
    {theme}
  </style>
</head>
<body data-style="{escape(style)}" data-language="{escape(language)}">
  <div class="progress"><div class="progress-bar"></div></div>
  <div class="counter"></div>
  <main id="deck">
    {''.join(slides)}
  </main>
  <script>
    const slides = Array.from(document.querySelectorAll('.slide'));
    const counter = document.querySelector('.counter');
    const progressBar = document.querySelector('.progress-bar');
    let index = 0;

    function fitSlide(slide) {{
      slide.classList.remove('fit-compact', 'fit-tight');
      const inner = slide.querySelector('.slide-inner');
      if (!inner) return;
      const overflow = () => inner.scrollHeight - inner.clientHeight > 2;
      if (!overflow()) return;
      slide.classList.add('fit-compact');
      if (!overflow()) return;
      slide.classList.remove('fit-compact');
      slide.classList.add('fit-tight');
    }}

    function fitSlides() {{
      slides.forEach(fitSlide);
    }}

    function render() {{
      slides.forEach((slide, i) => slide.classList.toggle('active', i === index));
      counter.textContent = `${{index + 1}} / ${{slides.length}}`;
      progressBar.style.width = `${{((index + 1) / slides.length) * 100}}%`;
    }}

    function go(nextIndex) {{
      index = Math.max(0, Math.min(nextIndex, slides.length - 1));
      render();
    }}

    document.addEventListener('keydown', (event) => {{
      if (['ArrowRight', 'Enter', ' '].includes(event.key)) go(index + 1);
      if (['ArrowLeft', 'Backspace'].includes(event.key)) go(index - 1);
      if (event.key === 'Home') go(0);
      if (event.key === 'End') go(slides.length - 1);
    }});

    let touchStartX = 0;
    document.addEventListener('touchstart', (event) => {{
      touchStartX = event.changedTouches[0].clientX;
    }}, {{ passive: true }});
    document.addEventListener('touchend', (event) => {{
      const diff = event.changedTouches[0].clientX - touchStartX;
      if (Math.abs(diff) < 40) return;
      go(diff < 0 ? index + 1 : index - 1);
    }}, {{ passive: true }});

    window.addEventListener('resize', fitSlides);
    fitSlides();
    render();
  </script>
</body>
</html>
"""


def render_lecture_slides(
    brief: DeckBriefDocument,
    language: str,
    support_items: list[str],
) -> list[str]:
    """Render lecture decks with a dedicated academic visual grammar."""
    slides = [render_title_slide(brief)]
    lecture_items = [section_items_for(brief, index) for index in range(len(brief.slide_titles))]
    slides.append(
        render_lecture_thesis_slide(
            title=title_for(brief, 0, "Main Thesis"),
            items=lecture_items[0],
            lead=goal_for(brief, 0, default_goal("snapshot", language)),
            support_items=support_items,
            language=language,
        )
    )
    if len(lecture_items) > 1:
        slides.append(
            render_lecture_framework_slide(
                title=title_for(brief, 1, "Analytical Frame"),
                items=lecture_items[1],
                lead=goal_for(brief, 1, default_goal("signals", language)),
                language=language,
            )
        )
    if len(lecture_items) > 2:
        slides.append(
            render_lecture_objects_slide(
                title=title_for(brief, 2, "Key Objects"),
                items=lecture_items[2],
                lead=goal_for(brief, 2, default_goal("signals", language)),
                language=language,
            )
        )
    if len(lecture_items) > 3:
        slides.append(
            render_lecture_context_slide(
                title=title_for(brief, 3, "Historical Forces"),
                items=lecture_items[3],
                lead=goal_for(brief, 3, default_goal("direction", language)),
                language=language,
            )
        )
    if len(lecture_items) > 4:
        slides.append(
            render_lecture_memory_slide(
                title=title_for(brief, 4, "What to Remember"),
                items=lecture_items[4],
                supporting_items=support_items,
                lead=goal_for(brief, 4, default_goal("actions", language)),
                language=language,
            )
        )
    return slides


def render_title_slide(brief: DeckBriefDocument) -> str:
    """Render the opening slide."""
    language = normalize_language(brief.language)
    copy = deck_copy(language)
    subtitle = f"{localize_meeting_type(brief.meeting_type, language)} • {brief.date}"
    support_items = build_support_items(brief)
    framing = choose_items(section_items_for(brief, 0), support_items, brief.context_items, brief.decisions)[:1]
    framing_text = framing[0] if framing else deck_copy(language)["none_identified"]
    framing_text = condense_card_text(framing_text, max_chars=196)
    agenda_html = "".join(
        render_agenda_card(brief, index - 1, title, language)
        for index, title in enumerate(brief.slide_titles[:5], start=1)
    )
    meta_html = "".join(f'<li class="meta-pill">{escape(item)}</li>' for item in build_title_meta_items(brief, language, support_items))
    return f"""
    <section class="slide active title-slide">
      <div class="slide-inner deck-shell hero">
        <p class="eyebrow">{escape(copy["brand"])}</p>
        <div class="hero-layout">
          <div class="hero-copy">
            <h1>{escape(brief.title)}</h1>
            <p class="subtitle">{escape(subtitle)}</p>
            <section class="hero-framing">
              <p class="panel-title">{escape(local_title_label(language, 'summary_focus'))}</p>
              <p class="hero-framing-text">{escape(framing_text)}</p>
            </section>
            <ul class="meta-strip">{meta_html}</ul>
          </div>
          <section class="panel hero-agenda">
            <p class="panel-title">{escape(local_title_label(language, 'agenda'))}</p>
            <div class="agenda-grid">{agenda_html}</div>
          </section>
        </div>
      </div>
    </section>
    """


def render_agenda_card(brief: DeckBriefDocument, index: int, title: str, language: str) -> str:
    """Render an agenda step with purpose and concrete anchors."""
    goal_text = condense_card_text(goal_for(brief, index, ""), max_chars=108)
    anchors = [
        compact_support_label(item)
        for item in section_items_for(brief, index)[:2]
        if compact_support_label(item) and compact_support_label(item) != title
    ]
    anchor_html = "".join(f'<li class="agenda-anchor">{escape(item)}</li>' for item in anchors[:2])
    goal_html = f'<p class="agenda-purpose">{escape(goal_text)}</p>' if goal_text else ""
    anchors_block = f'<ul class="agenda-anchors">{anchor_html}</ul>' if anchor_html else ""
    return f"""
    <article class="agenda-card">
      <div class="agenda-card-head">
        <span class="step-number">{index + 1:02d}</span>
        <span class="step-kind">{escape(agenda_kind_for(brief, index, language))}</span>
      </div>
      <h3>{escape(title)}</h3>
      {goal_html}
      {anchors_block}
    </article>
    """


def build_title_meta_items(brief: DeckBriefDocument, language: str, support_items: list[str]) -> list[str]:
    """Build title-slide pills that stay close to the actual deck context."""
    copy = deck_copy(language)
    date_item = f"{copy['date']}: {brief.date}"
    if brief.meeting_type == "lecture":
        lecture_items = [date_item]
        lecture_items.extend(item for item in support_items[:2] if item)
        if len(lecture_items) < 3:
            lecture_items.append(localize_meeting_type(brief.meeting_type, language))
        return lecture_items[:3]

    items = [date_item, localize_meeting_type(brief.meeting_type, language)]
    if brief.audience and brief.audience.strip():
        items.append(brief.audience)
    return items[:3]


def render_lecture_thesis_slide(
    title: str,
    items: list[str],
    lead: str,
    support_items: list[str],
    language: str,
) -> str:
    """Render a lecture opening slide as an assertion plus compact evidence."""
    fallback = deck_copy(language)["none_identified"]
    primary = items[:1]
    secondary = items[1:3]
    primary_item = primary[0] if primary else fallback
    headline = capitalize_card_detail(lecture_assertion_text(primary_item))
    _, detail_text, bullets, _ = decompose_card_content(primary_item)
    summary_text = detail_text if should_render_assertion_summary(detail_text, headline) else ""
    evidence_items = secondary if secondary else [primary_item]
    evidence_labels = {compact_support_label(item) for item in evidence_items if compact_support_label(item)}
    support_candidates = [
        item
        for item in support_items
        if item and item not in evidence_labels and item != compact_support_label(primary_item)
    ]
    evidence_html = "".join(
        render_lecture_compact_card(item, accent=accent, kind="")
        for item, accent in zip(evidence_items[:3], ("teal", "gold", "blue"))
    ) or render_lecture_compact_card(fallback, accent="teal", kind="")
    support_html = "".join(
        f'<li class="signal-chip accent-{escape(accent)}">{escape(item)}</li>'
        for item, accent in zip(support_candidates[:3], ("teal", "gold", "blue"))
    )
    support_block = (
        f"""
        <section class="lecture-chip-row">
          <ul class="signal-strip">{support_html}</ul>
        </section>
        """
        if support_html else ""
    )
    return f"""
    <section class="slide lecture-slide lecture-thesis-slide">
      <div class="slide-inner deck-shell">
        <span class="lecture-kicker">{escape(title)}</span>
        <div class="lecture-assertion-band">
          <section class="lecture-assertion-copy">
            <h2 class="lecture-headline">{escape(headline)}</h2>
            {f'<p class="lecture-assertion-summary">{escape(summary_text)}</p>' if summary_text else ""}
            {f'<ul class="mini-bullets">{"".join(f"<li>{escape(point)}</li>" for point in bullets[:2])}</ul>' if bullets else ""}
          </section>
          <section class="panel lecture-evidence-panel">
            <p class="panel-title">{escape(lecture_support_title(language))}</p>
            <div class="lecture-grid lecture-mini-grid">{evidence_html}</div>
          </section>
        </div>
        {support_block}
      </div>
    </section>
    """


def render_lecture_framework_slide(
    title: str,
    items: list[str],
    lead: str,
    language: str,
) -> str:
    """Render the conceptual frame as a reading matrix rather than four equal cards."""
    fallback = deck_copy(language)["none_identified"]
    matrix_html = render_lecture_matrix(items[:4], language)
    headline = lecture_framework_headline(items, language)
    return f"""
    <section class="slide lecture-slide lecture-framework-slide">
      <div class="slide-inner deck-shell">
        <span class="lecture-kicker">{escape(title)}</span>
        <h2 class="lecture-headline lecture-headline-compact">{escape(headline)}</h2>
        {matrix_html or render_lecture_compact_card(fallback, accent="teal", kind=local_title_label(language, "analysis"))}
      </div>
    </section>
    """


def render_lecture_objects_slide(
    title: str,
    items: list[str],
    lead: str,
    language: str,
) -> str:
    """Render named monuments/objects as a comparison slide with optional chronology."""
    fallback = deck_copy(language)["none_identified"]
    table_html = render_lecture_object_table(items[:4], language)
    timeline_html = render_lecture_timeline(items[:4], language)
    headline = lecture_objects_headline(items, language)
    return f"""
    <section class="slide lecture-slide lecture-objects-slide">
      <div class="slide-inner deck-shell">
        <span class="lecture-kicker">{escape(title)}</span>
        <h2 class="lecture-headline lecture-headline-compact">{escape(headline)}</h2>
        <div class="lecture-objects-layout">
          {table_html or render_lecture_compact_card(fallback, accent="teal", kind=local_title_label(language, "details"))}
          {timeline_html}
        </div>
      </div>
    </section>
    """


def render_lecture_context_slide(
    title: str,
    items: list[str],
    lead: str,
    language: str,
) -> str:
    """Render lecture context as historical drivers with implications."""
    fallback = deck_copy(language)["none_identified"]
    cards = "".join(
        render_lecture_compact_card(item, accent=accent, kind="")
        for item, accent in zip(items[:3], ("gold", "rose", "blue"))
    ) or render_lecture_compact_card(fallback, accent="gold", kind=local_title_label(language, "analysis"))
    takeaway_html = "".join(
        f"<li>{escape(decompose_card_content(item)[0])}</li>"
        for item in items[:3]
    ) or f"<li>{escape(fallback)}</li>"
    headline = lecture_context_headline(items, language)
    return f"""
    <section class="slide lecture-slide lecture-context-slide">
      <div class="slide-inner deck-shell">
        <span class="lecture-kicker">{escape(title)}</span>
        <h2 class="lecture-headline lecture-headline-compact">{escape(headline)}</h2>
        <div class="lecture-context-layout">
          <section class="lecture-grid lecture-grid-3 lecture-context-grid">{cards}</section>
          <section class="panel lecture-summary-panel">
            <p class="panel-title">{escape(local_title_label(language, 'what_to_hold'))}</p>
            <ul class="bullet-list compact">{takeaway_html}</ul>
          </section>
        </div>
      </div>
    </section>
    """


def render_lecture_memory_slide(
    title: str,
    items: list[str],
    supporting_items: list[str],
    lead: str,
    language: str,
) -> str:
    """Render closing lecture takeaways as dense numbered conclusions."""
    fallback = deck_copy(language)["none_identified"]
    cards = "".join(
        render_step_card(index, item, language, variant="lecture")
        for index, item in enumerate(items[:4], start=1)
    ) or render_step_card(1, fallback, language, variant="lecture")
    support_html = "".join(f'<li class="signal-chip accent-{escape(accent)}">{escape(item)}</li>' for item, accent in zip(supporting_items[:2], ("teal", "blue")))
    support_block = (
        f"""
        <section class="evidence-panel lecture-band">
          <p class="panel-title">{escape(local_title_label(language, 'keep_in_view'))}</p>
          <ul class="signal-strip">{support_html}</ul>
        </section>
        """
        if support_html else ""
    )
    return f"""
    <section class="slide lecture-slide lecture-memory-slide">
      <div class="slide-inner deck-shell">
        <span class="lecture-kicker">{escape(title)}</span>
        <h2 class="lecture-headline lecture-headline-compact">{escape(lecture_memory_headline(items, language))}</h2>
        <div class="step-grid">{cards}</div>
        {support_block}
      </div>
    </section>
    """


def render_lecture_timeline(items: list[str], language: str) -> str:
    """Render a compact timeline when lecture objects contain usable dates."""
    points = build_lecture_timeline_points(items)
    if len(points) < 2:
        return ""

    min_year = min(point["start"] for point in points)
    max_year = max(point["end"] for point in points)
    span = max(max_year - min_year, 1)
    rows = []
    for point in points:
        left = ((point["start"] - min_year) / span) * 100
        width = max(((point["end"] - point["start"]) / span) * 100, 7)
        rows.append(
            f"""
            <div class="timeline-row accent-{escape(point['accent'])}">
              <div class="timeline-meta">
                <span class="timeline-label">{escape(point['label'])}</span>
                <span class="timeline-year">{escape(point['year_label'])}</span>
              </div>
              <div class="timeline-track">
                <span class="timeline-span accent-{escape(point['accent'])}" style="left: {left:.2f}%; width: {width:.2f}%;"></span>
              </div>
            </div>
            """
        )

    return f"""
    <section class="panel timeline-panel">
      <p class="panel-title">{escape(local_title_label(language, 'timeline'))}</p>
      <div class="timeline-scale">
        <span>{min_year}</span>
        <span>{max_year}</span>
      </div>
      <div class="timeline-grid">{''.join(rows)}</div>
    </section>
    """


def render_lecture_matrix(items: list[str], language: str) -> str:
    """Render lecture ideas as a compact assertion-evidence matrix."""
    rows = []
    for item in items[:4]:
        title, detail, bullets, _ = decompose_card_content(item)
        claim_text = condense_card_text(detail, max_chars=116)
        implication = condense_card_text(lecture_implication_text(title, detail, bullets, language), max_chars=96)
        rows.append(
            f"""
            <div class="lecture-matrix-row">
              <div class="lecture-matrix-cell lecture-matrix-label">{escape(title)}</div>
              <div class="lecture-matrix-cell">{escape(claim_text)}</div>
              <div class="lecture-matrix-cell">{escape(implication)}</div>
            </div>
            """
        )
    if not rows:
        return ""
    return f"""
    <section class="panel lecture-matrix-panel">
      <div class="lecture-matrix-head">
        <span>{escape(local_title_label(language, 'lens'))}</span>
        <span>{escape(local_title_label(language, 'claim'))}</span>
        <span>{escape(local_title_label(language, 'why_it_matters'))}</span>
      </div>
      <div class="lecture-matrix-grid">{''.join(rows)}</div>
    </section>
    """


def render_lecture_object_table(items: list[str], language: str) -> str:
    """Render key lecture objects in a comparison table."""
    rows = []
    accents = ("teal", "gold", "blue", "rose")
    for index, item in enumerate(items[:4]):
        title, detail, bullets, _ = decompose_card_content(item)
        year = extract_year_badge(item) or "—"
        observation_text = condense_card_text(detail, max_chars=112)
        takeaway = condense_card_text(lecture_implication_text(title, detail, bullets, language), max_chars=92)
        rows.append(
            f"""
            <div class="lecture-table-row accent-{escape(accents[index % len(accents)])}">
              <div class="lecture-table-cell lecture-table-object">
                <strong>{escape(title)}</strong>
                <span class="figure-year">{escape(year)}</span>
              </div>
              <div class="lecture-table-cell">{escape(observation_text)}</div>
              <div class="lecture-table-cell">{escape(takeaway)}</div>
            </div>
            """
        )
    if not rows:
        return ""
    return f"""
    <section class="panel lecture-table-panel">
      <div class="lecture-table-head">
        <span>{escape(local_title_label(language, 'object'))}</span>
        <span>{escape(local_title_label(language, 'observation'))}</span>
        <span>{escape(local_title_label(language, 'why_it_matters'))}</span>
      </div>
      <div class="lecture-table-grid">{''.join(rows)}</div>
    </section>
    """


def render_contextual_overview_slide(
    title: str,
    items: list[str],
    topic_summaries: list[str],
    lead: str,
    language: str,
) -> str:
    """Render the first content slide with context and concise takeaways."""
    fallback = deck_copy(language)["none_identified"]
    focus_items = choose_items(topic_summaries, items)[:4]
    focus_html = "".join(render_compact_note_card(item) for item in focus_items) or render_compact_note_card(fallback)
    detail_html = "".join(f"<li>{escape(condense_card_text(item, max_chars=132))}</li>" for item in items[:5]) or f"<li>{escape(fallback)}</li>"
    return f"""
    <section class="slide">
      <div class="slide-inner deck-shell">
        <p class="eyebrow">{escape(lead)}</p>
        <h2>{escape(title)}</h2>
        <div class="context-layout">
          <section class="panel">
            <p class="panel-title">{escape(local_title_label(language, 'main_takeaways'))}</p>
            <div class="compact-note-grid">{focus_html}</div>
          </section>
          <section class="panel">
            <p class="panel-title">{escape(local_title_label(language, 'conversation_frame'))}</p>
            <ul class="bullet-list compact">{detail_html}</ul>
          </section>
        </div>
      </div>
    </section>
    """


def render_contextual_focus_slide(
    title: str,
    items: list[str],
    supporting_items: list[str],
    lead: str,
    language: str,
) -> str:
    """Render a contextual analysis slide without synthetic metrics."""
    fallback = deck_copy(language)["none_identified"]
    primary = items[:2]
    secondary = items[2:6]
    primary_html = "".join(render_analysis_card(item) for item in primary) or render_analysis_card(fallback)
    secondary_html = "".join(f"<li>{escape(condense_card_text(item, max_chars=126))}</li>" for item in secondary) or f"<li>{escape(fallback)}</li>"
    support_html = "".join(f'<li class="signal-chip">{escape(condense_card_text(item, max_chars=44))}</li>' for item in supporting_items[:3])
    support_block = (
        f"""
        <section class="evidence-panel">
          <p class="panel-title">{escape(local_title_label(language, 'important_moments'))}</p>
          <ul class="signal-strip">{support_html}</ul>
        </section>
        """
        if support_html else ""
    )
    return f"""
    <section class="slide">
      <div class="slide-inner deck-shell">
        <p class="eyebrow">{escape(lead)}</p>
        <h2>{escape(title)}</h2>
        <div class="context-layout">
          <section class="panel">
            <p class="panel-title">{escape(local_title_label(language, 'analysis'))}</p>
            <div class="analysis-grid">{primary_html}</div>
          </section>
          <section class="panel">
            <p class="panel-title">{escape(local_title_label(language, 'details'))}</p>
            <ul class="bullet-list compact">{secondary_html}</ul>
          </section>
        </div>
        {support_block}
      </div>
    </section>
    """


def render_contextual_action_slide(
    title: str,
    items: list[str],
    supporting_items: list[str],
    lead: str,
    language: str,
) -> str:
    """Render action/follow-up/further-study slides with concise numbered cards."""
    fallback = deck_copy(language)["none_identified"]
    cards = "".join(
        render_step_card(index, item, language, variant="action")
        for index, item in enumerate(items[:6], start=1)
    ) or render_step_card(1, fallback, language, variant="action")
    support_html = "".join(f'<li class="signal-chip">{escape(condense_card_text(item, max_chars=44))}</li>' for item in supporting_items[:3])
    support_block = (
        f"""
        <section class="evidence-panel">
          <p class="panel-title">{escape(local_title_label(language, 'keep_in_view'))}</p>
          <ul class="signal-strip">{support_html}</ul>
        </section>
        """
        if support_html else ""
    )
    return f"""
    <section class="slide">
      <div class="slide-inner deck-shell">
        <p class="eyebrow">{escape(lead)}</p>
        <h2>{escape(title)}</h2>
        <div class="action-grid">{cards}</div>
        {support_block}
      </div>
    </section>
    """


def render_dashboard_slide(
    title: str,
    metrics: list[dict[str, str]],
    context_items: list[str],
    evidence_items: list[str],
    lead: str,
    language: str = "en",
) -> str:
    """Render an infographic-style overview slide."""
    fallback = deck_copy(language)["none_identified"]
    metric_html = "".join(
        f"""
        <article class="metric-card accent-{escape(metric['tone'])}">
          <span class="metric-kicker">{escape(metric['kicker'])}</span>
          <strong class="metric-value">{escape(metric['value'])}</strong>
          <span class="metric-label">{escape(metric['label'])}</span>
          <div class="metric-meter"><span style="width: {metric['width']}%"></span></div>
          <p class="metric-detail">{escape(metric['detail'])}</p>
        </article>
        """
        for metric in metrics
    )
    context_html = "".join(f'<li class="signal-chip">{escape(item)}</li>' for item in context_items[:6]) or f'<li class="signal-chip">{escape(fallback)}</li>'
    return f"""
    <section class="slide">
      <div class="slide-inner deck-shell">
        <p class="eyebrow">{escape(lead)}</p>
        <h2>{escape(title)}</h2>
        <div class="metric-grid">{metric_html}</div>
        <section class="evidence-panel">
          <p class="panel-title">{escape(local_label(language, 'context_items'))}</p>
          <ul class="signal-strip">{context_html}</ul>
        </section>
        {render_evidence_rail(evidence_items, language)}
      </div>
    </section>
    """


def render_signal_slide(
    title: str,
    clusters: list[dict[str, object]],
    evidence_items: list[str],
    lead: str,
    language: str = "en",
) -> str:
    """Render semantic signal clusters as infographic cards."""
    fallback = deck_copy(language)["none_identified"]
    cards = []
    for cluster in clusters:
        items = cluster.get("items", [])
        item_html = "".join(f"<li>{escape(item)}</li>" for item in items[:3]) or f"<li>{escape(fallback)}</li>"
        cards.append(
            f"""
            <article class="insight-card accent-{escape(str(cluster['tone']))}">
              <div class="insight-head">
                <span class="panel-title">{escape(str(cluster['label']))}</span>
                <span class="insight-count">{len(items):02d}</span>
              </div>
              <div class="cluster-meter"><span style="width: {cluster['width']}%"></span></div>
              <p class="insight-summary">{escape(str(cluster['summary']))}</p>
              <ul class="bullet-list compact">{item_html}</ul>
            </article>
            """
        )
    return f"""
    <section class="slide">
      <div class="slide-inner deck-shell">
        <p class="eyebrow">{escape(lead)}</p>
        <h2>{escape(title)}</h2>
        <div class="insight-grid">{''.join(cards)}</div>
        {render_evidence_rail(evidence_items, language, limit=3)}
      </div>
    </section>
    """


def render_direction_slide(
    title: str,
    direction_items: list[str],
    risk_items: list[str],
    evidence_items: list[str],
    lead: str,
    language: str = "en",
) -> str:
    """Render a direction vs watchouts slide."""
    fallback = deck_copy(language)["none_identified"]
    direction_html = "".join(
        render_step_card(index, item, language) for index, item in enumerate(direction_items[:4], start=1)
    ) or render_step_card(1, fallback, language)
    risk_html = "".join(f'<li class="watch-item">{escape(item)}</li>' for item in risk_items[:5]) or f'<li class="watch-item">{escape(fallback)}</li>'
    return f"""
    <section class="slide">
      <div class="slide-inner deck-shell">
        <p class="eyebrow">{escape(lead)}</p>
        <h2>{escape(title)}</h2>
        <div class="direction-layout">
          <section class="panel">
            <p class="panel-title">{escape(local_label(language, 'direction'))}</p>
            <div class="step-grid">{direction_html}</div>
          </section>
          <section class="panel">
            <p class="panel-title">{escape(local_label(language, 'watchouts'))}</p>
            <ul class="bullet-list compact">{risk_html}</ul>
          </section>
        </div>
        {render_evidence_rail(evidence_items, language, limit=4)}
      </div>
    </section>
    """


def render_quote_slide(
    quotes: list[str],
    evidence_items: list[str],
    title: str = "Signal Quotes",
    lead: str = "Use direct language from the call to keep the deck credible.",
    language: str = "en",
) -> str:
    """Render a quote-focused slide."""
    fallback = deck_copy(language)["quote_fallback"]
    blocks = "".join(
        f"""
        <blockquote class="quote-card">
          <span class="quote-mark">“</span>
          <p>{escape(quote)}</p>
        </blockquote>
        """
        for quote in quotes[:4]
    ) or f'<blockquote class="quote-card"><p>{escape(fallback)}</p></blockquote>'
    return f"""
    <section class="slide">
      <div class="slide-inner deck-shell">
        <p class="eyebrow">{escape(lead)}</p>
        <h2>{escape(title)}</h2>
        <div class="quote-stack">{blocks}</div>
        {render_evidence_rail(evidence_items, language, limit=2)}
      </div>
    </section>
    """


def render_action_plan_slide(title: str, items: list[str], evidence_items: list[str], lead: str, language: str = "en") -> str:
    """Render a sendable next-step slide."""
    fallback = deck_copy(language)["none_identified"]
    cards = "".join(
        render_step_card(index, item, language, variant="action")
        for index, item in enumerate(items[:6], start=1)
    ) or render_step_card(1, fallback, language, variant="action")
    return f"""
    <section class="slide">
      <div class="slide-inner deck-shell">
        <p class="eyebrow">{escape(lead)}</p>
        <h2>{escape(title)}</h2>
        <div class="action-grid">{cards}</div>
        {render_evidence_rail(evidence_items, language, limit=3)}
      </div>
    </section>
    """


def render_research_bar_slide(
    title: str,
    primary_items: list[str],
    secondary_items: list[str],
    primary_label: str,
    secondary_label: str,
    lead: str,
    language: str = "en",
) -> str:
    """Render two aggregate bar lists for research mode."""
    left = render_bar_panel(primary_label, primary_items, language)
    right = render_bar_panel(secondary_label, secondary_items, language)
    return f"""
    <section class="slide">
      <div class="slide-inner deck-shell">
        <p class="eyebrow">{escape(lead)}</p>
        <h2>{escape(title)}</h2>
        <div class="direction-layout">
          {left}
          {right}
        </div>
      </div>
    </section>
    """


def render_research_distribution_slide(
    title: str,
    primary_items: list[str],
    secondary_items: list[str],
    primary_label: str,
    secondary_label: str,
    lead: str,
    language: str = "en",
) -> str:
    """Render aggregate distribution panels."""
    left = render_bar_panel(primary_label, primary_items, language)
    right = render_bar_panel(secondary_label, secondary_items, language)
    return f"""
    <section class="slide">
      <div class="slide-inner deck-shell">
        <p class="eyebrow">{escape(lead)}</p>
        <h2>{escape(title)}</h2>
        <div class="direction-layout">
          {left}
          {right}
        </div>
      </div>
    </section>
    """


def render_bar_panel(label: str, items: list[str], language: str) -> str:
    """Render a simple research bar chart panel."""
    rows = "".join(
        f"""
        <div class="bar-row">
          <div class="bar-meta">
            <span>{escape(item['label'])}</span>
            <span>{escape(item['value_label'])}</span>
          </div>
          <div class="bar-track"><span style="width: {item['width']}%"></span></div>
        </div>
        """
        for item in parse_chart_items(items)
    ) or f'<p class="metric-detail">{escape(deck_copy(language)["none_identified"])}</p>'
    return f"""
    <section class="panel">
      <p class="panel-title">{escape(label)}</p>
      <div class="bar-panel">{rows}</div>
    </section>
    """


def render_evidence_highlights_slide(title: str, evidence_items: list[str], lead: str, language: str = "en") -> str:
    """Render aggregate evidence highlights as compact cards."""
    fallback = deck_copy(language)["none_identified"]
    cards = "".join(
        f"""
        <article class="quote-card evidence-card">
          <p>{escape(item)}</p>
        </article>
        """
        for item in evidence_items[:4]
    ) or f'<article class="quote-card evidence-card"><p>{escape(fallback)}</p></article>'
    return f"""
    <section class="slide">
      <div class="slide-inner deck-shell">
        <p class="eyebrow">{escape(lead)}</p>
        <h2>{escape(title)}</h2>
        <div class="quote-stack">{cards}</div>
      </div>
    </section>
    """


def render_contextual_summary_slide(
    title: str,
    items: list[str],
    supporting_items: list[str],
    lead: str,
    language: str,
) -> str:
    """Render a closing slide with compact final takeaways."""
    fallback = deck_copy(language)["none_identified"]
    cards = "".join(render_compact_note_card(item, language=language) for item in items[:4]) or render_compact_note_card(fallback, language=language)
    support_html = "".join(f'<li class="signal-chip">{escape(condense_card_text(item, max_chars=48))}</li>' for item in supporting_items[:2])
    support_block = (
        f"""
        <section class="evidence-panel">
          <p class="panel-title">{escape(local_title_label(language, 'closing_note'))}</p>
          <ul class="signal-strip">{support_html}</ul>
        </section>
        """
        if support_html else ""
    )
    return f"""
    <section class="slide">
      <div class="slide-inner deck-shell">
        <p class="eyebrow">{escape(lead)}</p>
        <h2>{escape(title)}</h2>
        <div class="compact-note-grid">{cards}</div>
        {support_block}
      </div>
    </section>
    """


def build_context_items(brief: DeckBriefDocument) -> list[str]:
    """Build the meeting context slide content."""
    language = normalize_language(brief.language)
    copy = deck_copy(language)
    items = [
        f"{copy['date']}: {brief.date}",
        f"{copy['audience'].capitalize()}: {brief.audience}",
        f"Goal: {brief.presentation_goal}",
        f"Tone: {brief.tone}",
    ]
    items.extend(brief.context_items[:4])
    return items


def render_lecture_semantic_card(
    item: str,
    accent: str,
    kind: str,
    emphasis: bool = False,
) -> str:
    """Render an academic-style lecture card with stronger labeling."""
    title, detail, bullets, eyebrow = decompose_card_content(item)
    detail = capitalize_card_detail(detail)
    bullet_html = "".join(f"<li>{escape(point)}</li>" for point in bullets[:2])
    eyebrow_text = eyebrow or kind
    emphasis_class = " emphasis" if emphasis else ""
    return f"""
    <article class="lecture-card accent-{escape(accent)}{emphasis_class}">
      <div class="lecture-card-head">
        <span class="panel-title">{escape(eyebrow_text)}</span>
      </div>
      <h3>{escape(title)}</h3>
      <p>{escape(detail)}</p>
      {f'<ul class="mini-bullets">{bullet_html}</ul>' if bullet_html else ''}
    </article>
    """


def render_lecture_compact_card(item: str, accent: str, kind: str) -> str:
    """Render a smaller lecture card for evidence, support, and drivers."""
    title, detail, bullets, eyebrow = decompose_card_content(item)
    eyebrow_text = eyebrow or kind
    detail = capitalize_card_detail(detail)
    bullet_html = "".join(f"<li>{escape(point)}</li>" for point in bullets[:1])
    return f"""
    <article class="lecture-card lecture-compact-card accent-{escape(accent)}">
      {f'<div class="lecture-card-head"><span class="panel-title">{escape(eyebrow_text)}</span></div>' if eyebrow_text else ''}
      <h3>{escape(title)}</h3>
      <p>{escape(detail)}</p>
      {f'<ul class="mini-bullets">{bullet_html}</ul>' if bullet_html else ''}
    </article>
    """


def render_lecture_object_card(item: str, accent: str, language: str) -> str:
    """Render a lecture object/monument card with a simple figure poster."""
    title, detail, bullets, eyebrow = decompose_card_content(item)
    detail = capitalize_card_detail(detail)
    bullet_html = "".join(f"<li>{escape(point)}</li>" for point in bullets[:2])
    year_badge = extract_year_badge(item)
    year_html = f'<span class="figure-year">{escape(year_badge)}</span>' if year_badge else ""
    kicker = eyebrow or local_title_label(language, "details")
    return f"""
    <article class="lecture-card lecture-object-card accent-{escape(accent)}">
      <div class="lecture-card-head">
        <span class="panel-title">{escape(kicker)}</span>
        {year_html}
      </div>
      <div class="figure-poster accent-{escape(accent)}">
        {render_lecture_illustration(title, accent)}
      </div>
      <h3>{escape(title)}</h3>
      <p>{escape(detail)}</p>
      {f'<ul class="mini-bullets">{bullet_html}</ul>' if bullet_html else ''}
    </article>
    """


def render_lecture_illustration(title: str, accent: str = "teal") -> str:
    """Render a lightweight contextual SVG illustration for lecture slides."""
    stroke, fill = accent_colors(accent)
    lowered = title.lower()
    if any(token in lowered for token in ("сент-шапель", "sainte", "saint")):
        return f"""
        <svg viewBox="0 0 320 180" class="lecture-svg" aria-hidden="true">
          <rect x="48" y="26" width="224" height="128" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="2"/>
          <circle cx="160" cy="70" r="24" fill="none" stroke="{stroke}" stroke-width="3"/>
          <path d="M160 46 V94 M136 70 H184 M145 55 L175 85 M175 55 L145 85" stroke="{stroke}" stroke-width="2.4" />
          <path d="M82 40 V142 M112 40 V142 M142 40 V142 M178 40 V142 M208 40 V142 M238 40 V142" stroke="{stroke}" stroke-width="1.5" opacity="0.75"/>
          <path d="M74 106 H246" stroke="{stroke}" stroke-width="2" opacity="0.8"/>
        </svg>
        """
    if any(token in lowered for token in ("нотр", "notre")):
        return f"""
        <svg viewBox="0 0 320 180" class="lecture-svg" aria-hidden="true">
          <path d="M62 146 H258" stroke="{stroke}" stroke-width="3"/>
          <rect x="84" y="44" width="42" height="102" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="2"/>
          <rect x="194" y="44" width="42" height="102" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="2"/>
          <path d="M126 146 L160 74 L194 146" fill="{fill}" stroke="{stroke}" stroke-width="2"/>
          <circle cx="160" cy="98" r="17" fill="none" stroke="{stroke}" stroke-width="2.5"/>
          <path d="M160 81 V115 M143 98 H177" stroke="{stroke}" stroke-width="2"/>
        </svg>
        """
    if any(token in lowered for token in ("шартр", "chartres")):
        return f"""
        <svg viewBox="0 0 320 180" class="lecture-svg" aria-hidden="true">
          <circle cx="160" cy="92" r="46" fill="none" stroke="{stroke}" stroke-width="2.4"/>
          <circle cx="160" cy="92" r="31" fill="none" stroke="{stroke}" stroke-width="2"/>
          <path d="M160 46 C132 46 114 62 114 92 C114 118 132 138 160 138 C188 138 206 118 206 92" fill="none" stroke="{stroke}" stroke-width="2"/>
          <path d="M160 60 C143 60 130 72 130 92 C130 110 143 124 160 124 C177 124 190 110 190 92" fill="none" stroke="{stroke}" stroke-width="2"/>
          <path d="M160 124 V144" stroke="{stroke}" stroke-width="2"/>
        </svg>
        """
    if any(token in lowered for token in ("рейм", "reims")):
        return f"""
        <svg viewBox="0 0 320 180" class="lecture-svg" aria-hidden="true">
          <path d="M92 138 H228" stroke="{stroke}" stroke-width="3"/>
          <path d="M120 138 V86 H200 V138" fill="{fill}" stroke="{stroke}" stroke-width="2"/>
          <path d="M132 86 L160 52 L188 86" fill="{fill}" stroke="{stroke}" stroke-width="2"/>
          <path d="M132 44 L144 58 L160 36 L176 58 L188 44 L188 62 H132 Z" fill="none" stroke="{stroke}" stroke-width="2.4"/>
          <circle cx="160" cy="104" r="12" fill="none" stroke="{stroke}" stroke-width="2.2"/>
        </svg>
        """
    return f"""
    <svg viewBox="0 0 320 180" class="lecture-svg" aria-hidden="true">
      <path d="M84 146 H236" stroke="{stroke}" stroke-width="3"/>
      <path d="M106 146 V98 C106 74 126 54 160 40 C194 54 214 74 214 98 V146" fill="{fill}" stroke="{stroke}" stroke-width="2.2"/>
      <path d="M130 120 H190" stroke="{stroke}" stroke-width="2"/>
      <path d="M144 92 H176" stroke="{stroke}" stroke-width="2"/>
    </svg>
    """


def accent_colors(accent: str) -> tuple[str, str]:
    """Return stroke/fill colors for generated lecture illustrations."""
    palette = {
        "teal": ("rgba(106, 233, 193, 0.92)", "rgba(106, 233, 193, 0.14)"),
        "gold": ("rgba(255, 205, 97, 0.92)", "rgba(255, 205, 97, 0.14)"),
        "blue": ("rgba(96, 168, 255, 0.92)", "rgba(96, 168, 255, 0.14)"),
        "rose": ("rgba(255, 134, 171, 0.92)", "rgba(255, 134, 171, 0.14)"),
    }
    return palette.get(accent, palette["teal"])


def lecture_assertion_text(item: str) -> str:
    """Turn the first lecture item into a sentence-style headline."""
    title, detail, _, _ = decompose_card_content(item)
    if detail and detail != title:
        return condense_card_text(detail, max_chars=108)
    return condense_card_text(title, max_chars=96)


def lecture_framework_headline(items: list[str], language: str) -> str:
    """Return a lecture-framework headline aligned with assertion-evidence decks."""
    labels = {
        "en": "Read the lecture through a few recurring lenses, not as isolated monuments.",
        "ru": "Лекцию лучше читать через повторяющиеся линзы, а не как набор отдельных памятников.",
        "fr": "Il faut lire la conférence à travers quelques axes récurrents, pas comme une suite d'objets isolés.",
    }
    return labels[normalize_language(language)]


def lecture_objects_headline(items: list[str], language: str) -> str:
    """Return a headline for the compare slide."""
    labels = {
        "en": "The argument becomes clearer when the lecture is anchored in concrete buildings.",
        "ru": "Аргумент становится яснее, когда лекция опирается на конкретные здания и даты.",
        "fr": "L'argument devient plus net lorsqu'il s'appuie sur des bâtiments et des dates concrètes.",
    }
    return labels[normalize_language(language)]


def lecture_context_headline(items: list[str], language: str) -> str:
    """Return a headline for historical drivers."""
    labels = {
        "en": "Relics, power, and restoration explain why these cathedrals mattered beyond form alone.",
        "ru": "Реликвии, власть и реставрации объясняют, почему эти соборы значимы не только формой.",
        "fr": "Reliques, pouvoir et restaurations expliquent pourquoi ces cathédrales comptent au-delà de leur seule forme.",
    }
    return labels[normalize_language(language)]


def lecture_memory_headline(items: list[str], language: str) -> str:
    """Return a closing lecture headline."""
    labels = {
        "en": "A few anchors are enough to keep the lecture coherent after it ends.",
        "ru": "Достаточно нескольких опор, чтобы после лекции сохранилась цельная картина.",
        "fr": "Quelques repères suffisent pour garder une image cohérente après la conférence.",
    }
    return labels[normalize_language(language)]


def lecture_implication_text(title: str, detail: str, bullets: list[str], language: str) -> str:
    """Turn a lecture card into a short implication line instead of repeating its body."""
    lowered = f"{title} {detail}".lower()
    localized = {
        "en": {
            "light": "Read the interior as a system of light, not decoration.",
            "pilgrim": "The plan is organized around movement and ritual access.",
            "power": "Architecture doubles as a public technology of legitimacy.",
            "time": "Separate the medieval core from later restoration layers.",
            "style": "The comparison reveals stylistic transition, not static form.",
            "fallback": "Use this example as an interpretive key, not a standalone fact.",
        },
        "ru": {
            "light": "Интерьер читается как система света, а не как декор.",
            "pilgrim": "План собора подчинён маршруту и ритуалу, а не только симметрии.",
            "power": "Архитектура здесь работает и как публичная технология легитимности.",
            "time": "Средневековое ядро нужно отделять от поздних наслоений и реставраций.",
            "style": "Сравнение показывает переход стиля, а не набор разрозненных форм.",
            "fallback": "Этот пример нужен как ключ к чтению лекции, а не как отдельный факт.",
        },
        "fr": {
            "light": "L'intérieur se lit comme un système de lumière, pas comme un simple décor.",
            "pilgrim": "Le plan répond au parcours rituel et au mouvement des fidèles.",
            "power": "L'architecture agit aussi comme une technologie publique de légitimité.",
            "time": "Il faut distinguer le noyau médiéval des restaurations ultérieures.",
            "style": "La comparaison montre une transition stylistique, pas des formes isolées.",
            "fallback": "Cet exemple sert de clé de lecture, pas de fait isolé.",
        },
    }
    copy = localized[normalize_language(language)]
    if any(token in lowered for token in ("свет", "витраж", "light", "vitrail")):
        return copy["light"]
    if any(token in lowered for token in ("палом", "обход", "route", "pilgrim", "nef")):
        return copy["pilgrim"]
    if any(token in lowered for token in ("власть", "коронац", "power", "legitim", "roi")):
        return copy["power"]
    if any(token in lowered for token in ("реставрац", "разруш", "time", "layer", "xix", "xx")):
        return copy["time"]
    if any(token in lowered for token in ("стиль", "готик", "chartres", "reims", "notre-dame")):
        return copy["style"]
    if bullets:
        return bullets[0]
    return copy["fallback"]


def extract_year_badge(item: str) -> str:
    """Extract a compact year or range badge from an item when available."""
    match = re.search(r"\b(\d{4}(?:[–-]\d{4})?)\b", item)
    if match:
        return match.group(1).replace("-", "–")
    century_match = re.search(r"\b(X{0,3}(?:IX|IV|V?I{0,3})[-–]X{0,3}(?:IX|IV|V?I{0,3})|X{0,3}(?:IX|IV|V?I{0,3}))\s+век", item, flags=re.IGNORECASE)
    if century_match:
        return century_match.group(1).upper() + " век"
    return ""


def build_lecture_timeline_points(items: list[str]) -> list[dict[str, object]]:
    """Build chartable timeline points from lecture object cards."""
    accents = ("teal", "gold", "blue", "rose")
    points: list[dict[str, object]] = []
    for index, item in enumerate(items):
        title, _, _, _ = decompose_card_content(item)
        year_label = extract_year_badge(item)
        if not year_label:
            continue
        year_range = parse_year_range(year_label)
        if not year_range:
            continue
        start, end = year_range
        points.append(
            {
                "label": title,
                "year_label": year_label,
                "start": start,
                "end": end,
                "accent": accents[index % len(accents)],
            }
        )
    return points


def parse_year_range(label: str) -> tuple[int, int] | None:
    """Parse a compact year label into numeric start/end values."""
    normalized = label.replace("–", "-")
    match = re.search(r"(\d{4})(?:-(\d{4}))?", normalized)
    if match:
        start = int(match.group(1))
        end = int(match.group(2) or match.group(1))
        return start, max(start, end)
    roman_match = re.search(r"(X{0,3}(?:IX|IV|V?I{0,3}))(?:-(X{0,3}(?:IX|IV|V?I{0,3})))?\s+век", normalized, flags=re.IGNORECASE)
    if roman_match:
        start = roman_to_int(roman_match.group(1).upper())
        end = roman_to_int((roman_match.group(2) or roman_match.group(1)).upper())
        if start is None or end is None:
            return None
        return start * 100, max(start, end) * 100
    return None


def roman_to_int(value: str) -> int | None:
    """Convert a compact Roman numeral to an integer."""
    mapping = {"I": 1, "V": 5, "X": 10}
    total = 0
    previous = 0
    for char in reversed(value):
        current = mapping.get(char)
        if current is None:
            return None
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    return total


def capitalize_card_detail(text: str) -> str:
    """Uppercase the first letter of card detail copy for cleaner academic presentation."""
    if not text:
        return text
    for index, char in enumerate(text):
        if char.isalpha():
            return text[:index] + char.upper() + text[index + 1 :]
    return text


def build_support_items(brief: DeckBriefDocument) -> list[str]:
    """Build short support chips without leaking internal topic-summary formatting."""
    items: list[str] = []
    for title in brief.slide_titles[:4]:
        for candidate in brief.section_inputs.get(title, []):
            cleaned = compact_support_label(candidate)
            if cleaned and cleaned not in items:
                items.append(cleaned)
                break
    if items:
        return items[:4]
    return [compact_support_label(item) for item in brief.topic_summaries[:4]]


def compact_support_label(item: str) -> str:
    """Turn a long card payload into a short chip label."""
    cleaned = strip_topic_prefix(item)
    if ": " in cleaned:
        head, tail = cleaned.split(": ", 1)
        if len(head) <= 42:
            return head
        cleaned = tail
    if " — " in cleaned:
        head, _ = cleaned.split(" — ", 1)
        if len(head) <= 42:
            return head
    return condense_card_text(cleaned, max_chars=48)


def section_items_for(brief: DeckBriefDocument, index: int) -> list[str]:
    """Return contextual items for a slide, falling back to legacy brief inputs."""
    if index < len(brief.slide_titles):
        title = brief.slide_titles[index]
        if brief.section_inputs.get(title):
            return brief.section_inputs[title]

    fallbacks = [
        brief.context_items,
        brief.decisions,
        choose_items(brief.pains, brief.objections),
        brief.next_steps,
        choose_items(brief.objections, brief.evidence),
    ]
    return fallbacks[index] if index < len(fallbacks) else []


def is_action_slide(title: str, meeting_type: str) -> bool:
    """Return whether a slide should render as numbered actions/next steps."""
    lowered = title.lower()
    return any(
        token in lowered
        for token in ("action", "follow", "watchlist", "mvp", "study", "questions", "next", "суда", "шаг", "изуч")
    ) or (meeting_type == "social" and "agreement" in lowered)


def is_memory_slide(title: str) -> bool:
    """Return whether a slide should render as a final takeaway slide."""
    lowered = title.lower()
    return any(token in lowered for token in ("remember", "retenir", "запомнить"))


def render_compact_note_card(item: str, language: str | None = None) -> str:
    """Render a short contextual note card."""
    title, detail, bullets, eyebrow = decompose_card_content(item)
    bullet_html = "".join(f"<li>{escape(point)}</li>" for point in bullets[:2])
    eyebrow_html = f'<span class="panel-title">{escape(eyebrow)}</span>' if eyebrow else ""
    detail_html = (
        f"<p>{escape(detail)}</p>"
        if detail and not detail.startswith(title) and not title.startswith(detail)
        else ""
    )
    return f"""
    <article class="compact-note-card">
      {eyebrow_html}
      <h3>{escape(title)}</h3>
      {detail_html}
      {f'<ul class="mini-bullets">{bullet_html}</ul>' if bullet_html else ''}
    </article>
    """


def render_analysis_card(item: str) -> str:
    """Render an analysis card with short conclusion-style copy."""
    title, detail, bullets, eyebrow = decompose_card_content(item)
    title = condense_card_text(title, max_chars=66)
    detail = condense_card_text(detail, max_chars=118)
    bullet_html = "".join(f"<li>{escape(condense_card_text(point, max_chars=96))}</li>" for point in bullets[:2])
    eyebrow_html = f'<span class="panel-title">{escape(eyebrow)}</span>' if eyebrow else '<span class="panel-title">Focus</span>'
    return f"""
    <article class="insight-card">
      {eyebrow_html}
      <h3>{escape(title)}</h3>
      <p class="insight-summary">{escape(detail)}</p>
      {f'<ul class="mini-bullets">{bullet_html}</ul>' if bullet_html else ''}
    </article>
    """


def build_overview_metrics(brief: DeckBriefDocument, language: str) -> list[dict[str, str]]:
    """Build compact metrics for the opening dashboard slides."""
    total_signals = max(len(brief.context_items) + len(brief.pains) + len(brief.decisions), 1)
    raw_metrics = [
        {"kicker": local_label(language, "signal_count"), "value": total_signals, "label": local_label(language, "captured_signals"), "detail": local_detail(language, "captured_signals"), "tone": "teal"},
        {"kicker": local_label(language, "pain_count"), "value": len(brief.pains), "label": local_label(language, "frictions"), "detail": local_detail(language, "frictions"), "tone": "gold"},
        {"kicker": local_label(language, "decision_count"), "value": len(brief.decisions), "label": local_label(language, "direction_items"), "detail": local_detail(language, "direction_items"), "tone": "blue"},
        {"kicker": local_label(language, "action_count"), "value": len(brief.next_steps), "label": local_label(language, "next_steps"), "detail": local_detail(language, "next_steps"), "tone": "rose"},
    ]
    max_value = max(metric["value"] for metric in raw_metrics) or 1
    return [
        {
            "kicker": metric["kicker"],
            "value": f"{int(metric['value']):02d}",
            "label": metric["label"],
            "detail": metric["detail"],
            "tone": metric["tone"],
            "width": max(18, int((int(metric["value"]) / max_value) * 100)),
        }
        for metric in raw_metrics
    ]


def build_signal_clusters(brief: DeckBriefDocument, language: str) -> list[dict[str, object]]:
    """Map extracted items into semantic research-style buckets."""
    buckets = [
        {"label": local_label(language, "friction_cluster"), "tone": "gold", "items": [], "keywords": ("pain", "problem", "manual", "slow", "friction", "долг", "хаос", "нужно", "бол", "not scalable")},
        {"label": local_label(language, "workflow_cluster"), "tone": "teal", "items": [], "keywords": ("workflow", "process", "context", "system", "obsidian", "krisp", "pipeline", "контекст", "система", "процесс")},
        {"label": local_label(language, "opportunity_cluster"), "tone": "blue", "items": [], "keywords": ("opportunity", "build", "should", "priority", "project", "potential", "возмож", "проект", "приоритет", "будем")},
        {"label": local_label(language, "risk_cluster"), "tone": "rose", "items": [], "keywords": ("risk", "concern", "objection", "cannot", "worry", "style", "accuracy", "риск", "страх", "не могу")},
    ]
    source_items = [*brief.pains[:5], *brief.context_items[:5], *brief.decisions[:5], *brief.objections[:4]]
    leftovers: list[str] = []
    for item in source_items:
        lowered = item.lower()
        matched = False
        for bucket in buckets:
            if any(keyword in lowered for keyword in bucket["keywords"]):
                bucket["items"].append(item)
                matched = True
                break
        if not matched:
            leftovers.append(item)
    for index, item in enumerate(leftovers):
        buckets[index % len(buckets)]["items"].append(item)
    for bucket in buckets:
        bucket["items"] = dedupe_items(bucket["items"])[:3]
        bucket["summary"] = cluster_summary(str(bucket["label"]), bucket["items"], language)
        bucket["width"] = max(14, int((len(bucket["items"]) / 3) * 100)) if bucket["items"] else 14
    return buckets


def render_evidence_rail(evidence_items: list[str], language: str, limit: int = 4) -> str:
    """Render a compact audit rail with transcript-grounded references."""
    fallback = deck_copy(language)["none_identified"]
    items = evidence_items[:limit]
    item_html = "".join(f"<li>{escape(item)}</li>" for item in items) or f"<li>{escape(fallback)}</li>"
    return f"""
    <section class="evidence-rail">
      <p class="panel-title">{escape(local_label(language, 'evidence_signals'))}</p>
      <ul class="evidence-list">{item_html}</ul>
    </section>
    """


def cluster_summary(label: str, items: list[str], language: str) -> str:
    """Write a one-line summary for a cluster."""
    if not items:
        return deck_copy(language)["none_identified"]
    if language == "ru":
        return f"{label} собраны из самых повторяющихся сигналов разговора."
    if language == "fr":
        return f"{label} regroupe les signaux les plus saillants de l'échange."
    return f"{label} groups the strongest repeated signals from the conversation."


def parse_chart_items(items: list[str]) -> list[dict[str, object]]:
    """Parse aggregate strings into simple chart rows."""
    parsed: list[dict[str, object]] = []
    raw_rows: list[tuple[str, int, str]] = []
    for index, item in enumerate(items[:5]):
        match = re.match(r"^(?P<label>.+?)\s+[—-]\s+(?P<count>\d+)(?:\s+(?P<suffix>.+))?$", item)
        if match:
            label = match.group("label").strip()
            count = int(match.group("count"))
            suffix = f" {match.group('suffix').strip()}" if match.group("suffix") else ""
            raw_rows.append((label, count, f"{count}{suffix}"))
        else:
            fallback_value = max(len(items) - index, 1)
            raw_rows.append((item.strip(), fallback_value, item.strip()))
    max_value = max((count for _, count, _ in raw_rows), default=1)
    for label, count, value_label in raw_rows:
        parsed.append(
            {
                "label": label,
                "count": count,
                "value_label": value_label,
                "width": max(16, int((count / max_value) * 100)),
            }
        )
    return parsed


def render_step_card(index: int, item: str, language: str, variant: str = "direction") -> str:
    """Render a numbered step/action card."""
    title, detail = split_item_for_card(item)
    title = condense_card_text(title, max_chars=62)
    detail = condense_card_text(detail, max_chars=124)
    kind = local_label(language, "direction") if variant == "direction" else local_label(language, "sendable_action")
    return f"""
    <article class="step-card {escape(variant)}">
      <span class="step-number">{index:02d}</span>
      <span class="step-kind">{escape(kind)}</span>
      <h3>{escape(title)}</h3>
      <p>{escape(detail)}</p>
    </article>
    """


def local_title_label(language: str, key: str) -> str:
    """Return localized labels for contextual single-note slides."""
    labels = {
        "en": {
            "summary_focus": "What matters here",
            "main_takeaways": "Main takeaways",
            "conversation_frame": "Conversation frame",
            "agenda": "Structure",
            "analysis": "Analysis",
            "details": "Details",
            "evidence": "Evidence",
            "lens": "Lens",
            "claim": "What it shows",
            "why_it_matters": "Why it matters",
            "object": "Object",
            "observation": "What to notice",
            "driver": "Driver",
            "what_to_hold": "What this changes",
            "important_moments": "Important moments",
            "keep_in_view": "Keep in view",
            "closing_note": "Take away",
            "timeline": "Timeline",
            "visual_focus": "Visual focus",
        },
        "ru": {
            "summary_focus": "Что важно",
            "main_takeaways": "Главное",
            "conversation_frame": "Контекст",
            "agenda": "Структура",
            "analysis": "Выводы",
            "details": "Детали",
            "evidence": "Опоры",
            "lens": "Линза",
            "claim": "Что показывает",
            "why_it_matters": "Почему это важно",
            "object": "Объект",
            "observation": "Что видно",
            "driver": "Двигатель",
            "what_to_hold": "Что это меняет",
            "important_moments": "Важные моменты",
            "keep_in_view": "Держать в фокусе",
            "closing_note": "На выходе",
            "timeline": "Хронология",
            "visual_focus": "Визуальный фокус",
        },
        "fr": {
            "summary_focus": "À retenir",
            "main_takeaways": "Points clés",
            "conversation_frame": "Contexte",
            "agenda": "Structure",
            "analysis": "Analyse",
            "details": "Détails",
            "evidence": "Preuves",
            "lens": "Axe",
            "claim": "Ce que cela montre",
            "why_it_matters": "Pourquoi c'est important",
            "object": "Objet",
            "observation": "À observer",
            "driver": "Moteur",
            "what_to_hold": "Ce que cela change",
            "important_moments": "Moments importants",
            "keep_in_view": "À garder en vue",
            "closing_note": "À emporter",
            "timeline": "Chronologie",
            "visual_focus": "Focus visuel",
        },
    }
    return labels[normalize_language(language)][key]


def split_item_for_card(item: str) -> tuple[str, str]:
    """Split a raw extracted line into card title and supporting detail."""
    cleaned = " ".join(item.split())
    if ": " in cleaned:
        head, tail = cleaned.split(": ", 1)
        return head[:80], tail[:220]
    sentence_parts = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)
    if len(sentence_parts) == 2:
        return sentence_parts[0][:80], sentence_parts[1][:220]
    if len(cleaned) <= 90:
        return cleaned, cleaned
    return cleaned[:88].rstrip() + "…", cleaned


def decompose_card_content(item: str) -> tuple[str, str, list[str], str]:
    """Split a raw item into title, summary, optional bullets, and optional eyebrow."""
    cleaned = strip_topic_prefix(" ".join(item.split()))
    eyebrow = ""
    remainder = cleaned

    if " — " in cleaned:
        candidate, tail = cleaned.split(" — ", 1)
        if candidate in INTERNAL_TOPIC_LABELS:
            eyebrow = candidate
            remainder = tail.strip()
        elif len(candidate) <= 36 and candidate.count(" ") <= 5:
            return candidate.strip(), condense_card_text(tail.strip()), [], ""

    chunks = [chunk.strip(" .") for chunk in re.split(r";\s+|•\s+|\.\s+", remainder) if chunk.strip(" .")]
    if not chunks:
        title, detail = split_item_for_card(cleaned)
        return title, detail, [], eyebrow

    title_source = chunks[0]
    title, detail = split_item_for_card(title_source)
    detail = detail if detail != title else title_source
    bullets = [condense_card_text(chunk) for chunk in chunks[1:3]]
    if not bullets and len(detail) > 140:
        first, second = split_item_for_card(detail)
        title = first
        detail = second
    return title, condense_card_text(detail), bullets, eyebrow


def condense_card_text(text: str, max_chars: int = 140) -> str:
    """Clamp long card text without turning it into a paragraph wall."""
    cleaned = " ".join(text.split()).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def strip_topic_prefix(text: str) -> str:
    """Remove internal topic-summary prefixes such as `Thesis —` from deck copy."""
    cleaned = " ".join(text.split()).strip()
    if " — " not in cleaned:
        return cleaned
    candidate, tail = cleaned.split(" — ", 1)
    if candidate in INTERNAL_TOPIC_LABELS:
        return tail.strip()
    return cleaned


INTERNAL_TOPIC_LABELS = {
    "Thesis",
    "Facts & Examples",
    "Links Between Ideas",
    "Insights & Further Study",
    "Context & Goals",
    "Problems & Constraints",
    "Decisions & Direction",
    "Actions & Open Questions",
    "Market Context",
    "Trade Setups",
    "Risk & Watchouts",
    "Catalysts & Watchlist",
    "Project & Opportunity",
    "Current State",
    "Design Decisions",
    "MVP Path & Cuts",
    "What Came Up",
    "Personal Updates",
    "Recommendations & Agreements",
    "Follow-up",
    "Corpus Overview",
    "Repeated Pain Points",
    "Direction Patterns",
    "Evidence Highlights",
}


def dedupe_items(items: list[str]) -> list[str]:
    """Keep item order while removing duplicates."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def choose_items(*candidates: list[str]) -> list[str]:
    """Return the first non-empty list of items."""
    for candidate in candidates:
        if candidate:
            return candidate
    return []


def should_render_assertion_summary(summary_text: str, headline: str) -> bool:
    """Avoid showing a second line when it only repeats the thesis in different casing."""
    if not summary_text.strip():
        return False
    summary_norm = re.sub(r"\s+", " ", summary_text.strip().lower())
    headline_norm = re.sub(r"\s+", " ", headline.strip().lower())
    return summary_norm not in headline_norm and headline_norm not in summary_norm


def agenda_kind_for(brief: DeckBriefDocument, index: int, language: str) -> str:
    """Return a short contextual label for an agenda block."""
    if brief.meeting_type == "lecture":
        tags = {
            "ru": ["Тезис", "Линза", "Сравнение", "Контекст", "Итог"],
            "en": ["Thesis", "Lens", "Compare", "Context", "Takeaway"],
            "fr": ["Thèse", "Angle", "Comparer", "Contexte", "Retenir"],
        }
        localized = tags[normalize_language(language)]
        if index < len(localized):
            return localized[index]

    generic = {
        "ru": ["Фокус", "Разбор", "Опоры", "Контекст", "Вывод"],
        "en": ["Focus", "Analysis", "Support", "Context", "Takeaway"],
        "fr": ["Focus", "Analyse", "Appuis", "Contexte", "Retenir"],
    }
    localized = generic[normalize_language(language)]
    return localized[index] if index < len(localized) else localized[-1]


def lecture_support_title(language: str) -> str:
    """Return a more specific title for thesis support lines."""
    labels = {
        "ru": "Ключевые линии",
        "en": "Key lines",
        "fr": "Lignes clés",
    }
    return labels[normalize_language(language)]


def title_for(brief: DeckBriefDocument, index: int, default: str) -> str:
    """Return a slide title from the brief when available."""
    if index < len(brief.slide_titles) and brief.slide_titles[index]:
        return brief.slide_titles[index]
    return default


def goal_for(brief: DeckBriefDocument, index: int, default: str) -> str:
    """Return a slide lead from the brief when available."""
    if index < len(brief.slide_goals) and brief.slide_goals[index]:
        return brief.slide_goals[index]
    return default


def default_title(kind: str, language: str) -> str:
    """Return localized fallback slide titles."""
    titles = {
        "en": {"snapshot": "Executive Snapshot", "signals": "Signals and Patterns", "direction": "Direction and Watchouts", "quotes": "Voice of the Call", "actions": "Action Plan"},
        "ru": {"snapshot": "Ключевой снимок", "signals": "Сигналы и паттерны", "direction": "Направление и риски", "quotes": "Голос разговора", "actions": "План действий"},
        "fr": {"snapshot": "Vue exécutive", "signals": "Signaux et motifs", "direction": "Direction et risques", "quotes": "Voix de l'échange", "actions": "Plan d'action"},
    }
    return titles[normalize_language(language)][kind]


def default_goal(kind: str, language: str) -> str:
    """Return localized fallback slide leads."""
    goals = {
        "en": {
            "snapshot": "Open with a compact read on what matters in this conversation.",
            "signals": "Compress the transcript into interpretable themes instead of raw bullets.",
            "direction": "Separate where the call is pointing from what may block progress.",
            "quotes": "Use selective direct language to keep the deck grounded.",
            "actions": "Close with sendable next steps, not generic wrap-up text.",
        },
        "ru": {
            "snapshot": "Открыть deck коротким, но сильным снимком сути разговора.",
            "signals": "Сжать стенограмму в интерпретируемые темы, а не в сырые bullets.",
            "direction": "Развести направление разговора и то, что может тормозить движение.",
            "quotes": "Оставить deck заземлённым через точечные прямые цитаты.",
            "actions": "Закрыть презентацию отправляемыми следующими шагами, а не общим recap.",
        },
        "fr": {
            "snapshot": "Ouvrir le deck avec une lecture compacte de l'essentiel.",
            "signals": "Compresser la transcription en thèmes interprétables plutôt qu'en bullets bruts.",
            "direction": "Séparer la direction perçue pendant l'appel des points de blocage.",
            "quotes": "Garder le deck ancré grâce à des citations choisies.",
            "actions": "Terminer avec des prochaines étapes envoyables, pas un simple récap.",
        },
    }
    return goals[normalize_language(language)][kind]


def local_label(language: str, key: str) -> str:
    """Return localized labels for infographic UI."""
    labels = {
        "en": {
            "signal_count": "scan",
            "pain_count": "pressure",
            "decision_count": "direction",
            "action_count": "follow-up",
            "captured_signals": "captured signals",
            "context_items": "context items",
            "frictions": "frictions",
            "direction_items": "direction items",
            "next_steps": "next steps",
            "evidence_signals": "evidence signals",
            "friction_cluster": "Friction",
            "workflow_cluster": "Workflow",
            "opportunity_cluster": "Opportunity",
            "risk_cluster": "Risk",
            "direction": "Direction",
            "watchouts": "Watchouts",
            "sendable_action": "Sendable action",
            "pain_chart": "Repeated pain points",
            "tool_chart": "Tool signals",
            "direction_chart": "Direction patterns",
            "mix_chart": "Talk mix",
        },
        "ru": {
            "signal_count": "скан",
            "pain_count": "напряжение",
            "decision_count": "направление",
            "action_count": "follow-up",
            "captured_signals": "сигналы",
            "context_items": "контекст",
            "frictions": "точки трения",
            "direction_items": "направляющие сигналы",
            "next_steps": "следующие шаги",
            "evidence_signals": "сигналы из разговора",
            "friction_cluster": "Трение",
            "workflow_cluster": "Текущий контур",
            "opportunity_cluster": "Возможность",
            "risk_cluster": "Риск",
            "direction": "Направление",
            "watchouts": "Что может помешать",
            "sendable_action": "Отправляемое действие",
            "pain_chart": "Повторяющиеся боли",
            "tool_chart": "Сигналы по инструментам",
            "direction_chart": "Повторяющиеся направления",
            "mix_chart": "Срез типов разговоров",
        },
        "fr": {
            "signal_count": "scan",
            "pain_count": "friction",
            "decision_count": "direction",
            "action_count": "suite",
            "captured_signals": "signaux captés",
            "context_items": "contexte",
            "frictions": "frictions",
            "direction_items": "signaux de direction",
            "next_steps": "prochaines actions",
            "evidence_signals": "signaux sources",
            "friction_cluster": "Friction",
            "workflow_cluster": "Flux actuel",
            "opportunity_cluster": "Opportunité",
            "risk_cluster": "Risque",
            "direction": "Direction",
            "watchouts": "Points de vigilance",
            "sendable_action": "Action envoyable",
            "pain_chart": "Douleurs récurrentes",
            "tool_chart": "Signaux outils",
            "direction_chart": "Directions récurrentes",
            "mix_chart": "Mix des échanges",
        },
    }
    return labels[normalize_language(language)][key]


def local_detail(language: str, key: str) -> str:
    """Return localized metric helper text."""
    details = {
        "en": {
            "captured_signals": "usable transcript signals extracted into the deck",
            "frictions": "items that describe pain, blockers, or process drag",
            "direction_items": "decision, intent, or implied next-direction statements",
            "next_steps": "actions that can be turned into immediate follow-up",
        },
        "ru": {
            "captured_signals": "сигналы из стенограммы, которые реально вошли в deck",
            "frictions": "пункты про боль, блокеры и операционное трение",
            "direction_items": "решения, намерения и имплицитное направление разговора",
            "next_steps": "действия, которые можно сразу превращать в follow-up",
        },
        "fr": {
            "captured_signals": "signaux utiles de la transcription intégrés au deck",
            "frictions": "éléments décrivant douleur, blocage ou lourdeur du process",
            "direction_items": "décisions, intentions ou direction implicite de l'appel",
            "next_steps": "actions transformables immédiatement en suivi",
        },
    }
    return details[normalize_language(language)][key]


def build_theme(style: str) -> str:
    """Return the CSS theme for the selected deck style."""
    base = """
      * { box-sizing: border-box; }
      html, body {
        margin: 0;
        min-height: 100%;
        color: var(--text);
        font-family: var(--body-font);
      }
      body {
        overflow: hidden;
        background:
          radial-gradient(circle at top left, rgba(96, 168, 255, 0.12), transparent 32%),
          radial-gradient(circle at top right, rgba(106, 233, 193, 0.10), transparent 28%),
          radial-gradient(circle at bottom center, rgba(255, 205, 97, 0.08), transparent 30%),
          var(--bg);
      }
      #deck {
        position: relative;
        width: 100vw;
        height: 100vh;
      }
      .slide {
        position: absolute;
        inset: 0;
        opacity: 0;
        pointer-events: none;
        transform: translateX(32px);
        transition: opacity 0.28s ease, transform 0.28s ease;
        padding: 4rem 2.8rem 3.8rem;
      }
      .slide.active {
        opacity: 1;
        pointer-events: auto;
        transform: translateX(0);
      }
      .slide-inner {
        display: flex;
        flex-direction: column;
        gap: 1.15rem;
        width: min(1180px, 100%);
        min-height: calc(100vh - 7.8rem);
        margin: 0 auto;
        padding: 2.1rem 2.35rem;
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 30px;
        box-shadow: 0 30px 90px var(--shadow);
        backdrop-filter: blur(18px);
      }
      .deck-shell {
        position: relative;
        overflow: hidden;
      }
      .deck-shell::before {
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(180deg, rgba(255,255,255,0.035), transparent 24%);
        pointer-events: none;
      }
      .hero {
        justify-content: flex-start;
      }
      .hero-layout {
        display: grid;
        grid-template-columns: minmax(0, 1.05fr) minmax(360px, 0.95fr);
        gap: 1.2rem;
        align-items: start;
      }
      .hero-copy {
        display: grid;
        gap: 1rem;
        align-content: start;
      }
      .hero-framing {
        padding: 1rem 1.1rem;
        border-radius: 20px;
        background: var(--surface-panel);
        border: 1px solid var(--border);
      }
      .hero-framing-text {
        margin: 0.45rem 0 0;
        font-size: 1.08rem;
        line-height: 1.55;
      }
      .hero-agenda {
        min-height: 100%;
      }
      .agenda-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.9rem;
        margin-top: 0.9rem;
      }
      .agenda-card {
        padding: 1rem 1rem 1.05rem;
        border-radius: 18px;
        background: var(--surface-subtle);
        border: 1px solid var(--border);
        display: grid;
        gap: 0.6rem;
      }
      .agenda-card-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 0.75rem;
      }
      .agenda-card h3 {
        margin: 0;
        font-size: 1.05rem;
        line-height: 1.18;
      }
      .agenda-purpose {
        margin: 0;
        color: var(--muted);
        font-size: 0.9rem;
        line-height: 1.45;
      }
      .agenda-anchors {
        list-style: none;
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        padding: 0;
        margin: 0;
      }
      .agenda-anchor {
        padding: 0.45rem 0.7rem;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid var(--border);
        font-size: 0.76rem;
        line-height: 1;
      }
      .meta-strip {
        list-style: none;
        display: flex;
        flex-wrap: wrap;
        gap: 0.7rem;
        padding: 0;
        margin: 0.5rem 0 0.2rem;
      }
      .meta-pill {
        padding: 0.72rem 0.9rem;
        border-radius: 999px;
        border: 1px solid var(--border);
        background: var(--surface-panel);
        font-family: var(--mono-font);
        font-size: 0.82rem;
        letter-spacing: 0.08em;
      }
      .eyebrow, .subtitle, .label, .counter, .metric-kicker, .metric-label, .metric-detail, .panel-title, .step-kind {
        color: var(--muted);
      }
      .eyebrow {
        font-size: 0.82rem;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        font-family: var(--mono-font);
      }
      h1, h2, h3 {
        margin: 0;
      }
      h1 {
        font-family: var(--heading-font);
        font-size: clamp(2.8rem, 6vw, 5.8rem);
        line-height: 0.94;
      }
      .title-slide h1 {
        max-width: 10.5ch;
        font-size: clamp(2.7rem, 5.2vw, 4.9rem);
        line-height: 0.92;
      }
      h2 {
        font-family: var(--heading-font);
        font-size: clamp(2rem, 4vw, 3.35rem);
        line-height: 1.03;
      }
      h3 {
        font-family: var(--heading-font);
        font-size: 1.28rem;
        line-height: 1.08;
      }
      .subtitle {
        font-size: 1.08rem;
        max-width: 46rem;
      }
      .title-slide .subtitle {
        margin-top: -0.15rem;
      }
      .title-slide .hero-framing {
        padding: 0.9rem 1rem;
      }
      .title-slide .hero-framing-text {
        font-size: 1rem;
        line-height: 1.45;
      }
      .title-slide .meta-strip {
        gap: 0.55rem;
      }
      .title-slide .meta-pill {
        padding: 0.62rem 0.8rem;
        font-size: 0.76rem;
      }
      .title-slide .hero-agenda {
        align-self: start;
      }
      .hero-stats {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 1rem;
        margin: 0.5rem 0 0.4rem;
      }
      .hero-stat,
      .metric-card,
      .insight-card,
      .step-card,
      .evidence-panel,
      .quote-card,
      .panel,
      .meta-card > div {
        background: var(--surface-panel);
        border: 1px solid var(--border);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
      }
      .hero-stat {
        padding: 1rem 1.1rem;
        border-radius: 18px;
      }
      .meta-card {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 1rem;
        margin-top: 1rem;
      }
      .meta-card > div {
        padding: 1rem 1.1rem;
        border-radius: 18px;
      }
      .label,
      .metric-kicker,
      .metric-label,
      .panel-title,
      .step-kind {
        display: block;
        font-family: var(--mono-font);
        font-size: 0.78rem;
        letter-spacing: 0.16em;
        text-transform: uppercase;
      }
      .metric-grid,
      .insight-grid,
      .action-grid,
      .analysis-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem;
      }
      .context-layout {
        display: grid;
        grid-template-columns: 1.15fr 0.85fr;
        gap: 1rem;
      }
      .lecture-grid {
        display: grid;
        gap: 1rem;
      }
      .lecture-kicker {
        display: block;
        font-family: var(--mono-font);
        font-size: 0.8rem;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: var(--muted);
      }
      .lecture-headline {
        max-width: 18ch;
      }
      .lecture-headline-compact {
        max-width: 24ch;
        font-size: clamp(1.85rem, 3vw, 2.85rem);
      }
      .lecture-grid-2 {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .lecture-grid-3 {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
      .lecture-assertion-band {
        display: grid;
        grid-template-columns: 1.15fr 0.85fr;
        gap: 1rem;
        align-items: stretch;
      }
      .lecture-assertion-copy {
        display: grid;
        gap: 0.8rem;
        padding: 0.2rem 0;
      }
      .lecture-assertion-summary {
        margin: 0;
        max-width: 42rem;
        font-size: 1.08rem;
        line-height: 1.55;
      }
      .lecture-evidence-panel {
        display: grid;
        align-content: start;
        gap: 0.8rem;
      }
      .lecture-summary-grid {
        display: grid;
        grid-template-columns: 1.05fr 0.95fr;
        gap: 1rem;
        align-items: start;
      }
      .lecture-hero-grid {
        display: grid;
        grid-template-columns: 1.15fr 0.85fr;
        gap: 1rem;
        align-items: start;
      }
      .lecture-slide-head {
        display: flex;
        align-items: end;
        justify-content: space-between;
        gap: 1rem;
      }
      .lecture-column {
        display: grid;
        gap: 1rem;
        align-content: start;
      }
      .lecture-visual-stack {
        display: grid;
        gap: 1rem;
        align-content: start;
      }
      .lecture-mini-grid {
        grid-template-columns: 1fr;
      }
      .lecture-chip-row {
        margin: -0.2rem 0 0.1rem;
      }
      .lecture-matrix-panel {
        padding: 0.9rem 1rem 1rem;
      }
      .lecture-matrix-head,
      .lecture-matrix-row {
        display: grid;
        grid-template-columns: 0.9fr 1.35fr 1.15fr;
        gap: 0.9rem;
        align-items: start;
      }
      .lecture-matrix-head {
        padding: 0 0.1rem 0.7rem;
        border-bottom: 1px solid var(--border);
        font-family: var(--mono-font);
        font-size: 0.74rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--muted);
      }
      .lecture-matrix-grid {
        display: grid;
      }
      .lecture-matrix-row {
        padding: 0.95rem 0.1rem;
        border-bottom: 1px solid rgba(255,255,255,0.06);
      }
      .lecture-matrix-row:last-child {
        border-bottom: none;
        padding-bottom: 0.15rem;
      }
      .lecture-matrix-cell {
        font-size: 0.96rem;
        line-height: 1.45;
      }
      .lecture-matrix-label {
        font-family: var(--heading-font);
        font-size: 1.04rem;
        line-height: 1.12;
      }
      .lecture-objects-layout {
        display: grid;
        grid-template-columns: 1.15fr 0.85fr;
        gap: 1rem;
        align-items: start;
      }
      .lecture-table-panel {
        padding: 0.9rem 1rem 1rem;
      }
      .lecture-table-head,
      .lecture-table-row {
        display: grid;
        grid-template-columns: 0.9fr 1.25fr 1.05fr;
        gap: 0.9rem;
        align-items: start;
      }
      .lecture-table-head {
        padding: 0 0.1rem 0.7rem;
        border-bottom: 1px solid var(--border);
        font-family: var(--mono-font);
        font-size: 0.74rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--muted);
      }
      .lecture-table-grid {
        display: grid;
      }
      .lecture-table-row {
        padding: 0.95rem 0.1rem;
        border-bottom: 1px solid rgba(255,255,255,0.06);
      }
      .lecture-table-row:last-child {
        border-bottom: none;
        padding-bottom: 0.15rem;
      }
      .lecture-table-cell {
        font-size: 0.96rem;
        line-height: 1.45;
      }
      .lecture-table-object {
        display: grid;
        gap: 0.45rem;
        justify-items: start;
      }
      .lecture-context-layout {
        display: grid;
        grid-template-columns: 1.1fr 0.9fr;
        gap: 1rem;
        align-items: start;
      }
      .lecture-summary-panel .bullet-list li {
        min-height: 0;
      }
      .compact-note-grid {
        display: grid;
        gap: 0.9rem;
      }
      .lecture-card {
        position: relative;
        padding: 1rem 1rem 0.95rem;
        border-radius: 24px;
        background:
          linear-gradient(180deg, rgba(255,255,255,0.035), transparent 42%),
          var(--surface-panel);
        border: 1px solid var(--border);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
        min-height: 188px;
      }
      .lecture-card.emphasis {
        background:
          radial-gradient(circle at top right, rgba(255,255,255,0.10), transparent 35%),
          linear-gradient(180deg, rgba(255,255,255,0.04), transparent 48%),
          var(--surface-panel);
      }
      .lecture-column-main .lecture-card {
        min-height: 0;
      }
      .lecture-compact-card {
        min-height: 0;
      }
      .lecture-card-head {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: center;
        margin-bottom: 0.75rem;
      }
      .lecture-visual-panel {
        padding: 1rem;
        border-radius: 24px;
      }
      .lecture-visual-frame {
        display: grid;
        place-items: center;
        min-height: 184px;
        border-radius: 18px;
        border: 1px solid var(--border);
        background:
          radial-gradient(circle at top left, rgba(255,255,255,0.08), transparent 35%),
          linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01));
        overflow: hidden;
      }
      .lecture-visual-copy {
        margin-top: 0.85rem;
      }
      .lecture-visual-copy p {
        margin: 0.45rem 0 0;
        line-height: 1.5;
        font-size: 0.98rem;
      }
      .lecture-svg {
        width: 100%;
        height: 100%;
      }
      .lecture-card p {
        margin: 0.45rem 0 0;
        line-height: 1.5;
        font-size: 0.98rem;
      }
      .lecture-band {
        background:
          linear-gradient(90deg, rgba(255,255,255,0.02), rgba(255,255,255,0.04)),
          var(--surface-panel);
      }
      .figure-poster {
        position: relative;
        height: 74px;
        margin: 0.05rem 0 0.7rem;
        border-radius: 18px;
        overflow: hidden;
        border: 1px solid var(--border);
        background:
          radial-gradient(circle at top, rgba(255,255,255,0.18), transparent 40%),
          linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.01));
      }
      .figure-arch {
        position: absolute;
        inset: auto 20% 0 20%;
        height: 54px;
        border: 2px solid rgba(255,255,255,0.62);
        border-bottom: none;
        border-top-left-radius: 999px;
        border-top-right-radius: 999px;
        opacity: 0.8;
      }
      .figure-year {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.32rem 0.55rem;
        border-radius: 999px;
        background: rgba(255,255,255,0.06);
        border: 1px solid var(--border-strong);
        font-family: var(--mono-font);
        font-size: 0.74rem;
        letter-spacing: 0.08em;
        color: var(--muted);
      }
      .compact-note-card {
        padding: 1rem 1.05rem;
        border-radius: 18px;
        background: var(--surface-subtle);
        border: 1px solid var(--border);
      }
      .compact-note-card p {
        margin: 0.45rem 0 0;
        line-height: 1.5;
      }
      .mini-bullets {
        margin: 0.55rem 0 0;
        padding-left: 1rem;
        display: grid;
        gap: 0.28rem;
        font-size: 0.9rem;
        line-height: 1.36;
      }
      .metric-card {
        padding: 1.05rem 1.1rem 1rem;
        border-radius: 22px;
        min-height: 172px;
        display: flex;
        flex-direction: column;
        gap: 0.45rem;
      }
      .metric-meter,
      .cluster-meter {
        width: 100%;
        height: 0.42rem;
        border-radius: 999px;
        overflow: hidden;
        background: rgba(255,255,255,0.08);
      }
      .metric-meter span,
      .cluster-meter span {
        display: block;
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, var(--accent), rgba(255,255,255,0.88));
      }
      .metric-value {
        font-family: var(--heading-font);
        font-size: clamp(2.3rem, 4vw, 3.6rem);
        line-height: 0.9;
      }
      .metric-detail {
        margin: auto 0 0;
        line-height: 1.45;
        font-size: 0.96rem;
      }
      .evidence-panel {
        padding: 1rem 1.1rem 1.1rem;
        border-radius: 22px;
      }
      .signal-strip {
        list-style: none;
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        padding: 0;
        margin: 0.75rem 0 0;
      }
      .signal-chip {
        padding: 0.65rem 0.8rem;
        border-radius: 999px;
        border: 1px solid var(--border);
        background: var(--surface-subtle);
        line-height: 1.28;
        font-size: 0.92rem;
      }
      .lecture-context-grid .lecture-card {
        min-height: 172px;
      }
      .timeline-panel {
        margin-top: 0.15rem;
      }
      .timeline-scale {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        margin-top: 0.75rem;
        font-family: var(--mono-font);
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        color: var(--muted);
      }
      .timeline-grid {
        display: grid;
        gap: 0.75rem;
        margin-top: 0.75rem;
      }
      .timeline-row {
        display: grid;
        gap: 0.35rem;
      }
      .timeline-meta {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: baseline;
      }
      .timeline-label {
        font-size: 0.96rem;
        line-height: 1.3;
      }
      .timeline-year {
        font-family: var(--mono-font);
        font-size: 0.8rem;
        color: var(--muted);
        letter-spacing: 0.08em;
        white-space: nowrap;
      }
      .timeline-track {
        position: relative;
        height: 0.68rem;
        border-radius: 999px;
        background: rgba(255,255,255,0.06);
        border: 1px solid var(--border);
        overflow: hidden;
      }
      .timeline-span {
        position: absolute;
        top: 0;
        bottom: 0;
        border-radius: 999px;
        background: linear-gradient(90deg, var(--accent), rgba(255,255,255,0.86));
      }
      .slide.fit-compact .slide-inner {
        gap: 0.9rem;
        padding: 1.7rem 1.95rem;
      }
      .slide.fit-compact h1 {
        font-size: clamp(2.25rem, 4.2vw, 3.85rem);
      }
      .slide.fit-compact h2 {
        font-size: clamp(1.8rem, 3.2vw, 2.75rem);
      }
      .slide.fit-compact .eyebrow,
      .slide.fit-compact .panel-title,
      .slide.fit-compact .label,
      .slide.fit-compact .step-kind {
        font-size: 0.72rem;
      }
      .slide.fit-compact .lecture-grid,
      .slide.fit-compact .lecture-summary-grid,
      .slide.fit-compact .lecture-hero-grid,
      .slide.fit-compact .lecture-assertion-band,
      .slide.fit-compact .lecture-objects-layout,
      .slide.fit-compact .lecture-context-layout,
      .slide.fit-compact .context-layout,
      .slide.fit-compact .analysis-grid,
      .slide.fit-compact .action-grid,
      .slide.fit-compact .step-grid {
        gap: 0.8rem;
      }
      .slide.fit-compact .lecture-card,
      .slide.fit-compact .panel,
      .slide.fit-compact .step-card,
      .slide.fit-compact .evidence-panel {
        min-height: 0;
      }
      .slide.fit-tight .slide-inner {
        gap: 0.75rem;
        padding: 1.45rem 1.7rem;
      }
      .slide.fit-tight h1 {
        font-size: clamp(1.95rem, 3.3vw, 3.15rem);
        line-height: 0.94;
      }
      .slide.fit-tight h2 {
        font-size: clamp(1.6rem, 2.7vw, 2.35rem);
      }
      .slide.fit-tight h3 {
        font-size: 1.06rem;
      }
      .slide.fit-tight .subtitle,
      .slide.fit-tight .hero-framing-text,
      .slide.fit-tight .lecture-card p,
      .slide.fit-tight .bullet-list li,
      .slide.fit-tight .signal-chip,
      .slide.fit-tight .step-card p {
        font-size: 0.9rem;
      }
      .slide.fit-tight .lecture-card,
      .slide.fit-tight .panel,
      .slide.fit-tight .step-card {
        padding: 0.85rem 0.9rem 0.82rem;
        border-radius: 18px;
      }
      .slide.fit-tight .figure-poster {
        height: 58px;
        margin-bottom: 0.55rem;
      }
      .slide.fit-tight .lecture-visual-frame {
        min-height: 132px;
      }
      .slide.fit-tight .figure-arch {
        height: 40px;
      }
      .slide.fit-tight .mini-bullets {
        font-size: 0.84rem;
        gap: 0.22rem;
      }
      .slide.fit-tight .timeline-label,
      .slide.fit-tight .timeline-year {
        font-size: 0.76rem;
      }
      .slide.fit-tight .timeline-grid {
        gap: 0.55rem;
      }
      .slide.fit-tight .lecture-matrix-head,
      .slide.fit-tight .lecture-table-head {
        font-size: 0.68rem;
      }
      .slide.fit-tight .agenda-grid {
        gap: 0.75rem;
      }
      .slide.fit-tight .agenda-card {
        padding: 0.85rem 0.9rem;
      }
      .slide.fit-tight .agenda-purpose {
        font-size: 0.82rem;
        line-height: 1.35;
      }
      .slide.fit-tight .agenda-anchor {
        font-size: 0.72rem;
      }
      .slide.fit-tight .meta-pill {
        padding: 0.5rem 0.7rem;
        font-size: 0.7rem;
      }
      .slide.fit-tight .hero-framing-text {
        font-size: 0.9rem;
        line-height: 1.35;
      }
      .slide.fit-tight .lecture-matrix-cell,
      .slide.fit-tight .lecture-table-cell,
      .slide.fit-tight .lecture-assertion-summary {
        font-size: 0.88rem;
      }
      .slide.fit-tight .lecture-matrix-row,
      .slide.fit-tight .lecture-table-row {
        gap: 0.7rem;
      }
      .insight-card {
        padding: 1rem 1.1rem 1.1rem;
        border-radius: 24px;
        min-height: 245px;
      }
      .insight-head {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: baseline;
      }
      .insight-count {
        font-family: var(--mono-font);
        color: var(--muted);
        letter-spacing: 0.14em;
      }
      .cluster-meter {
        margin: 0.6rem 0 0.8rem;
      }
      .insight-summary {
        margin: 0.5rem 0 1rem;
        font-size: 1.02rem;
        line-height: 1.5;
      }
      .direction-layout {
        display: grid;
        grid-template-columns: 1.3fr 0.9fr;
        gap: 1rem;
      }
      .panel {
        border-radius: 22px;
        padding: 1rem 1rem 1.1rem;
      }
      .bullet-list {
        display: grid;
        gap: 0.8rem;
        list-style: none;
        padding: 0;
        margin: 0;
      }
      .bullet-list li,
      .watch-item {
        padding: 0.95rem 1rem;
        line-height: 1.5;
        border: 1px solid var(--border);
        border-radius: 18px;
        background: var(--surface-subtle);
      }
      .bar-panel {
        display: grid;
        gap: 0.9rem;
      }
      .bar-row {
        display: grid;
        gap: 0.35rem;
      }
      .bar-meta {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        font-size: 0.95rem;
        line-height: 1.4;
      }
      .bar-track {
        width: 100%;
        height: 0.62rem;
        border-radius: 999px;
        overflow: hidden;
        background: rgba(255,255,255,0.07);
        border: 1px solid var(--border);
      }
      .bar-track span {
        display: block;
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, var(--accent), rgba(255,255,255,0.85));
      }
      .step-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem;
      }
      .step-card {
        min-height: 174px;
        padding: 1.1rem 1.1rem 1rem;
        border-radius: 22px;
      }
      .step-number {
        display: inline-flex;
        width: 2.3rem;
        height: 2.3rem;
        align-items: center;
        justify-content: center;
        border-radius: 999px;
        font-family: var(--mono-font);
        font-size: 0.8rem;
        letter-spacing: 0.12em;
        background: rgba(255,255,255,0.06);
        border: 1px solid var(--border-strong);
        margin-bottom: 0.9rem;
      }
      .step-card p {
        margin: 0.55rem 0 0;
        line-height: 1.55;
      }
      .quote-stack {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem;
      }
      .quote-card {
        position: relative;
        margin: 0;
        padding: 1.15rem 1.15rem 1.05rem 3.1rem;
        border-radius: 22px;
        min-height: 188px;
      }
      .quote-card p {
        margin: 0;
        font-size: 1.02rem;
        line-height: 1.58;
      }
      .quote-mark {
        position: absolute;
        left: 1rem;
        top: 0.75rem;
        font-size: 2.8rem;
        line-height: 1;
        color: var(--accent);
      }
      .evidence-card {
        min-height: 162px;
        padding-left: 1.25rem;
      }
      .evidence-rail {
        padding: 0.95rem 1rem 1rem;
        border-radius: 18px;
        border: 1px dashed var(--border-strong);
        background: rgba(255,255,255,0.025);
      }
      .evidence-list {
        list-style: none;
        display: grid;
        gap: 0.6rem;
        padding: 0;
        margin: 0.7rem 0 0;
      }
      .evidence-list li {
        padding: 0.75rem 0.85rem;
        border-radius: 14px;
        background: var(--surface-subtle);
        border: 1px solid var(--border);
        font-family: var(--mono-font);
        font-size: 0.85rem;
        line-height: 1.45;
      }
      .accent-teal { border-color: var(--teal-line); }
      .accent-blue { border-color: var(--blue-line); }
      .accent-gold { border-color: var(--gold-line); }
      .accent-rose { border-color: var(--rose-line); }
      .figure-poster.accent-teal { background: radial-gradient(circle at top, rgba(106, 233, 193, 0.24), transparent 42%), linear-gradient(180deg, rgba(106, 233, 193, 0.12), rgba(255,255,255,0.01)); }
      .figure-poster.accent-blue { background: radial-gradient(circle at top, rgba(96, 168, 255, 0.24), transparent 42%), linear-gradient(180deg, rgba(96, 168, 255, 0.12), rgba(255,255,255,0.01)); }
      .figure-poster.accent-gold { background: radial-gradient(circle at top, rgba(255, 205, 97, 0.24), transparent 42%), linear-gradient(180deg, rgba(255, 205, 97, 0.12), rgba(255,255,255,0.01)); }
      .figure-poster.accent-rose { background: radial-gradient(circle at top, rgba(255, 134, 171, 0.24), transparent 42%), linear-gradient(180deg, rgba(255, 134, 171, 0.12), rgba(255,255,255,0.01)); }
      .counter {
        position: fixed;
        top: 1.2rem;
        right: 1.5rem;
        z-index: 10;
        font-size: 0.85rem;
        letter-spacing: 0.08em;
        font-family: var(--mono-font);
      }
      .progress {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        height: 4px;
        background: rgba(127, 127, 127, 0.15);
        z-index: 10;
      }
      .progress-bar {
        height: 100%;
        width: 0;
        background: var(--accent);
        transition: width 0.28s ease;
      }
      @media (max-width: 720px) {
        .slide {
          padding: 1rem 1rem 1.5rem;
        }
        .slide-inner {
          min-height: calc(100vh - 2.5rem);
          padding: 1.4rem 1.2rem;
          border-radius: 20px;
        }
        .direction-layout,
        .context-layout,
        .lecture-assertion-band,
        .lecture-objects-layout,
        .lecture-context-layout,
        .lecture-grid-2,
        .lecture-grid-3,
        .lecture-summary-grid,
        .lecture-hero-grid,
        .hero-layout,
        .agenda-grid,
        .metric-grid,
        .insight-grid,
        .action-grid,
        .analysis-grid,
        .hero-stats,
        .quote-stack,
        .step-grid {
          grid-template-columns: 1fr;
        }
        .lecture-matrix-head,
        .lecture-matrix-row,
        .lecture-table-head,
        .lecture-table-row {
          grid-template-columns: 1fr;
        }
      }
      @media print {
        @page {
          size: A4 portrait;
          margin: 12mm;
        }
        html, body {
          background: #ffffff;
        }
        body {
          overflow: visible;
        }
        #deck {
          position: static;
          width: auto;
          height: auto;
        }
        .slide {
          position: static;
          inset: auto;
          opacity: 1 !important;
          pointer-events: auto;
          transform: none !important;
          transition: none;
          padding: 0;
          margin: 0 0 8mm;
          break-after: page;
          page-break-after: always;
        }
        .slide:last-child {
          break-after: auto;
          page-break-after: auto;
        }
        .slide-inner {
          width: auto;
          min-height: auto;
          margin: 0;
          padding: 12mm;
          border-radius: 0;
          box-shadow: none;
          break-inside: avoid;
          page-break-inside: avoid;
          backdrop-filter: none;
        }
        .counter,
        .progress {
          display: none !important;
        }
      }
    """
    if style == "terminal":
        return base + """
      :root {
        --bg: #07111f;
        --bg-card: rgba(10, 20, 34, 0.82);
        --surface-panel: rgba(14, 24, 40, 0.88);
        --surface-subtle: rgba(255, 255, 255, 0.03);
        --text: #edf4ff;
        --muted: #98abc3;
        --accent: #7ce7cc;
        --border: rgba(114, 140, 175, 0.20);
        --border-strong: rgba(114, 140, 175, 0.30);
        --shadow: rgba(0, 0, 0, 0.42);
        --teal-line: rgba(124, 231, 204, 0.55);
        --blue-line: rgba(107, 163, 255, 0.55);
        --gold-line: rgba(255, 209, 110, 0.55);
        --rose-line: rgba(255, 131, 154, 0.50);
        --heading-font: "SFMono-Regular", "IBM Plex Mono", "JetBrains Mono", Menlo, monospace;
        --body-font: "Avenir Next", "Inter", "Segoe UI", sans-serif;
        --mono-font: "SFMono-Regular", "IBM Plex Mono", "JetBrains Mono", Menlo, monospace;
      }
      body::after {
        content: "";
        position: fixed;
        inset: 0;
        background: repeating-linear-gradient(
          0deg,
          transparent,
          transparent 2px,
          rgba(0, 0, 0, 0.08) 2px,
          rgba(0, 0, 0, 0.08) 4px
        );
        pointer-events: none;
      }
    """
    return base + """
      :root {
        --bg: #f5f0e8;
        --bg-card: rgba(255, 252, 247, 0.92);
        --surface-panel: rgba(255, 252, 247, 0.92);
        --surface-subtle: rgba(179, 92, 63, 0.05);
        --text: #1e1b16;
        --muted: #6f665d;
        --accent: #b35c3f;
        --border: #ddd0c4;
        --border-strong: #d3c1b2;
        --shadow: rgba(104, 81, 56, 0.12);
        --teal-line: rgba(109, 156, 144, 0.5);
        --blue-line: rgba(110, 134, 199, 0.45);
        --gold-line: rgba(207, 154, 78, 0.5);
        --rose-line: rgba(185, 102, 104, 0.4);
        --heading-font: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
        --body-font: "Avenir Next", "Segoe UI", sans-serif;
        --mono-font: "SFMono-Regular", "JetBrains Mono", Menlo, monospace;
      }
    """


def slugify(value: str) -> str:
    """Build a filesystem-safe slug."""
    lowered = value.lower()
    lowered = re.sub(r"[^0-9a-zа-яё\s-]+", "", lowered, flags=re.IGNORECASE)
    lowered = re.sub(r"\s+", "-", lowered.strip())
    return lowered or "deck"


def escape(value: str) -> str:
    """Escape text for HTML output."""
    return html.escape(value, quote=True)
