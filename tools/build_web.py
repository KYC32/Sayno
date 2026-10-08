"""Inline the study model, passages and worries into one self-contained page.

    python3 tools/build_web.py

Writes dist/study.html (page body, for hosts that add their own <html> skeleton)
and dist/index.html (a full document, for GitHub Pages).
"""
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DIST = ROOT / "dist"


def main():
    page = (WEB / "study.html").read_text(encoding="utf-8")
    glb = base64.b64encode((WEB / "assets" / "study.glb").read_bytes()).decode("ascii")
    passages = json.loads((WEB / "data" / "passages.json").read_text(encoding="utf-8"))
    worries = json.loads((WEB / "data" / "worries.json").read_text(encoding="utf-8"))
    inline = lambda d: json.dumps(d, ensure_ascii=False).replace("</", "<\\/")
    page = (page.replace("/*__GLB__*/", glb)
                .replace("/*__PASSAGES__*/", inline(passages))
                .replace("/*__WORRIES__*/", inline(worries)))
    DIST.mkdir(exist_ok=True)
    (DIST / "study.html").write_text(page, encoding="utf-8")
    full = ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '</head>\n<body>\n' + page + "\n</body>\n</html>\n")
    (DIST / "index.html").write_text(full, encoding="utf-8")
    print(f"dist/study.html {len(page) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
