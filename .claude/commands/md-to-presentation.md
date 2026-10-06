---
description: Convert a Markdown course/chapter file into a single-file interactive HTML slide deck, following the established Bedrock-deck v2 design system.
argument-hint: <path/to/file.md> [output.html]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# md-to-presentation

Convert the Markdown file at **$1** into a self-contained, interactive HTML presentation
in our house style (v2). If **$2** is given, write there; otherwise write a sibling
`.html` file with the same base name next to the source `.md`.

## Canonical reference (copy its structure, don't reinvent)

The gold-standard output already exists. Study it before writing anything:

@course-02/ch-04-Dynamic-Model-Routing.v2.html

Treat that file as the **template**. The fastest correct path:
1. Copy **verbatim** everything that is not chapter content:
   - the `<head>`
   - **both** `<style>` blocks (base chassis plus the `v2 presentation layer`)
   - the highlight.js `<script defer>`
   - the chrome: topbar with Contents / ⌨ / ⛶ / theme buttons, navbar with `#dots`, `#progress`, `.hint`, `.menu`
   - the help-popover markup (`.pop-head`, `.pop-progress`, `#helpBody`)
   - the `#keys` overlay, the `#lightbox`
   - the entire final `<script>`
2. Replace only the slide `<section>`s inside `<main class="deck">` and the deep-dive
   `<template>`s, generating them from the new Markdown with the markup patterns below.

Do not redesign the CSS or JS. Nearly all polish is applied **at runtime by the script**:
- deep-dive cards
- code bars, syntax highlighting and Copy buttons
- labelled paragraphs, example cards and callouts
- flow diagrams
- popover breadcrumb and Prev/Next between dives

Your job is correct **markup + classes**.

---

## Non-negotiable rules

### R0: Content fidelity (most important)
- **Do not change, summarize, paraphrase, reorder, or drop any content** from the Markdown.
  Every sentence, code block, table cell, number, and example must survive verbatim.
- You may only add **presentation structure**: wrappers, classes, accents, navigation, and
  decorative visuals marked `aria-hidden="true"`. Wording stays exactly as authored.
- Visuals may **re-show** numbers or phrases already in the text (bars, timelines, flow nodes).
  They must never **replace** that text: the original sentence/list always stays on the page.
  Never invent numbers a visual would need. If the data isn't in the Markdown, skip the visual.
- Escape HTML-significant characters faithfully: `&` → `&amp;`, `<`/`>` inside prose → `&lt;`/`&gt;`.
  Keep the arrows/symbols the author used (`->`, `→`, `·`, `≥`) as they are.

### R1: Single file
- One `.html` file. The only external resources:
  - the Google Fonts `<link>` (IBM Plex Sans + JetBrains Mono)
  - `https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js` (`defer`; the deck
    degrades to plain code if it is offline)

  Everything else is inline.
- Images that sit next to the `.md` (e.g. `<chapter>-img-01.png`) may be referenced by relative path.
  Use them in a `figure.fig` (see components). Before using an image, look at it to write accurate alt text.
- Update only: the `<title>`, and the topbar `<b>` brand text and its `<span>` (`· Course · Ch.NN`).

### R2: Container/card model (inherited; keep it)
- `body` → `--bg`; `.deck` card → `--deck-bg` backdrop with a 4px accent top bar.
- `.slide .inner` is the centered 16:9 **content card**: `--surface` plus mesh/glow background and
  `--shadow-lg`. It scrolls if it overflows. Under 900px it drops the 16:9 frame and flows naturally (already in CSS).
- `.help-popover` is confined to the deck bounds (`top/bottom:60px`, `left/right:14px`,
  `max-width:1300px` centered) and never goes full-viewport. Its header row `.pop-head` holds the
  breadcrumb, Prev/Next and the close button. Keep that markup and its ids exactly
  (`popPart`, `popCount`, `popPips`, `popPrev`, `popNext`, `helpClose`, `popProg`, `helpBody`).
