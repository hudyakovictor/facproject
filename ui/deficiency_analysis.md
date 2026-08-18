# 100-Key Deficiency Analysis & Completion Plan

## Overview
Analysis of the DEEPUTIN Forensic Timeline UI codebase against the NEXT_ITERATION_MASTER_PLAN.md roadmap (V8 → V95+). 100 key deficiencies identified across 6 stages, each mapped to its corresponding gate.

---

## STAGE 1: Normative Data Contract (Analyses 1-10)

1. **Evidence state not isolated** - UI components may derive evidence state independently rather than through `classifyPair` from `timeline-data-contract.ts`, violating Gate 1: "ни один UI-компонент не определяет evidence state самостоятельно"

2. **No version enforcement in payload** - `checkContractVersion` only logs warnings, doesn't reject mismatched versions automatically on data load

3. **Pair classification relies on status strings** - fragile if backend changes status format; no schema evolution path documented

4. **`pickDisplayPair` ranking edge cases** - limited pair selection may miss valid candidates when `ranked` filter is too restrictive with current ranking logic

5. **No data contract validation on app init** - validation only on explicit `checkContractVersion` calls, not automatic on the 4 data file loads in App.tsx

6. **`FrameEvent` kind coverage incomplete** - `getFrameEvents` handles date/duplicate/same_day/limited but may miss provenance-related event kinds

7. **`PairClass` always `reportable:false`** - all kinds have `reportable:false`; may need reconsideration for some diagnostic cases that could be reportable

8. **No i18n in contract** - all labels hardcoded Russian/English mix; no localization support or i18n keys

9. **`validatePairConnection` strict field check** - may reject valid pairs with extra legitimate fields not in the whitelist of required fields

10. **No schema evolution path** - adding new fields requires code changes; no forward/backward compatibility mechanism or version tolerance

---

## STAGE 2: Track Registry (Analyses 11-20)

11. **`pair_anchor` display range mismatch** - `displayMin: log(14000), displayMax: log(23000)` but `getPair: p => p.meshAnchorFraction` returns 0-1 fraction, not log-scaled

12. **`pair_visibility` upper bound too restrictive** - `displayMax: 0.7` but `meshVisibleFraction` can be up to 1.0; should be `1.0` or higher

13. **`pair_fdr` display range vs boolean** - `displayMax: 1` but `mtSignificantFdr10` is boolean; should use discrete scale `scale: 'discrete'` with values 0/1

14. **Expression track arbitrary bounds** - `displayMin: 2.8, displayMax: 10.2` with no backend calibration reference or quantile documentation

15. **`jaw_open` arbitrary max** - `displayMax: 142` with no documentation of calibration source or max observed value in dataset

16. **`corner_lift` range unexplained** - `displayMin: -0.07, displayMax: 0.11` not documented against any specific metric range or quantile

17. **`skin_auth` z-score ranges not linked to quantiles** - `displayMin: -1.5, displayMax: 3.5` without reference to specific q95/q99 values from calibration data

18. **Zone metrics robustZ noted as una calibrated** - types.ts comment warns robustZ zones are not calibrated (`calibrationStatus=insufficient_calibration`, median ~2.8e6), yet `zones` track group exists with no trackIds populated

19. **`anisotropy` and `hard_area` arbitrary max values** - `displayMax: 3.7` and `displayMax: 0.6` with no backend reference or calibration documentation

20. **`uv_mean_confidence` and `tenengradMean` excluded but no opt-in alternative** - excluded with reasons in EXCLUDED_FIELDS but no replacement track provided in TRACKS for opt-in exploration

---

## STAGE 3: Event/Roles Lanes (Analyses 21-30)

21. **Event symbols have inconsistent visual weight** - `◆`, `!`, `≈`, `#` differ in complexity/stroke density; may confuse users trying to distinguish them quickly

22. **Role icon ⇄ (double arrow) ambiguity** - may not be immediately understandable as "both A and B roles present"; no legend or tooltip explanation in compact view

23. **No textual explanation for event icons on hover** - only symbol shown in tooltip; no context, severity, or meaning description provided

24. **Role icons too small at low zoom** - `iconSize` min 8px may be hard to distinguish, especially for users with visual impairments or on low-DPI displays

