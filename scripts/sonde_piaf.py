"""Sonde temporaire (2) : où sont publiés les fichiers PIAF ?"""
import re, json, urllib.request, urllib.parse

def get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "radar-pluie"})
        with urllib.request.urlopen(req, timeout=30) as r:
            b = r.read()
            print(f"--- {url}\n    HTTP {r.status} {r.geturl()} {len(b)} o")
            return b.decode("utf-8", "replace")
    except Exception as e:
        print(f"--- {url}\n    ERREUR {e}")
        return ""

ORG = "534fff81a3a7292c64a77e5c"  # Météo-France sur data.gouv (vérifié plus bas)
for q in ["lame d'eau", "prevision immediate", "PIAF lame", "agregee fusionnee"]:
    t = get("https://www.data.gouv.fr/api/1/datasets/?" + urllib.parse.urlencode({"q": q, "page_size": 20}))
    if not t:
        continue
    for d in json.loads(t).get("data", []):
        org = (d.get("organization") or {}).get("name", "")
        if "france" not in org.lower() and "PIAF" not in d.get("title", ""):
            continue
        print("JEU:", d.get("title"), "|", d.get("slug"), "|", org, "| id", d.get("id"))
        if "fusionn" in d.get("title", "").lower() or "piaf" in d.get("title", "").lower():
            print("  DESC:", (d.get("description") or "")[:2000])
            for r in d.get("resources", []):
                print("  RESSOURCE:", r.get("title"), r.get("format"), r.get("url"))
                print("     ", (r.get("description") or "")[:1500])