- `<pre>` uses the light, theme-adaptive, accent-tinted code palette. Never use a dark terminal theme.

### R3: Per-slide accent color
- Every `<section class="slide">` has a `data-accent` from:
  `orange, teal, purple, green, blue, pink, red, amber`.
- Cover = `orange`. Give each top-level Part its own accent, cycling in palette order. All slides
  of the same Part share its accent. The script propagates the accent to the deck, progress bar,
  dots, brand dot, menu and deep-dive popover.

### R4: Contents index must equal the visible slide title
- `data-title` = the exact visible title. For content slides that is the `<h2>` text. For Part hub slides
  it is the `.num` text, e.g. `Part 02 · Dynamic Routing with Nova Models`.
- Hub/cover slides get `data-section="true"`. The Contents menu nests each hub's deep-dive titles
  automatically. Clicking one opens that dive.

---

## Slide taxonomy: mapping Markdown to slides

1. **Cover**: `<section class="slide divider" id="cover" data-accent="orange" data-section="true">`.
   Copy the reference cover **including the decorative `svg.hero-art`**, and swap only the text:
   ```html
   <div class="inner hero">
     <div class="hero-copy stagger">
       <p class="num">Course NN · Chapter NN</p>
       <h1>Deck title (MD H1)</h1>
       <p class="lead">One-line abstract (verbatim from MD)</p>
       <p class="meta"><kbd>←</kbd> <kbd>→</kbd> or <kbd>Space</kbd> to navigate · Press <kbd>C</kbd> for contents · <kbd>T</kbd> for theme</p>
     </div>
     <svg class="hero-art" …>…</svg>
     <p class="src"><a href="…">source link if the MD has one</a></p>
   </div>
   ```

2. **Part hub slide** (one per top-level Part with sub-sections). It is a two-column layout:
   ```html
   <section class="slide divider" id="<part>" data-accent="teal"
            data-title="Part 02 · <Part title>" data-section="true">
     <div class="inner">
       <div class="part-mark" aria-hidden="true">02</div>
       <div class="part-grid">
         <div class="part-main stagger">
           <p class="num">Part 02 · <Part title></p>
           …overview prose, notes, flow, figure (verbatim)…
         </div>
         <aside class="part-side">
           <p class="side-label" aria-hidden="true"><span>Deep dives</span><span class="cnt"></span></p>
           <p>…the MD sentence that introduces the sub-sections, if any…</p>
           <ul class="help-list">
             <li class="help-list-item"><button class="help-btn" type="button" data-help="<part>-lead"
                 aria-label="Open deep dive: 1. <Sub-section title>">?</button><span>1. <Sub-section title></span></li>
             …
           </ul>
         </aside>
       </div>
     </div>
   </section>
   ```
   - Put the `<span>` title text **exactly as the MD heading** (e.g. keep the leading `1.`). The script
     turns a leading `N.` into the number disc, and gives numberless titles an auto `01/02/…` disc.
   - The first sub-section id is conventionally `<part>-lead`. The script fills `.cnt` and
     replaces the `?` with an arrow icon (the `aria-label` stays).
   - A sentence in the overview that states the Part's key idea (often bold, or "Think of it as:")
     → `<p class="pull">`.

3. **Content slide** (`class="slide"`): for short material with no sub-sections. Use `.kicker` →
   `<h2>` → prose/lists/notes/tables inside `<div class="inner"><div class="stagger">…</div></div>`.

4. **Deep-dive templates**: one per sub-section, placed **after** `</main>`:
   ```html
   <template id="help-<id>">
     <div class="inner"> …full verbatim sub-section: h2, prose, notes, code, tables… </div>
   </template>
   ```
   `data-help` ↔ `help-<id>` must match exactly. Prev/Next inside the popover walks the dives of
   the current hub in list order, so order the `help-list` as the MD orders the sub-sections.

