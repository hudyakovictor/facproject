import os
import sys
import numpy as np
import cv2
from glob import glob
from itertools import combinations

masks_dir = sys.argv[1] if len(sys.argv) > 1 else "/Users/victorkhudyakov/work/FFHQ-detect-face-wrinkles/e1_result"

mask_paths = sorted(glob(os.path.join(masks_dir, "*_mask.png")))
if not mask_paths:
    print("No mask files found")
    sys.exit(1)

def extract_orientation_histogram(mask_path, bins=36):
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0

    grad_x = cv2.Sobel(mask, cv2.CV_32F, 1, 0, ksize=5)
    grad_y = cv2.Sobel(mask, cv2.CV_32F, 0, 1, ksize=5)

    magnitude = np.sqrt(grad_x**2 + grad_y**2)
    orientation = np.arctan2(grad_y, grad_x)

    wrinkle_pixels = magnitude > 0.01
    if not wrinkle_pixels.any():
        return np.zeros(bins)

    orient_hist, _ = np.histogram(
        orientation[wrinkle_pixels],
        bins=bins,
        range=(-np.pi, np.pi),
        weights=magnitude[wrinkle_pixels],
    )
    orient_hist = orient_hist.astype(np.float64)
    norm = np.linalg.norm(orient_hist)
    if norm > 0:
        orient_hist /= norm
    return orient_hist

def describe_mask(mask_path):
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
    h, w = mask.shape

    wrinkle_pct = float(mask.sum() / mask.size) * 100

    grad_x = cv2.Sobel(mask, cv2.CV_32F, 1, 0, ksize=5)
    grad_y = cv2.Sobel(mask, cv2.CV_32F, 0, 1, ksize=5)
    magnitude = np.sqrt(grad_x**2 + grad_y**2)
    orientation = np.arctan2(grad_y, grad_x)

    wrinkle_pixels = magnitude > 0.01
    avg_orient = np.arctan2(
        np.sin(2 * orientation[wrinkle_pixels]).mean(),
        np.cos(2 * orientation[wrinkle_pixels]).mean(),
    ) / 2 if wrinkle_pixels.any() else 0.0

    contours, _ = cv2.findContours((mask * 255).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    num_regions = len(contours)

    areas = [cv2.contourArea(c) for c in contours if cv2.contourArea(c) > 0]
    avg_wrinkle_size = np.mean(areas) if areas else 0

    return {
        "wrinkle_pct": wrinkle_pct,
        "avg_orientation_deg": np.degrees(avg_orient),
        "num_regions": num_regions,
        "avg_wrinkle_size": avg_wrinkle_size,
    }

print(f"Loading {len(mask_paths)} masks from {masks_dir}...\n")

histograms = {}
descriptors = {}
for path in mask_paths:
    name = os.path.basename(path).replace("_mask.png", "")
    histograms[name] = extract_orientation_histogram(path)
    descriptors[name] = describe_mask(path)

print(f"{'Photo':<30} {'Wrinkle%':<10} {'AvgDir°':<10} {'Regions':<8} {'AvgSize':<10}")
print("-" * 70)
for name in sorted(descriptors.keys()):
    d = descriptors[name]
    print(f"{name:<30} {d['wrinkle_pct']:<10.2f} {d['avg_orientation_deg']:<10.1f} {d['num_regions']:<8} {d['avg_wrinkle_size']:<10.1f}")

print("\n--- Pairwise orientation similarity (top-20 most similar) ---\n")
results = []
for (n1, h1), (n2, h2) in combinations(histograms.items(), 2):
    sim = float(np.dot(h1, h2))
    d1, d2 = descriptors[n1], descriptors[n2]
    results.append((sim, n1, n2, abs(d1['wrinkle_pct'] - d2['wrinkle_pct'])))

results.sort(key=lambda x: -x[0])
print(f"{'Rank':<5} {'Similarity':<12} {'Photo 1':<30} {'Photo 2':<30} {'%Diff':<8}")
print("-" * 85)
for i, (sim, n1, n2, pct_diff) in enumerate(results[:20]):
    print(f"{i+1:<5} {sim:<12.4f} {n1:<30} {n2:<30} {pct_diff:<8.2f}")

print(f"\n--- Orientation histograms saved for analysis ---")
print("To visualize: use the data above or extend this script with matplotlib")
