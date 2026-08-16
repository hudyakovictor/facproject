# Publication pipeline — 25-factor review

**Scope:** Stage 2 journalist handoff + Stage 3 multi-audience drafts.  
**Scale:** 25 × 4 = 100.  
**Current structural score:** **95/100**.  
**Important:** score reflects code/contracts/tests, not editorial approval of a real-data publication.

| ID | Factor | Score | Evidence / remaining work |
|---|---|---:|---|
| P01 | General-audience clarity | 4 | Plain-language method draft and glossary |
| P02 | Technical depth | 4 | Technical appendix with spaces/gates/calibration/evidence |
| P03 | Skeptical review | 4 | Dedicated challenge register and skeptic Q&A |
| P04 | Machine/AI auditability | 4 | Structured machine-review packet |
| P05 | Claims ledger | 4 | Stable claim IDs, kind, strength, review state |
| P06 | Claim-to-evidence trace | 4 | Artifact/row references required per claim |
| P07 | Denominators | 4 | Limited counts render `N из M`, missing denominator stays explicit |
| P08 | Provenance | 4 | Date/duplicate/source-chain claims and refs |
| P09 | Method/results separation | 4 | Independent method draft + separate results story |
| P10 | Calibration explanation | 4 | Same-person calibration, coverage and sensitivity |
| P11 | Confounders | 4 | Pose, visibility, expression, quality, duplicates |
| P12 | Statistical completeness | 3 | FDR/correlation explained; final drafts still need explicit ESS/CI values from production artifacts |
| P13 | Uncertainty/limitations | 4 | Limit claims and zero-candidate safety wording |
| P14 | Alternative explanations | 4 | Per-card alternatives + challenge register |
| P15 | Falsifiability | 4 | Explicit conditions for weakening/withdrawing a thesis |
| P16 | Reproducibility | 4 | Schema/config/artifact references and machine packet |
| P17 | Versioning/digests | 4 | Publication manifest with file digests |
| P18 | Public-safety lint | 4 | Assertive-construction lint; topic words allowed neutrally |
| P19 | Private/public isolation | 4 | Contract explicitly excludes private hypotheses |
| P20 | Journalist/technical collaboration | 4 | Stage 2 handoff + result draft placeholders |
| P21 | Visual/example integration | 3 | Independent demonstration protocol exists; generated figure/storyboard package not yet implemented |
| P22 | International publication readiness | 2 | Current generated prose is Russian; synchronized English publication layer remains to implement |
| P23 | Automated tests | 4 | Pure bundle, lint, resolver and Stage3 integration tests |
| P24 | Human review/adjudication | 4 | Unreviewed state, reviewer/adjudication fields and publication gate |
| P25 | Legal/rights workflow | 3 | Rights review required and demo protocol constrained; automated rights manifest gate remains |

## Result

```text
95/100 structural readiness
P0 violations: none in the draft generator
Real-data publication approval: not evaluated
```

## Route to 99/100

1. Add synchronized English drafts from the same claims ledger (+2 on P22).
2. Generate figure/storyboard manifests linked to claim IDs (+1 on P21).
3. Include production ESS/CI/LOPO values in technical claims (+1 on P12).
4. Add a machine-checkable rights/license gate for every published image (+1 on P25).

That would reach 100 structurally; the declared target remains 99 because final editorial persuasiveness and reader comprehension require human testing, not a self-score.
