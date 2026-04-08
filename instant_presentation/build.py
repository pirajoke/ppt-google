"""End-to-end build flow for transcript-to-deck generation."""

from __future__ import annotations

from pathlib import Path

from .aggregate import build_research_from_notes
from .brief import build_brief_file
from .normalization import normalize_transcript_file
from .render import render_summary_file
from .summary import summarize_note_file


def build_from_transcript(
    input_path: Path,
    output_dir: Path,
    source_hint: str = "auto",
    style: str = "editorial",
    project: str = "instant",
    context_notes: list[Path] | None = None,
    summary_engine: str = "auto",
    presentation_goal: str | None = None,
    audience: str | None = None,
    tone: str | None = None,
) -> dict[str, Path]:
    """Run the end-to-end local flow and write a small build manifest."""
    context_notes = context_notes or []
    normalized_path = normalize_transcript_file(
        input_path=input_path,
        output_dir=output_dir,
        source_hint=source_hint,
        project=project,
    )
    summary_path = summarize_note_file(
        input_path=normalized_path,
        output_dir=output_dir,
        project=project,
        context_notes=context_notes,
        summary_engine=summary_engine,
        presentation_goal=presentation_goal,
        audience=audience,
        tone=tone,
    )
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
    manifest_path = write_build_manifest(
        output_dir=output_dir,
        input_path=input_path,
        normalized_path=normalized_path,
        summary_path=summary_path,
        brief_path=brief_path,
        deck_path=deck_path,
        style=style,
        context_notes=context_notes,
        summary_engine=summary_engine,
        presentation_goal=presentation_goal,
        audience=audience,
        tone=tone,
    )
    return {
        "normalized": normalized_path,
        "summary": summary_path,
        "brief": brief_path,
        "deck": deck_path,
        "manifest": manifest_path,
    }


def build_from_note(
    input_path: Path,
    output_dir: Path,
    style: str = "editorial",
    project: str = "instant",
    context_notes: list[Path] | None = None,
    summary_engine: str = "auto",
    presentation_goal: str | None = None,
    audience: str | None = None,
    tone: str | None = None,
) -> dict[str, Path]:
    """Run the flow starting from an existing normalized transcript note."""
    context_notes = context_notes or []
    summary_path = summarize_note_file(
        input_path=input_path,
        output_dir=output_dir,
        project=project,
        context_notes=context_notes,
        summary_engine=summary_engine,
        presentation_goal=presentation_goal,
        audience=audience,
        tone=tone,
    )
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
    manifest_path = write_build_manifest(
        output_dir=output_dir,
        input_path=input_path,
        normalized_path=input_path,
        summary_path=summary_path,
        brief_path=brief_path,
        deck_path=deck_path,
        style=style,
        context_notes=context_notes,
        summary_engine=summary_engine,
        presentation_goal=presentation_goal,
        audience=audience,
        tone=tone,
    )
    return {
        "normalized": input_path,
        "summary": summary_path,
        "brief": brief_path,
        "deck": deck_path,
        "manifest": manifest_path,
    }


def build_research(
    input_paths: list[Path],
    output_dir: Path,
    style: str = "editorial",
    project: str = "instant",
    context_notes: list[Path] | None = None,
    summary_engine: str = "auto",
    audience: str | None = None,
    tone: str | None = None,
) -> dict[str, Path]:
    """Run the corpus-level research flow starting from multiple transcript notes."""
    return build_research_from_notes(
        input_paths=input_paths,
        output_dir=output_dir,
        style=style,
        project=project,
        context_notes=context_notes,
        summary_engine=summary_engine,
        audience=audience,
        tone=tone,
    )


def write_build_manifest(
    output_dir: Path,
    input_path: Path,
    normalized_path: Path,
    summary_path: Path,
    brief_path: Path,
    deck_path: Path,
    style: str,
    context_notes: list[Path],
    summary_engine: str,
    presentation_goal: str | None = None,
    audience: str | None = None,
    tone: str | None = None,
) -> Path:
    """Write a compact manifest for the end-to-end build."""
    manifest_path = output_dir / "build-manifest.md"
    lines = [
        "# Build Manifest",
        "",
        f"- Input transcript: `{input_path}`",
        f"- Normalized note: `{normalized_path}`",
        f"- Summary note: `{summary_path}`",
        f"- Deck brief: `{brief_path}`",
        f"- Deck: `{deck_path}`",
        f"- Style: `{style}`",
        f"- Summary engine: `{summary_engine}`",
        f"- Presentation goal: `{presentation_goal or 'infer'}`",
        f"- Audience: `{audience or 'infer'}`",
        f"- Tone: `{tone or 'infer'}`",
        "",
        "## Context Notes",
        "",
    ]
    if context_notes:
        lines.extend(f"- `{path}`" for path in context_notes)
    else:
        lines.append("- None")
    lines.append("")
    manifest_path.write_text("\n".join(lines), encoding="utf-8")
    return manifest_path
