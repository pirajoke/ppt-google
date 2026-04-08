"""Transcript normalization helpers."""

from __future__ import annotations

import re
from pathlib import Path

from .i18n import detect_language
from .models import TranscriptDocument, TranscriptSegment

METADATA_PATTERNS = {
    "title": re.compile(r"^(?:Meeting Title|Title):\s*(.+)$", re.IGNORECASE),
    "date": re.compile(r"^Date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})$", re.IGNORECASE),
    "participants": re.compile(r"^Participants:\s*(.+)$", re.IGNORECASE),
}

SEGMENT_PATTERNS = [
    re.compile(r"^\[(?P<ts>\d{1,2}:\d{2}(?::\d{2})?)\]\s*(?P<speaker>[^:]+):\s*(?P<text>.+)$"),
    re.compile(r"^(?P<ts>\d{1,2}:\d{2}(?::\d{2})?)\s+(?P<speaker>[^:]+):\s*(?P<text>.+)$"),
]


def normalize_transcript_file(
    input_path: Path,
    output_dir: Path,
    source_hint: str = "auto",
    project: str = "instant",
) -> Path:
    """Read a transcript file, normalize it, and write a canonical markdown note."""
    raw_text = input_path.read_text(encoding="utf-8")
    detected_source = detect_source(input_path=input_path, text=raw_text, source_hint=source_hint)
    document = parse_transcript_text(
        text=raw_text,
        source=detected_source,
        origin_file=input_path.name,
        project=project,
        fallback_title=input_path.stem.replace("-", " ").strip(),
    )
    # Pass raw_text so plain (unstructured) transcripts are preserved verbatim
    note_content = render_transcript_markdown(document, raw_text=raw_text if not document.segments else None)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / build_output_filename(document)
    output_path.write_text(note_content, encoding="utf-8")
    return output_path


def detect_source(input_path: Path, text: str, source_hint: str = "auto") -> str:
    """Resolve the transcript source from explicit input or content heuristics."""
    if source_hint != "auto":
        return source_hint

    lowered_text = text.lower()
    lowered_name = input_path.name.lower()

    if "source: krisp" in lowered_text or "krisp" in lowered_name:
        return "krisp"
    if "source: zoom" in lowered_text or "zoom" in lowered_name:
        return "zoom"
    if "source: google meet" in lowered_text or "meet" in lowered_name:
        return "meet"
    if "source: teams" in lowered_text or "teams" in lowered_name:
        return "teams"
    return "generic"


def parse_transcript_text(
    text: str,
    source: str,
    origin_file: str,
    project: str,
    fallback_title: str,
) -> TranscriptDocument:
    """Convert raw transcript text into the canonical in-memory document."""
    lines = [line.rstrip() for line in text.splitlines()]

    title = extract_metadata(lines, "title") or extract_heading(lines) or fallback_title
    date = extract_metadata(lines, "date") or "1970-01-01"
    participants = parse_participants(extract_metadata(lines, "participants"))
    language = detect_language(text)
    segments = extract_segments(lines)

    if not participants:
        participants = sorted({segment.speaker for segment in segments if segment.speaker})

    return TranscriptDocument(
        title=title,
        source=source,
        date=date,
        participants=participants,
        language=language,
        origin_file=origin_file,
        project=project,
        segments=segments,
    )


def extract_metadata(lines: list[str], field: str) -> str | None:
    """Extract a simple metadata value from transcript header lines."""
    pattern = METADATA_PATTERNS[field]
    for line in lines:
        match = pattern.match(line.strip())
        if match:
            return match.group(1).strip()
    return None


def extract_heading(lines: list[str]) -> str | None:
    """Use the first markdown heading as a title when metadata is absent."""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def parse_participants(raw_value: str | None) -> list[str]:
    """Turn a comma-separated participants string into a normalized list."""
    if not raw_value:
        return []
    return [part.strip() for part in raw_value.split(",") if part.strip()]


def extract_segments(lines: list[str]) -> list[TranscriptSegment]:
    """Parse transcript utterances from supported line formats."""
    segments: list[TranscriptSegment] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        for pattern in SEGMENT_PATTERNS:
            match = pattern.match(stripped)
            if match:
                segments.append(
                    TranscriptSegment(
                        timestamp=match.group("ts"),
                        speaker=match.group("speaker").strip(),
                        text=match.group("text").strip(),
                    )
                )
                break
    return segments


def build_output_filename(document: TranscriptDocument) -> str:
    """Build a predictable markdown filename for the normalized note."""
    title = sanitize_filename_part(document.title.lower())
    return f"{{{document.project}}} {{transcript}} {title} – {document.date}.md"


def sanitize_filename_part(value: str) -> str:
    """Keep filenames readable and stable."""
    cleaned = re.sub(r"[^0-9a-zа-яё\s-]+", "", value, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:60].rstrip() or "untitled transcript"


def render_transcript_markdown(document: TranscriptDocument, raw_text: str | None = None) -> str:
    """Render the canonical transcript note as markdown with YAML frontmatter."""
    participants = (
        "\n".join(f"  - {participant}" for participant in document.participants)
        if document.participants
        else "  []"
    )
    tags = "\n".join(
        [
            "  - type/transcript",
            f"  - source/{document.source}",
            f"  - project/{document.project}",
            "  - status/normalized",
        ]
    )

    lines = [
        "---",
        f'title: "{escape_quotes(document.title)}"',
        f"source: {document.source}",
        "type: transcript",
        f"date: {document.date}",
        f"status: {document.status}",
        f"project: {document.project}",
        f"language: {document.language}",
        f"origin_file: {document.origin_file}",
        "participants:",
        participants,
        "tags:",
        tags,
        "---",
        "",
        f"# {document.title}",
        "",
        f"- Source: `{document.source}`",
        f"- Date: `{document.date}`",
        f"- Language: `{document.language}`",
        f"- Project: `{document.project}`",
        f"- Origin file: `{document.origin_file}`",
        "",
        "## Participants",
        "",
    ]

    if document.participants:
        lines.extend(f"- {participant}" for participant in document.participants)
    else:
        lines.append("- Unknown")

    lines.extend(["", "## Transcript", ""])

    if document.segments:
        for segment in document.segments:
            prefix_parts = [part for part in [segment.timestamp, segment.speaker] if part]
            prefix = " | ".join(prefix_parts)
            if prefix:
                lines.append(f"**{prefix}**: {segment.text}")
            else:
                lines.append(segment.text)
            lines.append("")
    elif raw_text:
        # Plain text input (no structured segments) — include verbatim
        lines.append(raw_text.strip())
        lines.append("")
    else:
        lines.append("_No transcript segments parsed._")
        lines.append("")

    return "\n".join(lines)


def escape_quotes(value: str) -> str:
    """Escape double quotes for YAML string output."""
    return value.replace('"', '\\"')
