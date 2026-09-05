#!/usr/bin/env python3
"""Fetch recent natural-disaster news, cluster stories, write news-map.html."""

from __future__ import annotations

import email.utils
import html
import json
import re
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

TODAY = datetime.now(timezone.utc).date()
WINDOW_DAYS = 7
UA = "news-atlas/0.1 (personal map; +https://github.com/Minlos)"
FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("The Guardian", "https://www.theguardian.com/world/rss"),
    ("Guardian environment", "https://www.theguardian.com/environment/rss"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("NPR World", "https://feeds.npr.org/1004/rss.xml"),
    ("NYT World", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
    ("France 24", "https://www.france24.com/en/rss"),
    ("DW", "https://rss.dw.com/rdf/rss-en-world"),
    ("ReliefWeb", "https://reliefweb.int/updates/rss.xml?disaster_type[]=wild-fire&disaster_type[]=flood&disaster_type[]=earthquake&disaster_type[]=tropical-cyclone&disaster_type[]=land-slide&disaster_type[]=volcano&disaster_type[]=drought&disaster_type[]=tsunami"),
]

# City first, then country. Longer names win via sorted match.
PLACES = [
    ("Washington", 38.9072, -77.0369, "Americas"),
    ("New York", 40.7128, -74.0060, "Americas"),
    ("Los Angeles", 34.0522, -118.2437, "Americas"),
    ("Mexico City", 19.4326, -99.1332, "Americas"),
    ("Buenos Aires", -34.6037, -58.3816, "Americas"),
    ("Sao Paulo", -23.5505, -46.6333, "Americas"),
    ("Rio de Janeiro", -22.9068, -43.1729, "Americas"),
    ("Brasilia", -15.7975, -47.8919, "Americas"),
    ("Toronto", 43.6532, -79.3832, "Americas"),
    ("Ottawa", 45.4215, -75.6972, "Americas"),
    ("Havana", 23.1136, -82.3666, "Americas"),
    ("Bogota", 4.7110, -74.0721, "Americas"),
    ("Caracas", 10.4806, -66.9036, "Americas"),
    ("Lima", -12.0464, -77.0428, "Americas"),
    ("Santiago", -33.4489, -70.6693, "Americas"),
    ("London", 51.5074, -0.1278, "Europe"),
    ("Paris", 48.8566, 2.3522, "Europe"),
    ("Berlin", 52.5200, 13.4050, "Europe"),
    ("Brussels", 50.8503, 4.3517, "Europe"),
    ("Rome", 41.9028, 12.4964, "Europe"),
    ("Madrid", 40.4168, -3.7038, "Europe"),
    ("Barcelona", 41.3874, 2.1686, "Europe"),
    ("Lisbon", 38.7223, -9.1393, "Europe"),
    ("Amsterdam", 52.3676, 4.9041, "Europe"),
    ("Vienna", 48.2082, 16.3738, "Europe"),
    ("Warsaw", 52.2297, 21.0122, "Europe"),
    ("Prague", 50.0755, 14.4378, "Europe"),
    ("Budapest", 47.4979, 19.0402, "Europe"),
    ("Athens", 37.9838, 23.7275, "Europe"),
    ("Stockholm", 59.3293, 18.0686, "Europe"),
    ("Oslo", 59.9139, 10.7522, "Europe"),
    ("Helsinki", 60.1699, 24.9384, "Europe"),
    ("Copenhagen", 55.6761, 12.5683, "Europe"),
    ("Dublin", 53.3498, -6.2603, "Europe"),
    ("Zurich", 47.3769, 8.5417, "Europe"),
    ("Geneva", 46.2044, 6.1432, "Europe"),
    ("Kyiv", 50.4501, 30.5234, "Europe"),
    ("Kiev", 50.4501, 30.5234, "Europe"),
    ("Moscow", 55.7558, 37.6173, "Europe"),
    ("St Petersburg", 59.9311, 30.3609, "Europe"),
    ("Istanbul", 41.0082, 28.9784, "Europe"),
    ("Ankara", 39.9334, 32.8597, "Middle East"),
    ("Tel Aviv", 32.0853, 34.7818, "Middle East"),
    ("Jerusalem", 31.7683, 35.2137, "Middle East"),
    ("Gaza", 31.5017, 34.4668, "Middle East"),
    ("Ramallah", 31.9074, 35.2044, "Middle East"),
    ("Beirut", 33.8938, 35.5018, "Middle East"),
    ("Damascus", 33.5138, 36.2765, "Middle East"),
    ("Amman", 31.9454, 35.9284, "Middle East"),
    ("Baghdad", 33.3152, 44.3661, "Middle East"),
    ("Tehran", 35.6892, 51.3890, "Middle East"),
    ("Riyadh", 24.7136, 46.6753, "Middle East"),
    ("Jeddah", 21.4858, 39.1925, "Middle East"),
    ("Doha", 25.2854, 51.5310, "Middle East"),
    ("Abu Dhabi", 24.4539, 54.3773, "Middle East"),
    ("Dubai", 25.2048, 55.2708, "Middle East"),
    ("Cairo", 30.0444, 31.2357, "Middle East"),
    ("Sanaa", 15.3694, 44.1910, "Middle East"),
    ("Tripoli", 32.8872, 13.1913, "Middle East"),
    ("Tunis", 36.8065, 10.1815, "Africa"),
    ("Algiers", 36.7538, 3.0588, "Africa"),
    ("Rabat", 34.0209, -6.8416, "Africa"),
    ("Casablanca", 33.5731, -7.5898, "Africa"),
    ("Lagos", 6.5244, 3.3792, "Africa"),
    ("Abuja", 9.0765, 7.3986, "Africa"),
    ("Nairobi", -1.2921, 36.8219, "Africa"),
    ("Addis Ababa", 9.0320, 38.7469, "Africa"),
    ("Khartoum", 15.5007, 32.5599, "Africa"),
    ("Johannesburg", -26.2041, 28.0473, "Africa"),
    ("Cape Town", -33.9249, 18.4241, "Africa"),
    ("Kinshasa", -4.4419, 15.2663, "Africa"),
    ("Mogadishu", 2.0469, 45.3182, "Africa"),
    ("Beijing", 39.9042, 116.4074, "Asia"),
    ("Shanghai", 31.2304, 121.4737, "Asia"),
    ("Hong Kong", 22.3193, 114.1694, "Asia"),
    ("Taipei", 25.0330, 121.5654, "Asia"),
    ("Tokyo", 35.6762, 139.6503, "Asia"),
    ("Osaka", 34.6937, 135.5023, "Asia"),
    ("Seoul", 37.5665, 126.9780, "Asia"),
    ("Pyongyang", 39.0392, 125.7625, "Asia"),
    ("New Delhi", 28.6139, 77.2090, "Asia"),
    ("Delhi", 28.6139, 77.2090, "Asia"),
    ("Mumbai", 19.0760, 72.8777, "Asia"),
    ("Islamabad", 33.6844, 73.0479, "Asia"),
    ("Karachi", 24.8607, 67.0011, "Asia"),
    ("Lahore", 31.5204, 74.3587, "Asia"),
    ("Kabul", 34.5553, 69.2075, "Asia"),
    ("Islamabad", 33.6844, 73.0479, "Asia"),
    ("Dhaka", 23.8103, 90.4125, "Asia"),
    ("Bangkok", 13.7563, 100.5018, "Asia"),
    ("Hanoi", 21.0278, 105.8342, "Asia"),
    ("Jakarta", -6.2088, 106.8456, "Asia"),
    ("Manila", 14.5995, 120.9842, "Asia"),
    ("Singapore", 1.3521, 103.8198, "Asia"),
    ("Sydney", -33.8688, 151.2093, "Asia"),
    ("Melbourne", -37.8136, 144.9631, "Asia"),
    ("Canberra", -35.2809, 149.1300, "Asia"),
    ("Wellington", -41.2865, 174.7762, "Asia"),
    ("Kathmandu", 27.7172, 85.3240, "Asia"),
    ("Rasuwa", 28.1750, 85.3300, "Asia"),
    ("Nepal", 27.7172, 85.3240, "Asia"),
    ("California", 36.7783, -119.4179, "Americas"),
    ("Hawaii", 19.8968, -155.5828, "Americas"),
    ("Alberta", 53.9333, -116.5769, "Americas"),
    ("British Columbia", 53.7267, -127.6476, "Americas"),
    ("Greece", 37.9838, 23.7275, "Europe"),
    ("Portugal", 38.7223, -9.1393, "Europe"),
    ("Chile", -33.4489, -70.6693, "Americas"),
    ("Haiti", 18.5944, -72.3074, "Americas"),
    ("El Salvador", 13.7942, -88.8965, "Americas"),
    ("Libya", 32.8872, 13.1913, "Middle East"),
    ("Siberia", 60.0000, 100.0000, "Asia"),
    ("United States", 38.9072, -77.0369, "Americas"),
    ("America", 38.9072, -77.0369, "Americas"),
    ("Canada", 45.4215, -75.6972, "Americas"),
    ("Mexico", 19.4326, -99.1332, "Americas"),
    ("Brazil", -15.7975, -47.8919, "Americas"),
    ("Argentina", -34.6037, -58.3816, "Americas"),
    ("Venezuela", 10.4806, -66.9036, "Americas"),
    ("Colombia", 4.7110, -74.0721, "Americas"),
    ("United Kingdom", 51.5074, -0.1278, "Europe"),
    ("Britain", 51.5074, -0.1278, "Europe"),
    ("England", 51.5074, -0.1278, "Europe"),
    ("France", 48.8566, 2.3522, "Europe"),
    ("Germany", 52.5200, 13.4050, "Europe"),
    ("Italy", 41.9028, 12.4964, "Europe"),
    ("Spain", 40.4168, -3.7038, "Europe"),
    ("Poland", 52.2297, 21.0122, "Europe"),
    ("Ukraine", 50.4501, 30.5234, "Europe"),
    ("Russia", 55.7558, 37.6173, "Europe"),
    ("Turkey", 39.9334, 32.8597, "Middle East"),
    ("Israel", 31.7683, 35.2137, "Middle East"),
    ("Palestine", 31.9074, 35.2044, "Middle East"),
    ("Lebanon", 33.8938, 35.5018, "Middle East"),
    ("Syria", 33.5138, 36.2765, "Middle East"),
    ("Iraq", 33.3152, 44.3661, "Middle East"),
    ("Iran", 35.6892, 51.3890, "Middle East"),
    ("Saudi Arabia", 24.7136, 46.6753, "Middle East"),
    ("Yemen", 15.3694, 44.1910, "Middle East"),
    ("Qatar", 25.2854, 51.5310, "Middle East"),
    ("Egypt", 30.0444, 31.2357, "Middle East"),
    ("Sudan", 15.5007, 32.5599, "Africa"),
    ("Nigeria", 9.0765, 7.3986, "Africa"),
    ("Kenya", -1.2921, 36.8219, "Africa"),
    ("Ethiopia", 9.0320, 38.7469, "Africa"),
    ("South Africa", -26.2041, 28.0473, "Africa"),
    ("Morocco", 34.0209, -6.8416, "Africa"),
    ("China", 39.9042, 116.4074, "Asia"),
    ("Taiwan", 25.0330, 121.5654, "Asia"),
    ("Japan", 35.6762, 139.6503, "Asia"),
    ("South Korea", 37.5665, 126.9780, "Asia"),
    ("North Korea", 39.0392, 125.7625, "Asia"),
    ("India", 28.6139, 77.2090, "Asia"),
    ("Pakistan", 33.6844, 73.0479, "Asia"),
    ("Afghanistan", 34.5553, 69.2075, "Asia"),
    ("Bangladesh", 23.8103, 90.4125, "Asia"),
    ("Myanmar", 16.8409, 96.1735, "Asia"),
    ("Thailand", 13.7563, 100.5018, "Asia"),
    ("Vietnam", 21.0278, 105.8342, "Asia"),
    ("Indonesia", -6.2088, 106.8456, "Asia"),
    ("Philippines", 14.5995, 120.9842, "Asia"),
    ("Australia", -35.2809, 149.1300, "Asia"),
]

CITIES = {n for n, _, _, _ in PLACES if n not in {
    "United States", "America", "Canada", "Mexico", "Brazil", "Argentina", "Venezuela",
    "Colombia", "United Kingdom", "Britain", "England", "France", "Germany", "Italy",
    "Spain", "Poland", "Ukraine", "Russia", "Turkey", "Israel", "Palestine", "Lebanon",
    "Syria", "Iraq", "Iran", "Saudi Arabia", "Yemen", "Qatar", "Egypt", "Sudan",
    "Nigeria", "Kenya", "Ethiopia", "South Africa", "Morocco", "China", "Taiwan",
    "Japan", "South Korea", "North Korea", "India", "Pakistan", "Afghanistan",
    "Bangladesh", "Myanmar", "Thailand", "Vietnam", "Indonesia", "Philippines",
    "Australia", "Nepal", "California", "Hawaii", "Alberta", "British Columbia",
    "Greece", "Portugal", "Chile", "Haiti", "El Salvador", "Libya", "Siberia",
}}

STOP = {
    "the", "a", "an", "and", "or", "of", "in", "on", "for", "to", "from", "after",
    "with", "as", "at", "by", "over", "into", "says", "say", "said", "against",
    "new", "more", "than", "its", "his", "her", "their", "who", "after", "under",
    "about", "have", "has", "will", "been", "were", "this", "that", "with", "from",
    "world", "news", "video", "live", "update", "updates", "could", "would", "over",
}

HAZARDS = [
    ("wildfire", re.compile(
        r"\bwildfires?\b|\bbushfires?\b|\bforest fires?\b|\bwild fire\b|"
        r"\bлесн\w{0,10}\s+пожар\w*|\bпожар\w*\s+в\s+лес\w*", re.I)),
    ("flood", re.compile(
        r"\bfloods?\b|\bflooding\b|\bflooded\b|\bflash floods?\b|"
        r"\bнаводнен\w*|\bпаводок\b", re.I)),
    ("earthquake", re.compile(
        r"\bearthquakes?\b|\baftershocks?\b|\bземлетрясен\w*|"
        r"\b(?<!earth)quakes?\b", re.I)),
    ("cyclone", re.compile(
        r"\bhurricanes?\b|\btyphoons?\b|\bcyclones?\b|\btropical storms?\b|"
        r"\bураган\w*|\bтайфун\w*", re.I)),
    ("tornado", re.compile(r"\btornadoes?\b|\btwisters?\b", re.I)),
    ("volcano", re.compile(r"\bvolcanos?\b|\bvolcanoes?\b|\beruptions?\b|\bизвержен\w*", re.I)),
    ("landslide", re.compile(r"\blandslides?\b|\bmudslides?\b|\bоползн\w*", re.I)),
    ("tsunami", re.compile(r"\btsunamis?\b|\bцунами\b", re.I)),
    ("drought", re.compile(r"\bdroughts?\b|\bзасух\w*", re.I)),
    ("heatwave", re.compile(r"\bheatwaves?\b|\bheat waves?\b|\bжара\b", re.I)),
    ("avalanche", re.compile(r"\bavalanches?\b|\bлавин\w*", re.I)),
]

HAZARD_COLOR = {
    "wildfire": "#d4784a",
    "flood": "#6a9ec4",
    "earthquake": "#c4898a",
    "cyclone": "#8aa0c4",
    "tornado": "#9b8ac4",
    "volcano": "#c45a3a",
    "landslide": "#9b8a6a",
    "tsunami": "#4a7a8c",
    "drought": "#d4b483",
    "heatwave": "#d49a5a",
    "avalanche": "#c4d0d8",
}


def classify_hazard(text: str) -> str | None:
    for name, rx in HAZARDS:
        if rx.search(text or ""):
            return name
    return None

PLACE_BY_NAME = {n.lower(): (n, lat, lng, region) for n, lat, lng, region in PLACES}
PLACE_NAMES = sorted(PLACE_BY_NAME, key=len, reverse=True)


def fetch(url: str) -> bytes | None:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml"})
    try:
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            return r.read()
    except Exception as e:
        print(f"  fail {url}: {e}")
        return None


def parse_date(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        ts = email.utils.parsedate_to_datetime(raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.replace("Z", "+0000"), fmt).astimezone(timezone.utc)
        except Exception:
            continue
    return None


def local_name(tag: str) -> str:
    return tag.split("}")[-1]


def item_text(el: ET.Element, names: list[str]) -> str:
    for child in list(el):
        if local_name(child.tag) in names and (child.text or "").strip():
            return child.text.strip()
    return ""


def parse_feed(blob: bytes, source: str) -> list[dict]:
    try:
        root = ET.fromstring(blob)
    except ET.ParseError as e:
        print(f"  xml {source}: {e}")
        return []
    items = [el for el in root.iter() if local_name(el.tag) in ("item", "entry")]
    out = []
    for el in items:
        title = re.sub(r"\s+", " ", item_text(el, ["title"])).strip()
        if not title:
            continue
        link = item_text(el, ["link"])
        if not link:
            for child in el:
                if local_name(child.tag) == "link" and child.get("href"):
                    link = child.get("href")
                    break
        summary = re.sub(r"<[^>]+>", " ", item_text(el, ["description", "summary", "encoded"]))
        summary = re.sub(r"\s+", " ", summary).strip()[:400]
        pub = parse_date(item_text(el, ["pubDate", "date", "published", "updated"]))
        out.append({"title": title, "link": link, "summary": summary, "source": source, "when": pub})
    return out


def locate(text: str) -> dict | None:
    blob = " " + text + " "
    hits = []
    lower = blob.lower()
    for name in PLACE_NAMES:
        if re.search(r"[^a-z]" + re.escape(name) + r"[^a-z]", lower):
            canon, lat, lng, region = PLACE_BY_NAME[name]
            pos = lower.find(name)
            city = canon in CITIES
            hits.append((0 if city else 1, pos, -len(name), canon, lat, lng, region))
    if not hits:
        return None
    hits.sort()
    _, _, _, canon, lat, lng, region = hits[0]
    return {"name": canon, "lat": lat, "lng": lng, "region": region}


def tokens(title: str) -> set[str]:
    words = re.findall(r"[A-Za-z][A-Za-z'-]{3,}", title)
    return {w.lower() for w in words if w.lower() not in STOP}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cluster(articles: list[dict]) -> list[list[int]]:
    n = len(articles)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    toks = [tokens(a["title"]) for a in articles]
    for i in range(n):
        for j in range(i + 1, n):
            same_place = (
                articles[i]["place"]
                and articles[j]["place"]
                and articles[i]["place"]["name"] == articles[j]["place"]["name"]
            )
            same_hazard = articles[i].get("hazard") and articles[i]["hazard"] == articles[j].get("hazard")
            jac = jaccard(toks[i], toks[j])
            overlap = toks[i] & toks[j]
            if (same_hazard and same_place) or (same_hazard and jac >= 0.28) or jac >= 0.4 or (
                same_place and jac >= 0.18
            ) or (len(overlap) >= 3 and jac >= 0.22):
                union(i, j)
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return list(groups.values())


def cluster_title(members: list[dict]) -> str:
    members = sorted(members, key=lambda a: len(a["title"]))
    return members[0]["title"]


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Disaster atlas — wildfires, floods, quakes</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    :root {
      --ink: #efe6d6; --muted: #9b917f; --paper: #101218;
      --panel: rgba(22, 25, 34, .92); --line: #323848; --accent: #d4b07a;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; margin: 0; background: var(--paper); color: var(--ink);
      font-family: Georgia, "Iowan Old Style", Palatino, serif; }
    #map { position: absolute; inset: 0; }
    .leaflet-container { background: #101218; font-family: inherit; }
    .leaflet-tile-pane { filter: invert(1) hue-rotate(180deg) brightness(.92) contrast(.88) saturate(.3); }
    .panel {
      position: absolute; z-index: 500; top: 14px; left: 14px;
      width: min(400px, calc(100vw - 28px));
      background: var(--panel); backdrop-filter: blur(12px);
      border: 1px solid var(--line); border-radius: 16px;
      padding: 18px 18px 14px; box-shadow: 0 18px 50px rgba(0,0,0,.5);
      max-height: calc(100vh - 28px); overflow: auto;
    }
    h1 { font-size: 1.28rem; font-weight: 600; margin: 0 2px 2px; }
    .sub { color: var(--muted); font-size: .8rem; line-height: 1.5; margin: 0 0 14px; }
    .legend { display: flex; flex-wrap: wrap; gap: 8px 14px; margin-top: 12px; font-size: .75rem; color: var(--muted); }
    .swatch { width: 9px; height: 9px; border-radius: 50%; display: inline-block; margin-right: 5px; vertical-align: middle; }
    label { display: block; font-size: .68rem; letter-spacing: .12em; text-transform: uppercase;
      color: var(--muted); margin: 11px 0 5px; }
    select, button {
      width: 100%; background: #12141c; color: var(--ink); border: 1px solid var(--line);
      border-radius: 8px; padding: 8px 10px; font: inherit; font-size: .86rem;
    }
    .row { display: flex; gap: 8px; margin-top: 10px; }
    .row button { cursor: pointer; }
    .row button:hover { border-color: var(--accent); color: var(--accent); }
    .count { color: var(--accent); font-variant-numeric: tabular-nums; }
    .leaflet-popup-content-wrapper {
      background: #1a1d27; color: var(--ink); border-radius: 12px;
      border: 1px solid var(--line); max-width: 340px;
    }
    .leaflet-popup-tip { background: #1a1d27; }
    .leaflet-popup-content { margin: 13px 15px; font-size: .9rem; line-height: 1.45; }
    .popup-kicker { font-size: .68rem; letter-spacing: .04em; color: var(--accent); margin: 0 0 5px; }
    .popup-title { font-size: 1.02rem; margin: 0 0 8px; }
    .popup-item { margin: 0 0 7px; }
    .popup-item a { color: var(--ink); }
    .popup-src { color: var(--muted); font-size: .75rem; }
    .leaflet-control-attribution { background: rgba(16,18,24,.75) !important; color: #6e675c !important; }
    .leaflet-control-attribution a { color: #8e8576 !important; }
    @media (max-width: 640px) {
      .panel { top: auto; bottom: 10px; left: 10px; right: 10px; width: auto; max-height: 46vh; }
    }
  </style>
</head>
<body>
  <div id="map"></div>
  <aside class="panel">
    <h1>Disaster atlas</h1>
    <p class="sub"><span class="count" id="count"></span> natural-disaster stories in the last 7 days (forest fires, floods, quakes, storms). Pins are story groups.</p>
    <label for="hazard">Hazard</label>
    <select id="hazard"></select>
    <label for="region">Region</label>
    <select id="region"></select>
    <label for="place">Place</label>
    <select id="place"></select>
    <div class="row">
      <button type="button" id="world">World</button>
      <button type="button" id="asia">Asia</button>
      <button type="button" id="americas">Americas</button>
    </div>
    <div class="legend" id="legend"></div>
  </aside>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const TODAY = __TODAY__;
    const CLUSTERS = __CLUSTERS__;
    const HAZARD_COLOR = __HAZARD_COLOR__;
    const map = L.map("map", { zoomControl: true, minZoom: 2 }).setView([20, 15], 2);
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", {
      attribution: "Tiles &copy; Esri · wires + ReliefWeb",
      maxZoom: 19
    }).addTo(map);
    const layer = L.layerGroup().addTo(map);
    const hazards = ["all"].concat([...new Set(CLUSTERS.map(c => c.hazard))].sort());
    const hazardSel = document.getElementById("hazard");
    hazardSel.innerHTML = hazards.map(h => '<option value="' + h + '">' + (h === "all" ? "All hazards" : h) + "</option>").join("");
    const regions = ["all"].concat([...new Set(CLUSTERS.map(c => c.region))].sort());
    const regionSel = document.getElementById("region");
    regionSel.innerHTML = regions.map(r => '<option value="' + r + '">' + (r === "all" ? "All regions" : r) + "</option>").join("");
    const placeSel = document.getElementById("place");
    document.getElementById("legend").innerHTML = Object.keys(HAZARD_COLOR).filter(h => CLUSTERS.some(c => c.hazard === h)).map(h =>
      '<span><i class="swatch" style="background:' + HAZARD_COLOR[h] + '"></i>' + h + "</span>"
    ).join("");
    function filtered() {
      const hazard = hazardSel.value, region = regionSel.value, place = placeSel.value;
      return CLUSTERS.filter(c => {
        if (hazard !== "all" && c.hazard !== hazard) return false;
        if (region !== "all" && c.region !== region) return false;
        if (place !== "all" && c.place !== place) return false;
        return true;
      });
    }
    function placesFor() {
      const names = [...new Set(filtered().map(c => c.place))].sort();
      const keep = placeSel.value;
      placeSel.innerHTML = '<option value="all">All places</option>' + names.map(n => '<option>' + n + "</option>").join("");
      if (names.indexOf(keep) !== -1) placeSel.value = keep;
    }
    function render() {
      layer.clearLayers();
      const shown = filtered();
      document.getElementById("count").textContent = shown.length;
      shown.forEach(c => {
        const r = Math.min(16, 7 + c.articles.length * 1.6);
        const m = L.circleMarker([c.lat, c.lng], {
          radius: r, color: "#0b0c10", weight: 1,
          fillColor: HAZARD_COLOR[c.hazard] || "#d4b483", fillOpacity: 0.92
        });
        const items = c.articles.map(a =>
          '<p class="popup-item"><a href="' + a.link + '" target="_blank" rel="noopener">' + a.title +
          '</a><br><span class="popup-src">' + a.source + (a.today ? " · today" : "") + "</span></p>"
        ).join("");
        m.bindPopup(
          '<p class="popup-kicker">' + c.hazard + " · " + c.place + " · " + c.articles.length + " headline" + (c.articles.length > 1 ? "s" : "") + "</p>" +
          '<p class="popup-title">' + c.title + "</p>" + items
        );
        m.addTo(layer);
      });
    }
    hazardSel.addEventListener("change", function () { placesFor(); render(); });
    regionSel.addEventListener("change", function () { placesFor(); render(); });
    placeSel.addEventListener("change", render);
    document.getElementById("world").onclick = function () { map.setView([20, 15], 2); };
    document.getElementById("asia").onclick = function () { map.setView([28, 90], 4); };
    document.getElementById("americas").onclick = function () { map.setView([15, -80], 3); };
    placesFor();
    render();
  </script>
</body>
</html>
"""


def main() -> None:
    print(f"today UTC {TODAY.isoformat()}")
    articles = []
    for name, url in FEEDS:
        print(f"fetch {name}")
        blob = fetch(url)
        if not blob:
            continue
        got = parse_feed(blob, name)
        print(f"  {len(got)} items")
        articles.extend(got)

    cutoff = TODAY - timedelta(days=WINDOW_DAYS)
    disasters = []
    for a in articles:
        if a["when"] and a["when"].date() < cutoff:
            continue
        text = a["title"] + " " + a["summary"]
        hazard = classify_hazard(text)
        if not hazard:
            continue
        a["hazard"] = hazard
        a["today"] = bool(a["when"] and a["when"].date() == TODAY)
        disasters.append(a)
    print(f"disasters in {WINDOW_DAYS}d: {len(disasters)} (today {sum(1 for a in disasters if a['today'])})")

    located = []
    skipped = 0
    for a in disasters:
        place = locate(a["title"] + " " + a["summary"])
        if not place:
            skipped += 1
            continue
        a["place"] = place
        located.append(a)
    print(f"located {len(located)}, no place {skipped}")
    print("hazards", Counter(a["hazard"] for a in located))

    groups = cluster(located)
    clusters = []
    for idxs in groups:
        members = [located[i] for i in idxs]
        places = Counter(m["place"]["name"] for m in members)
        place_name = places.most_common(1)[0][0]
        place = next(m["place"] for m in members if m["place"]["name"] == place_name)
        seen = set()
        uniq = []
        for m in members:
            key = re.sub(r"\W+", "", m["title"].lower())[:80]
            if key in seen:
                continue
            seen.add(key)
            uniq.append({"title": m["title"], "link": m["link"], "source": m["source"], "today": m["today"]})
        hazards = Counter(m["hazard"] for m in members)
        clusters.append({
            "title": cluster_title(members),
            "place": place["name"],
            "lat": place["lat"],
            "lng": place["lng"],
            "region": place["region"],
            "hazard": hazards.most_common(1)[0][0],
            "articles": uniq,
        })
    clusters.sort(key=lambda c: (-len(c["articles"]), c["place"]))
    print(f"clusters {len(clusters)}")

    out = HTML.replace("__TODAY__", json.dumps(TODAY.isoformat()))
    out = out.replace("__CLUSTERS__", json.dumps(clusters, ensure_ascii=False))
    out = out.replace("__HAZARD_COLOR__", json.dumps(HAZARD_COLOR))
    path = "/Users/minlos/Downloads/news-atlas/news-map.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
