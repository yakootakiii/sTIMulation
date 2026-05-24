#!/usr/bin/env python3
import json
from pathlib import Path

md_path = Path('00 Reports/sTIMulation_paper.md')
out_dir = Path('assets/paper_charts')

with (out_dir / 'manifest.json').open('r', encoding='utf-8') as mf:
    manifest = json.load(mf)

with md_path.open('r', encoding='utf-8') as f:
    text = f.read()

# For each manifest entry, replace the first occurrence of the mermaid block with image link
for idx, entry in enumerate(manifest, start=1):
    svg_rel = f'assets/paper_charts/{entry["name"]}.svg'
    png_rel = f'assets/paper_charts/{entry["name"]}.png'
    img_md = f'![Figure {idx}]({svg_rel})\n\n<small>SVG: {svg_rel} — PNG fallback: {png_rel}</small>'

    # Replace the first ```mermaid ... ``` occurrence
    parts = text.split('```mermaid', 1)
    if len(parts) == 2:
        before, rest = parts
        # remove up to closing ```
        if '```' in rest:
            _, after = rest.split('```', 1)
            text = before + img_md + '\n' + after
        else:
            # malformed block; skip
            print('Malformed mermaid block; skipping replacement for', entry['name'])
            continue
    else:
        print('No more mermaid blocks to replace; stopping at', idx)
        break

with md_path.open('w', encoding='utf-8') as f:
    f.write(text)

print('Replaced mermaid blocks with image links in', md_path)
