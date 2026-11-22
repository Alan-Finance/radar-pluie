"""Robot du Radar Pluie : récupère les données Météo-France et fabrique les images de la carte.

Lancé toutes les 10 minutes par GitHub Actions (.github/workflows/radar.yml).

  * Radar (passé)      : mosaïque « lame d'eau » 500 m de Météo-France (API DPRadar + DPPaquetRadar),
                         une image toutes les 10 minutes sur les 2 dernières heures.
  * Prévision (futur)  : modèle AROME-PI (prévision immédiate), une image tous les 1/4 d'heure jusqu'à +3 h.

Chaque image est un PNG transparent en projection Web Mercator couvrant la France (BOUNDS),
lissé et colorié avec la palette de l'appli. La liste des images est écrite dans data/frames.json.

Les images déjà publiées sont relues depuis le site (PAGES_URL) pour garder l'historique d'une exécution à l'autre.
La clé Météo-France est lue dans la variable d'environnement METEOFRANCE_KEY et n'est jamais affichée.
"""

from __future__ import annotations

import io
import json
import os
import struct
import sys
import tarfile
import time
import traceback
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import requests
from PIL import Image
from scipy.ndimage import gaussian_filter

# ----------------------------------------------------------------------------------------------- réglages

OUT = Path(os.environ.get("OUT_DIR", "site"))
DATA = OUT / "data"
PAGES_URL = os.environ.get("PAGES_URL", "").rstrip("/")
KEY = os.environ.get("METEOFRANCE_KEY", "").strip()

API = "https://public-api.meteofrance.fr/public"
RADAR_URL = f"{API}/DPRadar/v1/mosaiques/METROPOLE/observations/LAME_D_EAU"
PAQUET_URL = f"{API}/DPPaquetRadar/v1/mosaique/paquet"
AROMEPI_URL = f"{API}/aromepi/1.0/wcs/MF-NWP-HIGHRES-AROMEPI-001-FRANCE-WCS"
AROMEPI_COVERAGE = "TOTAL_PRECIPITATION_RATE__GROUND_OR_WATER_SURFACE___{run}"

# Zone dessinée (ouest, sud, est, nord) = celle de la prévision AROME-PI : métropole + Corse.
WEST, SOUTH, EAST, NORTH = -6.0, 41.0, 10.5, 51.5
DEG_PER_PX = 0.010  # ~ 750 m à la latitude de la France (images plus légères pour les téléphones)
SMOOTH_SIGMA_PX = 1.3  # lissage façon Météus (0 = aucun)

PAST_HOURS = 3.0
RADAR_STEP_MIN = 10
FORECAST_HOURS = 3.0

# Seuils (mm/h) et couleurs (R, V, B, A) des classes 1..9 ; la classe 0 est transparente.
THRESHOLDS = (0.1, 0.5, 1.0, 2.0, 4.0, 7.0, 12.0, 20.0, 40.0)
COLORS = (
    (0, 0, 0, 0),
    (160, 215, 245, 190),  # bruine
    (70, 145, 230, 225),   # faible
    (40, 180, 75, 235),    # faible à modérée
    (165, 215, 45, 240),   # modérée
    (255, 230, 0, 245),    # modérée à forte
    (255, 160, 0, 250),    # forte
    (255, 70, 0, 255),     # très forte
    (205, 0, 0, 255),      # intense
    (170, 0, 210, 255),    # orage / extrême
)

SESSION = requests.Session()
SESSION.headers.update({"apikey": KEY, "accept": "*/*", "User-Agent": "radar-pluie (GitHub Actions)"})


def log(msg: str) -> None:
    print(msg, flush=True)


def safe_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}"
    return text.replace(KEY, "***") if KEY else text


# ----------------------------------------------------------------------------------------------- grille de sortie (Web Mercator)


def merc_y(lat: np.ndarray | float) -> np.ndarray | float:
    return np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


WIDTH = int(round((EAST - WEST) / DEG_PER_PX))
HEIGHT = int(round((merc_y(NORTH) - merc_y(SOUTH)) / np.radians(DEG_PER_PX)))


def output_latlon() -> tuple[np.ndarray, np.ndarray]:
    """Latitude et longitude du centre de chaque pixel de l'image de sortie (ligne 0 = nord)."""
    lon = WEST + (np.arange(WIDTH) + 0.5) * (EAST - WEST) / WIDTH
    y_top, y_bottom = merc_y(NORTH), merc_y(SOUTH)
    y = y_top - (np.arange(HEIGHT) + 0.5) * (y_top - y_bottom) / HEIGHT
    lat = np.degrees(2 * np.arctan(np.exp(y)) - np.pi / 2)
    return np.meshgrid(lon, lat)


