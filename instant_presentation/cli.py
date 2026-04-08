"""CLI scaffold for INSTANT PRESENTATION."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .brief import build_brief_file
from .build import build_from_note, build_from_transcript, build_research
from .io import render_result_json
from .normalization import normalize_transcript_file
from .render import render_summary_file
from .summary import summarize_note_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="instant-presentation",
        description="Turn meeting transcripts into structured notes, summaries, and decks.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    normalize = subparsers.add_parser(
        "normalize",
        help="Convert a raw transcript into a canonical transcript note.",
    )
    normalize.add_argument("input", type=Path, help="Path to the transcript file.")
    normalize.add_argument(
        "--source",
        choices=["auto", "krisp", "zoom", "meet", "teams", "generic"],
        default="auto",
        help="Transcript source override.",
    )
    normalize.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for generated artifacts.",
    )
    normalize.add_argument(
        "--project",
        default="instant",
        help="Project code used in generated filenames and frontmatter.",
    )

    summarize = subparsers.add_parser(
        "summarize",
        help="Generate a structured summary from a normalized transcript note.",
    )
    summarize.add_argument("input", type=Path, help="Path to the normalized transcript note.")
    summarize.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for generated artifacts.",
    )
    summarize.add_argument(
        "--project",
        default="instant",
        help="Project code used in generated filenames and frontmatter.",
    )
    summarize.add_argument(
        "--context-note",
        action="append",
        default=[],
        type=Path,
        help="Optional supporting context note path. Repeatable.",
    )
    summarize.add_argument(
        "--summary-engine",
        choices=["auto", "heuristic", "openai", "claude"],
        default="auto",
        help="Summary extraction engine.",
    )
    summarize.add_argument(
        "--goal",
        choices=["recap", "follow_up", "decision", "pitch", "research"],
        default=None,
        help="Optional presentation goal override.",
    )
    summarize.add_argument(
        "--audience",
        default=None,
        help="Optional audience label override.",
    )
    summarize.add_argument(
        "--tone",
        choices=["clear", "sharp", "persuasive", "insightful", "warm"],
        default=None,
        help="Optional tone override.",
    )

    brief = subparsers.add_parser(
        "brief",
        help="Generate an intermediate deck brief from a summary note.",
    )
    brief.add_argument("input", type=Path, help="Path to the summary note.")
    brief.add_argument(
        "--style",
        choices=["editorial", "terminal"],
        default="editorial",
        help="Deck visual style.",
    )
    brief.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for generated artifacts.",
    )

    render = subparsers.add_parser(
        "render",
        help="Render an HTML deck from a summary or brief note.",
    )
    render.add_argument("input", type=Path, help="Path to the summary note.")
    render.add_argument(
        "--style",
        choices=["editorial", "terminal"],
        default="editorial",
        help="Deck visual style.",
    )
    render.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for generated artifacts.",
    )

    build = subparsers.add_parser(
        "build",
        help="Run the end-to-end transcript-to-deck flow.",
    )
    build.add_argument("input", type=Path, help="Path to the transcript file.")
    build.add_argument(
        "--source",
        choices=["auto", "krisp", "zoom", "meet", "teams", "generic"],
        default="auto",
        help="Transcript source override.",
    )
    build.add_argument(
        "--style",
        choices=["editorial", "terminal"],
        default="editorial",
        help="Deck visual style.",
    )
    build.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for generated artifacts.",
    )
    build.add_argument(
        "--project",
        default="instant",
        help="Project code used in generated filenames and frontmatter.",
    )
    build.add_argument(
        "--context-note",
        action="append",
        default=[],
        type=Path,
        help="Optional supporting context note path. Repeatable.",
    )
    build.add_argument(
        "--summary-engine",
        choices=["auto", "heuristic", "openai", "claude"],
        default="auto",
        help="Summary extraction engine.",
    )
    build.add_argument("--goal", choices=["recap", "follow_up", "decision", "pitch", "research"], default=None, help="Optional presentation goal override.")
    build.add_argument("--audience", default=None, help="Optional audience label override.")
    build.add_argument("--tone", choices=["clear", "sharp", "persuasive", "insightful", "warm"], default=None, help="Optional tone override.")
    build.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a single path.",
    )

    build_note = subparsers.add_parser(
        "build-note",
        help="Run the end-to-end flow starting from an existing transcript note in Obsidian.",
    )
    build_note.add_argument("input", type=Path, help="Path to the normalized transcript note.")
    build_note.add_argument(
        "--style",
        choices=["editorial", "terminal"],
        default="editorial",
        help="Deck visual style.",
    )
    build_note.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for generated artifacts.",
    )
    build_note.add_argument(
        "--project",
        default="instant",
        help="Project code used in generated filenames and frontmatter.",
    )
    build_note.add_argument(
        "--context-note",
        action="append",
        default=[],
        type=Path,
        help="Optional supporting context note path. Repeatable.",
    )
    build_note.add_argument(
        "--summary-engine",
        choices=["auto", "heuristic", "openai", "claude"],
        default="auto",
        help="Summary extraction engine.",
    )
    build_note.add_argument("--goal", choices=["recap", "follow_up", "decision", "pitch", "research"], default=None, help="Optional presentation goal override.")
    build_note.add_argument("--audience", default=None, help="Optional audience label override.")
    build_note.add_argument("--tone", choices=["clear", "sharp", "persuasive", "insightful", "warm"], default=None, help="Optional tone override.")
    build_note.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a single path.",
    )

    build_research_parser = subparsers.add_parser(
        "build-research",
        help="Build a corpus-level research deck from multiple transcript notes.",
    )
    build_research_parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Paths to normalized transcript notes.",
    )
    build_research_parser.add_argument(
        "--style",
        choices=["editorial", "terminal"],
        default="editorial",
        help="Deck visual style.",
    )
    build_research_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for generated artifacts.",
    )
    build_research_parser.add_argument(
        "--project",
        default="instant",
        help="Project code used in generated filenames and frontmatter.",
    )
    build_research_parser.add_argument(
        "--context-note",
        action="append",
        default=[],
        type=Path,
        help="Optional supporting context note path. Repeatable.",
    )
    build_research_parser.add_argument(
        "--summary-engine",
        choices=["auto", "heuristic", "openai", "claude"],
        default="auto",
        help="Summary extraction engine for per-note analysis.",
    )
    build_research_parser.add_argument("--audience", default=None, help="Optional audience label override.")
    build_research_parser.add_argument("--tone", choices=["clear", "sharp", "persuasive", "insightful", "warm"], default=None, help="Optional tone override.")
    build_research_parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a single path.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "normalize":
        output_path = normalize_transcript_file(
            input_path=args.input,
            output_dir=args.output_dir,
            source_hint=args.source,
            project=args.project,
        )
        print(output_path)
        return 0

    if args.command == "summarize":
        output_path = summarize_note_file(
            input_path=args.input,
            output_dir=args.output_dir,
            project=args.project,
            context_notes=args.context_note,
            summary_engine=args.summary_engine,
            presentation_goal=args.goal,
            audience=args.audience,
            tone=args.tone,
        )
        print(output_path)
        return 0

    if args.command == "brief":
        output_path = build_brief_file(
            input_path=args.input,
            output_dir=args.output_dir,
            style=args.style,
        )
        print(output_path)
        return 0

    if args.command == "render":
        output_path = render_summary_file(
            input_path=args.input,
            output_dir=args.output_dir,
            style=args.style,
        )
        print(output_path)
        return 0

    if args.command == "build":
        result = build_from_transcript(
            input_path=args.input,
            output_dir=args.output_dir,
            source_hint=args.source,
            style=args.style,
            project=args.project,
            context_notes=args.context_note,
            summary_engine=args.summary_engine,
            presentation_goal=args.goal,
            audience=args.audience,
            tone=args.tone,
        )
        if args.json:
            print(render_result_json(result))
        else:
            print(result["deck"])
        return 0

    if args.command == "build-note":
        result = build_from_note(
            input_path=args.input,
            output_dir=args.output_dir,
            style=args.style,
            project=args.project,
            context_notes=args.context_note,
            summary_engine=args.summary_engine,
            presentation_goal=args.goal,
            audience=args.audience,
            tone=args.tone,
        )
        if args.json:
            print(render_result_json(result))
        else:
            print(result["deck"])
        return 0

    if args.command == "build-research":
        result = build_research(
            input_paths=args.inputs,
            output_dir=args.output_dir,
            style=args.style,
            project=args.project,
            context_notes=args.context_note,
            summary_engine=args.summary_engine,
            audience=args.audience,
            tone=args.tone,
        )
        if args.json:
            print(render_result_json(result))
        else:
            print(result["deck"])
        return 0

    print(f"{args.command} is not implemented yet.")
    return 0