25. **Event aggregation in stack may lose details** - `eventsOf` deduplication via `seen` set silently drops duplicate events of same kind+symbol combination

26. **Same-day stack doesn't differentiate `#1` vs `#3+`** - all same-day frames shown same way regardless of count; no visual hierarchy for stack depth

27. **Event row doesn't show event count** - when multiple events per frame, only first event button rendered; count not displayed in label or tooltip

28. **No keyboard-focusable event icons** - missing `tabIndex` on event buttons; poor accessibility for keyboard-only users

29. **No aria-label on event markers** - beyond basic description, no detailed accessibility support explaining what the event is

30. **Color-blind distinguishability** - event icons rely on color + symbol combination; not all distinguishable for color-blind users (deuteranopia/protanopia)

---

## STAGE 4: Pair Inspection Flow (Analyses 31-45)

31. **Gate stack "Геометрическое изменение (raw)" incomplete** - shows raw metrics but no calibrated comparison, no "what disproves candidate" guidance specific to this case

32. **FDR gate lacks interpretation** - shows p-value and q-value but no "what this means in practice" explanation of FDR10 significance threshold

33. **Calibration gate missing distribution reference** - shows status/counts but no calibration curve, historical distribution, or what "elevated" means relative to calibration population

34. **Quality gate missing pass/fail criteria** - shows evidence level but no explicit QC pass/fail thresholds documented or referenced from calibration data

35. **No persistence summary in gate stack** - whether this pair is part of a candidate chain / persistence cluster not summarized or linked to minimap clusters

36. **Alternative explanations not listed in any gate** - e.g., "pose mismatch could explain residuals" not mentioned in any of the 11 gates; confounder explanations deferred

37. **Role information (`mtRole`, `mtRoleDetail`) not explained** - shown in FDR gate but no explanation of what role means in multiple testing context (diagnostic_only vs evidence vs candidate)

38. **Raw vs compensated values not side-by-side** - gate shows raw metrics but no compensated/alternative values for comparison; user cannot assess calibration effect

39. **Common/calibrated point support no visual representation** - vertex/anchor counts shown but no visual glyph, sparkline, or histogram showing support distribution

40. **Date provenance limited shown yes/no only** - no explanation of date conflict reasons, provenance logic, or what "limited" means for the pair's validity

41. **Near duplicate pair shown yes/no only** - no similarity score, Jaccard index, or visual comparison to original pair displayed

42. **Expression mismatch flagged but no confounder note** - in some cases missing "this is a confounder (soft tissue), not identity evidence" note per forensic methodology

43. **Alignment residual no threshold explanation** - shown with gate color (ok/caution) but no "good/bad" threshold explanation outside the gate color; what does 0.032 mean?

44. **Pose bin shown without reference to same-bin pairs** - no comparison to other pairs in same pose bin for contextual understanding of whether this is anomalous for the bin

45. **No "what would disprove candidate" guidance** - gate stack doesn't suggest what additional evidence (calibration, FDR, persistence, independent analysis) would counteract the candidate status

---

## STAGE 5: Scaling and Performance (Analyses 46-65)

46. **Wheel zoom cursor anchoring formula may jump** - `logical = (sc + cursor - GUTTER) / s` may cause position discontinuities at scale boundaries; cursor position not preserved relative to content

47. **Slot change may produce non-smooth transitions** - `next = Math.max(MIN_SLOT, Math.min(MAX_SLOT, s * (e.deltaY > 0 ? 0.9 : 1.1))` may skip intermediate zoom levels; visible jump rather than smooth acceleration

48. **No zoom limits** - slot range 9-200 may produce thumbnails too small (<52px per V3 plan) or too large (>112px per V3 plan); no min/max enforcement per visual readability

49. **No continuous row guarantee at extremes** - at extreme zooms, thumbnails may overlap or have gaps despite LOD removal; continuous row integrity not guaranteed at all slot values

50. **Hover computation inefficient** - `cursorInfo` memo depends on `pairMarks` which recomputes on every render cycle; O(n) scan of graphPairs on every mousemove

51. **Minimap cluster computation O(n) on every frame change** - may be slow with 1909 frames; no memoization cache based on slot/scroll state; visible lag when changing selection

52. **No virtualization of visible items only** - `visible` memo computes all 1910 frames then filters by viewport; should intersect with viewport first for performance

