# NDF tools

A small Python CLI implementing the practical core of the accompanying Normative
Description Format proposal. The original English/Chinese proposals and PDFs are
unchanged. This implementation and its limitations are documented here separately.

Requires Python 3.10+ and Git for history commands. No runtime dependencies for
JSON manifests; JSON is valid YAML. Ordinary YAML manifests require optional
PyYAML (`pip install '.[yaml]'`).

Run directly from this checkout:

```sh
python3 ndf.py --root examples/chrono/spec check
python3 -m ndf --root examples/chrono/spec trace CHR-000
python3 ndf.py --root examples/chrono/spec coverage
python3 ndf.py --root examples/chrono/spec test
```

Optionally install with `pip install .` to obtain the `ndf` command.
`--root` defaults to `spec`. Put `--root` and `--json` before the subcommand.
Exit codes: 0 success, 1 validation errors, 2 invocation/configuration/Git errors.
The `test` command returns the test process exit code.

## Commands

| Command | Behavior |
| --- | --- |
| `init` | Create directories and a JSON-syntax `ndf.yaml`; never overwrite a manifest |
| `new-id SYS-AREA` | Generate an ID under a declared prefix |
| `check` | Check duplicate IDs, metadata, references, model paths, refinement layers/cycles, options; warn about keyword misuse, ambiguous wording and known conflicts |
| `check --since COMMIT` | Additionally flag refinement pairs whose clauses changed relative to a Git snapshot |
| `trace ID` | Show descendants, verification backlinks and outgoing typed edges |
| `coverage` | Count L1 must clauses and their active verification links, TBDs, questions, options, DSE markers and recorded conflicts |
| `status` | Coverage plus question status, blocked clauses, resolution and body |
| `options` | List design options and their metadata, including defaults/ranges/couplings |
| `deps [refs/]` | List local mentions/typed edges into the reference subtree, with source provenance |
| `log ID [--ref HEAD] [--all]` | Clause changes across every reachable parent, including merges and file moves; optionally include all local refs |
| `diff A..B` | Compare clause snapshots: additions, deletions, moves and content/metadata changes |
| `export` | JSON clause records, including metadata, text, references and locations |
| `test` | Execute Python unittest discovery in `models/` using the current Python interpreter |

Coverage counts *all* active L1 must clauses except `info`, including definitions
and constraints. It measures specified verification links, not passing tests.
Model tests run only when explicitly requested by `test`; `check` never executes
project code. Model tests should reference verification/requirement IDs in names
or assertion messages. `test` fails if no tests exist. See the toy project's README
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
Fenced code is preserved but never interpreted as headings, metadata or links.
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
`log` includes ancestors of the selected ref only. Shallow clones only provide
history present locally; fetch full history for complete reports. Snapshots with
duplicate IDs fail explicitly rather than arbitrarily choosing one clause.
Historical queries ignore current validation errors, but still require an existing
manifest. History is deliberately simple and scans snapshots; large repositories
may benefit from a future persistent cache.

## Limits and verification

There is no proof or automatic detection of contradictions in natural language.
`check --since` produces **review flags**, even for textually clean merges; it
compares the current tree with the selected commit, including removed edges.
Choose a pre-merge baseline to review an integrated change. Semantic review,
glossary synonym analysis, automatic reconciliation, HTML/PDF publishing and
reference ingestion are deferred. `diff` compares parsed content and metadata;
it does not decide whether differently worded prose means the same thing.
Executable models can test encoded behavior, not the adequacy of prose contracts.

Run the tool regressions and the independent toy project's acceptance tests:

```sh
python3 -m unittest discover -s tests -v
python3 ndf.py --root examples/chrono/spec test
```

Git regressions create disposable repositories and exercise divergent edits,
conflicting and clean merges, resolutions matching one/both parents, unmerged
branches, deletions/restoration, file moves, and history with a broken worktree.
