"""Assemble the GitHub Pages site: the web interface in demo mode plus the precomputed demo files.

python scripts/build_site.py site
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(out: Path) -> Path:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "src" / "unfaded" / "web", out)
    shutil.copytree(ROOT / "demo", out / "demo")
    page = out / "index.html"
    page.write_text(page.read_text().replace("<body", '<body data-demo="1"', 1))
    (out / ".nojekyll").write_text("")
    return out


if __name__ == "__main__":
    target = build(Path(sys.argv[1] if len(sys.argv) > 1 else "site"))
    print(f"site written to {target}")
