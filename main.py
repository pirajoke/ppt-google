"""PPT Google — FastAPI web app.

Flow:
  POST /upload (audio file or text) → process → return presentation URL
  GET  /p/{id}                       → serve generated HTML presentation
"""

from __future__ import annotations

import os
import uuid
from datetime import date
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from transcription import transcribe_bytes
from instant_presentation.models import TranscriptDocument, TranscriptSegment
from instant_presentation.claude_engine import summarize_with_claude
from instant_presentation.deck_render import render_deck_html
from storage import save_presentation, load_presentation

app = FastAPI(title="PPT Google", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

AUDIO_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".wav", ".ogg", ".webm", ".flac"}


@app.get("/", response_class=HTMLResponse)
async def index():
    return Path("templates/index.html").read_text()


@app.post("/upload")
async def upload(
    file: UploadFile | None = File(default=None),
    transcript: str | None = Form(default=None),
    audience: str | None = Form(default=None),
    goal: str | None = Form(default=None),
    style: str = Form(default="neon"),
):
    """Accept audio file OR raw transcript text, return presentation URL."""
    if not file and not transcript:
        raise HTTPException(status_code=400, detail="Provide file or transcript")

    # 1. Get transcript text
    if transcript:
        text = transcript.strip()
        source_name = "pasted-transcript"
    else:
        ext = Path(file.filename).suffix.lower()
        if ext not in AUDIO_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
        audio_bytes = await file.read()
        text = transcribe_bytes(audio_bytes, ext=ext.lstrip("."))
        source_name = file.filename

    if not text:
        raise HTTPException(status_code=422, detail="Empty transcript after processing")

    # 2. Build TranscriptDocument with plain-text fallback
    doc = TranscriptDocument(
        title="Meeting",
        source="meet",
        date=date.today().isoformat(),
        participants=[],
        language="auto",
        origin_file=source_name,
        project="ppt-google",
        segments=[TranscriptSegment(timestamp=None, speaker=None, text=text)],
    )

    # 3. Summarize via Claude (extract structure + slide plan)
    summary = summarize_with_claude(
        transcript=doc,
        context_notes=[],
        context_signals=[],
        presentation_goal=goal or None,
        audience=audience or None,
    )

    # 4. Render beautiful HTML deck
    html = render_deck_html(summary, style=style)

    # 5. Save and return link
    pres_id = str(uuid.uuid4())[:8]
    save_presentation(pres_id, html)

    return JSONResponse({"id": pres_id, "url": f"/p/{pres_id}"})


@app.get("/p/{pres_id}", response_class=HTMLResponse)
async def presentation(pres_id: str):
    html = load_presentation(pres_id)
    if html is None:
        raise HTTPException(status_code=404, detail="Presentation not found")
    return html
