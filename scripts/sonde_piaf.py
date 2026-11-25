"""Sonde temporaire : où sont publiés les fichiers PIAF (prévision de pluie à 5 min) ?"""
import re, json, urllib.request, urllib.parse

def get(url, n=3000):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "radar-pluie"})
        with urllib.request.urlopen(req, timeout=30) as r:
            b = r.read()
            print(f"--- {url}\n    HTTP {r.status} {r.geturl()} {len(b)} o")
            return b.decode("utf-8", "replace")
    except Exception as e:
        print(f"--- {url}\n    ERREUR {e}")
        return ""

# 1. jeu de données data.gouv
for q in ["prevision-de-lame-deau-issue-du-modele-de-prevision-immediate-agregee-fusionnee"]:
    t = get(f"https://www.data.gouv.fr/api/1/datasets/{q}/")
    if t:
        d = json.loads(t)
        print("DESCRIPTION:", d.get("description", "")[:1500])
        for r in d.get("resources", []):
            print("RESSOURCE:", r.get("title"), r.get("format"), r.get("url"))
            print("   ", (r.get("description") or "")[:800])
t = get("https://www.data.gouv.fr/api/1/datasets/?q=PIAF&page_size=10")
if t:
    for d in json.loads(t).get("data", []):
        print("JEU:", d.get("title"), d.get("slug"))
        for r in d.get("resources", []):
            print("   RESSOURCE:", r.get("title"), r.get("url"))

# 2. stockage objet (S3) : dossiers récents et sous-dossiers
def s3_list(base, prefix, delim="/", maxk=1000):
    q = urllib.parse.urlencode({"list-type": "2", "prefix": prefix, "delimiter": delim, "max-keys": str(maxk)})
    t = get(f"{base}/?{q}")
    pre = re.findall(r"<Prefix>([^<]*)</Prefix>", t)
    keys = re.findall(r"<Key>([^<]*)</Key>", t)
    return [p for p in pre if p != prefix], keys

for base in ["https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net", "https://files.data.gouv.fr/meteofrance-pnt"]:
    tops, keys = s3_list(base, "")
    print("RACINE", base, tops[:50], keys[:20])
    for top in tops[:10]:
        sub, k = s3_list(base, top)
        print("  ", top, "->", sub[-8:], k[:5])
        if sub:
            last = sorted(sub)[-1]
            sub2, k2 = s3_list(base, last)
            print("     dernier", last, "->", sub2, k2[:5])
            for s in sub2:
                if "piaf" in s.lower():
                    sub3, k3 = s3_list(base, s, delim="")
                    print("       PIAF", s, k3[:60])
    # recherche directe d'un préfixe piaf
    for p in ["piaf/", "pnt/piaf/", "PIAF/"]:
        s, k = s3_list(base, p)
        print("  essai", p, s[:10], k[:10])