LON_GRID, LAT_GRID = output_latlon()


# ----------------------------------------------------------------------------------------------- rendu


def render(rate_mm_h: np.ndarray, path: Path) -> None:
    """Lisse le champ de pluie (mm/h, NaN = hors couverture), le classe et l'écrit en PNG à palette transparent."""
    valid = np.isfinite(rate_mm_h)
    values = np.where(valid, rate_mm_h, 0.0).astype(np.float32)
    if SMOOTH_SIGMA_PX > 0:
        weight = gaussian_filter(valid.astype(np.float32), SMOOTH_SIGMA_PX)
        blurred = gaussian_filter(values, SMOOTH_SIGMA_PX)
        values = np.where(weight > 0.2, blurred / np.maximum(weight, 1e-6), 0.0)
    classes = np.searchsorted(np.asarray(THRESHOLDS, dtype=np.float32), values, side="right").astype(np.uint8)
    classes[~valid] = 0
    img = Image.fromarray(classes, mode="P")
    palette = []
    for c in COLORS:
        palette += list(c[:3])
    img.putpalette(palette + [0] * (768 - len(palette)))
    img.info["transparency"] = bytes(c[3] for c in COLORS)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.png")
    img.save(tmp, optimize=True, transparency=bytes(c[3] for c in COLORS))
    tmp.replace(path)


# ----------------------------------------------------------------------------------------------- radar (mosaïque lame d'eau 500 m)

# Grille de la mosaïque métropole (fichier HDF5 « H5rad », lu et vérifié par plusieurs projets publics) :
# 3472 x 3472 pixels de 500 m, stéréographique polaire (+proj=stere +lat_0=90 +lon_0=0 +lat_ts=45 +ellps=WGS84
# +x_0=619652.07 +y_0=5262818.34), coin haut-gauche en (0 ; 1 736 000) m. Valeurs : cumul 5 min en 0,01 mm,
# 65535 = hors couverture, 65534 = pas de pluie détectée.
R_SIZE = 3472
R_PIXEL = 500.0
_A = 6378137.0
_F = 1 / 298.257223563
_E = (2 * _F - _F * _F) ** 0.5


def _t(phi):
    s = np.sin(phi)
    return np.tan(np.pi / 4 - phi / 2) / (((1 - _E * s) / (1 + _E * s)) ** (_E / 2))


_PHI_C = np.radians(45.0)
_M_C = np.cos(_PHI_C) / np.sqrt(1 - (_E * np.sin(_PHI_C)) ** 2)
_T_C = _t(_PHI_C)


def stereo(lat, lon):
    rho = _A * _M_C * _t(np.radians(lat)) / _T_C
    lam = np.radians(lon)
    return 619652.07 + rho * np.sin(lam), 5262818.34 - rho * np.cos(lam)


_SX, _SY = stereo(LAT_GRID, LON_GRID)
R_COL = np.floor(_SX / R_PIXEL).astype(np.int64)
R_ROW = np.floor((R_SIZE * R_PIXEL - _SY) / R_PIXEL).astype(np.int64)
R_INSIDE = (R_COL >= 0) & (R_COL < R_SIZE) & (R_ROW >= 0) & (R_ROW < R_SIZE)


def _text(v) -> str:
    return v.decode() if isinstance(v, bytes) else str(v)


