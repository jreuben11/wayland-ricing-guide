#!/usr/bin/env python3
"""Insert a Table of Contents into every chapter .md file."""

import re
import os
import glob


def make_anchor(heading_text):
    """Generate GitHub-compatible anchor ID from heading text."""
    # Remove inline markdown (bold, italic, code)
    text = re.sub(r'[*_`]', '', heading_text)
    # Normalise em-dash / en-dash to a single space so we get one hyphen
    text = re.sub(r'\s*[—–]\s*', ' ', text)
    # Lowercase
    text = text.lower()
    # Remove anything that is not alphanumeric, space, or hyphen
    text = re.sub(r'[^\w\s-]', '', text)
    # Collapse whitespace → single hyphen
    text = re.sub(r'\s+', '-', text.strip())
    # Collapse consecutive hyphens
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def generate_toc(lines):
    """Return list of TOC markdown lines for h2/h3 headings."""
    entries = []
    for line in lines:
        m2 = re.match(r'^## (.+)$', line)
        m3 = re.match(r'^### (.+)$', line)
        if m2:
            text = m2.group(1).strip()
            anchor = make_anchor(text)
            entries.append(f'- [{text}](#{anchor})')
        elif m3:
            text = m3.group(1).strip()
            anchor = make_anchor(text)
            entries.append(f'  - [{text}](#{anchor})')
    return entries


def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Skip if TOC already present
    if re.search(r'^## (Table of Contents|Contents)\s*$', content, re.MULTILINE):
        return 'skip'

    lines = content.split('\n')

    entries = generate_toc(lines)
    if not entries:
        return 'no-headings'

    toc_block = ['## Contents', ''] + entries + ['', '---', '']

    # Insert right after the title line (# …) and any blank lines,
    # immediately before the first ## heading.
    insert_pos = None
    title_seen = False
    for i, line in enumerate(lines):
        if not title_seen and re.match(r'^# [^#]', line):
            title_seen = True
            continue
        if title_seen and re.match(r'^## ', line):
            insert_pos = i
            break

    if insert_pos is None:
        return 'no-insert-point'

    # Keep a blank line between the title block and the TOC
    # (ensure there's exactly one blank line before insert_pos)
    while insert_pos > 0 and lines[insert_pos - 1].strip() == '':
        insert_pos -= 1
    # Add a blank line separator
    toc_block = [''] + toc_block

    new_lines = lines[:insert_pos] + toc_block + lines[insert_pos:]
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
    return len(entries)


def main():
    base = '/home/jreuben1/Documents/wayland-ricing-guide'
    md_files = sorted(glob.glob(f'{base}/**/*.md', recursive=True))
    md_files = [f for f in md_files
                if '.git' not in f
                and os.path.basename(f) not in ('README.md', 'add_toc.py')]

    ok = skip = fail = 0
    for path in md_files:
        result = process_file(path)
        name = os.path.relpath(path, base)
        if isinstance(result, int):
            print(f'  OK  ({result:3d} entries)  {name}')
            ok += 1
        elif result == 'skip':
            print(f'  --  (already has TOC)  {name}')
            skip += 1
        else:
            print(f'  !!  ({result})  {name}')
            fail += 1

    print(f'\nDone: {ok} updated, {skip} skipped, {fail} failed.')


if __name__ == '__main__':
    main()
