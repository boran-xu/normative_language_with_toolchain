# Existing ndf executable: support without shrinking the proposal

This is an implementation guide, **not a replacement for the proposal**. Support
was checked against this repository's toolchain and the installed `ndf --help`.
The original proposal remains bundled verbatim alongside this file.

## Availability and state

The user's NDF tool is installed in `~/.local/share/venvs/ndf`, with its executable
symlinked onto PATH (locally `~/.local/bin/ndf`). Prefer `ndf`; activation is not
necessary when its shebang selects the venv. Do not reinstall globally or create a
new environment just to use it. On a different machine, check availability first:

```sh
command -v ndf
ndf --help
```

If PATH lookup fails here, the user-managed fallback is
`~/.local/share/venvs/ndf/bin/ndf`; check it rather than assuming another user's
home path. If the tool is unavailable, Markdown/Git authoring remains possible;
report which checks could not run. Do not substitute invented CLI results.

The canonical current state is the spec directory: Markdown, `ndf.yaml`, models,
reference projections and assets. Git holds past baselines. There is no required
database, server, allocator counter, or persistent cache to migrate. A normal clone
is sufficient once NDF is installed. An ID is stable across versions; an ID plus a
commit/tag identifies its exact wording. Uncommitted edits are outside that snapshot.

Inspect the local executable's help, manifest and outputs: installations can lag
behind the repository. `ndf.yaml` can use ordinary YAML if optional PyYAML is
installed; JSON syntax is valid YAML and works without that extra dependency.
Do not rewrite an existing project's manifest solely to match an example here.

## Global arguments and scaffold

Put `--root` and `--json` **before** the subcommand. Default root is `spec`.
Use `--root .` when the repository itself is the spec root, or an absolute path
when invoking from elsewhere.

```sh
ndf --root spec init
ndf --root spec new-id SYS
ndf --root spec --json check
```

Only run `init` for a new root. It creates the proposed directory areas and a
manifest with initial prefixes `SYS, VER, D, Q`; declare the project's prefixes
before requesting other IDs. `new-id FWD-ADM` is valid after declaring `FWD` (or
an appropriate area prefix). Generate IDs for decisions/questions too when making
new records; retain existing numeric IDs such as `D-0042` and `Q-017`.

**Format extension:** issued IDs have UUID4 hexadecimal suffixes, not Appendix A's
numeric `NUMBER`. This supports independent clones/branches without a shared
counter; collisions are negligibly probable, not formally impossible. Duplicate
IDs still fail validation. The generator only prints an ID; insert it into a
clause yourself. It does not reserve it or persist allocator state. Do not
renumber a generated ID to make it look like the examples.

## Commands

| Original purpose / command | Current invocation and behavior |
| --- | --- |
| New IDs | `ndf --root spec new-id FWD-ADM` prints a fresh ID under a declared prefix. |
| Structural/wording lint | `ndf --root spec check`: metadata, IDs, dangling refs, model-file paths, layer order/cycles, supersession, option fields; advisory keyword, glossary, ambiguity and recorded-conflict warnings. |
| Change-related refinement review | `ndf --root spec check --since BASE`: compare current files with BASE; flag directly related changed parent/child pairs, including removed links. This is not contradiction detection. |
| Refinement/dependency trace | `ndf --root spec trace ID`: recurse through incoming `refines` and outgoing `depends-on`; show verifier backlinks/typed edges; mark shared/cyclic encounters rather than expanding forever. Plain mentions are not recursively traversed. |
| Clause history | `ndf --root spec log ID`; options `--ref REF`, `--all`. Uses Git snapshots, survives moves within the root and compares every merge parent. `--all` includes reachable local refs/worktree heads, not missing remote history or reflog-only commits. |
| Baseline changelog | `ndf --root spec diff A..B`: tags, branches or hashes; added/deleted/moved, formatting/content/lifecycle, metadata/edge changes, unified text patches and census deltas. Comparisons work across branches and in reverse. |
| Verification/incompleteness | `ndf --root spec coverage`: active contract-layer must clauses versus active verification links; unverified IDs, TBDs, open options/questions, inline DSE and recorded conflicts. |
| Questions | `ndf --root spec status`: coverage plus each question's status, blocked IDs, resolution and body, preserving closed records. |
| Design parameters | `ndf --root spec options`: option metadata records, including default, explore range, couplings, level/status. |
| External reference surface | `ndf --root spec deps refs/`: typed and ordinary mentions into that subtree with provenance. ID, root-relative path-anchor and whole-file references resolve to stable IDs. |
| JSON records | `ndf --root spec export`: parsed clauses, IDs, locations, metadata and text. JSON is a derived view. |
| Model runner | `ndf --root spec test`: Python unittest discovery under `models/`, explicitly executing project code. Failing, missing, or zero-discovered tests do not silently pass. |
| Publication | `ndf publish` is **not implemented**. Retain §7.6/§8 outputs; generate them with other available tooling when requested. |
| Reference ingestion | `ndf ingest` is **not implemented**. Carry out §6's extraction, classification, restatement and audit using agent/human work and appropriate tools. |

