"""Sonde temporaire (6) : accès PIAF avec la clé du robot (clé jamais affichée) + liste des couvertures."""
import os, re, urllib.request

def get(url, headers=None):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "radar-pluie", **(headers or {})})
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read()
            print(f"--- {url}\n    HTTP {r.status} {len(b)} o")
            return b.decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        print(f"--- {url}\n    HTTP {e.code} : {e.read()[:300]!r}")
    except Exception as e:
        print(f"--- {url}\n    ERREUR {e}")
    return ""

key = os.environ.get("METEOFRANCE_KEY", "")
H = {"apikey": key}
for host in ("https://public-api.meteofrance.fr", "https://api.meteofrance.fr"):
    t = get(f"{host}/pro/piaf/1.0/wcs/MF-NWP-HIGHRES-PIAF-001-FRANCE-WCS/GetCapabilities?service=WCS&version=2.0.1&language=fre", H)
    if t:
        ids = re.findall(r"<(?:wcs:)?CoverageId>([^<]+)<", t)
        print("NB couvertures:", len(ids))
        for i in ids[:15] + ids[-15:]:
            print("  ", i)
        # échantillon de l'en-tête
        print(t[:1500])
        if ids:
            d = get(f"{host}/pro/piaf/1.0/wcs/MF-NWP-HIGHRES-PIAF-001-FRANCE-WCS/DescribeCoverage?service=WCS&version=2.0.1&coverageID={ids[-1]}", H)
            print(d[:5000])
        break
# contrôle : la clé marche-t-elle toujours pour AROME-PI ?
get("https://public-api.meteofrance.fr/public/aromepi/1.0/wcs/MF-NWP-HIGHRES-AROMEPI-001-FRANCE-WCS/GetCapabilities?service=WCS&version=2.0.1&language=fre", H)