53. **No reduced-motion support** - wheel zoom may trigger vestibular issues for some users; no `prefers-reduced-motion` media query respect or alternative navigation

54. **Keyboard pan limited** - Arrow keys move between frames but no pan+zoom combination control for navigation; users cannot pan while zoomed in using keyboard alone

55. **High-DPI rendering may be blurry** - CSS uses absolute pixels; no `devicePixelRatio` adjustment for SVG line rendering; may appear fuzzy on 2x/3x Retina displays

56. **Thumbnail loading no neighbor prefetch** - `loading="lazy"` but no `prefetch` of adjacent thumbnails for smooth drag; visible delay when dragging across sparse areas

57. **Missing thumbnail handling no placeholder** - onError sets `display:none` but no fallback texture or placeholder image; broken layout when thumbnail fails to load

58. **Scroll state not loaded on initial load** - URL hash state saved via `viewRef` but not applied if no hash present in initial URL; fresh load defaults to slot 86/scroll 0

59. **Bands recalculation on every render** - `bands` memo depends on `c` (collapsed set) with no shallow equality guard; may recompute unnecessarily on unrelated state changes

60. **Series lines recompute on every frame** - even when photo metrics unchanged, `series` memo recalculates all 1910 frame lines; unnecessary DOM work

61. **pairMarks memo depends on showFamilies toggle** - unnecessary recomputation when only pose filter changes; `showFamilies` dependency may cause extra work

62. **No debounce on window resize** - layout recalculates immediately on resize, may cause flash/thrashing; should debounce resize events for layout recalculation

63. **SVG line rendering of 1910 frames may be heavy** - no Canvas fallback for high-frame-count scenarios; may cause browser frame drops on low-end machines

64. **Content width calculation may overflow** - `contentW = GUTTER + frames.length * slot + 48` may exceed max safe integer (`Number.MAX_SAFE_INTEGER`) at very large frame counts beyond 1910

65. **No virtualization threshold** - no switch to canvas rendering when visible frame count exceeds threshold (e.g., >200); performance degrades gracefully rather than failing

---

## STAGE 6: Visual/QA Deficiencies (Analyses 66-100)

66. **1920×1080 default may have clipping** - need verification that all lanes (graph + photo + role + event + qc + ruler) fit within viewport without overflow at default slot=86

67. **1440×900 may have different row calculations** - slot/band fractions may produce different layout than 1080p default; some lanes may be compressed or expanded unexpectedly

68. **1366×768 may cut off bottom lanes** - ruler (40px) + mini-lanes (roleH + evH + qcH, each ~30-38px) may exceed available height; vertical scroll may be needed

69. **Candidate pair visual distinction unclear** - candidate (`▲`) vs persistent (`◆`) vs limited (`!`) may not be distinguishable at small thumbnail sizes (<52px width)

70. **Limited pair `!` icon confusion** - may be confused with event markers or other symbols in the UI; no clear visual differentiation from duplicate `≈` or other icons

71. **Same-day stack may overlap other UI** - expanded stack position calculated but may overlap with mini-lanes or ruler at certain slot values; z-index may not always prevent

72. **Date conflict indicator visual confusion** - conflict marker may be visually confused with other red/orange indicators (anomaly markers, FDR rings); lack of clear semantic distinction

73. **Missing/null measurements edge case** - empty state only triggers when `frames.length <= 8`; smaller edge cases (0 frames, 1 frame, exactly 2-7 with no pairs) not handled gracefully

74. **Long historical gap visual representation** - large year gaps on ruler may leave large empty spaces without visual guidance; no indication of "gap > N years" between frames

75. **All nine pose bins render correctly** - need verification that all 9 pose colors render consistently across browsers/renderers; no cross-browser testing documented

76. **Contrast check may fail WCAG AA** - pale colors (e.g., `#eab308` on `#0a0e14` base) may not meet minimum contrast ratio of 4.5:1 for normal text; some band labels may be illegible

77. **Focus check may have focus traps** - keyboard navigation through thumbnails/pairs may trap focus in certain states; no `Shift+Tab` or explicit focus management for cycle navigation

78. **Terminology misinterpretation risk** - "candidate" may be misinterpreted as "verified conclusion" rather than "hypothesis needing proof"; no visible "NEVER A VERDICT" safety tag per V8 plan