def decode_radar_h5(content: bytes) -> tuple[datetime, np.ndarray] | None:
    """(fin du cumul, pluie en mm/h sur la grille de sortie) d'un fichier HDF5 de la mosaïque 500 m, sinon None."""
    import h5py

    try:
        f = h5py.File(io.BytesIO(content), "r")
    except OSError:
        return None
    with f:
        try:
            where = f["where"].attrs
            proj = _text(where["projdef"])
            if "+proj=stere" not in proj or int(where["xsize"]) != R_SIZE or int(where["ysize"]) != R_SIZE:
                return None
            what = f["dataset1/data1/what"].attrs
            if _text(what["quantity"]) != "ACRR":
                return None
            gain = float(what["gain"])
            offset = float(what["offset"])
            nodata = int(what["nodata"])
            undetect = int(what["undetect"])
            when = f["dataset1/what"].attrs
            end = datetime.strptime(_text(when["enddate"]) + _text(when["endtime"]), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
            data = f["dataset1/data1/data"][:]
        except KeyError:
            return None
    raw = np.zeros(LAT_GRID.shape, dtype=np.uint16)
    raw[:] = nodata
    raw[R_INSIDE] = data[R_ROW[R_INSIDE], R_COL[R_INSIDE]]
    rate = (raw.astype(np.float32) * gain + offset) * 12.0  # cumul 5 min -> mm/h
    rate[raw == undetect] = 0.0
    rate[raw == nodata] = np.nan
    return end, rate


def iter_archive(content: bytes):
    """(nom, octets) de chaque fichier d'une archive zip ou tar (éventuellement compressée)."""
    if content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            for name in z.namelist():
                if not name.endswith("/"):
                    yield name, z.read(name)
        return
    try:
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as t:
            for m in t.getmembers():
                if m.isfile():
                    fh = t.extractfile(m)
                    if fh:
                        yield m.name, fh.read()
    except tarfile.TarError:
        return


def maybe_unzip(name: str, blob: bytes) -> bytes:
    """Décompresse un fichier .gz / .bz2 isolé si besoin."""
    import bz2
    import gzip

    if blob[:2] == b"\x1f\x8b":
        return gzip.decompress(blob)
    if blob[:3] == b"BZh":
        return bz2.decompress(blob)
    return blob


def fetch_radar() -> dict[datetime, np.ndarray]:
    """Les images radar disponibles maintenant : le paquet du dernier 1/4 h, sinon la dernière image."""
    frames: dict[datetime, np.ndarray] = {}
    try:
        r = SESSION.get(PAQUET_URL, timeout=120)
        log(f"Paquet radar : HTTP {r.status_code}, {len(r.content) / 1e6:.1f} Mo")
        if r.ok:
            names = []
            for name, blob in iter_archive(r.content):
                names.append(name)
                blob = maybe_unzip(name, blob)
                if blob[:4] != b"\x89HDF":
                    continue
                got = decode_radar_h5(blob)
                if got:
                    frames[got[0]] = got[1]
            log(f"  fichiers du paquet : {len(names)} ; exemples : {names[:12]}")
            log(f"  images 500 m lues : {sorted(t.strftime('%H:%M') for t in frames)}")
    except Exception as exc:  # le paquet est un bonus : on continue avec l'API ciblée
        log(f"Paquet radar en échec : {safe_error(exc)}")

    try:
        r = SESSION.get(f"{RADAR_URL}/produit", params={"maille": 500}, timeout=120)
        log(f"Radar dernière image : HTTP {r.status_code}, {len(r.content) / 1e6:.1f} Mo")
        r.raise_for_status()
        got = decode_radar_h5(maybe_unzip("produit", r.content))
        if got:
            frames[got[0]] = got[1]
            log(f"  image de {got[0].strftime('%H:%M')} UTC lue")
        else:
            log("  format de l'image inattendu")
    except Exception as exc:
        log(f"Radar en échec : {safe_error(exc)}")
    return frames


# ----------------------------------------------------------------------------------------------- AROME-PI (prévision)


def decode_grib2(data: bytes) -> tuple[np.ndarray, float, float, float, float]:
    """Un message GRIB2 (grille lat/lon régulière, empaquetage simple) -> (valeurs[j nord croissant, i est croissant], lat0, lon0, dlat, dlon)."""
    if data[:4] != b"GRIB" or data[7] != 2:
        raise ValueError("pas un message GRIB2")
    total = struct.unpack(">Q", data[8:16])[0]
    sections: dict[int, bytes] = {}
    pos = 16
    while pos < total - 4:
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        number = data[pos + 4]
        sections.setdefault(number, data[pos : pos + length])
        pos += length
    s3, s5, s7 = sections[3], sections[5], sections[7]
    if struct.unpack(">H", s3[12:14])[0] != 0:
        raise ValueError("grille GRIB2 non lat/lon")

    def signed(raw: int, bits: int) -> int:
        sign = 1 << (bits - 1)
        return -(raw & (sign - 1)) if raw & sign else raw

    ni, nj = struct.unpack(">II", s3[30:38])
    basic, subdiv = struct.unpack(">II", s3[38:46])
    unit = 1e-6 if basic in (0, 0xFFFFFFFF) or subdiv in (0, 0xFFFFFFFF) else basic / subdiv
    la1 = signed(struct.unpack(">I", s3[46:50])[0], 32) * unit
    lo1 = signed(struct.unpack(">I", s3[50:54])[0], 32) * unit
    di = struct.unpack(">I", s3[63:67])[0] * unit
    dj = struct.unpack(">I", s3[67:71])[0] * unit
    scan = s3[71]
    if struct.unpack(">H", s5[9:11])[0] != 0:
        raise ValueError("empaquetage GRIB2 non simple")
    count = struct.unpack(">I", s5[5:9])[0]
    reference = struct.unpack(">f", s5[11:15])[0]
    e = signed(struct.unpack(">H", s5[15:17])[0], 16)
    d = signed(struct.unpack(">H", s5[17:19])[0], 16)
    nbits = s5[19]
    payload = s7[5:]
    if nbits == 0:
        packed = np.zeros(count, dtype=np.float64)
    elif nbits in (8, 16, 32):
        packed = np.frombuffer(payload, dtype={8: ">u1", 16: ">u2", 32: ">u4"}[nbits], count=count).astype(np.float64)
    else:
        bits = np.unpackbits(np.frombuffer(payload, dtype=np.uint8))[: count * nbits].reshape(count, nbits)
        packed = bits.astype(np.float64) @ (2.0 ** np.arange(nbits - 1, -1, -1))
    values = ((reference + packed * 2.0**e) / 10.0**d).astype(np.float32)
    if 6 in sections and sections[6][5] == 0:  # masque : on remet les points absents à NaN
        bitmap = np.unpackbits(np.frombuffer(sections[6][6:], dtype=np.uint8))[: ni * nj].astype(bool)
        full = np.full(ni * nj, np.nan, dtype=np.float32)
        full[bitmap] = values[: bitmap.sum()]
        values = full
    grid = values.reshape(nj, ni)
    dlat = dj if scan & 0x40 else -dj
    dlon = -di if scan & 0x80 else di
    lat0, lon0 = la1, lo1
    if dlat < 0:
        grid = grid[::-1]
        lat0, dlat = la1 + dlat * (nj - 1), -dlat
    if dlon < 0:
        grid = grid[:, ::-1]
        lon0, dlon = lo1 + dlon * (ni - 1), -dlon
    if lon0 > 180:
        lon0 -= 360
    return np.ascontiguousarray(grid), lat0, lon0, dlat, dlon


def grib_to_output(grid, lat0, lon0, dlat, dlon) -> np.ndarray:
    j = np.rint((LAT_GRID - lat0) / dlat).astype(np.int64)
    i = np.rint((LON_GRID - lon0) / dlon).astype(np.int64)
    inside = (j >= 0) & (j < grid.shape[0]) & (i >= 0) & (i < grid.shape[1])
    out = np.full(LAT_GRID.shape, np.nan, dtype=np.float32)
    out[inside] = grid[j[inside], i[inside]]
    return out


def run_stamp(run: datetime) -> str:
    return run.strftime("%Y-%m-%dT%H.%M.%SZ")


def aromepi_get(coverage: str, valid: datetime, run: datetime) -> requests.Response:
    """Une échéance de la carte de la France (essaie la date ISO, puis le décalage en secondes)."""
    base = [
        ("service", "WCS"),
        ("version", "2.0.1"),
        ("coverageid", coverage),
        ("format", "application/wmo-grib"),
        ("subset", f"long({WEST},{EAST})"),
        ("subset", f"lat({SOUTH},{NORTH})"),
    ]
    r = None
    for time_subset in (valid.strftime("time(%Y-%m-%dT%H:%M:%SZ)"), f"time({int((valid - run).total_seconds())})"):
        r = SESSION.get(f"{AROMEPI_URL}/GetCoverage", params=base + [("subset", time_subset)], timeout=60)
        if r.ok and r.content[:4] == b"GRIB":
            return r
        time.sleep(0.7)
    return r


def fetch_forecast(existing_run: str | None) -> tuple[str | None, dict[datetime, np.ndarray]]:
    """Le run AROME-PI le plus récent publié : (identifiant du run, {échéance: pluie mm/h}). Rien si déjà à jour."""
    now = datetime.now(UTC)
    base = now.replace(minute=0, second=0, microsecond=0)
    for back in range(0, 4):
        run = base - timedelta(hours=back)
        stamp = run_stamp(run)
        if existing_run == stamp:
            log(f"AROME-PI : run {stamp} déjà en place")
            return None, {}
        coverage = AROMEPI_COVERAGE.format(run=stamp)
        r = SESSION.get(
            f"{AROMEPI_URL}/DescribeCoverage",
            params=[("service", "WCS"), ("version", "2.0.1"), ("coverageid", coverage)],
            timeout=30,
        )
        log(f"AROME-PI run {stamp} : DescribeCoverage HTTP {r.status_code}")
        if not r.ok:
            continue
        frames: dict[datetime, np.ndarray] = {}
        step = timedelta(minutes=15)
        valid = run + step
        # Jusqu'à run + 4 h 30 : le run suffit pour « maintenant + 3 h » jusqu'à la publication du suivant.
        limit = run + timedelta(hours=FORECAST_HOURS + 1, minutes=30)
        complete = True
        while valid <= limit:
            if valid > now - timedelta(minutes=15):
                resp = aromepi_get(coverage, valid, run)
                if resp is not None and resp.ok and resp.content[:4] == b"GRIB":
                    grid, lat0, lon0, dlat, dlon = decode_grib2(resp.content)
                    frames[valid] = grib_to_output(grid, lat0, lon0, dlat, dlon)
                    if len(frames) == 1:
                        finite = grid[np.isfinite(grid)]
                        log(f"  grille {grid.shape}, pas {dlat:.4f}°, max {finite.max():.2f} mm/h")
                else:
                    code = resp.status_code if resp is not None else "?"
                    log(f"  échéance {valid.strftime('%H:%M')} pas encore publiée (HTTP {code}) : run incomplet")
                    complete = False
                    break
                time.sleep(0.7)  # quota : 100 requêtes / minute
            valid += step
        if frames and complete:
            log(f"  {len(frames)} échéances lues (run complet)")
            return stamp, frames
        log("  run ignoré tant qu'il est incomplet, on garde le précédent")
    return None, {}


# ----------------------------------------------------------------------------------------------- état publié


def point_values(frames: dict[datetime, np.ndarray]) -> dict[str, float]:
    """Pluie (mm en 5 min) au-dessus du lieu de config.json : moyenne des pixels à moins d'1 km, par image radar."""
    try:
        lieu = json.loads(Path("config.json").read_text())["lieu"]
    except Exception:
        return {}
    i = (lieu["lon"] - WEST) / (EAST - WEST) * WIDTH
    j = (merc_y(NORTH) - merc_y(lieu["lat"])) / (merc_y(NORTH) - merc_y(SOUTH)) * HEIGHT
    i0, j0 = int(i), int(j)
    out = {}
    for t, rate in frames.items():
        if t.minute % 5:
            continue
        block = rate[max(0, j0 - 1) : j0 + 2, max(0, i0 - 1) : i0 + 2]
        vals = block[np.isfinite(block)]
        if vals.size:
            out[t.strftime("%Y-%m-%dT%H:%MZ")] = round(float(vals.mean()) / 12.0, 3)  # mm/h -> mm en 5 min
    log(f"Station virtuelle radar : {len(out)} relevé(s) de 5 min au-dessus de {lieu.get('nom')}")
    return out


def fname(t: datetime) -> str:
    return t.strftime("%Y%m%d%H%M")


def load_previous() -> dict:
    """Le frames.json déjà en ligne et ses images encore utiles, recopiés dans le dossier de sortie."""
    if not PAGES_URL:
        return {}
    try:
        r = requests.get(f"{PAGES_URL}/data/frames.json", timeout=30)
        if not r.ok:
            log(f"Pas d'état précédent ({r.status_code})")
            return {}
        state = r.json()
    except Exception as exc:
        log(f"État précédent illisible : {exc}")
        return {}
    cutoff = datetime.now(UTC) - timedelta(hours=PAST_HOURS, minutes=10)
    kept = []
    for fr in state.get("frames", []):
        t = datetime.fromisoformat(fr["time"].replace("Z", "+00:00"))
        if fr["kind"] == "radar" and t < cutoff:
            continue
        target = OUT / fr["file"]
        if not target.exists():
            try:
                img = requests.get(f"{PAGES_URL}/{fr['file']}", timeout=30)
                if not img.ok:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(img.content)
            except Exception:
                continue
        kept.append(fr)
    state["frames"] = kept
    log(f"État précédent : {len(kept)} images reprises")
    return state


def main() -> int:
    if not KEY:
        log("METEOFRANCE_KEY absente : ajoute le secret dans Settings → Secrets and variables → Actions.")
    DATA.mkdir(parents=True, exist_ok=True)
    state = load_previous()
    frames = {(f["kind"], f["time"]): f for f in state.get("frames", [])}
    now = datetime.now(UTC)

    # Radar
    if KEY:
        radar_now = fetch_radar()
        point_mm = point_values(radar_now)
        for t, rate in radar_now.items():
            latest = max([t] + [datetime.fromisoformat(k[1].replace("Z", "+00:00")) for k in frames if k[0] == "radar"])
            if t.minute % RADAR_STEP_MIN != 0 and t < latest:
                continue  # on garde un pas de 10 min, plus la toute dernière image
            iso = t.strftime("%Y-%m-%dT%H:%M:%SZ")
            path = DATA / "r" / f"{fname(t)}.png"
            render(rate, path)
            frames[("radar", iso)] = {"kind": "radar", "time": iso, "file": f"data/r/{path.name}"}

    radar_times = sorted(datetime.fromisoformat(k[1].replace("Z", "+00:00")) for k in frames if k[0] == "radar")
    # Les images radar à :05 sont retirées dès qu'une plus récente existe.
    for t in radar_times[:-1]:
        if t.minute % RADAR_STEP_MIN != 0:
            frames.pop(("radar", t.strftime("%Y-%m-%dT%H:%M:%SZ")), None)
    cutoff = now - timedelta(hours=PAST_HOURS, minutes=5)
    for k in [k for k in frames if k[0] == "radar" and datetime.fromisoformat(k[1].replace("Z", "+00:00")) < cutoff]:
        frames.pop(k)

    # Prévision
    old_run = state.get("forecast_run") if state.get("forecast_complete") else None
    if KEY:
        try:
            run, fc = fetch_forecast(old_run)
        except Exception as exc:
            log(f"AROME-PI en échec : {safe_error(exc)}")
            traceback.print_exc()
            run, fc = None, {}
        if run:
            for k in [k for k in frames if k[0] == "prevision"]:
                frames.pop(k)
            for t, rate in fc.items():
                iso = t.strftime("%Y-%m-%dT%H:%M:%SZ")
                path = DATA / "p" / f"{run.replace(':', '').replace('.', '')}_{fname(t)}.png"
                render(rate, path)
                frames[("prevision", iso)] = {"kind": "prevision", "time": iso, "file": f"data/p/{path.name}"}
            state["forecast_run"] = run
            state["forecast_complete"] = True

    # La prévision commence après la dernière image radar et s'arrête à +3 h.
    last_radar = max(
        (datetime.fromisoformat(k[1].replace("Z", "+00:00")) for k in frames if k[0] == "radar"), default=now
    )
    for k in list(frames):
        if k[0] == "prevision":
            t = datetime.fromisoformat(k[1].replace("Z", "+00:00"))
            if t <= last_radar or t > last_radar + timedelta(hours=FORECAST_HOURS, minutes=5):
                frames.pop(k)

    ordered = sorted(frames.values(), key=lambda f: f["time"])
    out = {
        "generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "forecast_run": state.get("forecast_run"),
        "forecast_complete": bool(state.get("forecast_complete")),
        "bounds": [[SOUTH, WEST], [NORTH, EAST]],
        "size": [WIDTH, HEIGHT],
        "legend": [
            {"min": th, "color": "#%02x%02x%02x" % c[:3]} for th, c in zip(THRESHOLDS, COLORS[1:], strict=True)
        ],
        "frames": ordered,
    }
    (DATA / "frames.json").write_text(json.dumps(out, indent=1))

    # Ménage : les images qui ne sont plus listées.
    listed = {OUT / f["file"] for f in ordered}
    for sub in ("r", "p"):
        for p in (DATA / sub).glob("*.png") if (DATA / sub).exists() else []:
            if p not in listed:
                p.unlink()
    # Relevés de pluie des stations proches du lieu (config.json) + station virtuelle radar
    if KEY:
        try:
            import releves

            releves.run(SESSION, OUT, PAGES_URL, log, radar_point=locals().get('point_mm', {}))
        except Exception as exc:
            log(f"Relevés en échec : {safe_error(exc)}")
            traceback.print_exc()

    n_r = sum(f["kind"] == "radar" for f in ordered)
    n_p = len(ordered) - n_r
    log(f"Publié : {n_r} images radar, {n_p} images de prévision ({WIDTH}x{HEIGHT} px)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
