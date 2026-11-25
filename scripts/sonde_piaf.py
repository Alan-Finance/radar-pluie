"""Sonde temporaire (4) : l'API PIAF sur le portail Météo-France (catalogue public, sans clé)."""
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

B = "https://portail-api.meteofrance.fr/api/am/devportal/v3"
t = get(f"{B}/apis?limit=100")
apis = json.loads(t).get("list", []) if t else []
for a in apis:
    print("API:", a.get("name"), "|", a.get("context"), "|", a.get("version"), "|", a.get("id"))
for a in apis:
    n = (a.get("name", "") + a.get("context", "")).lower()
    if "immediate" in n or "piaf" in n or "precipitation" in n:
        print("=== ", a.get("name"), a.get("context"))
        print((a.get("description") or "")[:1500])
        sw = get(f"{B}/apis/{a['id']}/swagger")
        if sw:
            try:
                s = json.loads(sw)
                print("SERVERS:", s.get("servers"), s.get("host"), s.get("basePath"))
                for p, ops in s.get("paths", {}).items():
                    for m, op in ops.items():
                        if not isinstance(op, dict):
                            continue
                        print(f"  {m.upper()} {p} : {op.get('summary','')}")
                        for prm in op.get("parameters", []):
                            print(f"      param {prm.get('name')} ({prm.get('in')}) req={prm.get('required')} : {str(prm.get('description',''))[:200]} {str(prm.get('schema',''))[:200]}")
            except Exception as e:
                print("swagger illisible", e, sw[:500])
        d = get(f"{B}/apis/{a['id']}/documents")
        if d:
            for doc in json.loads(d).get("list", []):
                print("  DOC:", doc.get("name"), doc.get("documentId"), doc.get("sourceType"))
