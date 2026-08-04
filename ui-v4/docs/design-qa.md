# UI v4 — матрица 150 факторов

Оценочная матрица реализации: 15 групп × 10 факторов. `PASS` означает наличие механизма в исходном коде; runtime/build проверяется в окружении проекта с уже установленными зависимостями.

## Timeline mechanics

- [001] **PASS** — cursor-anchored zoom
- [002] **PASS** — 96x zoom range
- [003] **PASS** — fit range
- [004] **PASS** — horizontal wheel pan
- [005] **PASS** — shift-wheel pan
- [006] **PASS** — space hand tool
- [007] **PASS** — middle-button pan
- [008] **PASS** — playhead ruler
- [009] **PASS** — date-proportional layout
- [010] **PASS** — navigator viewport

## Data integrity

- [011] **PASS** — no mocks
- [012] **PASS** — no random values
- [013] **PASS** — no seeded data
- [014] **PASS** — app6 timeline only
- [015] **PASS** — app6 image only
- [016] **PASS** — app6 detail only
- [017] **PASS** — app6 QC only
- [018] **PASS** — app6 skin only
- [019] **PASS** — app6 pair metrics only
- [020] **PASS** — null is not zero

## Forensic safety

- [021] **PASS** — not-a-verdict label
- [022] **PASS** — no H0/H1/H2
- [023] **PASS** — no identity posterior
- [024] **PASS** — no client evidence score
- [025] **PASS** — flags are source data
- [026] **PASS** — quality is source data
- [027] **PASS** — pair fetched on demand
- [028] **PASS** — errors stay visible
- [029] **PASS** — rejected rows counted
- [030] **PASS** — filters are non-destructive

## Nine-pose workflow

- [031] **PASS** — nine fixed tracks
- [032] **PASS** — canonical pose order
- [033] **PASS** — Russian pose labels
- [034] **PASS** — per-track counts
- [035] **PASS** — track visibility
- [036] **PASS** — pose filter
- [037] **PASS** — frontal center track
- [038] **PASS** — left/right symmetry
- [039] **PASS** — persistent rail
- [040] **PASS** — lane alternation

## Performance

- [041] **PASS** — viewport virtualization
- [042] **PASS** — lazy thumbnails
- [043] **PASS** — bounded hover work
- [044] **PASS** — memoized filtering
- [045] **PASS** — memoized bounds
- [046] **PASS** — single scroll surface
- [047] **PASS** — SVG quality polyline
- [048] **PASS** — no canvas redraw loop
- [049] **PASS** — no timer polling
- [050] **PASS** — abort timeout API

## Navigation

- [051] **PASS** — A selection
- [052] **PASS** — B selection
- [053] **PASS** — shift-click B
- [054] **PASS** — double-click original
- [055] **PASS** — ruler seek
- [056] **PASS** — navigator click
- [057] **PASS** — search
- [058] **PASS** — pose filter
- [059] **PASS** — flag filter
- [060] **PASS** — quality filter

## Inspector

- [061] **PASS** — face crop
- [062] **PASS** — original link
- [063] **PASS** — core metadata
- [064] **PASS** — pose angles
- [065] **PASS** — quality display
- [066] **PASS** — confidence display
- [067] **PASS** — flags display
- [068] **PASS** — detail tab
- [069] **PASS** — QC tab
- [070] **PASS** — skin tab

## Comparison

- [071] **PASS** — A/B status
- [072] **PASS** — secondary highlight
- [073] **PASS** — pair endpoint
- [074] **PASS** — no pair placeholder
- [075] **PASS** — selection colors
- [076] **PASS** — A/B footer
- [077] **PASS** — secondary guidance
- [078] **PASS** — URL encoding
- [079] **PASS** — error handling
- [080] **PASS** — loading handling

## Visual hierarchy

- [081] **PASS** — dark edit-suite theme
- [082] **PASS** — fixed toolbar
- [083] **PASS** — secondary filterbar
- [084] **PASS** — fixed track rail
- [085] **PASS** — red playhead
- [086] **PASS** — cyan primary
- [087] **PASS** — amber secondary
- [088] **PASS** — flag marker
- [089] **PASS** — era bands
- [090] **PASS** — compact status dock

## Accessibility

- [091] **PASS** — semantic buttons
- [092] **PASS** — native selects
- [093] **PASS** — native range
- [094] **PASS** — image alt context
- [095] **PASS** — tool titles
- [096] **PASS** — high contrast text
- [097] **PASS** — visible focus via browser
- [098] **PASS** — text status not color-only
- [099] **PASS** — responsive inspector
- [100] **PASS** — responsive rail

## Responsiveness

- [101] **PASS** — desktop workspace
- [102] **PASS** — 1050px inspector overlay
- [103] **PASS** — 760px compact rail
- [104] **PASS** — fluid search
- [105] **PASS** — bounded inspector width
- [106] **PASS** — no body scroll
- [107] **PASS** — horizontal timeline scroll
- [108] **PASS** — touchpad deltas
- [109] **PASS** — overscroll containment
- [110] **PASS** — mobile-safe controls

## API resilience

- [111] **PASS** — 45s timeout
- [112] **PASS** — HTTP detail surfaced
- [113] **PASS** — JSON error fallback
- [114] **PASS** — invalid row rejection
- [115] **PASS** — unknown pose rejection
- [116] **PASS** — timestamp validation
- [117] **PASS** — empty state
- [118] **PASS** — error state
- [119] **PASS** — loading state
- [120] **PASS** — manual retry

## Code architecture

- [121] **PASS** — typed Photo
- [122] **PASS** — typed Pose union
- [123] **PASS** — typed Era
- [124] **PASS** — central API adapter
- [125] **PASS** — central route encoding
- [126] **PASS** — isolated renderer
- [127] **PASS** — memoized derived data
- [128] **PASS** — single source selection
- [129] **PASS** — CSS variables
- [130] **PASS** — no external icon dependency

## Investigator ergonomics

- [131] **PASS** — Premiere-like lanes
- [132] **PASS** — clip thumbnails
- [133] **PASS** — date labels
- [134] **PASS** — quality strip
- [135] **PASS** — flag badges
- [136] **PASS** — era labels
- [137] **PASS** — hover title
- [138] **PASS** — visible zoom percent
- [139] **PASS** — visible record count
- [140] **PASS** — live app6 status

## Delivery quality

- [141] **PASS** — standalone ui-v4
- [142] **PASS** — Vite proxy config
- [143] **PASS** — production API base
- [144] **PASS** — Russian README
- [145] **PASS** — control documentation
- [146] **PASS** — API map
- [147] **PASS** — static verifier
- [148] **PASS** — 150-factor rubric
- [149] **PASS** — source-only archive
- [150] **PASS** — no dependency installation
