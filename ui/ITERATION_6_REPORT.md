# Iteration 6 — Critical Execution Core (80/20)

The highest-risk operational path is now closed: only allowlisted tests can run, one isolated process group at a time, with cancellation, timeout, recovery and live compact events.

## Delivered
- immutable allowlist registry; no shell strings or user-provided argv;
- single-worker queue (`max_parallel_runs=1`);
- process-group isolation, PID tracking, timeout, SIGTERM/SIGKILL cancellation and cleanup;
- race-safe cancellation before/after process creation;
- versioned `dpo-run-event-v1` JSONL with malformed-line isolation;
- live unbuffered stdout events, REST replay and WebSocket stream;
- compact metadata under control storage; event logs only under heavy storage;
- code/config hashes, seed, timestamps, exit code and reason;
- restart recovery marks nonterminal runs interrupted;
- UI runner panel with allowlisted buttons, status, cancel, hashes and live logs;
- external-storage readiness gate before a real run.

## Real end-to-end proof
The app6 regression suite was launched through RunManager, succeeded, generated 50 ordered events and preserved code/config hashes.

## Deferred lower-leverage work
Function-level `sys.setprofile` events, CPU/RAM sampling and animated Canvas pulses. These do not block safe test execution or the next Scientific Validation Core.

## Verification
41/41 backend tests; 65/65 app6 tests through the real manager; 7/7 frontend syntax; app6 unchanged.

Overall readiness: 44/100.
