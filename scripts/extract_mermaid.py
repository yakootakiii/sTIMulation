#!/usr/bin/env python3
import re
from pathlib import Path

md_path = Path('00 Reports/sTIMulation_paper.md')
out_dir = Path('assets/paper_charts')
out_dir.mkdir(parents=True, exist_ok=True)

with md_path.open('r', encoding='utf-8') as f:
    text = f.read()

pattern = re.compile(r"```mermaid\n(.*?)\n```", re.DOTALL)
blocks = pattern.findall(text)

manifest = []
for i, block in enumerate(blocks, start=1):
    name = f'chart_{i:02d}'
    mmd_file = out_dir / f'{name}.mmd'
    with mmd_file.open('w', encoding='utf-8') as mf:
        mf.write('```mermaid\n')
        mf.write(block.strip() + '\n')
        mf.write('```\n')
    manifest.append({'name': name, 'mmd': str(mmd_file)})

# Save manifest
import json
with (out_dir / 'manifest.json').open('w', encoding='utf-8') as mf:
    json.dump(manifest, mf, indent=2)

print(f'Extracted {len(manifest)} mermaid blocks to {out_dir}')
print('Manifest written to', out_dir / 'manifest.json')
