#!/usr/bin/env python3
"""Check that every word of a Markdown chapter survives in its HTML slide deck.

Usage: python3 -I .claude/scripts/deck_fidelity.py <chapter.md> <deck.html>

Compares word multisets (case-sensitive) of the Markdown source and the deck's
content text: slide <section>s plus deep-dive <template>s. Decorative
elements (aria-hidden, svg, script, style) and the deck chrome are ignored, so
only real content counts. Exit code 1 if any Markdown word is missing.
"""
import re, sys
from collections import Counter
from html.parser import HTMLParser

WORD = re.compile(r"[A-Za-z0-9$%][A-Za-z0-9$%.,'/_+-]*")


def md_words(text):
    text = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.S)           # front matter
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', text)                   # images
    text = re.sub(r'\[([^\]]*)\]\(([^)]*)\)', r'\1 \2', text)           # links: keep text + url
    text = re.sub(r'^```[^\n]*$', ' ', text, flags=re.M)                # fence lines
    text = re.sub(r'^\s{0,3}(#{1,6}|>|[-*+]|\d+\.)\s+', ' ', text, flags=re.M)  # block markers
    text = re.sub(r'^\s*\|?\s*:?-{3,}.*$', ' ', text, flags=re.M)       # table separators
    text = re.sub(r'(\*\*|__|\*|`|\|)', ' ', text)                      # inline markers
    return Counter(norm(w) for w in WORD.findall(text))


def norm(w):
    return w.strip('_').rstrip('.,:;_')


class Deck(HTMLParser):
    VOID = {'br', 'img', 'meta', 'link', 'input', 'hr', 'source', 'wbr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.depth_unit, self.hidden, self.out = [], 0, 0, []

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        a = dict(attrs)
        hid = tag in ('script', 'style', 'svg') or a.get('aria-hidden') == 'true'
        unit = tag in ('section', 'template') and bool(a.get('id'))
        self.stack.append((tag, hid, unit))
        self.hidden += hid
        self.depth_unit += unit

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        while self.stack:
            t, hid, unit = self.stack.pop()
            self.hidden -= hid
            self.depth_unit -= unit
            if t == tag:
                break

    def handle_data(self, data):
        if self.depth_unit and not self.hidden:
            self.out.append(data)


def html_words(text):
    p = Deck()
    p.feed(text)
    return Counter(norm(w) for w in WORD.findall(' '.join(p.out)))


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    md = md_words(open(sys.argv[1], encoding='utf-8').read())
    html = html_words(open(sys.argv[2], encoding='utf-8').read())
    missing = md - html
    extra = html - md
    total = sum(md.values())
    print(f'markdown words: {total}  deck words: {sum(html.values())}  '
          f'missing: {sum(missing.values())}  extra: {sum(extra.values())}')
    if missing:
        print('\nMISSING from deck (word x count):')
        for w, c in missing.most_common(60):
            print(f'  {w!r} x{c}')
    if extra:
        print('\nEXTRA in deck (review: should only be structural labels):')
        for w, c in extra.most_common(30):
            print(f'  {w!r} x{c}')
    sys.exit(1 if missing else 0)


if __name__ == '__main__':
    main()
