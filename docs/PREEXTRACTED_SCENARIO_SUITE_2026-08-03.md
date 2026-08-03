# Исполнение сценарной suite на предизвлечённой калибровке

**Команда:**

```bash
python tools/run_preextracted_scenario_suite.py \
  --input calibration_dataset --output /tmp/scenario_suite.json
```

**Версия suite:** `deeputin-preextracted-scenario-suite-v1.0`.

## Что реально было выполнено

Запущены восемь сценариев S01–S08 в каждом из девяти pose bins: всего **72** запусков. Для роли A/B/C автоматически отбирались разные персоны с достаточным количеством neutral-кадров; каждая следующая запись должна была пройти используемый в production axis-specific pose gate. Ландмарки — LDM134 raw-object-normalized; pair metric — RMS после trimmed Kabsch без scale. Порог каждого ракурса — 95-й перцентиль pose-matched same-person соседних пар соответствующего bin.

| Результат | Количество |
|---|---:|
| Запланировано scenario × bin | 72 |
| Измерено | 39 |
| Честно blocked | 33 |

`blocked` не является ошибкой harness. Он означает, что имеющаяся калибровка не позволила собрать fixture из нейтральных кадров **без нарушения pose gate**. Основные причины: `no_cross_step_pose_matched_frame` в profile/deep bins и недостаточное число разных персон с нужным числом neutral кадров.

## Проверка AABBAA

S03 (`AABBAA`) исполнился и корректно локализовал ожидаемые границы `[2, 4]`, а return-condition был наблюдён в следующих bins:

- `left_deep`;
- `left_mid`;
- `left_light`;
- `frontal`;
- `right_light`.

В `left_profile`, `right_mid`, `right_deep`, `right_profile` S03 заблокирован до измерения из-за отсутствия pose-matched межролевого кадра. Это правильный fail-closed результат: suite не ослабляет угловой gate только для того, чтобы получить демонстрационный AABBAA.

## Интерпретация

Этот запуск подтверждает, что на доступной части corpus сценарный отбор, 3-axis pose gate, same-person null threshold, pairwise raw geometry и detection границ могут быть прогнаны end-to-end без подмены данных. Он **не** доказывает ни различие лиц, ни реальную смену личности: A/B/C — контролируемые роли, synthetic dates задают только порядок, а выборка зависима по видеосериям.

## Следующий технический gate

Для полного покрытия девяти ракурсов необходимо добрать для каждого profile/deep bin по меньшей мере три независимые персоны, у которых есть: 1) нужное число neutral кадров, 2) одинаковый profile sub-bin, 3) pose-matched pitch/roll, 4) достаточный LDM134 visibility. После этого тот же suite запускается повторно, а JSON/HTML из `/tmp/scenario_suite.*` становятся golden fixture для Stage 2 → Stage 3 → API → UI/export regression.
