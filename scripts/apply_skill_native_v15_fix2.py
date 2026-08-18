from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

for script_name in ("apply_skill_native_v15.py", "apply_skill_native_v15_fix1.py"):
    script = ROOT / "scripts" / script_name
    if script.is_file():
        runpy.run_path(str(script), run_name="__main__")

for relative in ("scripts/validate_skill.py", "scripts/validate-skill-v15.mjs"):
    target = ROOT / relative
    if not target.is_file():
        continue
    text = target.read_text(encoding="utf-8")
    replacements = {
        '"' + chr(0x00C3) + '"': '"\\u00c3"',
        '"' + chr(0x00C2) + '"': '"\\u00c2"',
        '"' + chr(0x00E2) + chr(0x20AC) + '"': '"\\u00e2\\u20ac"',
        "'" + chr(0x00C3) + "'": "'\\u00c3'",
        "'" + chr(0x00C2) + "'": "'\\u00c2'",
        "'" + chr(0x00E2) + chr(0x20AC) + "'": "'\\u00e2\\u20ac'",
    }
    for source, replacement in replacements.items():
        text = text.replace(source, replacement)
    target.write_text(text, encoding="utf-8", newline="\n")

print("applied V15 installer and Unicode self-audit correction")
