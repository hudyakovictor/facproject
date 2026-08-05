# DEEPUTIN V5 — Манифест рендеров (арhive recovery)

Статус восстановления после отката воркспейса (2026-08-05). Лимит генератора: 10 изображений за ход → восстановление идёт этапами по ~10.

## ✓ Восстановлено (13)

| Файл | Что |
|---|---|
| `docs/design-v5-main-page.png` | Главная страница (концепт) |
| `docs/design-v5-timeline-v4.png` | Таймлайн v4 — реальные данные ТЗ |
| `docs/design-v5-timeline-v5-99.png` | Таймлайн v5 — gate chain, СРАВНЕНИЕ, what-if |
| `v5-screens/34-timeline-overview-v2.png` | Состояние таймлайна: обзор 2× |
| `v5-screens/35-timeline-focus-v2.png` | Состояние: фокус 36× + live-пороги |
| `v5-screens/36-timeline-findings-v2.png` | Состояние: находки + сравнение A/B |
| `v5-screens/02-filters-live.png` | Фильтры + плавающие live-пороги |
| `v5-screens/03-profiles.png` | Профили 9 ракурсов |
| `v5-screens/04-data-manager.png` | Менеджер данных + provenance |
| `v5-screens/ton-01-onchain-collage.png` | TON: NFT-коллаж |
| `v5-screens/ton-02-ton-integration.png` | TON: Mini App, минтинг, Stars |
| `v5-screens/ton-03-morphing-infra-funnel.png` | TON: инфра морфинга + хостинг + воронка |

## ⚠ К перегенерации (артефакт рендера)

| Файл | Проблема |
|---|---|
| `docs/design-v5-timeline-v6.png` | Генератор нарисовал **5 эпох с чужими границами** (1999–2004…2021–2026). Канонические эпохи (`ERA_BOUNDS`): **1999–2007 / 2008–2013 / 2014–2019 / 2020–2026**. Также gutter перенасыщен (флаги/−3 на каждой колонке). |

## ⏳ В очереди на восстановление (29)

Экраны разделов: `05-settings` · `06-calibration` · `07-photo-lab` · `08-landmark-compare` · `09-morphing` · `10-advisor` · `11-pair-analysis` · `12-logs` · `13-run-manager` · `14-reports` · `15-blind-review` · `16-dataset-inventory` · `17-provenance` · `18-probe` · `19-evidence-package` · `20-run-diff` · `21-command-palette`
Кластеры (5): `22-clusters-chronology` · `23-clusters-embedding` · `24-clusters-cloud-far` · `25-clusters-cloud-near` · `26-clusters-switches`
Гипотезы (3): `27-hypothesis-validation` · `28-hypothesis-registry` · `29-shift-lab`
Дизайн-система (4 листа): `30-design-system` · `31-design-system-states` · `32-design-system-dataviz` · `33-design-system-patterns`

План: этапы по 10/ход → 3 хода до полного набора (42 рендера итого).

## Каноны, по которым восстанавливаем
`ui-v4/docs/v5-user-brief.md` — все требования; доктрина таймлайна (ВЫШЕ/НИЖЕ/ВНИЗУ, 1 фото = 1 колонка, без glow); палитра #0b0e13/#10141b/#2b323e + 6 акцентов; футер «ОТОБРАЖЕНИЕ ДАННЫХ · НЕ ВЕРДИКТ».
