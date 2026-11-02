# Versioned stopwatch integration fixture

`history/` is a real Git submodule. The outer repository records its exact
`v2.0` commit as a mode-160000 gitlink; `history.json` records that pin and the
object IDs of all 35 scenario tags. The fixture is a separate repository with
its own commits, branches, merges, tags and `.git` storage.

`chrono.bundle` is a complete, cloneable transport for that repository, including
all scenario refs and ancestors. Tracking this small bundle alongside the gitlink
makes fresh checkouts reproducible without publishing a second repository or
requiring network credentials. It is **not** a replacement for the submodule:
tests require the initialized submodule, verify its pin, clone from it, and
assert that its checkout remains unchanged.

## Setup and tests

From the outer repository root:

```sh
python3 tools/bootstrap_history.py
python3 -m unittest discover -s tests -v
```

Use the bootstrap command rather than plain `git submodule update --init`.
The relative bundle URL in `.gitmodules` is a locator; bootstrap resolves it
inside the current outer checkout and supplies an absolute local URL for that
one Git invocation. This avoids resolving it against a hosting service's remote
URL. Local file transport is enabled only for that invocation, never globally.
No publishing, network service, global Git configuration or third-party Python
packages are needed.

Bootstrap rejects a dirty fixture or an inconsistent pin. It fetches every
bundle branch/tag and verifies all advertised scenario tags against
`history.json`; a detached HEAD alone would not preserve side histories.
It also rejects shallow history. Tests fail with setup instructions if the
submodule is absent or points at the wrong commit; they do not silently skip.

Manual inspection:

```sh
git -C tests/fixtures/history log --graph --decorate --oneline --all
python3 ndf.py --root tests/fixtures/history/spec trace CHR-000
python3 ndf.py --root tests/fixtures/history/spec coverage
python3 ndf.py --root tests/fixtures/history/spec log CNT-001
python3 ndf.py --root tests/fixtures/history/spec diff v0.2..v0.3
```

The source fixture is for inspection. Make a temporary clone for experiments.
Some intentionally invalid tagged snapshots contain duplicate IDs. Consequently,
`log --all` over *all* fixture refs must report ambiguous clause identity rather
than silently select a duplicate. Integration tests first clone/fetch only valid
scenario refs to exercise successful `--all`, then deliberately fetch invalid refs
to test that failure. No refs are deleted from the source submodule.

## Development story and graph

| Snapshots | Development event |
| --- | --- |
| `v0.1` | L0 intent, definitions, two L1 contracts, an open debounce question, disconnected informative note |
| `v0.2` | L2 mechanism and normative code, executable model/tests, L3 acceptance, projected external reference/provenance, constraint/interface, coupled options, decision and legacy requirement |
| `v0.3` | Resolve the question in a decision, freeze both options, supersede the reset contract, redirect verification, deprecate legacy input |
| `v0.4` | Move counting through a filename containing a space and Unicode; reflow prose |
| `scenario/conflict-{main,side,resolved}` | Divergent wrap contracts/models and a real conflicted merge resolved differently from both parents |
| `scenario/clean-{main,side,merge}` | Independent clock/display work and a clean two-parent merge |
| `v1.0` | Original integrated release; same commit as the clean merge |
| `scenario/hierarchy-base` | Five nested domains, layered contracts/mechanisms, five additional acceptance criteria, shared reference units, constraint, option/question/decision, informative code examples and a nested model-test package |
| `scenario/hierarchy-{io,telemetry,main,octopus}` | Independent input/telemetry/power branches combined by a real three-parent merge |
| `scenario/hierarchy-move-split`, `v2.0` | Move input contracts to interfaces and split telemetry mechanism into a separate file; v2.0 is the new gitlink pin |
| `scenario/match-{main,side}` and their `-main`/`-side` parent tags | Two additional actual conflict merges, each resolved to exactly one parent's clause contents |
| `scenario/dependency-cycle` | Unmerged dependency experiment with a cycle and a shared reference |
| `scenario/{delete-note,restore-note}` | Informative clause deletion and restoration with its identity preserved |
| `scenario/known-conflict` | Recorded `conflicts-with`, a new blocking question, and `derived-from` provenance |
| `invalid/{duplicate,dangling,metadata,conflict-markers,refinement-cycle}` | Deliberately broken committed snapshots |
| `tests/{failing,missing}` | Explicit model-test failure and removal of all model tests |

The principal history is:

