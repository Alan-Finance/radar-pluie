"""Sonde temporaire (5) : documentation et conditions de l'API PIAF ; test d'accès avec la clé actuelle (clé jamais affichée)."""
import json, os, urllib.request

def get(url, headers=None, n=6000):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "radar-pluie", **(headers or {})})
        with urllib.request.urlopen(req, timeout=40) as r:
            b = r.read()
            print(f"--- {url}\n    HTTP {r.status} {len(b)} o")
            return b.decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        print(f"--- {url}\n    HTTP {e.code} : {e.read()[:400]!r}")
    except Exception as e:
        print(f"--- {url}\n    ERREUR {e}")
    return ""

B = "https://portail-api.meteofrance.fr/api/am/devportal/v3/apis/aa174208-b051-4c95-af8f-dd52241a4d06"
a = get(B)
if a:
    a = json.loads(a)
    for k in ("name", "context", "tiers", "policies", "visibility", "businessInformation", "categories", "tags", "additionalProperties"):
        print(k, ":", str(a.get(k))[:800])
for doc in ("edd14ae2-9bba-4aba-ab14-0b90677c7a2f", "78c21bc6-e173-43f6-a48b-cf47cbbbd89c"):
    t = get(f"{B}/documents/{doc}/content")
    print(t[:6000])
key = os.environ.get("METEOFRANCE_KEY", "")
print("clé présente :", bool(key))
for base in ("https://public-api.meteofrance.fr/pro/piaf/1.0", "https://public-api.meteofrance.fr/public/piaf/1.0"):
    t = get(f"{base}/wcs/MF-NWP-HIGHRES-PIAF-001-FRANCE-WCS/GetCapabilities?service=WCS&version=2.0.1&language=fre", {"apikey": key})
    print(t[:4000])
