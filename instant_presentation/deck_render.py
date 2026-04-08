"""Generate a full HTML slide deck from a SummaryDocument using Claude."""

from __future__ import annotations

import json
import os

from .models import SummaryDocument

# Premium dark design system — modern, clean, high-contrast
DESIGN_SPEC = """
You are generating a PREMIUM DARK HTML presentation. It must look like a product from Linear, Vercel, or Notion — clean, modern, high-end.

## Visual direction
- Dark background: #09090b
- Cards: #111113 with subtle border #27272a
- Text: #fafafa (primary), #a1a1aa (secondary), #52525b (dim)
- Accent: #6366f1 (indigo), second accent #22d3ee (cyan), danger #f43f5e
- Font: Inter for everything. Load from Google Fonts.
- Tight spacing, big bold numbers, clean lines.
- NO decorative gradients on backgrounds. Clean flat dark.
- Accent color only on key numbers, labels, or active elements.

## HTML Template Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{{TITLE}}</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    /* === RESET & BASE === */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #09090b;
      --bg-2: #111113;
      --bg-3: #18181b;
      --border: #27272a;
      --border-light: #3f3f46;
      --text: #fafafa;
      --text-2: #a1a1aa;
      --text-3: #52525b;
      --accent: #6366f1;
      --accent-2: #22d3ee;
      --accent-3: #f59e0b;
      --danger: #f43f5e;
      --success: #4ade80;
    }
    html, body {
      width: 100%; height: 100%;
      background: var(--bg);
      color: var(--text);
      font-family: 'Inter', -apple-system, sans-serif;
      -webkit-font-smoothing: antialiased;
      overflow: hidden;
    }

    /* === SLIDES === */
    .slide {
      display: none;
      width: 100vw; height: 100vh;
      padding: 64px 80px 80px;
      flex-direction: column;
      justify-content: center;
      align-items: flex-start;
      position: relative;
    }
    .slide.active { display: flex; }
    .slide-inner { width: 100%; max-width: 1100px; }

    /* === COUNTER === */
    .counter {
      position: absolute;
      top: 28px; right: 40px;
      font-size: 12px;
      font-weight: 500;
      color: var(--text-3);
      letter-spacing: 0.5px;
    }
    .counter .current { color: var(--text-2); }

    /* === TYPOGRAPHY === */
    .label {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 2px;
      text-transform: uppercase;
      color: var(--text-3);
      margin-bottom: 16px;
    }
    .label.accent { color: var(--accent); }
    h1 {
      font-size: 52px;
      font-weight: 800;
      line-height: 1.1;
      color: var(--text);
      letter-spacing: -1.5px;
      margin-bottom: 20px;
    }
    h2 {
      font-size: 36px;
      font-weight: 700;
      line-height: 1.2;
      color: var(--text);
      letter-spacing: -0.8px;
      margin-bottom: 24px;
    }
    .sub {
      font-size: 18px;
      font-weight: 400;
      color: var(--text-2);
      line-height: 1.6;
      max-width: 700px;
      margin-bottom: 32px;
    }
    .meta {
      font-size: 13px;
      color: var(--text-3);
      font-weight: 400;
    }

    /* === CARDS GRID === */
    .cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 12px;
      margin-top: 8px;
    }
    .card {
      background: var(--bg-2);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 20px 22px;
      transition: border-color 0.15s;
    }
    .card:hover { border-color: var(--border-light); }
    .card-label {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      color: var(--text-3);
      margin-bottom: 10px;
    }
    .card-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 6px;
      line-height: 1.4;
    }
    .card-body {
      font-size: 14px;
      color: var(--text-2);
      line-height: 1.6;
    }

    /* === STATS ROW === */
    .stats {
      display: flex;
      gap: 12px;
      margin-top: 8px;
      flex-wrap: wrap;
    }
    .stat {
      background: var(--bg-2);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 20px 24px;
      flex: 1;
      min-width: 140px;
    }
    .stat-num {
      font-size: 40px;
      font-weight: 800;
      letter-spacing: -1.5px;
      color: var(--accent);
      line-height: 1;
      margin-bottom: 6px;
    }
    .stat-num.cyan { color: var(--accent-2); }
    .stat-num.amber { color: var(--accent-3); }
    .stat-num.green { color: var(--success); }
    .stat-label {
      font-size: 13px;
      color: var(--text-3);
      font-weight: 400;
    }

    /* === LIST (bullet points) === */
    .list {
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin-top: 8px;
    }
    .list-item {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 14px 18px;
      background: var(--bg-2);
      border: 1px solid var(--border);
      border-radius: 8px;
      font-size: 15px;
      color: var(--text-2);
      line-height: 1.5;
    }
    .list-item .dot {
      width: 6px; height: 6px;
      border-radius: 50%;
      background: var(--accent);
      margin-top: 6px;
      flex-shrink: 0;
    }
    .list-item .dot.cyan { background: var(--accent-2); }
    .list-item .dot.amber { background: var(--accent-3); }
    .list-item strong { color: var(--text); font-weight: 600; }

    /* === STEPS (ordered) === */
    .steps {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-top: 8px;
    }
    .step {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 16px 20px;
      background: var(--bg-2);
      border: 1px solid var(--border);
      border-radius: 8px;
      transition: border-color 0.15s;
    }
    .step:hover { border-color: var(--border-light); }
    .step-num {
      font-size: 11px;
      font-weight: 700;
      color: var(--accent);
      background: rgba(99,102,241,0.12);
      border-radius: 4px;
      padding: 3px 8px;
      letter-spacing: 0.5px;
      flex-shrink: 0;
    }
    .step-text { font-size: 15px; color: var(--text); font-weight: 500; flex: 1; }
    .step-sub { font-size: 13px; color: var(--text-3); }

    /* === TWO COLUMNS === */
    .split {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
      margin-top: 8px;
    }
    .col-label {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 2px;
      text-transform: uppercase;
      color: var(--text-3);
      margin-bottom: 12px;
    }

    /* === HIGHLIGHT BLOCK === */
    .highlight {
      background: rgba(99,102,241,0.08);
      border: 1px solid rgba(99,102,241,0.25);
      border-left: 3px solid var(--accent);
      border-radius: 8px;
      padding: 18px 22px;
      margin-top: 16px;
    }
    .highlight p {
      font-size: 16px;
      color: var(--text);
      line-height: 1.65;
    }

    /* === TAG === */
    .tag {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 11px;
      font-weight: 600;
      padding: 3px 10px;
      border-radius: 4px;
      letter-spacing: 0.3px;
    }
    .tag.purple { background: rgba(99,102,241,0.15); color: var(--accent); }
    .tag.cyan { background: rgba(34,211,238,0.12); color: var(--accent-2); }
    .tag.amber { background: rgba(245,158,11,0.12); color: var(--accent-3); }
    .tag.red { background: rgba(244,63,94,0.12); color: var(--danger); }
    .tag.green { background: rgba(74,222,128,0.12); color: var(--success); }

    /* === PROGRESS BAR === */
    .progress {
      position: fixed;
      bottom: 0; left: 0;
      height: 1px;
      background: var(--accent);
      transition: width 0.25s ease;
      z-index: 100;
      opacity: 0.6;
    }

    /* === NAV HINT === */
    .nav-hint {
      position: fixed;
      bottom: 20px; right: 40px;
      font-size: 11px;
      color: var(--text-3);
      opacity: 0.5;
    }

    /* === ANIMATIONS === */
    @keyframes up {
      from { opacity: 0; transform: translateY(16px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    .slide.active .slide-inner > * { animation: up 0.4s ease-out both; }
    .slide.active .slide-inner > *:nth-child(1) { animation-delay: 0s; }
    .slide.active .slide-inner > *:nth-child(2) { animation-delay: 0.06s; }
    .slide.active .slide-inner > *:nth-child(3) { animation-delay: 0.12s; }
    .slide.active .slide-inner > *:nth-child(4) { animation-delay: 0.18s; }
    .slide.active .slide-inner > *:nth-child(5) { animation-delay: 0.24s; }
    .slide.active .slide-inner > *:nth-child(6) { animation-delay: 0.30s; }

    /* === RESPONSIVE === */
    @media (max-width: 768px) {
      .slide { padding: 32px 24px 48px; }
      h1 { font-size: 32px; }
      h2 { font-size: 24px; }
      .split { grid-template-columns: 1fr; }
      .cards { grid-template-columns: 1fr; }
      .stats { flex-direction: column; }
    }

    /* === TITLE SLIDE SPECIAL === */
    .slide.title-slide {
      background: var(--bg);
    }
    .slide.title-slide h1 {
      font-size: 60px;
      letter-spacing: -2px;
    }
    .title-divider {
      width: 48px; height: 3px;
      background: var(--accent);
      border-radius: 2px;
      margin: 20px 0;
    }
    .title-tags {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 28px;
    }
  </style>
</head>
<body>
  <!-- SLIDES GO HERE -->
  <div class="progress" id="bar"></div>
  <div class="nav-hint">← → space</div>
  <script>
    let cur = 0;
    const slides = document.querySelectorAll('.slide');
    const bar = document.getElementById('bar');
    function go(n) {
      slides[cur].classList.remove('active');
      cur = Math.max(0, Math.min(n, slides.length - 1));
      slides[cur].classList.add('active');
      bar.style.width = ((cur + 1) / slides.length * 100) + '%';
      document.querySelectorAll('.cur').forEach(e => e.textContent = cur + 1);
    }
    document.querySelectorAll('.tot').forEach(e => e.textContent = slides.length);
    go(0);
    document.addEventListener('keydown', e => {
      if (['ArrowRight','Space','Enter'].includes(e.code)) { e.preventDefault(); go(cur + 1); }
      if (['ArrowLeft','Backspace'].includes(e.code)) { e.preventDefault(); go(cur - 1); }
      if (e.code === 'Home') go(0);
      if (e.code === 'End') go(slides.length - 1);
    });
    let tx = 0;
    document.addEventListener('touchstart', e => tx = e.changedTouches[0].screenX);
    document.addEventListener('touchend', e => {
      const d = tx - e.changedTouches[0].screenX;
      if (Math.abs(d) > 50) d > 0 ? go(cur + 1) : go(cur - 1);
    });
  </script>
</body>
</html>
```

## Components to use

**Counter** (every slide, top-right):
```html
<div class="counter"><span class="current cur">1</span> / <span class="tot">1</span></div>
```

**Title slide** (first slide only):
```html
<div class="slide title-slide active">
  <div class="slide-inner">
    <div class="label accent">Meeting recap</div>
    <h1>Title Here</h1>
    <div class="title-divider"></div>
    <p class="sub">One-line key takeaway from the meeting.</p>
    <p class="meta">8 апреля 2026</p>
    <div class="title-tags">
      <span class="tag purple">tag1</span>
      <span class="tag cyan">tag2</span>
    </div>
  </div>
  <div class="counter"><span class="current cur">1</span> / <span class="tot">1</span></div>
</div>
```

**List slide** (bullet points):
```html
<div class="slide">
  <div class="slide-inner">
    <div class="label">Section label</div>
    <h2>Slide title</h2>
    <div class="list">
      <div class="list-item"><div class="dot"></div><div>Item text here</div></div>
      <div class="list-item"><div class="dot cyan"></div><div><strong>Bold part</strong> — rest of item</div></div>
    </div>
  </div>
  <div class="counter">...</div>
</div>
```

**Cards slide** (2–3 cards):
```html
<div class="slide">
  <div class="slide-inner">
    <div class="label">Overview</div>
    <h2>Slide title</h2>
    <div class="cards">
      <div class="card">
        <div class="card-label">Label</div>
        <div class="card-title">Card title</div>
        <div class="card-body">Short description here.</div>
      </div>
    </div>
  </div>
  <div class="counter">...</div>
</div>
```

**Steps slide** (action items, ordered):
```html
<div class="slide">
  <div class="slide-inner">
    <div class="label">Action items</div>
    <h2>Next steps</h2>
    <div class="steps">
      <div class="step">
        <span class="step-num">01</span>
        <div class="step-text">Action description</div>
        <span class="step-sub">owner</span>
      </div>
    </div>
  </div>
  <div class="counter">...</div>
</div>
```

**Stats slide**:
```html
<div class="slide">
  <div class="slide-inner">
    <div class="label">Key numbers</div>
    <h2>Slide title</h2>
    <div class="stats">
      <div class="stat"><div class="stat-num">42</div><div class="stat-label">label</div></div>
      <div class="stat"><div class="stat-num cyan">7</div><div class="stat-label">label</div></div>
    </div>
    <div class="highlight"><p>Key insight or quote from the meeting.</p></div>
  </div>
  <div class="counter">...</div>
</div>
```

**Split slide**:
```html
<div class="slide">
  <div class="slide-inner">
    <div class="label">Compare</div>
    <h2>Slide title</h2>
    <div class="split">
      <div>
        <div class="col-label">Left</div>
        <div class="list">...</div>
      </div>
      <div>
        <div class="col-label">Right</div>
        <div class="list">...</div>
      </div>
    </div>
  </div>
  <div class="counter">...</div>
</div>
```

## Rules
- ALL slides must use dark theme (#09090b background) — absolutely no white or light backgrounds
- 5–8 slides max
- First slide = title slide (class="slide title-slide active")
- Last slide = action items or next steps (use .steps component)
- Mix components — don't use .list for every slide
- Counters: every slide has a `.counter` with `.cur` and `.tot` spans
- Return ONLY the complete HTML. No markdown fences. No commentary.
"""


