# Interaction audit after the 117-test pass

This pass found **15 distinct additional pre-existing behavioral defects and
fixed all 15**, with regression evidence below. Counts are not failing assertions:
several scenarios exercising one cause are grouped together. In particular,
current-tree Git-metadata enumeration issues count once, and bootstrap shape/ref
preflight failures found independently by two reviewers count once. Compatibility
regressions caught while replacing the parser were fixed without inflating the
pre-existing-defect count.

## Defects and independent regression coverage

| # | Confirmed defect | Regression / resulting behavior |
| --- | --- | --- |
| 1 | Global backtick matching crossed comments, fences, paragraphs and clause boundaries | Markdown interaction tests verify each boundary; CommonMark block/inline parsing isolates contexts |
| 2 | Escaped backticks opened code spans and hid real references | Odd/even backslash interaction tests; parser escape rules determine code delimiters |
| 3 | List/paragraph continuation indentation was always treated as code | Unordered, ordered, nested and tab-indented prose controls versus genuine list-contained code |
| 4 | Inline-code text was removed from exported heading titles | Code/emphasis titles retain display syntax, editorial comments remain hidden |
| 5 | Wiki-reference syntax inside an ordinary link destination created a false clause reference | Link-label/destination controls; NDF links are recognized by an inline token rule |
| 6 | Current-tree enumeration excluded `.git` in unrelated absolute ancestors but validation included actual Git metadata | Root-as-repository and unrelated `.git`-ancestor tests; one shared root-relative enumeration policy |
| 7 | Directories ending in `.md` were read as files | Nested `appendix.md/` directory test; only regular files are read |
| 8 | Tracked Markdown symlinks gave different current and historical clause namespaces | Current/snapshot parity, broken aliases and clean-checkout review tests; explicit symlink rejection in both paths |
| 9 | Equivalent ID/file-anchor/path spellings and reference-file moves produced phantom diff edges | Diff mentions resolve to stable clause IDs in each snapshot |
| 10 | Coverage accepted renamed layers but hardcoded `L1` | Dictionary/list renamed-layer tests; contract layer is selected by its ordered role and reported explicitly |
| 11 | Self/cyclic supersession passed checks and hid all affected contracts | Cycle validation rejects self/mutual replacement; valid chains/shared terminals remain supported |
| 12 | Conflicting replacement targets in status and explicit metadata silently discarded one | Contradictory representations are rejected; matching representations are tested |
| 13 | Root symlink loops failed before CLI error handling | Root resolution now happens inside the error boundary and returns a clean failure |
| 14 | Malformed bootstrap manifests exposed Python errors, and tag mismatch was checked after initialization | Validate typed metadata and advertised bundle refs before mutation; rejected cases cannot create/reset the fixture |
| 15 | An unchanged whole-file-reference consumer was omitted when its target file gained a clause | Graph-only diff tests check added edges and reverse removals even when source text is unchanged |

No confirmed case above remains unresolved. Passing tests are evidence for these
behaviors, not a proof that no other defects exist.

## Why replace the scanner

The handwritten scanner was repeatedly approximating Markdown context. It is now
replaced with `markdown-it-py` CommonMark block/inline tokens, plus a small inline
rule for NDF's existing `[[target | label]]` syntax. This is deterministic parsing,
not an LLM. It delegates list indentation, escapes, code spans, comments and link
syntax to a maintained parser instead of adding more local heuristics.

The parser's [official token/API documentation](https://markdown-it-py.readthedocs.io/en/latest/using.html)
describes the block token maps and inline children used by NDF. Source-line
locations and raw clause bodies remain tied to original files; heading display
syntax and quoted metadata are covered by compatibility tests. The established
NDF behavior of reading ordinary prose after a comment's closing delimiter is
retained explicitly.

`markdown-it-py>=3,<5` is now a direct runtime dependency; install with
`python3 -m pip install .`. Optional ordinary YAML still uses PyYAML. Bootstrap
itself remains Python/Git-only and works offline from the tracked bundle.

## Expanded validation

- 26 Markdown interaction methods cover context composition and token-map/body
  compatibility, including list/quote heading examples, quoted backticks in
  metadata, successive metadata blocks, real links versus code/destination text,
  and fence closure before another clause.
- 18 CLI interaction methods cover renamed layers, supersession representations,
  root errors, direct reconciliation flags, model import exits and skipped tests,
  bootstrap preflight, idempotence and user-file preservation.
- 15 Git interaction methods cover namespace scope, regular/symlink entry parity,
  resolved edge identity, dynamic whole-file reference graphs, detached linked
  worktree heads, explicit tag/branch namespaces, merge reverts/reapplications,
  and crisscross merges with equal final snapshots.
- Six additional bootstrap edge methods exercise malformed typed metadata,
  mismatched pins/tags, damaged bundles, dirty/untracked work and global-config
  preservation in disposable outer clones.
- All earlier 117 tests remain in the suite: fixture reconstruction, releases,
  model acceptance, concurrency, generated graph oracles and deep refinement.
- Offline package construction and the installed `ndf` console entry point are
  verified separately, alongside fresh-clone bootstrap and the full suite.

The bundled fixture remains v2.0 with 41 clauses and 35 named snapshots. No
history expansion was needed for this pass: the newly isolated cases are clearer
in disposable repositories, and all existing fixture histories are still verified.
The bundle, manifest and gitlink remain unchanged and consistent. Source fixtures
are not mutated by the tests; the original proposal files remain untouched.

GitHub Actions installs the package before running the existing bootstrap/suite
steps on its Python matrix. Local verification does not claim a remote CI run.

```sh
python3 -m pip install .
python3 tools/bootstrap_history.py
python3 -m unittest discover -s tests -v
```

The remaining boundaries are explicit: NDF clauses use top-level ATX headings,
Markdown files must be regular files (directory-root aliases are allowed), and
prose interpretation remains a human/agent responsibility. Parser nesting and
large-history performance are bounded by the parser and the snapshot-scanning
implementation; this pass does not claim unlimited-input or semantic correctness.
