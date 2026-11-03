# Quality and performance audit

This pass found and fixed **seven additional correctness bugs**, grouping
variants and overlapping independent discoveries by cause. Performance work is
reported separately rather than inflating the bug count.

| # | Reproduced defect | Regression / fix |
| --- | --- | --- |
| 1 | Image alt child tokens omitted real references and treated code keywords as obligations | Recursively process Markdown children while retaining code/destination exclusions |
| 2 | Python `splitlines()` disagreed with CommonMark physical line maps for VT/FF/NEL and Unicode separators | One physical-line normalizer preserves raw non-linebreak source characters and later clause locations; history diffs use it too |
| 3 | A UTF-8 BOM hid the first anchored clause | Normalize only the initial BOM before token/source mapping |
| 4 | Escaped/entity-decoded anchor examples invented machine clause IDs | Require literal, unescaped source anchors matching the parsed heading |
| 5 | Resolution extraction chose fenced/commented samples over actual answers | Select real top-level Markdown prose fields, including successive fields in one paragraph; explicit metadata retains priority |
| 6 | `init` followed a dangling manifest symlink and wrote outside the chosen root | Reject the existing entry and create the manifest exclusively |
| 7 | Duplicate verification targets duplicated acceptance IDs/backlinks | One unique incoming relationship index now drives reports and tracing |

Independent CLI/parser testers wrote failures before the fixes. Multiple separator
variants and repeated resolution examples count once each. The seven confirmed
cases are fixed; passing this audit does not prove the absence of other defects.

## Structural improvement

A shared `SpecIndex` now owns IDs, paths, reference resolution and unique graph
relationships. Validation, reports, tracing and historical diffs reuse it.
Current reports are pure functions separate from command dispatch. Batched Git
object reading and immutable-object caches replace per-file subprocess calls.
See [architecture](../docs/ARCHITECTURE.md) for interfaces and limitations.

## Evidence

- The suite grew from 182 to 240 tests, preserving prior fixture/reconstruction
  and CLI coverage.
- History operation counts and parse counts are regression-gated independently
  of timing. SHA-256, large blobs, symbolic HEAD changes, cache-state isolation,
  scope filtering, empty specs and real Git pretty subjects are exercised.
- Shared-index tests cover path/ID equivalence, whole-file and empty-file
  inventory, metadata backlinks, asset references and non-quadratic lookup work.
- The same 181-commit/160-file history query fell from 93.935 to 0.190 seconds
  while preserving the exact three expected events; Git process count fell from
  29,509 to 8. A 10,000-reference workload fell from 12.306 to 0.083 seconds,
  including index construction. These are measured workloads, not global claims.
- Full-suite verification uses both declared parser versions (3.0.0 and 4.2.0),
  plus fresh-clone offline bootstrap and installed-console checks.
- The original proposal files and pinned fixture artifacts remain unchanged.

Raw results and reproduction instructions are in
[the performance report](../docs/PERFORMANCE.md). No persistent service or LLM was
introduced. Memory scales with distinct history objects and retained snapshots;
large histories still have costs. Development benchmarks intentionally remain
separate from machine-independent regression gates.
