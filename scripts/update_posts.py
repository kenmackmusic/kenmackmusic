"""Refresh posts.json from the Kenmack Music Blog's Substack feed.

Run daily by .github/workflows/update-posts.yml. It keeps the four newest
posts, always includes the pinned Featured post, and uses Ken's own images
for posts listed in IMAGE_OVERRIDES. If the feed can't be read, posts.json
is left exactly as it is, so the site keeps showing the last good list.
"""

import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

FEED_URL = "https://kenmackmusic.substack.com/feed"
OUT = Path(__file__).resolve().parent.parent / "posts.json"
SHOW = 4
FEATURED_SLUG = "grace-note"

# Posts whose image on this site should be Ken's own file rather than the feed's.
IMAGE_OVERRIDES = {
    "finding-humanity": ("images/blog-finding-humanity.jpg", None),
    "the-visit": ("images/blog-the-visit.jpg", "center 40%"),
    "grace-note": ("images/blog-grace-note.jpg", "center 22%"),
    "everybody-knows-her-name": ("images/blog-everybody-knows-her-name.jpg", "center 30%"),
}


def fetch_feed():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "kenmackmusic.com post updater"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def slug_of(link):
    return link.rstrip("/").split("/p/")[-1] if "/p/" in link else ""


def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    posts = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        subtitle = (item.findtext("description") or "").strip()
        when = parsedate_to_datetime(item.findtext("pubDate"))
        enclosure = item.find("enclosure")
        image = enclosure.get("url") if enclosure is not None else None
        slug = slug_of(link)
        position = None
        if slug in IMAGE_OVERRIDES:
            image, position = IMAGE_OVERRIDES[slug]
        post = {
            "title": title,
            "subtitle": subtitle,
            "date": f"{when:%b} {when.day}, {when.year}",
            "link": link,
            "image": image,
            "featured": slug == FEATURED_SLUG,
            "_when": when,
        }
        if position:
            post["imagePosition"] = position
        posts.append(post)
    return posts


def choose(posts):
    posts.sort(key=lambda p: p["_when"], reverse=True)
    featured = [p for p in posts if p["featured"]]
    shown = posts[:SHOW]
    if featured and featured[0] not in shown:
        shown = posts[: SHOW - 1] + featured[:1]
    for p in shown:
        p.pop("_when", None)
    return shown


def main():
    try:
        posts = parse(fetch_feed())
    except Exception as err:  # network or feed problem: keep the current file
        print(f"Feed not updated: {err}")
        return 0
    if not posts:
        print("Feed had no posts; leaving posts.json unchanged.")
        return 0
    shown = choose(posts)
    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    if old.get("posts") == shown:
        print("No new posts.")
        return 0
    OUT.write_text(json.dumps({"updated": datetime.utcnow().strftime("%Y-%m-%d"), "posts": shown}, indent=2) + "\n")
    print(f"posts.json updated with {len(shown)} posts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
