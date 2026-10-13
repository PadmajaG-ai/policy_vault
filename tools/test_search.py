import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from search_index import search  # noqa: E402

TESTS = {
    "meal limit increase sales offsite": "TKT-1042",
    "mileage posting failed field length exceeded": "TKT-1135",
    "metro hotel cap reduced": "TKT-1177",
}

for query, expected in TESTS.items():
    links = search(query, page_size=3)
    hit = "PASS" if links and expected in links[0] else "CHECK"
    print(f"[{hit}] {query}\n   top 3: {links}\n")