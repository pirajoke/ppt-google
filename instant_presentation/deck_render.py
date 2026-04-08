"""Generate a full HTML slide deck from a SummaryDocument using Claude.

Produces a single-file HTML presentation with:
- Editorial style (light, serif, book-like)
- Keyboard navigation (arrows / space / swipe)
- Progress bar, slide counter
- Cards, stats, quotes, layers components
"""

from __future__ import annotations

import json
import os

from .models import SummaryDocument

DESIGN_SPEC = """
## CSS Variables (Editorial style)
```css
:root {
  --bg: #faf9f6;
  --bg-light: #f0eeeb;
  --bg-card: #ffffff;
  --text: #1a1a1a;
  --text-dim: #6b6b6b;
  --accent: #c45a3c;
  --accent2: #2d5f8a;
  --accent3: #5a8a5c;
  --border: #e0ddd8;
  --font-heading: 'Playfair Display','Georgia',serif;
  --font-body: 'Inter','Helvetica Neue','Arial',sans-serif;
}
```

## Google Fonts
```html
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
```

## Base layout
```css
html, body { width:100%; height:100%; background:var(--bg); color:var(--text); font-family:var(--font-body); overflow:hidden; -webkit-font-smoothing:antialiased; }
.slide { display:none; flex-direction:column; justify-content:center; align-items:center; width:100vw; height:100vh; padding:56px 80px 80px; position:relative; }
.slide.active { display:flex; }
.slide-inner { width:100%; max-width:1100px; flex:1; display:flex; flex-direction:column; justify-content:center; }
.slide-counter { position:absolute; top:24px; right:32px; font-size:12px; color:var(--text-dim); opacity:0.6; }
h1 { font-family:var(--font-heading); font-size:44px; font-weight:700; color:var(--text); margin-bottom:16px; line-height:1.2; }
h2 { font-family:var(--font-heading); font-size:30px; font-weight:600; color:var(--text); margin-bottom:20px; line-height:1.3; }
h3 { font-family:var(--font-body); font-size:14px; font-weight:500; color:var(--text-dim); text-transform:uppercase; letter-spacing:2px; margin-bottom:12px; }
p, li { font-family:var(--font-body); font-size:18px; line-height:1.7; color:var(--text); }
ul { padding-left:20px; }
li { margin-bottom:6px; }
```

## Animations
```css
@keyframes slideIn { from { opacity:0; transform:translateX(-20px); } to { opacity:1; transform:translateX(0); } }
.slide.active .slide-inner > * { animation:slideIn 0.5s ease-out both; }
.slide.active .slide-inner > *:nth-child(2) { animation-delay:0.08s; }
.slide.active .slide-inner > *:nth-child(3) { animation-delay:0.16s; }
.slide.active .slide-inner > *:nth-child(4) { animation-delay:0.24s; }
.slide.active .slide-inner > *:nth-child(5) { animation-delay:0.32s; }
```

## Components

Cards grid:
```html
<div class="cards">
  <div class="card"><h3>Label</h3><p>Content</p></div>
</div>
```
```css
.cards { display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:16px; margin-top:16px; }
.card { background:var(--bg-card); border:1px solid var(--border); border-radius:8px; padding:20px; box-shadow:0 2px 12px rgba(0,0,0,0.06); transition:box-shadow 0.3s; }
.card:hover { box-shadow:0 4px 20px rgba(0,0,0,0.1); }
```

Stat row:
```html
<div class="stat-row">
  <div class="stat"><div class="num">86%</div><div class="lbl">label</div></div>
</div>
```
```css
.stat-row { display:flex; gap:16px; margin-top:16px; flex-wrap:wrap; }
.stat { background:var(--bg-card); border:1px solid var(--border); border-radius:8px; padding:14px 18px; flex:1; min-width:130px; text-align:center; }
.stat .num { font-size:28px; font-weight:700; font-family:var(--font-heading); color:var(--accent); }
.stat .lbl { font-size:11px; color:var(--text-dim); margin-top:4px; }
```

Layers (steps):
```html
<div class="layers">
  <div class="layer l1"><div class="ln">01</div><div class="lt">Title</div><div class="ld">Description</div></div>
</div>
```
```css
.layers { display:flex; flex-direction:column; gap:8px; margin-top:18px; }
.layer { display:flex; align-items:center; gap:14px; padding:14px 20px; border-radius:8px; border:1px solid var(--border); }
.layer.l1 { border-color:rgba(196,90,60,0.4); background:rgba(196,90,60,0.04); }
.layer.l2 { border-color:rgba(45,95,138,0.4); background:rgba(45,95,138,0.04); }
.layer.l3 { border-color:rgba(90,138,92,0.4); background:rgba(90,138,92,0.04); }
.ln { font-size:20px; font-weight:700; min-width:36px; color:var(--text-dim); }
.lt { font-size:17px; font-weight:600; min-width:160px; color:var(--text); }
.ld { font-size:14px; color:var(--text-dim); }
```

Quote:
```html
<div class="quote"><p>Quote text here.</p><div class="author">— Source</div></div>
```
```css
.quote { border-left:3px solid var(--accent); padding:16px 24px; margin:16px 0; }
.quote p { font-family:var(--font-heading); font-style:italic; font-size:20px; line-height:1.6; }
.quote .author { font-size:12px; color:var(--text-dim); margin-top:6px; }
```

Split columns:
```html
<div class="split"><div>Left</div><div>Right</div></div>
```
```css
.split { display:grid; grid-template-columns:1fr 1fr; gap:28px; margin-top:14px; }
```

## Navigation JS
```javascript
let current = 0;
const slides = document.querySelectorAll('.slide');
const bar = document.querySelector('.progress-bar');
function showSlide(n) {
  slides[current].classList.remove('active');
  current = Math.max(0, Math.min(n, slides.length - 1));
  slides[current].classList.add('active');
  if (bar) bar.style.width = ((current + 1) / slides.length * 100) + '%';
  document.querySelectorAll('.current').forEach(el => el.textContent = current + 1);
}
document.querySelectorAll('.total').forEach(el => el.textContent = slides.length);
slides[0].classList.add('active');
if (bar) bar.style.width = (1 / slides.length * 100) + '%';
document.addEventListener('keydown', e => {
  if (['ArrowRight','Space','Enter'].includes(e.code)) { e.preventDefault(); showSlide(current + 1); }
  if (['ArrowLeft','Backspace'].includes(e.code)) { e.preventDefault(); showSlide(current - 1); }
  if (e.code === 'Home') { e.preventDefault(); showSlide(0); }
  if (e.code === 'End') { e.preventDefault(); showSlide(slides.length - 1); }
});
let tx = 0;
document.addEventListener('touchstart', e => { tx = e.changedTouches[0].screenX; });
document.addEventListener('touchend', e => {
  const d = tx - e.changedTouches[0].screenX;
  if (Math.abs(d) > 50) d > 0 ? showSlide(current + 1) : showSlide(current - 1);
});
```

## Progress bar CSS
```css
.progress-bar { position:fixed; bottom:0; left:0; height:2px; background:var(--accent); transition:width 0.3s; z-index:100; }
.nav-hint { position:fixed; bottom:16px; right:32px; font-size:11px; color:var(--text-dim); opacity:0.4; }
```

## Responsive
```css
@media (max-width: 768px) {
  .slide { padding:32px 24px 48px; }
  h1 { font-size:28px; }
  h2 { font-size:22px; }
  p, li { font-size:15px; }
  .split { grid-template-columns:1fr; }
  .cards { grid-template-columns:1fr; }
  .nav-hint { display:none; }
}
```

## Rules
- Single-file HTML, all CSS/JS inline
- 5–8 slides based on content density
- No emojis — use colored text via inline style or color vars
- First slide = title + key takeaway. Last slide = action items / next steps.
- Each slide: one clear idea
- Use components (cards, layers, stats, quote) to vary visual rhythm
- Slide counter format: `<span class="current">1</span> / <span class="total">1</span>`
"""


