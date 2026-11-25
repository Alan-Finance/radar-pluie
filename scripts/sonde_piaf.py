"""Sonde temporaire (9) : images PIAF et radar côte à côte (sans rien publier)."""
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
sys.path.insert(0, "scripts")
import numpy as np
import update as U

out = Path("sonde"); out.mkdir(exist_ok=True)
radar = U.fetch_radar()
tr = max(radar)
U.render(radar[tr], out / f"radar_{tr:%H%M}.png")
run = U.piaf_latest_run(datetime.now(UTC))
cov = U.PIAF_COVERAGE.format(run=U.run_stamp(run))
for m in (5, 30, 90, 180):
    t = run + timedelta(minutes=m)
    g, lat0, lon0, dlat, dlon = U.decode_grib2(U.piaf_get(cov, run, t).content)
    rate = U.grib_to_output(g * 12, lat0, lon0, dlat, dlon)
    U.render(rate, out / f"piaf_{t:%H%M}.png")
    j, i = np.unravel_index(np.nanargmax(g), g.shape)
    f = g[np.isfinite(g)]
    print(t.strftime("%H:%M"), "max", float(f.max()) * 12, "à lat", lat0 + j * dlat, "lon", lon0 + i * dlon, "nb NaN", int(np.isnan(g).sum()), "valeurs distinctes hautes", np.unique(np.round(f[f * 12 > 60], 2))[:10])
f = radar[tr][np.isfinite(radar[tr])]
print("radar", tr.strftime("%H:%M"), "pixels>0.1", int((f > 0.1).sum()), "max", float(f.max()))
