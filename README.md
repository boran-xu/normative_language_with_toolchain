# NDF tools

A small Python CLI implementing the practical core of the accompanying Normative
Description Format proposal. The original English/Chinese proposals and PDFs are
unchanged. This implementation and its limitations are documented here separately.

Requires Python 3.10+, Git for history commands, and `markdown-it-py` for
deterministic CommonMark parsing. Install the package and its parser dependency
with `python3 -m pip install .`. JSON manifests are valid YAML; ordinary YAML
syntax additionally requires `python3 -m pip install '.[yaml]'`.

Run directly from this checkout:

```sh
python3 ndf.py --root examples/chrono/spec check
python3 -m ndf --root examples/chrono/spec trace CHR-000
python3 ndf.py --root examples/chrono/spec coverage
python3 ndf.py --root examples/chrono/spec test
```

Installation also provides the `ndf` command. The source-checkout commands above
use the same installed parser dependency.
`--root` defaults to `spec`. Put `--root` and `--json` before the subcommand.
Exit codes: 0 success, 1 validation errors, 2 invocation/configuration/Git errors.
The `test` command returns the test process exit code.

## Commands

| Command | Behavior |
| --- | --- |
| `init` | Create directories and a JSON-syntax `ndf.yaml`; never overwrite a manifest |
| `new-id SYS-AREA` | Generate an ID under a declared prefix |
| `check` | Check duplicate IDs, metadata, references, model paths, refinement layers/cycles, options; warn about keyword misuse, ambiguous wording, glossary drift and known conflicts |
| `check --since COMMIT` | Additionally flag refinement pairs whose clauses changed relative to a Git snapshot |
| `trace ID` | Recursively traverse refinements and dependencies, showing typed links and verification backlinks |
| `coverage` | Count L1 must clauses and their active verification links, TBDs, questions, options, DSE markers and recorded conflicts |
| `status` | Coverage plus question status, blocked clauses, resolution and body |
| `options` | List design options and their metadata, including defaults/ranges/couplings |
| `deps [refs/]` | List local mentions/typed edges into the reference subtree, with source provenance |
| `log ID [--ref HEAD] [--all]` | Clause changes across every reachable parent, including merges and file moves; optionally include all local refs |
| `diff A..B` | Clause changelog: lifecycle, formatting/content, edges, metadata, text patches and census deltas |
| `export` | JSON clause records, including metadata, text, references and locations |
| `test` | Execute Python unittest discovery in `models/` using the current Python interpreter |

Coverage counts *all* active contract-layer must clauses except `info`, including definitions
and constraints. The contract layer is the second entry of the declared ordered
ladder, including renamed layers; output reports `contract_layer` and retains
`L1_must` as the compatible count key. It measures specified verification links,
not passing tests.
Model tests run only when explicitly requested by `test`; `check` never executes
project code. Model tests should reference verification/requirement IDs in names
or assertion messages. `test` fails if no tests exist or discovery executes zero tests. See the toy project's README
for its intentionally incomplete coverage and executable acceptance tests.

## Authoring

```markdown
## Required behavior {#SYS-001}
<!-- ndf: kind=req level=must layer=L1 status=draft since=0.1 -->

The system MUST retain its count while stopped.

## Acceptance criterion {#VER-001}
<!-- ndf: kind=verif level=must layer=L3 verifies=SYS-001 -->

After stopping, 100 ticks MUST leave the count unchanged.
```

Clauses end at the next clause heading or a heading at the same/higher level;
ordinary deeper headings remain inside a clause. Metadata may span multiple
one-line comments. Quote values containing spaces. References use `[[ID]]`,
`[[ID | label]]`, `[[decisions/D-001]]` or `[[path.md#CLAUSE-ID]]`.
Fenced and indented code is preserved but never interpreted as headings, metadata
or links. HTML comments are non-authoritative except standalone NDF metadata
comments. Code spans can cross prose line breaks; escaped reference delimiters
remain literal. ATX headings may have up to three leading spaces and closing hashes.
Inline-code examples do not create references or establish normative keywords.
Conflict markers inside fenced examples are ignored. `deps` resolves ID,
file-and-anchor, and whole-file references; directory filters respect path
boundaries (`refs` does not match `refs-old`).
File anchors must be NDF clause IDs, not generated Markdown heading slugs.
External standard section references must be projected into actual clauses/files;
unresolved pointers intentionally fail validation.

