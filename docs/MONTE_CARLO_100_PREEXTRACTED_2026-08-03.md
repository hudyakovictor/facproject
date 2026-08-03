# Monte Carlo: 100 сценарных симуляций предизвлечённой геометрии

**Исполнение:** 2026-08-03

```bash
python tools/run_scenario_monte_carlo.py \
  --input calibration_dataset \
  --output /tmp/monte_carlo_100.json \
  --runs 100 --seed 20260803
```

## Конфигурация

Каждый запуск выбирал один из S01–S08 и один из девяти pose bins. Если fixture нельзя собрать из разных neutral-кадров без нарушения production axis-specific pose gate, запуск получал `blocked`; порог не ослаблялся. Для измеримых fixtures применялась одна из контролируемых perturbations:

- без добавленного шума;
- малый и высокий isotropic coordinate noise;
- 15% или 85% artificial landmark visibility dropout;
- искусственный pitch shock +10°;
- точный duplicate кадра.

Геометрия: LDM134 raw-object-normalized, trimmed Kabsch без scale. Порог: P95 pose-matched same-person null соответствующего bin. Все даты в fixture синтетические и задают только порядок.

## Результат

| Показатель | Значение |
|---|---:|
| Запрошено запусков | 100 |
| Измеримых | 56 |
| Честно blocked | 44 |
| Passed guard checks | 55 |
| Выявленных failures | 1 |

Единственный наблюдённый failure: **run 17**, `S01 / left_mid / coordinate_noise_high`: NULL-последовательность создала один false transition. Это не является биометрическим выводом; это конкретная техническая граница устойчивости текущего landmark-only порога при добавленном шуме.

## Выявленные доработки

1. **Стратифицированный NULL threshold.** P95 same-person null нельзя применять как единственную линию для кадров с различной геометрической нестабильностью. Добавить reference strata минимум по visibility coverage, residual pose distance, quality/expression state и bin. Порог формируется на train persons, проверяется LOPO.
2. **Persistent-event gate.** Одиночный переход не должен становиться persistent chronology event без соседнего подтверждения/anchor comparison. Для S01 добавляется hard acceptance: `event_length >= 2` либо независимое подтверждение в другом source/date/bin; иначе `isolated_outlier/retest_required`.
3. **Добор coverage.** 44% fixture-слотов не собраны без ослабления pose gate. Требуются новые neutral кадры, особенно для profile/deep/right-mid, причём в совпадающих profile sub-bins и с допустимыми pitch/roll.
4. **Следующий слой симуляций.** Landmark-only suite не проверяет source provenance, duplicate perceptual hashes, raw image crop, UV/skin/texture, EXIF conflict и UI/export research mode. Эти 6 семейств должны быть добавлены после доступа к исходным фото и Stage-1 outputs.

## Не обнаруженные нарушения в доступной области

В измеримых runs pitch shock был остановлен pose gate; severe visibility dropout не превратился в измеренный score; exact duplicate не создал геометрический переход. Это означает только, что эти guards выдержали данный набор perturbations — не освобождает их от интеграционных тестов Stage 1 → Stage 2 → Stage 3 → API/UI.
