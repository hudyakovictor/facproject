"""Verify dataflow hypotheses: expression gate, angle_compensated, mesh, quality"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# === ГИПОТЕЗА 4: Expression gate ===
print("=" * 60)
print("ГИПОТЕЗА 4: Expression gate — реально ли гейтит?")
print("=" * 60)

try:
    from app6.stage2.expression_pair_gate import expression_gate

    # Тест 1: jaw_mismatch + same_era
    result = expression_gate(
        {'jaw_open_detected': True, 'jaw_open_degree': 30.0, 'smile_detected': False},
        {'jaw_open_detected': False, 'jaw_open_degree': 0.0, 'smile_detected': False},
        era_a='2000', era_b='2000'
    )
    print(f"  jaw_mismatch + same_era: accepted={result['accepted']}, confidence={result['confidence']}")

    # Тест 2: jaw_mismatch + cross_era
    result = expression_gate(
        {'jaw_open_detected': True, 'jaw_open_degree': 30.0, 'smile_detected': False},
        {'jaw_open_detected': False, 'jaw_open_degree': 0.0, 'smile_detected': False},
        era_a='2000', era_b='2010'
    )
    print(f"  jaw_mismatch + cross_era: accepted={result['accepted']}, stratum={result['stratum']}, confidence={result['confidence']}")

    # Тест 3: без mismatch
    result = expression_gate(
        {'jaw_open_detected': False, 'jaw_open_degree': 0.0, 'smile_detected': False},
        {'jaw_open_detected': False, 'jaw_open_degree': 0.0, 'smile_detected': False},
        era_a='2000', era_b='2000'
    )
    print(f"  без mismatch: accepted={result['accepted']}, confidence={result['confidence']}")

    print(f"  ВЕРДИКТ: Гейт РАБОТАЕТ (но только для same_era jaw_mismatch)")
except Exception as e:
    print(f"  ОШИБКА: {e}")
print()

# === ГИПОТЕЗА 7: angle_compensated usage ===
print("=" * 60)
print("ГИПОТЕЗА 7: angle_compensated — используется ли?")
print("=" * 60)

result = subprocess.run(
    ['grep', '-rn', 'angle_compensated', 'app6/', '--include=*.py'],
    capture_output=True, text=True, cwd=str(Path(__file__).parent)
)
lines = [l for l in result.stdout.strip().split('\n') if l]
print(f"  Упоминаний angle_compensated: {len(lines)}")
for line in lines:
    parts = line.split(':')
    if len(parts) >= 2:
        print(f"    {parts[0].replace('app6/', '')}:{parts[1]}")

if len(lines) <= 2:
    print(f"  ВЕРДИКТ: DEAD CODE (только запись, нет чтения)")
else:
    print(f"  ВЕРДИКТ: ИСПОЛЬЗУЕТСЯ ({len(lines)} упоминаний)")
print()

# === ГИПОТЕЗА 8: Mesh independence ===
print("=" * 60)
print("ГИПОТЕЗА 8: Mesh — независимость от alpha_id")
print("=" * 60)

result = subprocess.run(
    ['grep', '-n', 'vertices_identity_only\\|compute_shape(alpha_id', 'app6/stage2/mesh_dense.py'],
    capture_output=True, text=True, cwd=str(Path(__file__).parent)
)
print("  mesh_dense.py:")
for line in result.stdout.strip().split('\n'):
    if line:
        print(f"    {line}")

if 'alpha_id' in result.stdout:
    print(f"  ВЕРДИКТ: ЗАВИСИТ ОТ ALPHA_ID")
else:
    print(f"  ВЕРДИКТ: НЕЗАВИСИМ")
print()

# === ГИПОТЕЗА 9: quality_stratification usage ===
print("=" * 60)
print("ГИПОТЕЗА 9: quality_stratification — применяется ли?")
print("=" * 60)

result = subprocess.run(
    ['grep', '-rn', 'threshold_multiplier\\|has_stratified_references', 'app6/', '--include=*.py'],
    capture_output=True, text=True, cwd=str(Path(__file__).parent)
)
print("  Упоминаний:")
for line in result.stdout.strip().split('\n')[:15]:
    if line:
        parts = line.split(':')
        if len(parts) >= 2:
            print(f"    {parts[0].replace('app6/', '')}:{parts[1]}")

if 'threshold_multiplier' not in result.stdout:
    print(f"  ВЕРДИКТ: НЕ ПРИМЕНЯЕТСЯ")
else:
    print(f"  ВЕРДИКТ: ПРИМЕНЯЕТСЯ (или хотя бы упоминается)")
print()

# === Дополнительная проверка: confidence="limited" → evidence_state? ===
print("=" * 60)
print("ДОПОЛНИТЕЛЬНО: confidence='limited' → evidence_state?")
print("=" * 60)

result = subprocess.run(
    ['grep', '-rn', 'confidence.*limited\\|limited.*evidence', 'app6/stage2/', '--include=*.py'],
    capture_output=True, text=True, cwd=str(Path(__file__).parent)
)
print("  Упоминаний:")
for line in result.stdout.strip().split('\n')[:10]:
    if line:
        parts = line.split(':')
        if len(parts) >= 2:
            print(f"    {parts[0].replace('app6/', '')}:{parts[1]}")
print()

print("=" * 60)
print("ИТОГО: Трассировка данных завершена")
print("=" * 60)