Kinds include the proposal's requirements, definitions, architecture, constraints,
options, verification and information, plus `decision` and `question` from its
examples. Decisions/questions need no level/layer. Questions may use metadata
`resolution="..."` or a prose `**Resolution.** ...` field. Resolved questions should
link a decision. Replaced clauses use `status=superseded-by=NEW-ID` and remain in
the tree. Missing status/since are permitted to match the proposal's examples.

`ndf.yaml` must have `id-prefixes`; ordered `layers` may customize the refinement
ladder. See the example for a complete manifest. Code paths are relative to the
spec root. Lint warnings are advisory; structural errors block the check.

## Glossary checks

`check` reads active or historical `kind=def` clauses anywhere under the spec
root. A definition heading supplies a term; the proposal's list syntax
`- **running / stopped** — ...` supplies two separately defined terms. Simple
explicit prose such as `BCD means ...` also supplies a term. No special term-link
syntax is required. Matching is case-insensitive.

Use ordinary glossary prose to declare synonyms:

```markdown
## frame {#DEF-FRAME-001}
<!-- ndf: kind=def level=must layer=L1 -->

An Ethernet transmission unit.
Synonyms: packet, datagram
```

Occurrences of `packet` or `datagram` in other clauses then produce advisory
warnings recommending `frame`. Alternatively, set a `glossary.synonyms` mapping
in `ndf.yaml`, e.g. `{"glossary": {"synonyms": {"packet": "frame"}}}` alongside
the existing manifest keys. Synonym relations are explicit data; the checker
does not infer them from arbitrary prose.

Undefined capitalized words and acronyms produce glossary warnings. Known terms
are matched as phrases, common sentence starters and normative keywords are
excluded, and sentence-initial capitalization alone does not trigger a warning
(except acronyms). Fenced/inline code, metadata and clause-ID references are
excluded. This is an advisory capitalization heuristic: it can miss terms or
flag ordinary words. It does not assess whether a defined term is used correctly.

## Graph tracing and clause diffs

`trace` follows incoming `refines` edges down to more detailed clauses and outgoing
`depends-on` edges recursively. At every visited clause it lists incoming
`verifies` links and other outgoing typed edges. Plain mentions are not traversed.
Self/cyclic supersession and contradictory replacement targets are structural
errors; dependency cycles remain valid graphs.

A repeated node is marked `already shown` and is not expanded again, whether
encountered through a cycle or a shared dependency. The traversal is iterative,
so long dependency chains do not hit Python's recursion limit. `--json` returns
records with IDs, source, relation, depth, repetition marker and verification links.

`diff A..B` retains its original `change` field and adds `categories`: added,
deleted, modified, formatting-only, moved, deprecated and superseded (multiple
categories can apply). The formatting rule ignores prose whitespace/wrapping and
reordering of typed-edge targets; fenced, indented and inline code whitespace is
preserved. Census deltas use the same active-clause rules as coverage and exclude
markers inside code examples. This is a
syntactic classification, not a judgment about changed meaning. Metadata deltas,
added/removed typed edges and mentions, title changes, unified body patches and
per-clause TBD/open-option/open-question census deltas are included. Mention
edges resolve to stable IDs, so equivalent file/ID spellings do not invent graph
changes. Whole-file references expand to the clauses present in each snapshot;
a consumer can have `graph_only: true` when a target file gains or loses a clause
without changing the consumer text. Results are
sorted by clause ID and compare the exact two snapshots, regardless of whether
their commits are on the same branch.

## IDs and branch history

IDs use a UUID4 suffix, e.g. `SYS-ADM-4d21…` (32 hexadecimal characters).
This deliberately extends the proposal's numeric examples to allow independent
agents, processes and branches to allocate IDs without a shared server or
merge-prone counter. Accidental UUID collisions are negligibly probable, not
mathematically impossible; duplicate IDs are always checked. Do not reuse IDs.
Manually authored numeric IDs remain supported.