def render_deck_html(summary: SummaryDocument) -> str:
    """Call Claude to render a full HTML slide deck from the summary."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    model = os.environ.get("INSTANT_PRESENTATION_CLAUDE_MODEL", "claude-sonnet-4-6")

    slide_data = {
        "title": summary.title,
        "date": summary.date,
        "meeting_type": summary.meeting_type,
        "goals": summary.goals,
        "themes": summary.themes,
        "decisions": summary.decisions,
        "action_items": summary.action_items,
        "narrative": summary.narrative,
        "pain_points": getattr(summary, "pain_points", []),
        "slide_plan": None,
    }

    if summary.slide_plan:
        slide_data["slide_plan"] = {
            "slide_titles": summary.slide_plan.slide_titles,
            "slide_goals": summary.slide_plan.slide_goals,
            "section_inputs": summary.slide_plan.section_inputs,
        }

    prompt = f"""Generate a complete single-file HTML presentation using the design system below.

{DESIGN_SPEC}

## Meeting content to present

{json.dumps(slide_data, ensure_ascii=False, indent=2)}

Use slide_plan if provided for slide structure and content.
If no slide_plan, infer 5–7 slides from goals/decisions/action_items/narrative.
Return ONLY the complete HTML document. No markdown fences. No commentary.
"""

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )

    html = response.content[0].text.strip()

    if html.startswith("```"):
        lines = html.split("\n")
        html = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    return html
