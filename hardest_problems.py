"""Utility to scrape Project Euler archives and rank problems by a simple
hardness proxy: (number_of_solvers) / (days_since_publication).

Lower score => harder (fewer solves per day of life)."""

from __future__ import annotations

import datetime as _dt
import os as _os
import re as _re
import time as _time
from dataclasses import dataclass
from typing import Iterable, List

try:  # Prefer external libs for robustness
	import requests  # type: ignore
	from bs4 import BeautifulSoup  # type: ignore
except Exception as exc:  # pragma: no cover - import error path
	raise RuntimeError(
		"Missing dependencies. Install with: pip install requests beautifulsoup4"
	) from exc

ARCHIVES_URL = "https://projecteuler.net/archives"
USER_AGENT = (
	"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
	"AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)


@dataclass(slots=True)
class EulerProblem:
	id: int
	title: str
	published: _dt.date
	solvers: int

	@property
	def days_since_publication(self) -> int:
		return max(1, (_dt.date.today() - self.published).days)

	@property
	def score(self) -> float:
		# Solves per day (lower => harder under this simple heuristic)
		return self.solvers / self.days_since_publication


def _fetch(page: int | None = None, delay: float = 0.4) -> str:
	"""Fetch a single archives page. Page numbering starts at 0 on the site.

	Args:
		page: zero-based page index or None for first page.
		delay: polite sleep inserted before the request.
	"""
	if delay:
		_time.sleep(delay)
	# Empirically the archives pagination uses the semicolon form ;page=N
	# The ?page= variant serves the first page again (duplicates) -> avoid.
	if page in (None, 0):
		url = ARCHIVES_URL
	else:
		url = f"{ARCHIVES_URL};page={page}"
	headers = {"User-Agent": USER_AGENT, "Accept-Language": "en"}
	resp = requests.get(url, headers=headers, timeout=20)
	resp.raise_for_status()
	return resp.text


_DATE_INLINE_RE = _re.compile(r"Published on .*?, (\d+)(?:st|nd|rd|th) (\w+) (\d{4})")
_MON = {m: i for i, m in enumerate(["January","February","March","April","May","June","July","August","September","October","November","December"], start=1)}


def _parse(html: str) -> List[EulerProblem]:
	soup = BeautifulSoup(html, "html.parser")
	# Current layout: single table with header th classes id_column/title_column/solved_by_column.
	table = soup.find("table")
	if not table:
		return []
	out: List[EulerProblem] = []
	for tr in table.find_all("tr"):
		tds = tr.find_all("td")
		# Expected columns now: ID | Title | Solved By
		if len(tds) != 3:
			continue
		try:
			pid_text = tds[0].get_text(strip=True)
			if not pid_text.isdigit():
				continue
			pid = int(pid_text)
			link = tds[1].find('a')
			if not link:
				continue
			title = link.get_text(strip=True)
			meta = link.get('title', '')
			m = _DATE_INLINE_RE.search(meta)
			if not m:
				continue
			day, mon_name, year = m.groups()
			month = _MON.get(mon_name)
			if not month:
				continue
			published = _dt.date(int(year), month, int(day))
			solvers_txt = tds[2].get_text(strip=True).replace(",", "")
			solvers = int(solvers_txt) if solvers_txt.isdigit() else 0
			out.append(EulerProblem(pid, title, published, solvers))
		except Exception:
			continue
	return out


def iter_all_problems(max_pages: int | None = None) -> Iterable[EulerProblem]:
	"""Iterate over all problems currently in the archives.

	Args:
		max_pages: optional hard cap (for faster debugging).
	"""
	page = 0
	seen_ids: set[int] = set()
	while True:
		if max_pages is not None and page > max_pages:
			break
		html = _fetch(page)
		problems = _parse(html)
		if not problems:
			break
		for p in problems:
			if p.id in seen_ids:  # safety against unexpected duplication
				continue
			seen_ids.add(p.id)
			yield p
		page += 1


def hardest_problems(limit: int = 25, max_pages: int | None = None) -> List[EulerProblem]:
	"""Return the hardest problems under the (solves/day) heuristic.

	Args:
		limit: number of rows to return.
		max_pages: cap number of pages scraped.
	"""
	problems = list(iter_all_problems(max_pages=max_pages))
	problems.sort(key=lambda p: (p.score, p.id))  # stable tie-breaker by ID
	return problems[:limit]


def format_table(rows: List[EulerProblem]) -> str:
	head = f"{'Rank':>4} {'ID':>4}  {'Title':<30} {'Pub Date':<11} {'Solvers':>8} {'Days':>6} {'Ratio':>10}"
	lines = [head, "-" * len(head)]
	for i, p in enumerate(rows):
		lines.append(
			f"{i+1:>4} {p.id:>4}  {p.title[:30]:<30} {p.published:%d %b %Y} {p.solvers:>8} {p.days_since_publication:>6} {p.score:>10.6f}"
		)
	return "\n".join(lines)


def main():  
	limit = 1000 #int(_os.environ.get("PE_LIMIT", "100"))
	max_pages_env = 19 # 1 page = 50 problems. E.g. https://projecteuler.net/archives;page=2
	max_pages = int(max_pages_env) if max_pages_env else None
	rows = hardest_problems(limit=limit, max_pages=max_pages)
	print(format_table(rows))


if __name__ == "__main__": 
	main()