**Guiding heuristic:** overview content goes on the hub slide's left column. Detailed walk-throughs,
long code samples and per-item examples go into `help-*` templates.

---

## Markdown → component mapping

### Base components
| Markdown | HTML in the deck |
|---|---|
| `# Title` (doc) | Cover `<h1>` |
| `## Part / Section` | `.num` on a hub slide, or `<h2>` on a content slide / template |
| `### Subsection` | `<h3>` (gets a diamond marker in the popover) |
| Paragraph | `<p>` |
| `**bold**` / `` `code` `` | `<strong>` / `<code>` |
| ` ```lang … ``` ` | `<pre><code>…</code></pre>` (verbatim whitespace). The script adds a header with the language label and a Copy button, plus highlighting (`json` if it starts with `{`/`[`, else `python`) |
| Bulleted / numbered list | `<ul>` / `<ol>` |
| Table | `<div class="tbl"><table>…</table></div>` |
| Blockquote / "Tip" / "Note" | `.note` or `.note.tip` with `<span class="tag">LABEL</span><p>…</p>` |
| Pull quote / example line | `<p class="quote">` |

### Presentation patterns (use them whenever the MD shape matches)
| MD shape | Markup | Effect |
|---|---|---|
| A flow written as `A -> B -> C` (in a note or its own line) | Add `data-flow` to the `<p>` that holds it, e.g. `<p data-flow>…</p>` or `<p class="quote" data-flow><code>…</code></p>` | The script draws an animated node diagram above it from the exact words (bold parts are highlighted) and turns the sentence into a caption |
| "Static vs Dynamic" / "Before vs After" pair of notes | `<div class="versus"><div class="note vs-static">…</div><span class="vs-badge" aria-hidden="true">VS</span><div class="note tip vs-dynamic">…</div></div>` | Side-by-side comparison |
| Short numbered list of named options (`**Name:** description`) on a slide | `<ol class="tiles">` | Numbered tiles |
| Ordered workflow / steps list | `<ol class="steps">` | Vertical timeline |
| Steps written as paragraphs (`**1. Step:** …`, `**2. …**`), optionally with a nested `<ul>` | Wrap them in `<div class="steps-p">…</div>` | Timeline with dots |
| A set of parallel parameters (`**a) …**`, `**b) …**`) | Wrap them in `<div class="param-grid">…</div>` | 2×2 card grid |
| A table of tiers/models (one row per tier) | `<div class="tbl tier-table">` | Colored tier rail per row (rows 2–5) |
| An image that ships with the chapter | `<figure class="fig"><button class="fig-btn" type="button" data-zoom aria-label="Enlarge diagram"><img src="…" alt="…" loading="lazy"><span class="zoom" aria-hidden="true">⤢</span></button></figure>` | Framed thumbnail with a click-to-zoom lightbox |

Automatic enhancements need no markup. They key off the MD text, so keep the author's labels:
- `<p><strong>The Problem:</strong>…` → amber panel. `Static Routing Fails:`, `With Static Routing:` and `Static Approach:` → red panel. `Dynamic Routing Solution:` and `Dynamic Approach…` → green panel. `Result:` and `Total =` → accent panel.
- A paragraph that is **only** a bold label ending in `:` (e.g. `**Technical Example:**`) → an eyebrow heading.
- A `.note` whose tag contains "Technical Example" → an example card. A `p.quote` containing "Router Analysis" → a callout.

### Data visuals (only when the MD already contains the numbers)
Insert them **next to** the list/paragraph they illustrate, always with `aria-hidden="true"`. Copy the
markup shape from the reference deck.
- **Split / mix bar**: percentages or counts that add up to a whole (see `help-ipr-specialization`, `help-adv-cost`):
  `<div class="viz" aria-hidden="true"><div class="split"><span class="seg" style="--w:70%;--c:var(--c-teal)"><b>70%</b> Name</span>…</div><div class="legend"><span style="--c:…">Name · $56</span>…</div></div>`
