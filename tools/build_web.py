"""Inline the models and data into self-contained pages.

    python3 tools/build_web.py

Writes dist/study.html (page body, for hosts that add their own <html> skeleton)
and dist/index.html (a full document, for GitHub Pages); likewise the figures' motion
preview as dist/characters.html and dist/characters/index.html.
"""
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DIST = ROOT / "dist"


def full(page):
    return ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '</head>\n<body>\n' + page + "\n</body>\n</html>\n")


def b64(path):
    return base64.b64encode(path.read_bytes()).decode("ascii")


def characters():
    page = (WEB / "characters.html").read_text(encoding="utf-8").replace("/*__GLB__*/", b64(WEB / "assets" / "characters.glb"))
    (DIST / "characters.html").write_text(page, encoding="utf-8")
    (DIST / "characters").mkdir(exist_ok=True)
    (DIST / "characters" / "index.html").write_text(full(page), encoding="utf-8")
    print(f"dist/characters.html {len(page) / 1e6:.2f} MB")


def main():
    page = (WEB / "study.html").read_text(encoding="utf-8")
    glb = b64(WEB / "assets" / "study.glb")
    passages = json.loads((WEB / "data" / "passages.json").read_text(encoding="utf-8"))
    worries = json.loads((WEB / "data" / "worries.json").read_text(encoding="utf-8"))
    inline = lambda d: json.dumps(d, ensure_ascii=False).replace("</", "<\\/")
    page = (page.replace("/*__GLB__*/", glb)
                .replace("/*__PASSAGES__*/", inline(passages))
                .replace("/*__WORRIES__*/", inline(worries)))
    DIST.mkdir(exist_ok=True)
    (DIST / "study.html").write_text(page, encoding="utf-8")
    (DIST / "index.html").write_text(full(page), encoding="utf-8")
    print(f"dist/study.html {len(page) / 1e6:.2f} MB")
    characters()


if __name__ == "__main__":
    main()
