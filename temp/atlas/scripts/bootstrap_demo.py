from pathlib import Path
import sys, json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import storage, registry, analysis
from server.models.tddfa import get_model
from server.config import ROOT


class ConsoleJob:
    def check(self):
        pass

    def update(self, p, m, **kw):
        print(f"{p:5.0%} {m}", flush=True)


if __name__ == "__main__":
    storage.ensure_demo()
    registry.discover()
    demo_ids = [p["id"] for p in storage.read_db()["photos"] if p.get("demo")]
    print(storage.process(ConsoleJob(), demo_ids), flush=True)
    topo = get_model().topology()
    (ROOT / "data/topology.json").write_text(json.dumps(topo, separators=(",", ":")))
    result = analysis.metrics_table()
    print("Metrics", len(result["catalog"]), "rows", len(result["rows"]))
    for r in result["rows"]:
        print(
            r["date"],
            r["pose"],
            {
                k: round(v["value"], 4) if v["value"] is not None else None
                for k, v in r["metrics"].items()
                if k.startswith("mesh_")
            },
        )
    from server.rendering import rasterize, colorize
    import numpy as np
    from PIL import Image

    ps = [p for p in storage.library() if p.get("demo")]
    a = storage.load_features(storage.photo(ps[0]["id"]))
    b = storage.load_features(storage.photo(ps[-1]["id"]))
    values = np.linalg.norm(a["vertices"] - b["vertices"], axis=1)
    rgb = rasterize(
        b["vertices"],
        get_model().tri,
        colorize(values, hi=max(float(np.percentile(values, 95)), 0.001)),
        512,
        15,
    )
    Image.fromarray(rgb).save(ROOT / "reports/smoke-render.png")
    print("CPU renderer smoke passed", flush=True)
