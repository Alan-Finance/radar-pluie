"""Sonde temporaire (3) : où sont publiés les fichiers PIAF ?"""
import json, urllib.request, urllib.parse

def get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "radar-pluie", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            b = r.read()
            print(f"--- {url}\n    HTTP {r.status} {len(b)} o")
            return b.decode("utf-8", "replace")
    except Exception as e:
        print(f"--- {url}\n    ERREUR {e}")
        return ""

found = []
for page in range(1, 6):
    t = get(f"https://www.data.gouv.fr/api/1/organizations/meteo-france/datasets/?page_size=100&page={page}")
    if not t:
        break
    d = json.loads(t)
    data = d.get("data", [])
    for x in data:
        print("  -", x.get("title"), "|", x.get("slug"))
        if any(w in x.get("title", "").lower() for w in ("fusionn", "piaf", "immédiate", "immediate")):
            found.append(x)
    if not data:
        break
for x in found:
    print("=== JEU:", x.get("title"), x.get("id"), x.get("slug"))
    print("DESC:", (x.get("description") or "")[:2500])
    t = get(f"https://www.data.gouv.fr/api/1/datasets/{x['id']}/")
    for r in (json.loads(t).get("resources", []) if t else x.get("resources", [])):
        print("RESSOURCE:", r.get("title"), r.get("format"), r.get("url"))
        print("   ", (r.get("description") or "")[:2000])
