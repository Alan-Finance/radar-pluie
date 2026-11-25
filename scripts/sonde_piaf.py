"""Sonde temporaire (8) : essai de fetch_piaf (sans rien publier)."""
import sys, time
from datetime import UTC, datetime, timedelta
sys.path.insert(0, "scripts")
import numpy as np
import update as U

now = datetime.now(UTC)
start = now - timedelta(minutes=12)
t0 = time.time()
stamp, fc = U.fetch_piaf(None, start, start + timedelta(hours=2, minutes=30))
print("run", stamp, "nb", len(fc), "durée", round(time.time() - t0, 1), "s")
for t, g in sorted(fc.items())[:3] + sorted(fc.items())[-2:]:
    f = g[np.isfinite(g)]
    print(t.strftime("%H:%M"), "pixels pluie>0.1:", int((f > 0.1).sum()), "p99", round(float(np.percentile(f, 99.9)), 2), "max", round(float(f.max()), 1))
# cohérence des unités : PT15M ~ 3 x PT5M ?
run = U.piaf_latest_run(now)
t = run + timedelta(minutes=15)
a = U.decode_grib2(U.piaf_get(U.PIAF_COVERAGE.format(run=U.run_stamp(run)), run, t).content)[0]
b = U.decode_grib2(U.piaf_get(U.PIAF_COVERAGE.format(run=U.run_stamp(run)).replace("_PT5M", "_PT15M"), run, t).content)[0]
m = np.isfinite(a) & np.isfinite(b) & (b > 0.5)
print("somme PT5M", float(np.nansum(a)), "somme PT15M", float(np.nansum(b)), "rapport", float(np.nansum(b) / max(np.nansum(a), 1e-9)))
