"""Book text helpers: the cleaned text and the page of any passage."""
import bisect
import re

FOOT_EVEN = re.compile(r"(\d+) 세이노의 가르침")
FOOT_ODD = re.compile(r"(?:서문|[123]부 .+|부록.*|세이노가 독자들에게) (\d+)")


class Book:
    def __init__(self, path):
        parts, ends, pages = [], [], []
        pos = 0
        for line in open(path, encoding="utf-8").read().splitlines():
            s = line.strip()
            m = FOOT_EVEN.fullmatch(s) or FOOT_ODD.fullmatch(s)
            if m:
                ends.append(pos)
                pages.append(int(m.group(1)))
                continue
            parts.append(line)
            pos += len(line)
        self.text = "".join(parts)
        self._ends, self._pages = ends, pages

    def page_at(self, offset):
        i = bisect.bisect_left(self._ends, offset + 1)
        return self._pages[i] if i < len(self._pages) else None

    def find(self, quote):
        """Return (start_page, end_page) of a verbatim quote, or None."""
        i = self.text.find(quote)
        if i < 0:
            return None
        return self.page_at(i), self.page_at(i + len(quote) - 1)

    def search(self, pattern, lo=0, hi=10**4, width=160):
        for m in re.finditer(pattern, self.text):
            p = self.page_at(m.start())
            if p and lo <= p <= hi:
                yield p, self.text[max(0, m.start() - width // 2): m.end() + width]
