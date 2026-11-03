# Specification and history modules

The command names and file format remain unchanged. The improvement is to put
identity, resolution and history work behind modules shared by every caller.

| Module | Interface and responsibility |
| --- | --- |
| `core` | Read authored files, parse clauses/configuration, validate structure; existing helper imports remain compatible |
| `markdown` | CommonMark tokens, nested inline content, strict physical source lines, literal anchors and real resolution fields |
| `index.SpecIndex` | One snapshot's ID/path indexes, memoized reference resolution, unique typed/mention edges and incoming relationships |
| `paths` | One root-relative POSIX namespace rule shared by current and historical references |
| `reports` | Pure coverage/status/options/dependency reports from an index; no filesystem/Git orchestration |
| `graph` | Iterative typed traversal using the same incoming/typed index as reports |
| `history.History` | Resolve revisions and read immutable Git objects in batches; return clause snapshots and parent-aware events |
| `history.changelog` | Compare indexed snapshots, including graph-only changes, lifecycle and census deltas |
| `cli` | Parse arguments, orchestrate loading/checks, dispatch and render results |

## Shared index

Build `SpecIndex` once per snapshot. `resolve(reference)` returns stable IDs for
ID, path-anchor or whole-file addresses; `edges(id)` returns unique typed and
resolved mention edges. `incoming(relation, id)` supplies backlinks without
rescanning the specification. Reports reuse these operations; they do not carry
independent versions of reference resolution or verification counting.

The index materializes its input once, caches resolutions, indexes clauses by
path and ID, and deduplicates relationships. Whole-file references resolve to the
clauses present in that snapshot. A file inventory also records empty projection
files. When resolution is not possible in a historical invalid snapshot, diff
retains the original address as a fallback rather than silently dropping it.

Indexes describe one snapshot: if callers intentionally mutate clauses, build a
new index. The CLI does not mutate indexed clauses. Existing `core.reference_ids`
and `core.resolve` helpers remain available for occasional calls; callers doing
repeated work should reuse an index.

## Git object batches

A history query obtains the topological commit/parent graph and Git's own formatted
subjects once. Commit objects yield root trees; scoped trees are read in depth
waves; regular Markdown blobs are fetched together with `git cat-file --batch`.
The size-framed protocol is decoded as bytes, so newlines/NUL bytes inside blobs
cannot be mistaken for record separators. Hash width comes from object IDs,
supporting SHA-1 and SHA-256 repositories.

Caches are command-local and keyed by immutable object IDs. Identical trees and
blobs are not repeatedly read or parsed. Parsed blob templates are copied into
per-commit/per-path clauses so moves retain location and mutable metadata is not
shared between different snapshots. Symbolic revisions are resolved anew for each
public query; caching does not freeze a moving branch or HEAD.

There is no server, persistent disk cache, or long-lived Git child process. A
`Snapshot` remains a dictionary of clause IDs with a `files` inventory alongside
it. Every merge is still compared independently against every parent. Shallow
logs and unsupported Markdown symlinks still fail explicitly.

## Evidence and limits

The [benchmark report](PERFORMANCE.md) records a roughly 495× faster history query
on the measured workload and roughly 149× faster reference resolution. Regression
checks enforce bounded Git process counts and clause-path reads rather than
machine-dependent timing thresholds.

Memory use scales with unique objects and retained snapshots for the query;
large histories can still consume substantial memory. Deep trees require more
batch waves. These are measured module improvements, not a claim that every
command or repository is hundreds of times faster.