For available JSON reports, insert `--json` before the subcommand. `export` always
produces JSON; `test` produces the actual test runner's output. Exit codes are
0 success, 1 structural validation failure, 2 invocation/configuration/Git failure;
model execution returns its runner's status. Warnings alone do not fail `check`.

## Apply the whole method beyond the checker

These limits do **not** repeal the original design responsibilities:

- `since`/status may be omitted by the parser to accommodate draft examples.
  Authors still maintain lifecycle and substantive revision history. The tool
  cannot establish that every reused-looking ID preserves the same intent, and
  does not enforce retaining replaced clauses or decision/requirement edits in
  the same commit. Follow the proposal's discipline yourself.
- The proposal's acceptance goal is L1 must contracts with L3 criteria. Current
  coverage counts active `verif` links without enforcing an L3 source layer and
  includes definitions/constraints tagged contract-layer must. Inspect criteria
  and assess actual gaps; never report links as proof or passing test results.
- Current diff is deterministic clause/graph bookkeeping, not prose meaning
  inference. It lacks the proposal's explicit coverage delta; compare coverage
  reports at the two baselines in clean temporary worktrees when that matters.
  Its formatting classification is syntactic, not a semantic equivalence proof.
- Normative inline code is preserved, but the CLI does not extract or execute
  `ndf:normative` blocks or prove their consistency with linked models. Keep their
  authority/scopes explicit and run the linked model/acceptance checks separately.
- `check` validates `model=` file existence, not model correctness. Run `test` in
  CI alongside `check`; for another language/test framework, run that project's
  real commands as part of the spec build. Capture clause IDs in real failures.
- EARS suggestions and the full precision/ambiguity analysis are not implemented;
  apply §4.4 editorially. Glossary capitalization/synonym checks are advisory
  heuristics and use explicit definitions/alias declarations, not inferred meaning.
- `options` lists records; it does not run DSE, choose values, normalize a complete
  undirected coupling visualization, or commit closure decisions. Keep the allowed
  range, usable default and symmetric coupling interpretation from §4.8 yourself.
- The proposal's non-clause section pointer examples such as
  `[[refs/ieee-802.1q#8.6.1]]` need a real local projection in a live project.
  Current file anchors resolve NDF clause IDs, not arbitrary heading slugs or
  numeric sections. Use a stable projection ID and retain the original numbered
  source section/edition in `origin`; do not invent a missing source clause.

The CLI supports literal top-level ATX clause headings and regular `.md` files.
It rejects Markdown symlinks consistently; root-directory aliases are allowed.
It preserves prose/code/source mapping through CommonMark parsing. Ignore fake
clauses, metadata and links inside code/comment examples; do not turn informative
samples into normative requirements.

Full history is required for `log`; a shallow clone is rejected explicitly rather
than labeling a boundary as a new clause. `diff` needs its requested snapshots
available locally. Run `git status` and use the intended root before interpreting
reports. History queries ignore current broken/missing Markdown or manifest, but
historical snapshots with duplicate IDs or unsupported Markdown symlinks fail.
The submodule fixture/bundle in the tool's development repository is test data;
ordinary spec projects do not need a submodule or that bootstrap script.

## Honest checking loop

For authorized work on an existing spec, select the relevant operations rather
than blindly running every command:

```sh
ndf --root spec trace CHR-000
ndf --root spec check --since BASE
ndf --root spec coverage
ndf --root spec status
ndf --root spec options
ndf --root spec deps refs/
ndf --root spec test
ndf --root spec diff BASE..HEAD
```

`CHR-000` and `BASE` are placeholders for real project IDs/revisions. `diff` compares
committed snapshots, not uncommitted files; `check --since` includes current edits.
Run `test` only when model execution is within the task's authorized scope. Report
structural failures, advisory review flags, remaining open work, actual executed
tests and semantic review conclusions separately. An agent may review meanings;
the executable is not required to embed an LLM.