`log` reads the clause ID from complete Git snapshots rather than following a
filename. Every relevant commit is compared independently against **every parent**.
A merge matching one parent still appears when it differs from another. A merge
resolution differing from both records both comparisons. Output is topological,
newest first, with full commit and parent hashes. Moves within the selected spec
root are tracked, even through filenames containing spaces or Unicode. Changes
outside that root are out of scope. Removed clauses appear as deletions; unrelated
commits are omitted. The working tree is not part of `log` or `diff`.

Use `log --all` to include unmerged branches reachable from local refs. A normal
`log` includes ancestors of the selected ref only. Clause logs reject shallow repositories explicitly rather than misreporting a
truncated boundary as a newly added clause; fetch full history first. Snapshot
diffs remain available in shallow repositories when both commits exist locally. Snapshots with
duplicate IDs fail explicitly rather than arbitrarily choosing one clause.
Authored Markdown must use regular files: symlink Markdown is rejected in both
current-tree and historical queries. Root-directory symlinks are supported.
Directories ending in `.md` are traversed, never read as files; Git metadata is
excluded relative to the selected root.
Historical queries read Git snapshots independently of the current manifest and
Markdown, even if the current spec directory is missing. History batches Git objects and caches immutable trees/blobs per query. It
does not spawn a process per file or require a persistent cache; memory use still
scales with distinct objects and retained snapshots.

## Limits and verification

There is no proof or automatic detection of contradictions in natural language.
`check --since` produces **review flags**, even for textually clean merges; it
compares the current tree with the selected commit, including removed edges.
Choose a pre-merge baseline to review an integrated change. HTML/PDF publishing
and reference ingestion are deferred. All tools use deterministic rules; prose
interpretation and reconciliation are the responsibility of the human or agent
using them.
Executable models can test encoded behavior, not the adequacy of prose contracts.

Run the tool regressions and the independent toy project's acceptance tests:

```sh
python3 tools/bootstrap_history.py
python3 -m unittest discover -s tests -v
python3 ndf.py --root examples/chrono/spec test
```

The [history fixture](tests/fixtures/README.md) is a real pinned Git submodule,
backed by a tracked cloneable bundle for offline setup. It contains 35 named
snapshots and a realistic development graph. Integration tests use independent
expected answers and mutate only temporary clones. Bootstrap fetches the full
branch/tag history; it never changes global Git protocol settings. The CI runs
bootstrap before the complete suite.

Git regressions create disposable repositories and exercise divergent edits,
conflicting and clean merges, resolutions matching one/both parents, unmerged
branches, deletions/restoration, file moves, and history with a broken worktree.

The [second adversarial audit report](tests/ADVERSARIAL_AUDIT.md) records the
18 distinct bugs found and fixed, their regressions, and the expanded test scope.

The [interaction audit report](tests/INTERACTION_AUDIT.md) covers the next pass,
including the CommonMark parser replacement, bootstrap preflight checks and
15 further defects with regressions.

The [quality audit](tests/QUALITY_AUDIT.md) documents seven further correctness
fixes and shared indexing/report modules. [Measured benchmarks](docs/PERFORMANCE.md)
show roughly 495× faster history queries on the recorded workload and roughly
149× faster indexed reference resolution. [Architecture](docs/ARCHITECTURE.md)
describes the modules and their limits.

## Agent skill

The portable [`ndf-spec` skill](skills/ndf-spec/SKILL.md) teaches the full proposal,
not only the implemented CLI subset. It bundles byte-for-byte English and Chinese
proposal references, a section-by-section feature map, and a separate guide to
current `ndf` commands and remaining manual responsibilities.

Copy the entire `skills/ndf-spec` directory into your agent's skill directory;
Codex's default is `~/.codex/skills/ndf-spec`. The references must travel with
`SKILL.md`. Invoke it explicitly as `$ndf-spec`, or let normal skill discovery
select it for NDF work. It uses the existing `ndf` on PATH; it does not install a
second CLI or require a different Python environment.

Verify source fidelity and portable reference links after intentional updates:

```sh
python3 tools/check_ndf_skill.py
```

The provenance manifest records source revisions and hashes. Keep both proposal
snapshots aligned with the originals when deliberately refreshing the skill;
never silently rewrite the originals to fit current tool limitations.
