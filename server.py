"""Local server for Founder Pain Radar.

Serves ./site and exposes /api/posts, which pulls the week's top posts from
Reddit's public RSS feeds, groups them by keyword, caches the result for
15 minutes and writes it to site/latest.json.
"""
import html
import json
import re
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
SITE = ROOT / "site"
PORT = 8765
SUBREDDITS = ["Entrepreneur", "smallbusiness"]
CACHE_SECONDS = 900
UA = "founder-pain-radar/0.1 (local student project)"
ATOM = "{http://www.w3.org/2005/Atom}"

GROUPS = [
    ("platform", "Platforms and payment providers acting against owners",
     ["banned", "ban ", "suspend", "frozen", "chargeback", "dispute", "refund", "yelp", "meta ", "square", "shopify",
      "wise ", "stripe", "paypal", "terms", "unexpected charge", "account"]),
    ("team", "Managing people and what they cost",
     ["employee", "staff", "manager", "hiring", "hire ", "morale", "insurance", "payroll", "team"]),
    ("doubt", "Doubt and isolation",
     ["struggl", "progress", "burnout", "lonely", "quit", "don't know", "discourag", "anxiety", "motivation",
      "giving up", "edge"]),
    ("visibility", "Being visible without a marketing team",
     ["social media", "instagram", "tiktok", "marketing", "followers", "personal brand", "seo", "famous",
      "face of", "ads "]),
    ("paid", "Getting paid and keeping processes simple",
     ["not pay", "won't pay", "unpaid", "invoice", "late payment", "client", "process", "simplif", "workflow", "tools"]),
    ("money", "Planning money before the big moment",
     ["tax", "profit", "cash flow", "loan", "funding", "revenue", "sold my", "exit", "valuation"]),
]

_cache = {"at": 0.0, "data": None}
_lock = threading.Lock()


def fetch_feed(sub):
    url = f"https://www.reddit.com/r/{sub}/top/.rss?t=week&limit=10"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        root = ET.fromstring(r.read())
    posts = []
    for e in root.findall(ATOM + "entry"):
        title = (e.findtext(ATOM + "title") or "").strip()
        link = e.find(ATOM + "link")
        content = e.findtext(ATOM + "content") or ""
        text = html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(content)))
        posts.append({
            "subreddit": sub,
            "title": title,
            "url": link.get("href") if link is not None else "",
            "text": re.sub(r"\s+", " ", text).strip()[:400],
        })
    return posts


def classify(post):
    blob = (post["title"] + " " + post["text"]).lower() + " "
    best, best_score = "other", 0
    for key, _label, words in GROUPS:
        score = sum(blob.count(w) for w in words)
        if score > best_score:
            best, best_score = key, score
    return best


_sub_cache = {}


def build():
    posts, errors = [], []
    for n, sub in enumerate(SUBREDDITS):
        if n:
            time.sleep(2)  # Reddit rate-limits anonymous bursts
        try:
            _sub_cache[sub] = fetch_feed(sub)
        except Exception as exc:  # network, 429, parse
            errors.append(f"r/{sub}: {exc} (showing last good copy)" if sub in _sub_cache else f"r/{sub}: {exc}")
        posts += [dict(p) for p in _sub_cache.get(sub, [])]
    for p in posts:
        p["group"] = classify(p)
        p.pop("text")
    groups = []
    for key, label, _ in GROUPS + [("other", "Everything else", [])]:
        items = [p for p in posts if p["group"] == key]
        groups.append({"key": key, "label": label, "count": len(items), "posts": items})
    return {
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(posts),
        "errors": errors,
        "groups": groups,
    }


def get_data():
    with _lock:
        ttl = 60 if _cache["data"] and _cache["data"]["errors"] else CACHE_SECONDS
        fresh = _cache["data"] and time.time() - _cache["at"] < ttl
        if not fresh:
            data = build()
            if data["total"] or not _cache["data"]:
                _cache.update(at=time.time(), data=data)
                (SITE / "latest.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return _cache["data"]


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] == "/api/posts":
            body = json.dumps(get_data(), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), partial(Handler, directory=str(SITE)))
    print(f"Founder Pain Radar on http://localhost:{PORT}", flush=True)
    server.serve_forever()
