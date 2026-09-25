---
description: Convert a Markdown course/chapter file into a single-file interactive HTML slide deck, following the established Bedrock-deck design system.
argument-hint: <path/to/file.md> [output.html]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# md-to-presentation

Convert the Markdown file at **$1** into a self-contained, interactive HTML presentation
that matches our house style. If **$2** is given, write there; otherwise write a sibling
`.html` file with the same base name next to the source `.md`.

## Canonical reference (copy its structure, don't reinvent)

The gold-standard output already exists — study it before writing anything:

@course-01/ch-02-Fundamentals-of-Amazon-Bedrock-PoC-design.html

Treat that file as the **template**. The fastest correct path is: copy its `<head>`,
`<style>`, chrome (topbar / navbar / menu / progress / hint), help-popover markup, and the
entire `<script>` **verbatim**, then replace only the slide `<section>`s and the deep-dive
`<template>`s with content generated from the new Markdown. Do not redesign the CSS or JS.

---

## Non-negotiable rules

### R0 — Content fidelity (most important)
- **Do not change, summarize, paraphrase, reorder, or drop any content** from the Markdown.
  Every sentence, code block, table cell, number, and example must survive verbatim.
- You may only add **presentation structure** (section wrappers, headings tags, accents,
  navigation). Wording stays exactly as authored.
- Escape HTML-significant characters faithfully: `&` → `&amp;`, `<`/`>` inside prose → `&lt;`/`&gt;`,
  and keep arrows/symbols the author used (`->`, `→`, `·`, `≥`) as-is.

### R1 — Single self-contained file
- One `.html` file. No external JS/CSS except the Google Fonts `<link>` already in the template
  (IBM Plex Sans + JetBrains Mono). Everything else is inline.
- Keep the `<div id="progress">`, `<header class="topbar">`, `<main class="deck" id="deck">`,
  `<nav class="navbar">`, `<div class="hint">`, and `<div class="menu">` exactly as in the template.
- Update only: the `<title>`, the topbar `<b>` course/brand text and its `<span>` (`· Course · Ch.NN`),
  and the localStorage theme key if you want per-deck persistence (optional — leaving `poc-theme` is fine).

### R2 — The container/card model
- The page (`body`) uses `--bg`; the `.deck` **card** (border, 16px radius, shadow, top accent bar)
  uses a distinct `--deck-bg` backdrop (GitHub canvas-inset: `#eaeef2` light / `#010409` dark) so the
  centered `--surface` `.inner` card reads explicitly as a distinct card in the middle. Never make
  slides flush with the page background.
- The help popover is confined to the deck bounds and **capped to the `.inner` width** so it renders
  over the content card (`position:fixed`; `top/bottom:60px`, `left/right:14px` like `.deck`, `8px`
  on mobile; `max-width:1300px; margin-inline:auto` to center it over `.inner`; plus the card border,
  16px radius and shadow) — never full-viewport `inset:0`. Its close button is `position:absolute`
  at the card's top-right corner, and the topbar/navbar stay visible behind it.

### R3 — Per-slide accent color
- Every `<section class="slide">` carries a `data-accent` from this palette:
  `orange, teal, purple, green, blue, pink, red, amber` (tokens `--c-*`, defined for light + both
  dark modes in the template).
- The accent drives the card's top bar, `.kicker`, `h2`, `.divider .num`, `.help-btn`, `.q-inline`,
  the `.help-list-item` left rail, and `.note.tip`. `render()` copies the active slide's
  `data-accent` onto `#deck`, so the card recolors as you navigate — this is already wired; just
  set the attribute per section.
- **Accent assignment:** give each top-level Part/section its own accent, cycling through the palette
  in order so adjacent sections differ. Keep all slides belonging to the same Part on the same accent.

### R4 — Contents index must equal the visible slide title
- The Contents menu is generated from each section's `data-title`. Set `data-title` to the **exact
  text shown as that slide's title**:
  - Content slides → the `<h2>` text.
  - Part divider slides (no `<h2>`) → the `.num` eyebrow text, e.g. `Part 04 · PoC Scoping Methodology`.
- Mark section/divider slides with `data-section="true"` so they render bold in the menu.

