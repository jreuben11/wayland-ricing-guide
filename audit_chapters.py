#!/usr/bin/env python3
"""Audit chapters for missing/thin Overview and Installation sections."""

import re, os, glob

def audit_file(path):
    with open(path) as f:
        content = f.read()

    # Extract h1 title
    title_m = re.search(r'^# (.+)$', content, re.MULTILINE)
    title = title_m.group(1) if title_m else '(no title)'

    # Overview: present and non-trivial?
    ov_m = re.search(r'^## Overview\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL | re.MULTILINE)
    if ov_m:
        ov_text = ov_m.group(1).strip()
        ov_words = len(ov_text.split())
    else:
        ov_text = ''
        ov_words = 0

    # Install section present?
    has_install = bool(re.search(
        r'^## [^\n]*(install|setup|getting started|prerequisites)[^\n]*$',
        content, re.MULTILINE | re.IGNORECASE
    ))
    # Also accept subsections like ### Installation
    has_install = has_install or bool(re.search(
        r'^### [^\n]*(install|setup)[^\n]*$',
        content, re.MULTILINE | re.IGNORECASE
    ))
    # Accept inline install commands (pacman/nix/apt)
    has_install_cmd = bool(re.search(r'pacman -S|nix-env|nix profile|home-manager|apt install|dnf install', content))

    needs_intro  = ov_words < 30
    needs_install = not has_install and not has_install_cmd

    return {
        'path': path,
        'title': title,
        'ov_words': ov_words,
        'has_install': has_install,
        'has_install_cmd': has_install_cmd,
        'needs_intro': needs_intro,
        'needs_install': needs_install,
    }

base = '/home/jreuben1/Documents/wayland-ricing-guide'
files = sorted(glob.glob(f'{base}/**/*.md', recursive=True))
files = [f for f in files if '.git' not in f
         and os.path.basename(f) not in ('README.md', 'add_toc.py', 'audit_chapters.py')]

results = [audit_file(f) for f in files]

need_work = [r for r in results if r['needs_intro'] or r['needs_install']]
print(f'Total files: {len(results)}')
print(f'Need work:   {len(need_work)}\n')

print(f'{"File":<55} {"OvWords":>7}  {"NeedIntro":>9}  {"NeedInstall":>11}')
print('-' * 90)
for r in need_work:
    name = os.path.relpath(r['path'], base)
    print(f'{name:<55} {r["ov_words"]:>7}  {"YES" if r["needs_intro"] else "":>9}  {"YES" if r["needs_install"] else "":>11}')
