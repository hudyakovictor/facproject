# DEEPUTIN V5 — Манифест рендеров (arhive recovery)

Восстановление после отката воркспейса (2026-08-05). Лимит генератора: 10/ход → этапы. PR #15.

## ✓ Восстановлено (23/42)

| Файл | Что |
|---|---|
| `docs/design-v5-main-page.png` | Главная (концепт) |
| `docs/design-v5-timeline-v4.png` | Таймлайн v4 — реальные данные ТЗ |
| `docs/design-v5-timeline-v5-99.png` | Таймлайн v5 — gate chain · СРАВНЕНИЕ · what-if |
| `docs/design-v5-timeline-v6.png` | Таймлайн v6 — доктрина (эпохи исправлены: 1999–2007 / 2008–2013 / 2014–2019 / 2020–2026 ✓) |
| `v5-screens/34-timeline-overview-v2.png` | Таймлайн: обзор 2× |
| `v5-screens/35-timeline-focus-v2.png` | Таймлайн: фокус 36× + live-пороги |
| `v5-screens/36-timeline-findings-v2.png` | Таймлайн: находки + A/B |
| `v5-screens/02-filters-live.png` | Фильтры + live-пороги |
| `v5-screens/03-profiles.png` | Профили 9 ракурсов |
| `v5-screens/04-data-manager.png` | Данные + provenance |
| `v5-screens/05-settings.png` | Настройки (дефолты + тест-фото) |
| `v5-screens/06-calibration.png` | Калибровка (median/MAD/p95, FDR, m) |
| `v5-screens/07-photo-lab.png` | Photo Lab (3D-стейдж, чипы, облако данных) |
| `v5-screens/08-landmark-compare.png` | Лендмарки A/B + парный скрабер |
| `v5-screens/09-morphing.png` | Морфинг (ручной скраб, re-scope, слои) |
| `v5-screens/10-advisor.png` | Advisor (дыры покрытия, приоритеты) |
| `v5-screens/11-pair-analysis.png` | Парный анализ (±20%, референс 1999–2005) |
| `v5-screens/12-logs.png` | Логи (структурные, цепи событий) |
| `v5-screens/13-run-manager.png` | Runs (статусы, preflight, retry=новый) |
| `v5-screens/ton-01-onchain-collage.png` | TON: NFT-коллаж |
| `v5-screens/ton-02-ton-integration.png` | TON: Mini App · минтинг · Stars |
| `v5-screens/ton-03-morphing-infra-funnel.png` | TON: инфра морфинга · хостинг · воронка |
| `v5-screens/` | + `34/35/36` v2 (см. выше) |

## ⏳ В очереди (19)

Разделы: `14-reports` · `15-blind-review` · `16-dataset-inventory` · `17-provenance` · `18-probe` · `19-evidence-package` · `20-run-diff` · `21-command-palette`
Кластеры (5): `22-clusters-chronology` · `23-clusters-embedding` · `24-clusters-cloud-far` · `25-clusters-cloud-near` · `26-clusters-switches`
Гипотезы (3): `27-hypothesis-validation` · `28-hypothesis-registry` · `29-shift-lab`
Дизайн-система (4): `30-design-system` · `31-design-system-states` · `32-design-system-dataviz` · `33-design-system-patterns`

План: этап 3 (14–21 + 2 кластера), этап 4 (остаток + финальный zip).

## Каноны
`ui-v4/docs/v5-user-brief.md`; доктрина таймлайна (ВЫШЕ/НИЖЕ/ВНИЗУ; 1 фото = 1 колонка; без glow); палитра #0b0e13/#10141b/#2b323e + 6 акцентов; футер «ОТОБРАЖЕНИЕ ДАННЫХ · НЕ ВЕРДИКТ»; изоляция «Валидации гипотез».
