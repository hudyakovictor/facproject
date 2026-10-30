"""Download only official inference assets; large files live in the ephemeral model cache.
Run again after restoring an Arena workspace snapshot. No user credentials needed.
"""

from pathlib import Path
import hashlib, json, urllib.request

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "models" / "3ddfa_v3"
REVISION = "ffedf42ca91a072beaaf3bc858fcd752ab3b1502"
EXPECTED = {
    "face_model.npy": "f07ada9b4748ecdfeae3fa67aae88bb4b824ea7adc26853778c55d8dc0efa832",
    "net_recon_mbnet.pth": "435f33e6fc93f3c0857538ffc5024d29bd6d09f98391d9be55f2d32b23cc2604",
    "similarity_Lm3D_all.mat": "53b83ce6e35c50ddc3e97603650cef4970320c157e75c241c844f29c1dcba65a",
    "face_detection_yunet_2023mar.onnx": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
}
FILES = ["face_model.npy", "net_recon_mbnet.pth", "similarity_Lm3D_all.mat"]


def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        print(f"Downloading {path.name}", flush=True)
        tmp = path.with_suffix(path.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(path)
    actual = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
    if path.name in EXPECTED and actual != EXPECTED[path.name]:
        raise RuntimeError(f"SHA-256 mismatch: {path.name}; preserved for inspection")
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": hashlib.file_digest(path.open("rb"), "sha256").hexdigest(),
        "url": url,
    }


def main():
    out = {
        f: download(
            f"https://huggingface.co/datasets/Zidu-Wang/3DDFA-V3/resolve/{REVISION}/assets/{f}",
            CACHE / f,
        )
        for f in FILES
    }
    out["yunet"] = download(
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        CACHE / "face_detection_yunet_2023mar.onnx",
    )
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "assets-manifest.json").write_text(
        json.dumps({"revision": REVISION, "files": out}, indent=2)
    )
    print(json.dumps(out, indent=2), flush=True)


if __name__ == "__main__":
    main()