### R5 — Centered content card on a deck backdrop
- The deck is a wide backdrop; each slide's `.inner` is a centered content **card** floating on it.
  The deck's background must differ from the card's. Keep these chassis rules, don't remove:
  - `.deck{ background:var(--deck-bg) }` — the backdrop tone. `--deck-bg` is GitHub canvas-inset
    (`#eaeef2` light / `#010409` dark, per the bitly presentation reference), defined in all three
    `:root` theme blocks, so the card pops against it.
  - `.slide .inner` — the content card, and the element that carries the **16:9 frame** (like the
    bitly `.presentation`, not the `section`): `width:100%; max-width:1300px; aspect-ratio:16 / 9;
    max-height:100%; overflow-y:auto` (max-height + scroll so tall content is never clipped on short
    viewports). Plus border, 16px radius, elevated `box-shadow:var(--shadow-lg)` (a stronger token
    than `--shadow`, defined in all three `:root` blocks, so the card lifts off the deck), `28px 32px`
    padding, and a **mesh + gradient** background over `var(--surface)` (per the bitly reference): two
    1px grid linear-gradients at `background-size:46px 46px` tinted `color-mix(--local-accent 6%)`,
    plus two corner radial glows (`--local-accent 14%` top-left, `--c-purple 11%` bottom-right). Its
    base `--surface` must stay distinct from the deck's `--deck-bg` (deck bg ≠ inner bg).
  - `.help-popover` carries the **same mesh + gradient** over `var(--surface)`, tinted by
    `--pop-accent` (with the `--c-purple` complementary glow), and the same `--shadow-lg` elevation,
    so the deep dive matches the card.
  - `.slide{ background:transparent }` and `.divider{ background:transparent }` — the section itself
    has **no background** and no size cap; it's a full-size (`inset:0`) transparent wrapper that
    centers the `.inner` card (flex + `margin:auto 0`). Only the `--deck-bg` backdrop and the `.inner`
    card's mesh/gradient read; the 16:9 card is what you see in the middle, never a slide-wide fill.
  - `.help-popover` is confined to the deck bounds and capped to `max-width:1300px` centered (matching
    the `.inner` card, see R2), so the deep dive renders over the card, not the full viewport.
  - `<pre><code>` uses a **light, theme-adaptive** palette (not the old dark terminal): `--code-bg`
    `#F1F4F8` light / `#101922` dark and `--code-text` `#152230` light / `#EBF1F7` dark, defined in all
    three `:root` blocks. To keep blocks from looking dull, `pre` is **accent-tinted**: background
    `color-mix(--local-accent 6%, --code-bg)`, border `color-mix(--local-accent 22%, --border)`, and a
    `border-left:3px solid --local-accent` bar — so each block carries its section's accent. The
    popover maps `--local-accent:var(--pop-accent)` so deep-dive code (and `.note.tip`) match the
    popover's accent.
- Do not reintroduce full-width slides, full-viewport popovers, a `--surface`/`--surface-2` deck
  background (the deck must use `--deck-bg`), a section/`.slide` background fill, a dark terminal
  `<pre>` theme, or a card whose background matches the deck.

---

## Slide taxonomy — how to map Markdown to slides

Decide per block; don't force everything into one shape.

1. **Cover slide** (first, `class="slide divider"`, `data-section="true"`, `data-accent="orange"`):
   `.num` (course · chapter) → `<h1>` (deck title) → `.lead` (one-line abstract) →
   `.meta` (nav hint). Built from the MD H1 / front matter.

