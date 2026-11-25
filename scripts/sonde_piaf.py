"""Sonde temporaire (10) : PIAF bien calé sur le radar ? (recouvrement des zones de pluie à la même heure)."""
import sys, base64, io
from datetime import UTC, datetime, timedelta
sys.path.insert(0, "scripts")
import numpy as np
from PIL import Image
import update as U

radar = U.fetch_radar()
tr = max(radar)
run = U.piaf_latest_run(datetime.now(UTC))
cov = U.PIAF_COVERAGE.format(run=U.run_stamp(run))
t = run + timedelta(minutes=5)
g, lat0, lon0, dlat, dlon = U.decode_grib2(U.piaf_get(cov, run, t).content)
p = U.grib_to_output(g * 12, lat0, lon0, dlat, dlon)
r = radar[tr]
A = np.isfinite(r) & (r > 0.5); B = np.isfinite(p) & (p > 0.5)
iou = lambda a, b: (a & b).sum() / max((a | b).sum(), 1)
print("radar", tr.strftime("%H:%M"), "piaf", t.strftime("%H:%M"), "IoU", round(iou(A, B), 3), "IoU inversé N-S", round(iou(A, B[::-1]), 3), "IoU décalé 20px", round(iou(A, np.roll(B, 20, 1)), 3))
# vignette autour de la maison : radar | piaf (vert = pluie > 0.5 mm/h)
lat, lon = 47.0394, 0.4583
J = np.abs(U.LAT_GRID[:, 0] - lat).argmin(); I = np.abs(U.LON_GRID[0] - lon).argmin()
win = lambda a: np.where(np.isfinite(a[J-150:J+150, I-150:I+150]), a[J-150:J+150, I-150:I+150], 0)
img = np.concatenate([win(r), np.full((300, 4), 99), win(p)], 1)
im = Image.fromarray(np.where(img > 98, 0, np.clip(img * 40, 0, 255)).astype(np.uint8)).resize((302, 150))
buf = io.BytesIO(); im.save(buf, "PNG")
print("VIGNETTE", base64.b64encode(buf.getvalue()).decode())