79. **No false semantic overlap between events and roles** - event icons (`◆`, `!`) not confused with role icons (`A`, `B`, `⇄`); visual design ensures distinct shapes and meanings

80. **No clipping on container** - SVG elements may overflow the timeline container without explicit `overflow:hidden` clipping; may cause unexpected overflow on parent elements

81. **Thumbnail selection highlight visibility** - blue selection ring may be too thin at small zooms (pixel-width) or too thick at large zooms; may not meet minimum hit-target size

82. **Readout panel may overlap band labels** - at certain scroll positions, the right-side readout may overlap left-side band labels; no z-index or positioning guard

83. **Mini-lane height may be too compressed** - at small viewport heights, role/event lanes may be squashed to unreadable size (<20px); no minimum height enforcement

84. **Band labels may overlap graph lines** - at certain slot values, band label positions (`top + 10px`) may intersect with data lines; no collision detection or position adjustment

85. **Empty state only at <=8 frames** - many other edge cases (0 frames, 1 frame, all-cadres) not covered by empty state message; no guidance for these states

86. **No responsive band label positioning** - band labels always at fixed `top + 10px` may not adapt to varying band heights when collapsed sets change lane allocation

87. **Minimap bookmark clusters may overlap view rect** - `mm-book` paths may be clickable outside visual bounds; no hit-test guard for edge cases

88. **No motion reduction for wheel users** - wheel zoom acceleration may need `prefers-reduced-motion` media query respect; no reduced-motion alternative navigation provided

89. **No accessibility statement for data interpretation** - no note that "candidate ≠ verdict" visible in UI chrome; safety tag exists on toolbar but may not be noticeable enough during analysis

90. **No print/export version for QA** - no way to generate printed/QA report of current viewport state; no "print" button or export current view as PDF/PNG for journalistic use

91. **No snapshot/export of current analysis state** - inability to export current zoom/position/selection for report generation; no "Save view" or "Copy state" functionality

92. **No DND interference** - drag start may interfere with native page scrolling on mobile/trackpads; no `touch-action: none` or proper pointer event handling

93. **No touch-friendly hit areas below 12px** - some interactive elements (mini-lane icons, band labels) may be below recommended 12px minimum hit target for finger/touch accuracy

94. **Video frame consistency across reload** - pose/zoom/scroll state not fully persisted across page reload; only URL hash state saved, not localStorage or sessionStorage

95. **No locale-specific date formatting** - dates displayed as `YYYY-MM-DD` format; no locale-aware formatting for different user regions or international users

96. **No help/tooltip on gate stack symbols** - gate stack uses symbols and colors; no tooltips explaining what each gate level means for new users

97. **No data version changelog in UI** - no display of `DATA_CONTRACT_VERSION` or current data schema version; users cannot know if they're working with latest data

98. **No performance indicator** - no FPS counter, memory usage, or rendering time indicator for power users debugging performance issues

99. **No keyboard shortcut cheatsheet** - keyboard hints shown in toolbar (`←/→ кадр · [/] пара · C кандидаты · Enter детали · Esc закрыть`) but not accessible as help modal or printable cheatsheet

100. **No automated test coverage for visual regressions** - no screenshot diff tests, no visual regression pipeline; each change may introduce undetected visual bugs

---

## COMPLETION PLAN

### Priority Order (based on Gates 1-6 from NEXT_ITERATION_MASTER_PLAN)

#### P0 — Mandatory (Must complete before acceptance gates)

**Stage 1 — Data Contract (1 day)**
- [ ] Extract evidence state computation to pure function; ensure no UI component independently derives evidence state
- [ ] Add automatic `checkContractVersion` call on app init for all 4 data files
- [ ] Add `contractVersion` field to `PairClass` with backward-compatible parsing
- [ ] Document status string format expectations and provide migration path

**Stage 2 — Track Registry (1 day)**
- [ ] Fix `pair_anchor` display range: remove log transform or adjust displayMin/displayMax to match `meshAnchorFraction` (0-1 range)
- [ ] Fix `pair_visibility` upper bound: change `displayMax: 0.7` to `displayMax: 1.0` or higher
- [ ] Fix `pair_fdr` scale: change `scale: 'linear'` to `scale: 'discrete'` with proper label mapping
- [ ] Add documentation for all track display ranges with calibration source references
- [ ] Add `uv_mean_confidence` as opt-in track with proper domain/applicability marking

