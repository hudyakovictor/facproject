#!/bin/bash
set -e

SRC="/Volumes/SDCARD/photo/main"
DST="/Users/victorkhudyakov/work/photos_150x150"

total=0
done=0
failed=0

while IFS= read -r -d '' file; do
    total=$((total + 1))
    basename=$(basename "$file")
    out="$DST/$basename"
    if sips -s format jpeg --resampleHeightWidth 150 150 "$file" --out "$out" >/dev/null 2>&1; then
        done=$((done + 1))
    else
        failed=$((failed + 1))
        echo "FAILED: $basename"
    fi
    if (( total % 100 == 0 )); then
        echo "Processed $total/$total... done=$done failed=$failed"
    fi
done < <(find "$SRC" -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.tiff' -o -iname '*.tif' -o -iname '*.gif' -o -iname '*.bmp' \) -print0 | sort -z)

echo "=== RESULT: total=$total done=$done failed=$failed ==="
