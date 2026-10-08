"""Check that every quoted passage appears word for word in the book text.

    python3 tools/check_passages.py <book.txt> web/data/passages.json

The book text is not in this repository. Page footers are removed and lines are joined
before searching, so a quote may cross a line or page break.
"""
import json
import re
import sys


def clean(text):
    keep = []
    for line in text.splitlines():
        s = line.strip()
        if re.fullmatch(r"\d+ 세이노의 가르침", s):
            continue
        if re.fullmatch(r"(서문|[123]부 .+|부록.*|세이노가 독자들에게) \d+", s):
            continue
        keep.append(line)
    return "".join(keep)


def main(book, passages):
    text = clean(open(book, encoding="utf-8").read())
    data = json.load(open(passages, encoding="utf-8"))
    bad = 0
    for key, item in data["objects"].items():
        for q in item.get("quotes", []):
            if q["text"] not in text:
                bad += 1
                print("NOT FOUND", key, q["page"], q["text"][:40])
    for q in data["daily"]:
        if q["text"] not in text:
            bad += 1
            print("NOT FOUND daily", q["page"], q["text"][:40])
    print("checked, missing:", bad)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(*sys.argv[1:3])
