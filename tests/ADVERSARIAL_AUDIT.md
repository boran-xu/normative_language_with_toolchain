# Second adversarial audit

This session found **18 distinct pre-existing bugs and fixed all 18**. Counts are
by reproducible behavioral defect, not by failing assertions, parameter variants
or new test count. Overlapping discoveries were consolidated: lifecycle-census
failures reported by both CLI and history reviewers count once; equivalent path
spellings and the `/` validation bypass form one path-handling bug. Regressions
caught while developing fixes were corrected as well, without inflating this count.

The tests specify expected results independently. They use fresh CLI processes,
disposable repositories/clones, known authored clauses and explicit graph oracles.
No LLM is embedded in the implementation or tests. Original proposal files remain
unchanged.

## Confirmed defects and regressions

| # | Bug found | Fix / regression evidence |
| --- | --- | --- |
| 1 | HTML comments could create authoritative clause headings, metadata and references | Shared visibility masking; Markdown audit comment tests |
| 2 | A reference inside a multiline inline-code span became a dangling link | Scan complete clause bodies, preserving code-span context; multiline-code test |
| 3 | Indented code supplied metadata, references or normative keywords; stripping body indentation could expose it | Mask indented blocks and preserve source indentation; Markdown tests plus generated boundary-code test |
| 4 | Valid ATX headings with closing hashes or 1–3 leading spaces silently lost clauses | Normalize valid ATX heading syntax; parameterized heading tests |
| 5 | Escaped `\[[...]]` delimiters created real references | Recognize odd/even escaping before reference openers; escaped-link test |
| 6 | Equivalent `./refs/...` spellings failed resolution/filtering; `/` bypassed the absolute-path check after stripping slashes | Shared lexical relative-path normalization, before filtering; reference and CLI path matrices |
| 7 | Glossary terms and declared synonym phrases failed when prose wrapped across lines | Match whitespace-separated phrase tokens; both wrapped glossary tests |
| 8 | `layers: null` crashed with TypeError and repeated layer names were accepted | Validate explicit ladder shape, names and uniqueness; malformed-manifest matrix |
| 9 | TBD/DSE syntax inside code examples added false active work | Census reads visible prose; marker example test and nested fixture example |
| 10 | Archived DSE/conflicts remained active, and retiring a retained TBD disagreed between coverage and diff | Shared lifecycle-aware census used by current reports and historical deltas; CLI and history census tests |
| 11 | Option metadata named `id` overwrote its heading-anchored identity | Anchored ID takes precedence in option records; option identity test |
| 12 | UUID allocation unnecessarily parsed unrelated damaged Markdown | ID issuance reads the prefix manifest without loading clauses; non-UTF8 new-ID test |
| 13 | The model runner lost spec-root package imports that worked with canonical unittest discovery | Retain the spec root on subprocess import path; package/direct/nested model tests |
| 14 | Empty typed-edge values or CSV elements silently disappeared | Validate declared edge lists before traversal; parameterized edge tests |
| 15 | Repository paths ending in a space, tab or newline were corrupted by `.strip()` | Remove exactly Git's record terminator; whitespace-root log/diff tests |
| 16 | Changes to indented code whitespace were labeled formatting-only | Preserve indented code in syntactic normalization; indented-code diff test |
| 17 | A shallow-history boundary was falsely reported as a proven clause addition | Reject incomplete clause logs with an explicit shallow-history error; shallow-clone test |
| 18 | A valid deep custom refinement ladder failed at Python's recursion limit | Iterative refinement validation; reversed-source 1,100-layer check and trace test |

All 18 have regression coverage. There are no unresolved failures from these
confirmed cases; this does not establish that the implementation has no other bugs.

## Expanded fixture

The real submodule now pins **v2.0**, containing **41 clauses**. The tracked bundle
preserves **35 named snapshots**, including all previously tested v1 history.
The new cycle adds five subsystems under nested directories, child headings,
shared projections and dependency chains, five verification clauses, coupled
configuration work, a nested Python test package, a three-parent octopus merge,
and clause movement/splitting across files and hierarchy boundaries.

The builder uses fixed authors/dates/messages; a regression rebuilds the bundle
and verifies every named commit, including the updated main/gitlink pin. Bootstrap
checks the exact pin and fetches all scenario refs. Mutation tests use clones;
the source submodule's HEAD and worktree are verified unchanged.

## Broader command and input matrix

- All implemented commands: `init`, `new-id`, `check`, `trace`, `coverage`, `status`,
  `options`, `deps`, `export`, `log`, `diff`, `test`; default and explicit roots,
  JSON and text paths, direct script and `python -m ndf`, help and invalid arguments.
- Populated/empty specs; malformed manifests, nulls, duplicate custom layers,
  malformed metadata and edge lists; question resolution spellings, every active
  or archived lifecycle state, retired verification and anchored identity.
- Inline/multiline/multi-backtick code, fenced/long/tilde fences, indented code,
  comments, escaped links, nested/indented/closing-hash headings, CRLF and Unicode,
  quoted metadata, root-relative paths, whole-file and file-anchor projections.
- Eight seeded mixed graphs of 32 clauses, with independent reachability oracles
  for three starting nodes each; disconnected nodes, diamonds/shared nodes,
  dependency cycles, duplicate/reordered edges and deep refinement/dependency chains.
- Tagged releases, divergent and unrelated branches, two- and three-parent merges,
  exact-parent resolutions, annotated tags, linked worktrees, split/moved clauses,
  whitespace roots, colon/tab/newline/dash filenames, mode-only changes, reflog-only
  commits, shallow clones and incomplete/broken/missing current specs.
- Forward/reverse diff invariants, edge and census inverses, metadata ordering,
  code-whitespace preservation, current-versus-historical lifecycle consistency.
- Direct, package and nested-package model imports; passing, failing, missing and
  zero-discovered tests. Failed tests must propagate a failing exit status.

## Reproduce

```sh
python3 tools/bootstrap_history.py
python3 -m unittest discover -s tests -v
python3 ndf.py --root examples/chrono/spec test
```

The full suite is also verified from a fresh outer clone using offline bootstrap,
not only the development checkout. GitHub Actions is configured to perform the
same setup and suite on Python 3.10 and 3.13; local verification does not claim a
remote CI run has occurred.

The scope remains deterministic structural tooling. Prose meaning, physical
hardware behavior and completeness of requirements remain review concerns.
Markdown handling covers the documented authoring forms tested here; it is not a
claim of complete CommonMark conformance. Snapshot history scans are intentionally
simple and can be expensive on large repositories. Shallow `log` requires a full
fetch; snapshot `diff` can operate when its two requested commits are available.
