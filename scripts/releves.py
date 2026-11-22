"""Relevés de pluie des stations Météo-France proches du lieu (config.json).

Source : API « Paquet Observations » de Météo-France (DPPaquetObs), observations horaires de toutes les stations.
Chaque exécution du robot complète les heures manquantes des dernières 24 h (l'API garde 24 h), puis
recalcule les cumuls par jour (heure de Paris). L'historique est gardé d'une exécution à l'autre via le site publié.

Sortie : data/releves.json
"""

from __future__ import annotations

import csv
import io
import json
import math
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

OBS_URL = "https://public-api.meteofrance.fr/public/DPPaquetObs/v2/paquet/stations/horaire"
LIST_URL = "https://public-api.meteofrance.fr/public/DPPaquetObs/v2/liste-stations"
PARIS = ZoneInfo("Europe/Paris")
KEEP_HOURS = 72
KEEP_DAYS = 62
MAX_REQUESTS_PER_RUN = 26


def distance_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _num(v):
    return float(v) if isinstance(v, (int, float)) else None


def station_names(session: requests.Session, log) -> dict[str, str]:
    """Identifiant -> nom de la station (liste officielle, CSV ou JSON)."""
    try:
        r = session.get(LIST_URL, timeout=60)
        if not r.ok:
            log(f"Relevés : liste des stations HTTP {r.status_code}")
            return {}
        text = r.text
        names: dict[str, str] = {}
        if text.lstrip().startswith("[") or text.lstrip().startswith("{"):
            data = r.json()
            rows = data if isinstance(data, list) else data.get("stations", [])
            for row in rows:
                sid = str(row.get("id") or row.get("Id_station") or row.get("id_station") or "")
                nom = row.get("name") or row.get("Nom_usuel") or row.get("nom")
                if sid and nom:
                    names[sid] = str(nom).title()
        else:
            sample = text[:2000]
            delim = ";" if sample.count(";") > sample.count(",") else ","
            for row in csv.DictReader(io.StringIO(text), delimiter=delim):
                keys = {k.lower().strip(): v for k, v in row.items() if k}
                sid = keys.get("id_station") or keys.get("id") or ""
                nom = keys.get("nom_usuel") or keys.get("nom") or keys.get("name")
                if sid and nom:
                    names[sid.strip()] = nom.strip().title()
        log(f"Relevés : {len(names)} noms de stations")
        return names
    except Exception as exc:  # les noms sont un confort
        log(f"Relevés : liste des stations illisible ({type(exc).__name__})")
        return {}


