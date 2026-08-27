#!/bin/bash
# verify_code.sh — Поиск в коде для проверки гипотез 3, 6 + допроверка

cd "$(dirname "$0")"

echo "============================================================"
echo "ГИПОТЕЗА 3: _build_references — UnboundLocalError?"
echo "============================================================"
echo "Поиск ci = cluster_bootstrap_ci и использования ci:"
grep -n "ci = cluster_bootstrap_ci\|ci_status\|ci_lo\|ci_hi" app6/stage2/calibration.py | head -20
echo ""
echo "Проверка логики:"
echo "  Если ci определён ТОЛЬКО внутри 'if len(set(finite_ids)) >= 2:'"
echo "  и используется СНАРУЖИ — будет UnboundLocalError"
echo ""

echo "============================================================"
echo "ГИПОТЕЗА 6: Coverage — реальное распределение pose_bin"
echo "============================================================"
if [ -f ui/real_examples/stage2/analysis_manifest.json ]; then
    echo "Из analysis_manifest.json:"
    grep -o '"pose_bin": "[^"]*"' ui/real_examples/stage2/analysis_manifest.json 2>/dev/null | sort | uniq -c || echo "  (не найдено в манифесте)"
fi
echo ""
if [ -f ui/public/data/pair_metrics.csv ]; then
    echo "Из pair_metrics.csv (первые 10):"
    head -2 ui/public/data/pair_metrics.csv
    echo "..."
    cut -d',' -f3 ui/public/data/pair_metrics.csv 2>/dev/null | sort | uniq -c | head -10 || echo "  (не удалось извлечь)"
fi
echo ""

echo "============================================================"
echo "ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: Все спорные поля"
echo "============================================================"

echo ""
echo "1. angle_noise_compensated (который читает engine.py:468):"
grep -rn "angle_noise_compensated" app6/ --include=*.py
echo ""

echo "2. *_angle_compensated (который пишет angle_noise.py):"
grep -rn "_angle_compensated" app6/ --include=*.py | head -10
echo ""

echo "3. has_stratified_references — что возвращает?"
grep -A10 "def has_stratified_references" app6/stage2/calibration.py
echo ""

echo "4. POSE_LEAKAGE_DISTANCE_THRESHOLD:"
grep -rn "POSE_LEAKAGE_DISTANCE_THRESHOLD" app6/ --include=*.py
echo ""

echo "5. pose_distance для profile bins:"
grep -n "profile\|PROFILE\|SUB_BIN" app6/stage2/analysis_policy.py 2>/dev/null | head -10
echo ""

echo "6. expression_gate использование в engine.py:"
grep -n "expression_gate\|expr_gate" app6/stage2/engine.py | head -15
echo ""

echo "7. evidence_state с confidence=limited:"
grep -n "confidence\|limited\|evidence_state" app6/stage2/evidence.py | head -15
echo ""

echo "============================================================"
echo "ИТОГО: Поиск в коде завершён"
echo "============================================================"
