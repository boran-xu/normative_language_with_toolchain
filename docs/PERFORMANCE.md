# Measured performance improvements

Measurements compare the pre-change implementation at `68bb9a3` with this change
on the same Linux/Python 3.12.3 environment. Raw results are in
[performance.json](performance.json). Results are workload-specific, not promises
about every command or machine.

| Workload | Before | After | Improvement |
| --- | ---: | ---: | ---: |
| Clause history: 181 commits, 160 Markdown files | 93.935 s | 0.190 s | 495× wall-time speedup |
| Git processes for that history query | 29,509 | 8 | 3,689× fewer processes |
| 10,000 path-anchor lookups in 10,000 clauses | 12.306 s | 0.083 s | 149× wall-time speedup |

The history runs read the **same repository and commit objects**. A separately
authored oracle checks the exact three expected history-event commits, not just
an event count. The reference runs assert all 10,000 resolved IDs. Index creation
is included in the indexed measurement; input Clause construction is excluded
from both reference measurements.

The history improvement removes one Git process per file per snapshot, plus
repeated revision/subject calls. Batches and immutable-object caches replace that
fan-out. Reference improvement replaces repeated namespace scans with a shared
ID/path index. Neither benchmark skips structural data needed for the query.

## Reproduce

Construct the history workload in a **new** path and measure the current code:

```sh
python3 tools/benchmark_ndf.py --repo /tmp/ndf-benchmark-new --build --output /tmp/ndf-history-result.json
python3 tools/benchmark_ndf.py --repo /tmp/ndf-benchmark-new
```

Construction refuses an existing path and never overwrites a repository. To
compare implementations, create the workload once and use that same `--repo`
with the script copied into a checkout of the older implementation and with the
current script. The benchmark script defers the shared-index import until the
reference benchmark is selected, so history benchmarking works against the old
checkout too. Do not include construction time in the query measurement.

For reference lookup, the explicit `scan` mode retains the old algorithm only
as a benchmark control; production commands use the index:

```sh
python3 tools/benchmark_ndf.py --references --reference-method scan
python3 tools/benchmark_ndf.py --references --reference-method index
```

The default workload is 180 update commits after one initial commit, with 160
separate clause files. Flags allow different sizes. The operation-count regression
uses a smaller independent repository and requires at most 12 Git processes,
including deeper paths; it does not enforce a fragile wall-clock threshold.
A second regression ensures an unchanged blob is parsed once across commits and
moves. The shared-index regression counts path reads to prevent quadratic scans.

## Validation scope

The full suite covers merge resolutions, octopus/crisscross histories, linked
worktrees, symbolic-ref movement, SHA-256 repositories, large/empty blobs,
source separators, duplicate identity, scoped binary files, and mutable-cache
isolation. Fresh-clone bootstrap and installed CLI checks complement in-process
instrumentation. CI also tests the declared Markdown parser versions 3.0.0 and
4.2.0 against its Python matrix; local verification covers Python 3.12.3 with
both versions and does not claim a remote CI run occurred.
