"""Vigilance Météo-France du département (config.json : "departement_vigilance") → data/vigilance.json.

API « Données Publiques Vigilance » (même clé que le reste, en-tête apikey).
Couleurs : 1 vert, 2 jaune, 3 orange, 4 rouge. L'appli n'affiche un bandeau qu'en orange ou rouge.
Si l'API ne répond pas, on republie le fichier précédent (l'appli ignore les périodes terminées).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import requests

URL = "https://public-api.meteofrance.fr/public/DPVigilance/v1/cartevigilance/encours"
PHENOMENES = {
    "1": "Vent violent", "2": "Pluie-inondation", "3": "Orages", "4": "Crues", "5": "Neige-verglas",
    "6": "Canicule", "7": "Grand froid", "8": "Avalanches", "9": "Vagues-submersion",
}


def _find_domain(node, dept: str):
    """Cherche le bloc du département (domain_id == dept) n'importe où sous node."""
    if isinstance(node, dict):
        if str(node.get("domain_id", "")) == dept:
            return node
        for v in node.values():
            found = _find_domain(v, dept)
            if found is not None:
                return found
    elif isinstance(node, list):
        for v in node:
            found = _find_domain(v, dept)
            if found is not None:
                return found
    return None


def parse(data: dict, dept: str) -> list[dict]:
    periods = (data.get("product") or data).get("periods") or []
    jours = []
    for p in periods:
        dom = _find_domain(p.get("timelaps", p), dept)
        if dom is None:
            continue
        phen = []
        for it in dom.get("phenomenon_items") or []:
            pid = str(it.get("phenomenon_id", ""))
            col = int(it.get("phenomenon_max_color_id") or it.get("max_color_id") or 1)
            if col >= 2:
                phen.append({"id": pid, "nom": PHENOMENES.get(pid, "Phénomène " + pid), "couleur": col})
        phen.sort(key=lambda x: -x["couleur"])
        jours.append({
            "echeance": p.get("echeance"),
            "debut": p.get("begin_validity_time"),
            "fin": p.get("end_validity_time"),
            "couleur": int(dom.get("max_color_id") or max([1] + [x["couleur"] for x in phen])),
            "phenomenes": phen,
        })
    return jours


def run(session: requests.Session, out_dir: Path, pages_url: str, log) -> None:
    cfg_path = Path("config.json")
    config = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    dept = str(config.get("departement_vigilance", "")).strip()
    if not dept:
        return
    out = out_dir / "data" / "vigilance.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        r = session.get(URL, timeout=60)
        if r.status_code in (401, 403):
            raise RuntimeError(f"accès refusé (HTTP {r.status_code}) — abonnement « Données Publiques Vigilance » à vérifier")
        r.raise_for_status()
        data = r.json()
        jours = parse(data, dept)
        if not jours:
            top = data.get("product", data)
            log(f"Vigilance : département {dept} introuvable — clés : {sorted(top.keys())[:15]}")
        result = {"updated": now, "status": "ok" if jours else "inconnu", "departement": dept, "jours": jours}
        resume = ", ".join(f"{j['echeance']} {j['couleur']}" for j in jours)
        log(f"Vigilance {dept} : {resume or 'rien'}")
    except Exception as exc:
        log(f"Vigilance en échec : {type(exc).__name__}: {str(exc)[:200]}")
        previous = None
        if pages_url:
            try:
                previous = requests.get(f"{pages_url}/data/vigilance.json", timeout=30).json()
            except Exception:
                previous = None
        result = dict(previous or {"departement": dept, "jours": []}, status="echec", essai=now)
    out.write_text(json.dumps(result, ensure_ascii=False))