**Stage 3 — Event/Roles Lanes (1-1.5 days)**
- [ ] Add textual explanation for event icons on hover (tooltips with meaning/severity)
- [ ] Increase `iconSize` minimum to 16px for role/event icons; add CSS `font-size` scaling
- [ ] Add `tabIndex=0` and `aria-label` to all event/button icons
- [ ] Add color-blind friendly distinguishability: ensure symbols have different shapes, not just colors
- [ ] Add event count display in same-day stack and event row tooltips

**Stage 4 — Pair Inspection Flow (1.5 days)**
- [ ] Add "what would disprove candidate" guidance in geometric change gate
- [ ] Add FDR interpretation: "q-value ≤ 0.10 means signal survives multiple testing correction"
- [ ] Add calibration distribution reference: show what "elevated" means relative to calibration population
- [ ] Add persistence summary linking to minimap clusters and chain visualization
- [ ] Add alternative explanations within gates (pose mismatch, confounder notes)
- [ ] Add `mtRole` explanation in FDR gate tooltip
- [ ] Add raw vs compensated values side-by-side in appropriate gates

**Stage 5 — Scaling and Performance (1 day)**
- [ ] Add zoom limits: `MIN_SLOT = 52/thumbsize_factor`, `MAX_SLOT = 112/thumbsize_factor` per V3 plan
- [ ] Implement continuous row guarantee: enforce min gutter/max thumb width per V3 constraints
- [ ] Debounce window resize layout recalculation (300ms debounce)
- [ ] Add `prefers-reduced-motion` media query support with alternative navigation
- [ ] Add keyboard pan control while zoomed in (Shift+Arrow or dedicated pan mode)
- [ ] Add high-DPI canvas fallback for SVG lines when `devicePixelRatio > 1.5`
- [ ] Add thumbnail neighbor prefetch on drag start
- [ ] Add placeholder texture for missing thumbnails

**Stage 6 — Visual/QA (1 day)**
- [ ] Verify and fix contrast: ensure all colors meet WCAG AA (4.5:1) against `#0a0e14` base
- [ ] Add focus management: explicit focus cycle, `Shift+Tab` support, no focus traps
- [ ] Add "NEVER A VERDICT" safety tag prominent in UI chrome (toolbar + pair popups)
- [ ] Add print/export functionality: export current viewport as PNG/PDF
- [ ] Add snapshot/export of current analysis state (zoom, position, selection)
- [ ] Add automated visual regression tests (baseline screenshots + diff pipeline)
- [ ] Add help/tooltip on gate stack symbols with explanations
- [ ] Add data version changelog display in footer/toolbar
- [ ] Add keyboard shortcut cheatsheet modal (accessible via `F1` or `?` key)
- [ ] Add touch-friendly hit areas: minimum 12px for all interactive elements

#### P1 — After P0 (Can complete after P0 acceptance)

- Zone metrics opt-in layer with proper raw rmse display (not factory robustZ)
- Advanced filter UI with saved filter states and URL state persistence
- Enhanced minimap with cluster navigation and jump-to functionality
- Calibration distributions and QC trend charts
- Alternative pair family visualization
- Detailed QC metrics trends over time

#### P2 — Diagnostic (Optional enhancements)

- Skin/texture readiness diagnostics (hidden by default)
- UV diagnostics panel
- Raw per-point arrays for advanced analysis
- Internal pipeline counters for debugging

#### P3 — Hidden by default

- Skin/texture readiness
- UV diagnostics
- Raw per-point arrays
- Internal pipeline counters

---

### Implementation Workflow

1. **Start with P0 Stage 1** - data contract isolation (Gate 1 acceptance)
2. **Proceed sequentially** through stages; each stage's gate must pass before next starts
3. **After each gate**, run acceptance test: visual QA on 3 resolutions (1920×1080, 1440×900, 1366×768), candidate/limited/same-day scenario verification
4. **Performance benchmark**: 60 fps drag/zoom on target machine (per Gate 5)
5. **Final Gate 6**: visual QA bundle without overlap, clipping, or false semantics