def update_releves(session: requests.Session, config: dict, previous: dict, log) -> dict:
    lieu = config["lieu"]
    radius = float(config.get("rayon_stations_km", 35))
    wanted = int(config.get("nb_stations", 5))
    now = datetime.now(UTC)
    state = previous if previous.get("lieu", {}).get("nom") == lieu["nom"] else {}
    if state and state.get("rayon_km") != radius:
        state = dict(state, hours_done=[])  # nouveau rayon : on relit les 24 h pour les nouvelles stations
    stations: dict[str, dict] = {s["id"]: s for s in state.get("stations", [])}
    hours_done: set[str] = set(state.get("hours_done", []))
    status = "ok"

    # Les heures pleines des dernières 24 h (les observations de HH sont publiées vers HH+10 min).
    last_hour = (now - timedelta(minutes=12)).replace(minute=0, second=0, microsecond=0)
    todo = [last_hour - timedelta(hours=h) for h in range(0, 24)]
    todo = [h for h in todo if h.strftime("%Y-%m-%dT%H:%MZ") not in hours_done][:MAX_REQUESTS_PER_RUN]
    log(f"Relevés : {len(todo)} heure(s) à lire")

    for hour in todo:
        key = hour.strftime("%Y-%m-%dT%H:%MZ")
        try:
            r = session.get(OBS_URL, params={"date": hour.strftime("%Y-%m-%dT%H:%M:%SZ"), "format": "json"}, timeout=60)
        except Exception as exc:
            log(f"  {key} : {type(exc).__name__}")
            continue
        if r.status_code in (401, 403):
            body = r.text[:300].replace(session.headers.get("apikey", "") or "\x00", "***")
            log(f"  {key} : accès refusé (HTTP {r.status_code}) — réponse : {body}")
            status = "acces_refuse"
            break
        if r.status_code == 404:
            log(f"  {key} : pas encore publié")
            continue
        if not r.ok:
            log(f"  {key} : HTTP {r.status_code}")
            continue
        try:
            rows = r.json()
        except ValueError:
            log(f"  {key} : réponse non JSON")
            continue
        rows = rows if isinstance(rows, list) else []
        if rows and not stations and not hours_done:
            log(f"  champs d'une observation : {sorted(rows[0].keys())}")
        found = 0
        for row in rows:
            lat, lon = _num(row.get("lat")), _num(row.get("lon"))
            if lat is None or lon is None:
                continue
            d = distance_km(lieu["lat"], lieu["lon"], lat, lon)
            if d > radius:
                continue
            rr = _num(row.get("rr1"))
            t = _num(row.get("t"))
            sid = str(row.get("geo_id_insee") or row.get("id_station") or row.get("id") or f"{lat:.3f},{lon:.3f}")
            st = stations.setdefault(sid, {"id": sid, "nom": row.get("name") or sid, "lat": lat, "lon": lon, "km": round(d, 1), "heures": {}})
            st["heures"][key] = {"rr": rr, "t": round(t - 273.15, 1) if t is not None and t > 150 else t}
            found += 1
        hours_done.add(key)
        log(f"  {key} : {len(rows)} stations en France, {found} près du lieu")
        time.sleep(1.3)

    # Noms des stations (une fois)
    if any(s["nom"] == s["id"] for s in stations.values()):
        names = station_names(session, log)
        for s in stations.values():
            if s["id"] in names:
                s["nom"] = names[s["id"]]

    # Ménage et cumuls journaliers (heure de Paris). rr1 de HH = pluie entre HH-1 et HH.
    cutoff = (now - timedelta(hours=KEEP_HOURS)).strftime("%Y-%m-%dT%H:%MZ")
    hours_done = {h for h in hours_done if h >= cutoff}
    day_cutoff = (now.astimezone(PARIS) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    for s in stations.values():
        jours = s.get("jours", {})
        per_day: dict[str, list[float]] = {}
        for h, v in s["heures"].items():
            if v.get("rr") is None:
                continue
            end = datetime.strptime(h, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)
            day = (end - timedelta(minutes=1)).astimezone(PARIS).strftime("%Y-%m-%d")
            per_day.setdefault(day, []).append(v["rr"])
        for day, values in per_day.items():
            # on ne remplace un jour gardé que si l'on a au moins autant d'heures qu'avant
            old = jours.get(day)
            if not old or len(values) >= old.get("n", 0):
                jours[day] = {"mm": round(sum(values), 1), "n": len(values)}
        s["jours"] = {d: v for d, v in sorted(jours.items()) if d >= day_cutoff}
        s["heures"] = {h: v for h, v in sorted(s["heures"].items()) if h >= cutoff}

    # Les stations les plus proches qui mesurent la pluie
    useful = [s for s in stations.values() if any(v.get("rr") is not None for v in s["heures"].values()) or s.get("jours")]
    useful.sort(key=lambda s: s["km"])
    return {
        "updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status if (useful or status != "ok") else "aucune_station",
        "lieu": lieu,
        "rayon_km": radius,
        "hours_done": sorted(hours_done),
        "stations": useful[:wanted],
    }


def update_virtuelle(config: dict, prev: dict, new_slots: dict, log) -> dict:
    """Station virtuelle : pluie radar Météo-France (lame d'eau) au-dessus du lieu, cumulée par heure et par jour.

    Chaque image radar couvre 5 minutes : une heure complète = 12 images. Les cumuls d'une heure incomplète
    (robot en retard) sont gardés et marqués par le nombre d'images reçues."""
    lieu = config["lieu"]
    now = datetime.now(UTC)
    slots = dict(prev.get("slots", {}))
    slots.update(new_slots)
    cutoff = (now - timedelta(hours=KEEP_HOURS)).strftime("%Y-%m-%dT%H:%MZ")
    slots = {k: v for k, v in sorted(slots.items()) if k >= cutoff}
    heures: dict[str, dict] = {}
    for k, mm in slots.items():
        end = datetime.strptime(k, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)
        hour_end = (end - timedelta(minutes=1)).replace(minute=0) + timedelta(hours=1)
        h = heures.setdefault(hour_end.strftime("%Y-%m-%dT%H:%MZ"), {"rr": 0.0, "t": None, "n": 0})
        h["rr"] += mm
        h["n"] += 1
    for h in heures.values():
        h["rr"] = round(h["rr"], 1)
    jours = dict(prev.get("jours", {}))
    per_day: dict[str, list] = {}
    for k, mm in slots.items():
        end = datetime.strptime(k, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)
        day = (end - timedelta(minutes=1)).astimezone(PARIS).strftime("%Y-%m-%d")
        per_day.setdefault(day, []).append(mm)
    for day, values in per_day.items():
        old = jours.get(day)
        n = round(len(values) / 12)  # heures couvertes
        if not old or n >= old.get("n", 0):
            jours[day] = {"mm": round(sum(values), 1), "n": n}
    day_cutoff = (now.astimezone(PARIS) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    jours = {d: v for d, v in sorted(jours.items()) if d >= day_cutoff}
    log(f"Station virtuelle : {len(slots)} images de 5 min gardées, {len(heures)} heures")
    return {"id": "radar", "nom": f"{lieu['nom']} (radar)", "lat": lieu["lat"], "lon": lieu["lon"], "km": 0.0,
            "virtuelle": True, "slots": slots, "heures": heures, "jours": jours}


DATAGOUV_QUOT = "https://www.data.gouv.fr/api/2/datasets/6569b51ae64326786e4e8e1a/resources/"
QUOT_EVERY_HOURS = 3


def _quot_urls(log) -> dict[str, str]:
    """Département -> adresse du fichier quotidien « RR-T-Vent » de la période en cours (data.gouv.fr)."""
    urls: dict[str, tuple[str, str]] = {}
    page = 1
    while page <= 10:
        r = requests.get(DATAGOUV_QUOT, params={"page": page, "page_size": 200, "type": "main"}, timeout=60)
        r.raise_for_status()
        data = r.json()
        for res in data.get("data", []):
            title = res.get("title", "")
            if "RR-T-Vent" not in title or "departement_" not in title or "periode_" not in title:
                continue
            dep = title.split("departement_")[1].split("_")[0]
            period = title.split("periode_")[1].split("_")[0]
            if dep not in urls or period > urls[dep][0]:
                urls[dep] = (period, res.get("url", ""))
        if not data.get("next_page"):
            break
        page += 1
    log(f"Pluviomètres quotidiens : {len(urls)} fichiers départementaux trouvés sur data.gouv.fr")
    return {d: u for d, (_, u) in urls.items()}


def update_quotidiennes(config: dict, prev: dict, log) -> dict:
    """Pluviomètres Météo-France à relevé quotidien (dont bénévoles), près du lieu : cumul par jour, publié le lendemain."""
    import gzip

    now = datetime.now(UTC)
    deps = config.get("departements", [])
    radius = float(config.get("rayon_quotidien_km", 15))
    if prev.get("updated") and prev.get("rayon_km") == radius and prev.get("deps") == deps and prev.get("stations") and prev.get("v") == 2:
        age = (now - datetime.strptime(prev["updated"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)).total_seconds()
        if age < QUOT_EVERY_HOURS * 3600:
            return prev
    lieu = config["lieu"]
    day_cutoff = (now.astimezone(PARIS) - timedelta(days=KEEP_DAYS)).strftime("%Y%m%d")
    try:
        urls = _quot_urls(log)
    except Exception as exc:
        log(f"Pluviomètres quotidiens : liste illisible ({type(exc).__name__})")
        return prev
    stations: dict[str, dict] = {}
    for dep in deps:
        url = urls.get(dep)
        if not url:
            log(f"  département {dep} : pas de fichier")
            continue
        try:
            raw = gzip.decompress(requests.get(url, timeout=120).content).decode("utf-8", "replace")
        except Exception as exc:
            log(f"  département {dep} : téléchargement en échec ({type(exc).__name__})")
            continue
        reader = csv.DictReader(io.StringIO(raw), delimiter=";")
        log(f"  département {dep} : fichier {url.rsplit('/', 1)[-1]}, colonnes {reader.fieldnames[:8] if reader.fieldnames else '?'}")
        nearest, max_date, nrows = None, "", 0
        for row in reader:
            nrows += 1
            max_date = max(max_date, (row.get("AAAAMMJJ") or "").strip())
            try:
                lat = float(row["LAT"].replace(",", ".")); lon = float(row["LON"].replace(",", "."))
            except (KeyError, ValueError):
                continue
            d = distance_km(lieu["lat"], lieu["lon"], lat, lon)
            if nearest is None or d < nearest[0]:
                nearest = (round(d, 1), row.get("NOM_USUEL", "").strip())
            if d > radius:
                continue
            date = (row.get("AAAAMMJJ") or "").strip()
            rr = (row.get("RR") or "").strip().replace(",", ".")
            if date < day_cutoff or not rr:
                continue
            sid = row["NUM_POSTE"].strip()
            st = stations.setdefault(sid, {"id": sid, "nom": row.get("NOM_USUEL", sid).strip().title(), "lat": lat, "lon": lon,
                                           "km": round(d, 1), "quotidien": True, "heures": {}, "jours": {}})
            st["jours"][f"{date[:4]}-{date[4:6]}-{date[6:8]}"] = {"mm": round(float(rr), 1), "n": 24}
        log(f"  département {dep} : {nrows} lignes, dernier jour {max_date}, poste le plus proche {nearest} ; {len(stations)} pluviomètre(s) retenu(s) jusqu'ici")
    useful = sorted((s for s in stations.values() if s["jours"]), key=lambda s: s["km"])
    for s in useful:
        s["jours"] = dict(sorted(s["jours"].items()))
        s["dernier_jour"] = max(s["jours"])
    log("Pluviomètres quotidiens : " + (", ".join(f"{s['nom']} ({s['km']} km, dernier relevé {s['dernier_jour']})" for s in useful) or "aucun"))
    return {"v": 2, "updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "rayon_km": radius, "deps": deps, "stations": useful}


def load_json(url: str) -> dict:
    try:
        r = requests.get(url, timeout=30)
        return r.json() if r.ok else {}
    except Exception:
        return {}


def run(session: requests.Session, out_dir: Path, pages_url: str, log, radar_point: dict | None = None) -> None:
    cfg_path = Path("config.json")
    config = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    if "lieu" not in config:
        log("Relevés : pas de lieu dans config.json")
        return
    previous = load_json(f"{pages_url}/data/releves.json") if pages_url else {}
    result = update_releves(session, config, previous, log)
    try:
        result["quotidiennes"] = update_quotidiennes(config, previous.get("quotidiennes", {}), log)
    except Exception as exc:
        log(f"Pluviomètres quotidiens en échec : {type(exc).__name__}: {exc}")
        result["quotidiennes"] = previous.get("quotidiennes", {})
    result["virtuelle"] = update_virtuelle(config, previous.get("virtuelle", {}) if previous.get("lieu", {}).get("nom") == config["lieu"]["nom"] else {}, radar_point or {}, log)
    (out_dir / "data").mkdir(parents=True, exist_ok=True)
    (out_dir / "data" / "releves.json").write_text(json.dumps(result, ensure_ascii=False))
    names = ", ".join(f"{s['nom']} ({s['km']} km)" for s in result["stations"][:8]) + (f" … ({len(result['stations'])} stations)" if len(result["stations"]) > 8 else "")
    log(f"Relevés publiés : {result['status']} — {names or 'aucune station'}")