```text
v0.1 -- v0.2 -- v0.3 -- v0.4 -- conflict-main -- conflict-resolved
                            \-- conflict-side --/

conflict-resolved -- clean-main -- clean-merge = v1.0
                 \-- clean-side --/

v1.0 -- independent match-main/match-side merge experiments
     -- dependency-cycle, note lifecycle, known-conflict experiments
     -- invalid snapshots and failing/missing test experiments
     -- hierarchy-base -- independent io/telemetry/main changes
                       -- hierarchy-octopus (three parents)
                       -- hierarchy-move-split = v2.0 (gitlink pin)
```

Branches that never merged remain reachable through stable tags and bundle refs.
All nine clause kinds, L0–L3, typed edges, code islands, ordinary links, a
file-and-anchor projection link, TBD/DSE markers, lifecycle markers, decisions
and questions appear in the fixture.

## Independently specified test matrix

The builder never imports or executes NDF. Original v1 command regressions still
check out v1.0 in disposable clones; source-submodule pin checks and additional
hierarchy tests verify the new v2.0 release separately. Expected results are authored in
`tests/test_history_fixture.py` and `tests/test_cli_edges.py`; they are not
snapshots generated by the implementation. `history.json` contains Git identities
only. Counts below are calculated from the fixture's authored clauses:

| Version | Clauses | Active L1 must | Linked to acceptance | Open Q | Open options |
| --- | ---: | ---: | ---: | ---: | ---: |
| `v0.1` | 6 | 3 | 0 | 1 | 0 |
| `v0.2` | 17 | 6 | 3 | 1 | 2 |
| `v0.3` | 19 | 6 | 3 | 0 | 0 |
| `v0.4` | 19 | 6 | 3 | 0 | 0 |
| `v1.0` | 19 | 6 | 3 | 0 | 0 |
| `v2.0` | 41 | 14 | 8 | 1 | 1 |

| Commands / boundaries | Independent assertions |
| --- | --- |
| `init`, `new-id` | Empty spec creation, overwrite rejection, invalid prefixes, 32 concurrent IDs allocated across independent clones |
| `check`, `check --since` | All releases/valid branches; expected invalid-state errors; clean-merge refinement review flags; known conflicts remain advisory |
| `trace` | Recursive refinements/dependencies, edge types/direction, verification backlinks, shared nodes, dependency cycles, disconnected clauses, text and structured output |
| `coverage`, `status`, `options` | Exact counts/gaps per release; archived contracts excluded; question resolution, decision links, option defaults/ranges/couplings/closure |
| `deps` | Exact five projection dependencies; ID/file-anchor resolution, provenance, whole-file and directory filters; no sibling-prefix leakage |
| `export` | Exact clause totals and all kinds, stable repeated results, metadata/lifecycle records |
| `log`, `--ref`, `--all` | Exact counter-history commit set, per-parent merge changes, both branches, moves/reflows, each matching-parent merge, side refs, deletion/restoration, unknown IDs, duplicate-ID rejection |
| `diff` | Forward/reverse and cross-branch comparisons, identical snapshots, tags/commit hashes, formatting-only move, deprecation/supersession, edge deltas and census changes |
| `test` | Three passing acceptance tests on original scenarios and four on the nested hierarchy scenarios; explicit assertion failure, missing models/tests, no silent zero-test success |
| Broken worktrees / arguments | Non-UTF8 Markdown, missing manifest/spec directory cannot disable historical queries; invalid refs/ranges/paths fail without mutation |
| Markdown/config boundaries | Inline-code keywords/links ignored, fenced conflict examples ignored, malformed metadata/config and empty supersession targets rejected |
| Existing focused regressions | Long dependency chains, glossary warnings and synonym rules, code-whitespace preservation, additional disposable Git histories |

Every integration test receives a fresh temporary clone. Negative/mutating
scenarios never switch the source submodule's checkout. The suite checks its HEAD
and worktree again on teardown.

## Rebuild and extend

The readable builder records actual Git development operations, including merges
that must conflict. Fixed authors, timestamps and commit messages make the commit
IDs reproducible. To verify regeneration without changing tracked artifacts:

```sh
python3 tests/fixtures/build_history.py --bundle /tmp/chrono-rebuilt.bundle --manifest /tmp/chrono-rebuilt.json
python3 -m unittest discover -s tests -p test_fixture_build.py -v
```

The reproduction test compares every ref with the checked-in manifest and verifies
the generated bundle's advertised refs. Bundle pack bytes need not be identical
across Git versions; object IDs and history must be identical.

When extending the story, update the builder, regenerate the tracked bundle and
manifest, update the submodule gitlink if the pin changes, and hand-author the new
expectations/matrix. Commit the bundle, manifest, gitlink and tests together. Do
not rewrite expected results from whatever the current CLI happens to print.

The broader command/layout/Markdown/graph test matrix and root-cause accounting
are recorded in [the second audit report](../ADVERSARIAL_AUDIT.md).