def render_deck_html(summary: SummaryDocument) -> str:
    """Call Claude to render a full HTML slide deck from the summary."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    model = os.environ.get("INSTANT_PRESENTATION_CLAUDE_MODEL", "claude-sonnet-4-6")

    # Build content payload for Claude
    slide_data = {
        "title": summary.title,
        "date": summary.date,
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

    prompt = f"""You are a presentation designer. Generate a complete single-file HTML slide deck.

## Design System

{DESIGN_SPEC}

## Meeting Summary Data

{json.dumps(slide_data, ensure_ascii=False, indent=2)}

## Instructions

1. Use the slide_plan if provided — it defines the exact slides and their content.
2. Each slide must have a `.slide-counter` with `<span class="current"></span> / <span class="total"></span>`.
3. Use appropriate components for each slide type:
   - Overview / context → cards or layers
   - Decisions / key points → bullet list or split
   - Action items → layers (numbered steps)
   - Stats or metrics → stat-row
   - Key quote → quote component
4. Title slide: large h1, subtitle (date, meeting type), and a short h3 tagline.
5. All CSS and JS must be inline in the single HTML file.
6. Return ONLY the complete HTML document. No markdown fences. No commentary.
"""

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )

    html = response.content[0].text.strip()

    # Strip markdown fences if Claude wrapped the output
    if html.startswith("```"):
        lines = html.split("\n")
        html = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    return html