- **Before/after bars**: two totals, e.g. a cost comparison (`help-adv-cost`):
  `<div class="viz-row"><span class="viz-lbl">Static</span><div class="bar full" style="--w:100%"><i style="--c:var(--c-red)"></i><b>$3,000</b></div></div>`.
  The width is proportional to the value. Add `<span class="delta">↓ ~86%</span>` only if the MD states the %.
- **Range timeline**: latency/SLO bands per option (`help-nova-latency`):
  `.lat-row` > `.lat-name` + `.lat-track` > `<i style="--l:0%;--w:10%;--c:…">` (add `class="open"` for "N+"), plus a `.lat-axis`.

Use only palette tokens (`var(--c-*)`) for `--c`. Never use raw hex values.

---

## Behaviours provided by the template script (keep them working; no JS edits)
- Slides: ←/→/Space/PageUp/PageDown/Home/End, swipe, dots, hash deep-links (`#slide-id`), progress bar.
- Keys: **C** Contents (with nested deep dives), **T** theme (persisted), **F** fullscreen,
  **?** shortcuts panel, **Enter** opens the first deep dive of the slide.
- Deep dive: breadcrumb + "Deep dive N of M" + pips, reading progress, Prev/Next and ←/→ between
  dives, Esc to close, focus trap, focus returned to the card.
- Lightbox for `[data-zoom]` figures. Build-in animations (`.stagger` children, cards, flows, bars).
  All motion is disabled under `prefers-reduced-motion`.

The script selects `.slide`, `.help-btn[data-help]`, `[data-flow]`, `.stagger`, `[data-zoom]` and
reads `data-title` / `data-accent`. Correct markup is all it needs.

---

## Procedure

1. Read the source `.md` (**$1**) and the reference deck in full. List images that sit next to the `.md`.
2. Plan the slide list: the cover, then one hub (or content) slide per Part. Make an inventory of
   sub-sections → `help-*` ids, assign an accent per Part (R3), and pick the presentation patterns and
   data visuals that the MD shape supports.
3. Copy the reference deck's non-content parts verbatim. Generate the `<section>`s and `<template>`s.
4. Set every `data-accent`, `data-title` (= visible title), `data-section` and matching `data-help`/ids.
5. Verify before finishing:
   - **Fidelity (required):**
     `python3 -I .claude/scripts/deck_fidelity.py $1 <output.html>` must report `missing: 0`.
     Review the `EXTRA` words. They should only be hub-card titles (which repeat the deep-dive `h2`),
     `Part NN`, the cover hint, and other structural labels. Anything else means you added content: remove it.
   - `data-help` count == `help-*` template count, and every id resolves
     (`grep -o 'data-help="[^"]*"'` vs `grep -o 'id="help-[^"]*"'`).
   - Every `.slide` has a `data-accent`, and every `data-title` equals its on-slide title.
   - **Visual check:** screenshot with headless Chrome (works without the extension):
     `google-chrome --headless=new --disable-gpu --hide-scrollbars --window-size=1440,900 --virtual-time-budget=3000 --screenshot=<out>.png file://<abs path>#<slide-id>`
     Do this at least for the cover and one hub slide, plus one at `--window-size=390,844`. To capture a
     deep dive or a settled state, make a scratchpad copy that injects
     `<style>*{animation-duration:0s!important;animation-delay:0s!important}</style>` and a
     `load` handler that clicks `[data-help=<id>]`. Read the PNGs and fix overlaps or clipping.
6. Report the output path, the slide/deep-dive count, which patterns and visuals were used, and the fidelity result.

## Guardrails
- Never invent content to "fill" a slide. If the Markdown is thin, the slide is thin.
- Never alter the design-system tokens, CSS or JS unless the user explicitly asks. If the Markdown
  implies a component we don't have, prefer the closest existing pattern above over new CSS.
- Decorative or visual-only elements must be `aria-hidden="true"`, so screen readers and the
  fidelity check see only the author's text.