2. **Part divider / hub slide** (`class="slide divider"`, `data-section="true"`):
   Use for each top-level Part when its sub-sections are long or example-heavy.
   - `.num` = `Part NN · <Part title>` (this is the slide's title → mirror into `data-title`).
   - Intro paragraph(s) = the Part's overview prose, verbatim.
   - `<ul class="help-list">` with one `<li class="help-list-item">` per sub-section:
     `<button class="help-btn" data-help="<id>" aria-label="Open deep dive: <title>">?</button><span><title></span>`.
   - The **first** sub-section id is conventionally `<part>-lead`.

3. **Content slide** (`class="slide"`): for concise conceptual material that fits on screen —
   `.kicker` (Part · label) → `<h2>` → paragraphs, `<ul>/<ol>`, `.note`, `.tbl`, `.quote`.
   (Part 01 in the reference uses real content slides instead of a hub — do this when content is short.)

4. **Deep-dive templates** (the key pattern for long content): every sub-section referenced by a
   `data-help="<id>"` button has a matching hidden template **after** `</main>`:
   ```html
   <template id="help-<id>">
     <div class="inner"> … full verbatim sub-section: h2, prose, notes, code, tables … </div>
   </template>
   ```
   This keeps slides uncluttered while preserving 100% of the Markdown. `data-help` ↔ template id
   (`help-` prefix) must match exactly, or the button opens nothing.

**Guiding heuristic:** short/overview content goes directly on a slide; detailed walk-throughs,
long code samples, and per-item deep dives go into `help-*` templates opened from a hub slide's
`help-list`.

---

## Markdown → component mapping

| Markdown | HTML in the deck |
|---|---|
| `# Title` (doc) | Cover `<h1>` |
| `## Part / Section` | `<h2>` (content slide) or `.num` (divider) |
| `### Subsection` | `<h3>` |
| Paragraph | `<p>` (lead paragraph → `class="lead"`) |
| `**bold**` | `<strong>` |
| `` `code` `` | inline `<code>` |
| ` ```lang … ``` ` | `<pre><code> … </code></pre>` (verbatim, keep whitespace) |
| Bulleted / numbered list | `<ul>` / `<ol>` |
| Table | `<div class="tbl"><table>…</table></div>` |
| Blockquote / "Tip"/"Note" callout | `.note` (info, teal) or `.note.tip` (accent); `<span class="tag">LABEL</span>` + `<p>` |
| Pull quote / example line | `<p class="quote">` |
| Status/label chip | `<span class="badge">` |
| Inline "?" affordance mention | `<span class="q-inline">?</span>` |

---

## Behaviours already provided by the template script (keep them working)
- Arrow / Space / PageUp-Down / Home / End navigation; **C** = Contents, **T** = theme, **Esc** closes menu/deep-dive.
- Touch swipe left/right to move slides (suppressed while a deep dive is open).
- Progress bar, slide counter, hash-based deep-linking (`#slide-id`), Contents menu auto-built from `data-title`.
- Light/dark theme toggle persisted in `localStorage`, honoring `prefers-color-scheme`.
- Deep-dive popover fills the card; content cloned from the matching `<template>`.

Because the script selects slides via `document.querySelectorAll('.slide')` and reads
`data-help` / `data-title` / `data-accent`, you only need correct **markup** — no JS edits.

---

## Procedure

1. Read the source `.md` (**$1**) and the reference HTML template in full.
2. Plan the slide list: cover, then one hub (or content) slide per Part, and the sub-section
   inventory that becomes `help-*` templates. Assign an accent per Part (R3).
3. Copy the template's head/style/chrome/script; swap in the generated `<section>`s and `<template>`s.
4. Set every `data-accent`, `data-title` (= visible title, R4), `data-section`, and matching
   `data-help`/template ids.
5. Verify before finishing:
   - `data-help` count == number of `help-*` templates, and every id resolves
     (`grep -o 'data-help="[^"]*"'` vs `grep -o 'id="help-[^"]*"'`).
   - Every `.slide` has a `data-accent`; every section's `data-title` equals its on-slide title.
   - `{`/`}` balanced in the file; `.help-popover` is confined to the deck card (not `inset:0`
     full-viewport); no `<h3>In this section …</h3>` lines remain (R5).
   - All Markdown content is present verbatim (spot-check code blocks, tables, numbers).
6. Report the output path and a one-line summary of slide count + sections. Offer to open it in a
   browser (`file://…`) for visual review — the in-editor Chrome preview needs the extension connected.

## Guardrails
- Never invent content to "fill" a slide. If the Markdown is thin, the slide is thin.
- Never alter the design system tokens or JS unless the user explicitly asks.
- If the Markdown implies a component we don't have, prefer the closest existing one over new CSS.
