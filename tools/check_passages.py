"""Check that every quoted passage appears word for word in the book, on the page we cite.

    python3 tools/check_passages.py <book.txt> web/data/passages.json web/data/worries.json

The book text is not in this repository. Page footers are removed and lines are joined
before searching, so a quote may cross a line or page break; its cited page must be the
page where it starts or ends.
"""
import json
import sys

from booktext import Book


def quotes_in(data):
    """Yield (label, text, page) for every quote in either data file."""
    for key, item in data.get("objects", {}).items():
        for q in item.get("quotes", []):
            yield key, q["text"], q["page"]
    for q in data.get("daily", []):
        yield "daily " + q["id"], q["text"], q["page"]
    for key, q in data.get("quotes", {}).items():
        yield key, q["text"], q["page"]
    for key, m in data.get("missions", {}).items():
        yield "mission " + key, m["quote"], m["page"]


def main(book_path, *files):
    book = Book(book_path)
    bad = total = 0
    for f in files:
        for label, text, page in quotes_in(json.load(open(f, encoding="utf-8"))):
            total += 1
            loc = book.find(text)
            if loc is None:
                bad += 1
                print("NOT FOUND", label, text[:40])
            elif page not in loc:
                bad += 1
                print("WRONG PAGE", label, page, "is on", loc)
    print(f"checked {total}, problems: {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(*sys.argv[1:])