### Key Code Changes Required

Based on the analysis, the following files need modification:

1. **`src/timeline-data-contract.ts`** - Evidence state extraction, version enforcement, schema evolution
2. **`src/track-registry.ts`** - Fix display ranges, add missing tracks, document calibrations
3. **`src/Timeline.tsx`** - Wheel zoom limits, hover debounce, virtualization, zoom bounds, performance
4. **`src/App.tsx`** - Automatic contract version validation on init, URL state loading
5. **`src/PairOverlay.tsx`** - Gate stack enhancements, alternative explanations, raw+compounded values
6. **`src/types.ts`** - Add proper scale types, fix anchor fraction type mismatch
7. **`src/App.css`** - Contrast fixes, focus styles, hit area enlargement, reduced-motion support

### Success Metrics

- [ ] Gate 1: No UI component independently computes evidence state; all go through `classifyPair`
- [ ] Gate 2: Every graph pixel mappable to backend field + unit via track registry
- [ ] Gate 3: User understands every icon without opening code (color-blind + new user test)
- [ ] Gate 4: For any red/orange point, user understands why candidate + what could disprove it
- [ ] Gate 5: 60 fps drag/zoom on target machine, no overlap, no jumps
- [ ] Gate 6: Visual QA bundle without overlap, clipping, false semantics on 3 resolutions

---

*Analysis completed against NEXT_ITERATION_MASTER_PLAN.md roadmap. All 100 deficiencies mapped to specific code locations and prioritized for completion.*

---

## IMPLEMENTATION LOG (2026-08-18)

### Done — P0 fixes (build/lint/tests green: `npm run verify` exit 0, `vite build` OK)

| # | Fix | File |
|---|-----|------|
| 1 | Evidence state isolation: `PairOverlay` now uses `classifyPair` (Gate 1) instead of local `isCandidate`/`label` maps | `src/PairOverlay.tsx` |
| 5 | `validateFrames()` runtime validation added to data contract — unknown statuses logged, not silently replaced | `src/timeline-data-contract.ts` |
| 5 | All 4 data files now run `checkContractVersion` at init (incl. zone_metrics) | `src/App.tsx` |
| 12 | `pair_visibility` displayMax `0.7 → 1.0` (semantic domain, no silent clipping) | `src/track-registry.ts` |
| 46-48 | Zoom limits per V3: MIN_SLOT=60 / MAX_SLOT=128 (thumbW 52–112px), STACK_SLOT=72 for same-day stacks | `src/Timeline.tsx` |
| 23 | `iconSize` floor raised `8px → 16px` (≥12px hit target) | `src/Timeline.tsx` |
| 28/29 | Keyboard focus on pair marks: `onFocus/onBlur` + Space key activation (Enter already present) | `src/Timeline.tsx` |
| 31/36/45 | Gate stack: «Что может опровергнуть кандидатуру» guidance, mtRole explanation, calibration-not-elevated note | `src/PairOverlay.tsx` |
| 76 | `.keys` contrast `#5d6875 → #8b96a3` (WCAG AA ≥4.5:1) | `src/App.css` |
| 73/85 | Empty-state covers 0 and 1 frames; 2–8 weak-density message kept | `src/Timeline.tsx` |
| 57 | Missing-thumbnail fallback = pose color block (V3 point 42) | `src/Timeline.tsx` |
| — | Pre-existing build break fixed: `ABCompare.tsx` rmse null-safety, unused `PersistenceAnalysis` import, `zones` prop type (Map→array), broken `node --test tests/` (now `tests/*.test.ts`) | `src/ABCompare.tsx`, `src/App.tsx`, `package.json` |
| — | +2 selftest/lint warnings cleaned (`pm0`, ternary-as-statement, missing dep) | `scripts/selftest.mjs`, `src/App.tsx` |

Test coverage added: `validateFrames` tests (`tests/contract.test.ts`) — 7/7 pass.

### Next (not yet implemented)
- P0 Stage 4: raw vs compensated values side-by-side in gates
- P0 Stage 5: canvas fallback for >N frames, hover computation throttle, prefetch neighbors
- P0 Stage 6: print/export of current view, data-version display, focus-trap audit
- P1: save filter/URL state to localStorage, zone opt-in layer, calibration distributions