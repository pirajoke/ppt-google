"""Generate a full HTML slide deck from a SummaryDocument using Claude."""

from __future__ import annotations

import json
import os

from .models import SummaryDocument

DESIGN_SPEC = """
You are generating a NEON TERMINAL HTML presentation. Aesthetic: hacker/cyber, monospace, very dark, neon accent lines. Think: terminal meets Cyberpunk meets meeting notes.

## Visual Direction
- Background: #050505 (near-black)
- Surface cards: #0d0d0d with 1px border #1a1a1a
- Active borders: 1px solid #00ff9d (neon green) or #ff0066 (neon pink)
- Primary text: #e0e0e0
- Dim text: #555
- Label/tag text: #00ff9d or #ff0066
- Font: JetBrains Mono everywhere (monospace). Load from Google Fonts.
- NO serifs. NO Inter. Only monospace.
- Numbers/counters: large, neon colored
- Progress bar: thin (1px), neon green #00ff9d

## HTML Shell

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{{TITLE}}</title>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700;800&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #050505;
      --bg2: #0d0d0d;
      --bg3: #111;
      --border: #1a1a1a;
      --border-lit: #2a2a2a;
      --text: #e0e0e0;
      --dim: #555;
      --dim2: #333;
      --green: #00ff9d;
      --pink: #ff0066;
      --cyan: #00e5ff;
      --amber: #ffcc00;
      --font: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    }
    html, body {
      width: 100%; height: 100%;
      background: var(--bg);
      color: var(--text);
      font-family: var(--font);
      -webkit-font-smoothing: antialiased;
      overflow: hidden;
    }

    /* === SLIDES === */
    .slide {
      display: none;
      width: 100vw; height: 100vh;
      padding: 56px 72px 72px;
      flex-direction: column;
      justify-content: center;
      position: relative;
    }
    .slide.active { display: flex; }
    .slide-inner { width: 100%; max-width: 1100px; }

    /* corner decorations */
    .slide::before {
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      background:
        linear-gradient(90deg, var(--green) 1px, transparent 1px),
        linear-gradient(180deg, var(--green) 1px, transparent 1px);
      background-size: 100% 100%;
      background-position: 0 0;
      opacity: 0.03;
      pointer-events: none;
    }

    /* === HEADER CHROME === */
    .chrome {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 28px;
    }
    .chrome-prompt {
      font-size: 11px;
      color: var(--green);
      font-weight: 700;
      letter-spacing: 1px;
    }
    .chrome-path {
      font-size: 11px;
      color: var(--dim);
    }
    .chrome-sep { color: var(--dim2); font-size: 11px; }
    .chrome-status {
      margin-left: auto;
      font-size: 11px;
      color: var(--dim);
    }
    .chrome-line {
      width: 100%;
      height: 1px;
      background: var(--border-lit);
      margin-bottom: 24px;
      position: relative;
    }
    .chrome-line::after {
      content: '';
      position: absolute;
      left: 0; top: 0;
      height: 1px;
      width: 30%;
      background: linear-gradient(90deg, var(--green), transparent);
    }

    /* === TYPOGRAPHY === */
    h1 {
      font-size: 52px;
      font-weight: 800;
      line-height: 1.05;
      letter-spacing: -2px;
      color: var(--text);
      margin-bottom: 16px;
    }
    h2 {
      font-size: 32px;
      font-weight: 700;
      letter-spacing: -1px;
      color: var(--text);
      margin-bottom: 20px;
      line-height: 1.2;
    }
    .sub {
      font-size: 16px;
      color: var(--dim);
      line-height: 1.7;
      max-width: 680px;
      margin-bottom: 28px;
      font-weight: 300;
    }
    .meta { font-size: 11px; color: var(--dim); }

    /* === TAGS === */
    .tags { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 20px; }
    .tag {
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      padding: 4px 10px;
      border-radius: 2px;
    }
    .tag.green { border: 1px solid var(--green); color: var(--green); background: rgba(0,255,157,0.06); }
    .tag.pink { border: 1px solid var(--pink); color: var(--pink); background: rgba(255,0,102,0.06); }
    .tag.cyan { border: 1px solid var(--cyan); color: var(--cyan); background: rgba(0,229,255,0.06); }
    .tag.amber { border: 1px solid var(--amber); color: var(--amber); background: rgba(255,204,0,0.06); }

    /* === BLOCK (card) === */
    .block {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 18px 20px;
      margin-bottom: 8px;
      transition: border-color 0.15s;
    }
    .block:hover { border-color: var(--border-lit); }
    .block.green { border-left: 2px solid var(--green); }
    .block.pink { border-left: 2px solid var(--pink); }
    .block.cyan { border-left: 2px solid var(--cyan); }
    .block.amber { border-left: 2px solid var(--amber); }
    .block-label {
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 2px;
      text-transform: uppercase;
      margin-bottom: 6px;
    }
    .block-label.green { color: var(--green); }
    .block-label.pink { color: var(--pink); }
    .block-label.cyan { color: var(--cyan); }
    .block-label.amber { color: var(--amber); }
    .block-title { font-size: 15px; font-weight: 600; color: var(--text); margin-bottom: 4px; }
    .block-body { font-size: 13px; color: var(--dim); line-height: 1.6; }

    /* === GRID (2 or 3 col blocks) === */
    .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }

    /* === LINES (bullet list) === */
    .lines { display: flex; flex-direction: column; gap: 6px; }
    .line {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 12px 16px;
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 3px;
      font-size: 14px;
      color: var(--dim);
      line-height: 1.5;
    }
    .line:hover { border-color: var(--border-lit); color: var(--text); }
    .line .bullet { color: var(--green); flex-shrink: 0; font-size: 10px; margin-top: 3px; }
    .line .bullet.pink { color: var(--pink); }
    .line .bullet.cyan { color: var(--cyan); }
    .line strong { color: var(--text); font-weight: 600; }

    /* === STEPS (numbered) === */
    .steps { display: flex; flex-direction: column; gap: 6px; }
    .step {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 14px 18px;
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 3px;
    }
    .step:hover { border-color: var(--green); }
    .step-n {
      font-size: 11px;
      font-weight: 800;
      color: var(--green);
      min-width: 28px;
      letter-spacing: 0.5px;
    }
    .step-text { font-size: 14px; color: var(--text); font-weight: 500; flex: 1; }
    .step-who { font-size: 11px; color: var(--dim); }

    /* === STAT ROW === */
    .stats { display: flex; gap: 8px; margin-bottom: 16px; }
    .stat {
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 16px 20px;
      flex: 1;
      text-align: center;
    }
    .stat-n {
      font-size: 44px;
      font-weight: 800;
      letter-spacing: -2px;
      line-height: 1;
      margin-bottom: 6px;
    }
    .stat-n.green { color: var(--green); }
    .stat-n.pink { color: var(--pink); }
    .stat-n.cyan { color: var(--cyan); }
    .stat-n.amber { color: var(--amber); }
    .stat-l { font-size: 11px; color: var(--dim); }

    /* === HIGHLIGHT === */
    .hl {
      border: 1px solid var(--border-lit);
      border-left: 2px solid var(--green);
      background: rgba(0,255,157,0.03);
      border-radius: 3px;
      padding: 16px 20px;
      margin-top: 12px;
      font-size: 15px;
      color: var(--text);
      line-height: 1.65;
      font-weight: 300;
    }

    /* === SPLIT === */
    .split { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .col-head { font-size: 10px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: var(--green); margin-bottom: 10px; }
    .col-head.pink { color: var(--pink); }

    /* === COUNTER === */
    .counter {
      position: absolute;
      top: 24px; right: 40px;
      font-size: 11px;
      color: var(--dim);
      font-weight: 500;
    }
    .counter .cur { color: var(--text); }

    /* === PROGRESS === */
    .prog {
      position: fixed;
      bottom: 0; left: 0;
      height: 1px;
      background: var(--green);
      box-shadow: 0 0 6px var(--green);
      transition: width 0.2s ease;
      z-index: 100;
    }

    /* === NAV HINT === */
    .hint {
      position: fixed;
      bottom: 18px; right: 40px;
      font-size: 10px;
      color: var(--dim2);
    }

    /* === ANIMATIONS === */
    @keyframes fadeUp {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .slide.active .chrome,
    .slide.active .chrome-line,
    .slide.active .slide-inner > * {
      animation: fadeUp 0.3s ease-out both;
    }
    .slide.active .slide-inner > *:nth-child(1) { animation-delay: 0.05s; }
    .slide.active .slide-inner > *:nth-child(2) { animation-delay: 0.10s; }
    .slide.active .slide-inner > *:nth-child(3) { animation-delay: 0.15s; }
    .slide.active .slide-inner > *:nth-child(4) { animation-delay: 0.20s; }
    .slide.active .slide-inner > *:nth-child(5) { animation-delay: 0.25s; }

    @media (max-width: 768px) {
      .slide { padding: 32px 24px 48px; }
      h1 { font-size: 30px; }
      h2 { font-size: 22px; }
      .grid2, .grid3, .split { grid-template-columns: 1fr; }
      .stats { flex-direction: column; }
    }
  </style>
</head>
<body>
  <!-- SLIDES HERE -->
  <div class="prog" id="bar"></div>
  <div class="hint">← → space</div>
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
      if (['ArrowRight','Space','Enter'].includes(e.code)) { e.preventDefault(); go(cur+1); }
      if (['ArrowLeft','Backspace'].includes(e.code)) { e.preventDefault(); go(cur-1); }
      if (e.code==='Home') go(0);
      if (e.code==='End') go(slides.length-1);
    });
    let tx=0;
    document.addEventListener('touchstart', e => tx=e.changedTouches[0].screenX);
    document.addEventListener('touchend', e => {
      const d=tx-e.changedTouches[0].screenX;
      if(Math.abs(d)>50) d>0?go(cur+1):go(cur-1);
    });
  </script>
</body>
</html>
```

## SLIDE TEMPLATES — use ALL of them, mix colors per slide

---

### TEMPLATE 1: TITLE SLIDE (always first, class="slide active")
Rich dashboard layout. Show stats, themes, participants. DENSE — no empty space.

```html
<div class="slide active">
  <div class="chrome">
    <span class="chrome-prompt">></span>
    <span class="chrome-path">meeting_recap.md</span>
    <span class="chrome-sep">/</span>
    <span class="chrome-path" style="color:#333">overview</span>
    <span class="chrome-status">1 / 7</span>
  </div>
  <div class="chrome-line"></div>
  <div class="slide-inner">
    <!-- top: title + subtitle -->
    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:32px;margin-bottom:20px">
      <div style="flex:1">
        <h1 style="margin-bottom:8px">Meeting Title Here</h1>
        <p class="sub" style="margin-bottom:0">One sharp sentence — the single most important takeaway from this meeting.</p>
      </div>
      <!-- right: big stat -->
      <div style="text-align:right;flex-shrink:0">
        <div style="font-size:52px;font-weight:800;color:var(--green);letter-spacing:-2px;line-height:1">7</div>
        <div style="font-size:10px;color:var(--dim);letter-spacing:2px;text-transform:uppercase">slides</div>
      </div>
    </div>

    <!-- middle: 3 stat boxes -->
    <div class="stats" style="margin-bottom:16px">
      <div class="stat"><div class="stat-n green">3</div><div class="stat-l">decisions</div></div>
      <div class="stat"><div class="stat-n pink">4</div><div class="stat-l">action items</div></div>
      <div class="stat"><div class="stat-n cyan">2</div><div class="stat-l">open questions</div></div>
      <div class="stat"><div class="stat-n amber">5</div><div class="stat-l">themes</div></div>
    </div>

    <!-- bottom: tags + meta -->
    <div style="display:flex;align-items:center;justify-content:space-between">
      <div class="tags">
        <span class="tag green">theme1</span>
        <span class="tag pink">theme2</span>
        <span class="tag cyan">theme3</span>
        <span class="tag amber">theme4</span>
      </div>
      <span class="meta">8 апреля 2026 · meet</span>
    </div>
  </div>
  <div class="counter"><span class="cur">1</span> / <span class="tot">1</span></div>
</div>
```

---

### TEMPLATE 2: BIG QUOTE / INSIGHT (use for 1 key insight or decision)
Full-bleed text. One idea. Huge font. Use green accent.

```html
<div class="slide">
  <div class="chrome">
    <span class="chrome-prompt" style="color:var(--green)">></span>
    <span class="chrome-path">key_insight.md</span>
    <span class="chrome-status">2 / 7</span>
  </div>
  <div class="chrome-line" style="--glow:var(--green)"></div>
  <div class="slide-inner">
    <div style="font-size:11px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:var(--green);margin-bottom:24px">// KEY INSIGHT</div>
    <div style="font-size:36px;font-weight:700;line-height:1.25;color:var(--text);letter-spacing:-0.5px;max-width:900px;margin-bottom:24px">
      "The exact insight or decision stated boldly here — make it punchy and direct."
    </div>
    <div style="display:flex;gap:12px;align-items:center">
      <div style="width:32px;height:1px;background:var(--green)"></div>
      <span style="font-size:12px;color:var(--dim)">Source or context label</span>
    </div>
  </div>
  <div class="counter"><span class="cur">2</span> / <span class="tot">1</span></div>
</div>
```

---

### TEMPLATE 3: GRID CARDS (context, themes, options — use pink/cyan accents)
2 or 3 cards. Each card = one idea. Use pink this time for variety.

```html
<div class="slide">
  <div class="chrome">
    <span class="chrome-prompt" style="color:var(--pink)">></span>
    <span class="chrome-path">context.md</span>
    <span class="chrome-status">3 / 7</span>
  </div>
  <div class="chrome-line" style="background: linear-gradient(90deg, var(--pink), transparent)"></div>
  <div class="slide-inner">
    <h2>Slide Title</h2>
    <div class="grid3">
      <div class="block pink">
        <div class="block-label pink">// LABEL 01</div>
        <div class="block-title">Card Title</div>
        <div class="block-body">2–3 sentence description of this point. Specific and grounded.</div>
      </div>
      <div class="block cyan">
        <div class="block-label cyan">// LABEL 02</div>
        <div class="block-title">Card Title</div>
        <div class="block-body">2–3 sentence description of this point.</div>
      </div>
      <div class="block amber">
        <div class="block-label amber">// LABEL 03</div>
        <div class="block-title">Card Title</div>
        <div class="block-body">2–3 sentence description.</div>
      </div>
    </div>
  </div>
  <div class="counter"><span class="cur">3</span> / <span class="tot">1</span></div>
</div>
```

---

### TEMPLATE 4: SPLIT — left list + right highlight (use cyan accent)
Left = bullet lines. Right = big number + insight block.

```html
<div class="slide">
  <div class="chrome">
    <span class="chrome-prompt" style="color:var(--cyan)">></span>
    <span class="chrome-path">decisions.md</span>
    <span class="chrome-status">4 / 7</span>
  </div>
  <div class="chrome-line" style="background:linear-gradient(90deg,var(--cyan),transparent)"></div>
  <div class="slide-inner">
    <h2>Slide Title</h2>
    <div class="split">
      <div>
        <div class="col-head" style="color:var(--cyan)">// DECISIONS</div>
        <div class="lines">
          <div class="line"><span class="bullet" style="color:var(--cyan)">■</span><div><strong>Decision 1</strong> — brief rationale</div></div>
          <div class="line"><span class="bullet" style="color:var(--cyan)">■</span><div><strong>Decision 2</strong> — brief rationale</div></div>
          <div class="line"><span class="bullet" style="color:var(--cyan)">■</span><div><strong>Decision 3</strong> — brief rationale</div></div>
        </div>
      </div>
      <div>
        <div class="col-head pink">// IMPACT</div>
        <div style="font-size:64px;font-weight:800;color:var(--cyan);letter-spacing:-3px;line-height:1;margin-bottom:12px">3</div>
        <div style="font-size:12px;color:var(--dim);margin-bottom:16px">confirmed decisions</div>
        <div class="hl" style="border-left-color:var(--cyan);background:rgba(0,229,255,0.03)">
          One-line synthesis of what these decisions mean together.
        </div>
      </div>
    </div>
  </div>
  <div class="counter"><span class="cur">4</span> / <span class="tot">1</span></div>
</div>
```

---

### TEMPLATE 5: FULL-WIDTH BULLETS (blockers, risks, open questions — use amber)
Dense list. Left-aligned label. Use amber for warning/risk feel.

```html
<div class="slide">
  <div class="chrome">
    <span class="chrome-prompt" style="color:var(--amber)">></span>
    <span class="chrome-path">blockers.md</span>
    <span class="chrome-status">5 / 7</span>
  </div>
  <div class="chrome-line" style="background:linear-gradient(90deg,var(--amber),transparent)"></div>
  <div class="slide-inner">
    <div style="display:flex;align-items:baseline;gap:16px;margin-bottom:20px">
      <h2 style="margin:0">Blockers & Risks</h2>
      <span style="font-size:11px;color:var(--amber);font-weight:700;letter-spacing:2px">// WARNING</span>
    </div>
    <div class="lines">
      <div class="line" style="border-left:2px solid var(--amber)"><span class="bullet" style="color:var(--amber)">▲</span><div><strong>Risk title</strong> — what could go wrong and why it matters</div></div>
      <div class="line" style="border-left:2px solid var(--amber)"><span class="bullet" style="color:var(--amber)">▲</span><div><strong>Risk title</strong> — explanation</div></div>
      <div class="line" style="border-left:1px solid var(--border-lit)"><span class="bullet" style="color:var(--dim)">◇</span><div>Open question — not yet resolved</div></div>
      <div class="line" style="border-left:1px solid var(--border-lit)"><span class="bullet" style="color:var(--dim)">◇</span><div>Open question — needs follow-up</div></div>
    </div>
  </div>
  <div class="counter"><span class="cur">5</span> / <span class="tot">1</span></div>
</div>
```

---

### TEMPLATE 6: STEPS — ACTION ITEMS (always last slide, green accent)
Numbered steps. Owner on the right. Clean and clear.

```html
<div class="slide">
  <div class="chrome">
    <span class="chrome-prompt" style="color:var(--green)">></span>
    <span class="chrome-path">action_items.md</span>
    <span class="chrome-status">6 / 7</span>
  </div>
  <div class="chrome-line"></div>
  <div class="slide-inner">
    <div style="display:flex;align-items:baseline;gap:16px;margin-bottom:20px">
      <h2 style="margin:0">Next Steps</h2>
      <span style="font-size:11px;color:var(--green);font-weight:700;letter-spacing:2px">// ACTION REQUIRED</span>
    </div>
    <div class="steps">
      <div class="step"><span class="step-n">01</span><div class="step-text">Action description — specific and clear</div><span class="step-who">owner</span></div>
      <div class="step"><span class="step-n">02</span><div class="step-text">Another action item</div><span class="step-who">owner</span></div>
      <div class="step"><span class="step-n">03</span><div class="step-text">Third action</div><span class="step-who">owner</span></div>
    </div>
    <!-- deadline or next meeting -->
    <div style="margin-top:16px;padding:12px 16px;border:1px solid var(--border-lit);border-radius:3px;display:flex;justify-content:space-between;align-items:center">
      <span style="font-size:12px;color:var(--dim)">// NEXT CHECKPOINT</span>
      <span style="font-size:13px;color:var(--green);font-weight:600">date or deadline here</span>
    </div>
  </div>
  <div class="counter"><span class="cur">6</span> / <span class="tot">1</span></div>
</div>
```

---

## RULES
- ALWAYS use Template 1 for the first slide — it MUST have stats, tags, meta
- Use a DIFFERENT template and a DIFFERENT accent color for every slide
- Rotate colors: green → pink → cyan → amber → pink → green (never same color twice in a row)
- Template 2 (big quote) is great for 1 key decision or insight
- Template 6 (steps) is always the LAST slide
- 6–8 slides total
- Every slide: `.counter` with `.cur`/`.tot`, `.chrome` + `.chrome-line`
- Chrome path = snake_case slug of the section topic
- Return ONLY complete HTML. No markdown fences. No commentary.
"""


def render_deck_html(summary: SummaryDocument) -> str:
    """Call Claude to render a Neon Terminal HTML slide deck from the summary."""
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

    prompt = f"""Generate a complete single-file HTML presentation using the NEON TERMINAL design system.

{DESIGN_SPEC}

## Meeting content

{json.dumps(slide_data, ensure_ascii=False, indent=2)}

Use slide_plan if provided. If not, build 5–7 slides from the content above.
Return ONLY the complete HTML. No markdown fences. No commentary.
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
