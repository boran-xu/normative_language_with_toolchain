---
name: ndf-spec
description: Create, maintain, review, and implement against system-lifetime NDF specifications using the Normative Language proposal and the ndf CLI. Use when a project adopts NDF, requests its structured requirements workflow, or needs clause-linked refinement, decisions, verification, reference ingestion, and design-space exploration. Do not apply merely because a task edits ordinary Markdown.
---

# NDF specification workflow

Apply **Normative Description Format (NDF)** as proposed in *Normative Language:
Organizing the Normative Description of Highly Complicated Systems*, draft v0.1.
Maintain the system's canonical normative description over its lifetime, not a
per-feature scaffold discarded when implementation finishes.

## Read the source; preserve the scope

The complete proposal is bundled **verbatim**, not replaced by this operating
summary:

- [English proposal](references/normative_language.md).
- [Chinese proposal](references/normative_language_cn.md), the maintained translation.
- [Proposal map](references/proposal-map.md): section-by-section routing and full-feature checklist.
- [Current tool guide](references/ndf-tool.md): executable commands, limitations, and manual work still required.
- [Provenance](references/provenance.json): exact source hashes and revision identities.

For first adoption, read the proposal's §§1–2 and 4–9. For an existing project,
read its manifest, charter/glossary, relevant clauses and linked context; consult
the corresponding original sections before changing their conventions. Read §3
when comparing approaches, §§10–11 when planning/evaluating adoption, Appendix A
when authoring syntax, and Appendices B–C for refinement and complete examples.
Choose the English or Chinese version; loading both is unnecessary.

Treat the proposal as the methodological source. The CLI implements a subset;
**do not narrow the methodology to what the executable currently checks**. Keep
its future capabilities and limitations visible. The user's explicit instructions
and project-specific adopted conventions take precedence; distinguish any local
extension from the original text rather than silently rewriting it.

## Keep the middle path

> Structure is imposed at the *organizational* level, not the *sentence* level.

Use natural language for intent, rationale, uncertainty, and non-functional
requirements. Use code/data where cheaper and more precise: models, packet/register
formats, state tables, schemas, pseudocode. Do not require total formalization,
proofs, a database, a server, one-item-per-file storage, or mandatory EARS prose.
Keep readable documents with several related clauses. Aim for monotonic quality
improvement, not a claim of perfect consistency or completeness (§§2–4.5).

> prose lives in a tree, meaning lives in a graph, time lives in git — and stable clause IDs are the rivets holding all three together.

The canonical state is the specification tree plus Git history. JSON exports,
retrieval indexes, dashboards and published books are derived views.

## Establish the project and the work order

Find the existing spec root and `ndf.yaml` before scaffolding. Follow the proposed
areas (§4.1): charter/glossary, architecture, behavior by subsystem, interfaces,
constraints, verification, `models/`, `refs/`, `decisions/`, and `open/`. Give each
clause exactly one home; let typed edges cross directory ownership. Adapt the
areas to the system, rather than copying the stopwatch or switch domain blindly.
Use `ndf init` only for a new root and declare project prefixes and ordered layers.

Frame each task as **a baseline plus a work order referencing clause IDs** (§7).
A `spec-vX` tag is convenient; an exact Git commit also identifies a baseline.
Starting from latest is fine: record what latest meant. State any uncommitted
changes separately. Read the requested subtree and its refinement/dependency
neighborhood, including relevant projections, questions, decisions and models.
Do not interpret a baseline as permission to ignore relevant subsequent changes.

## Author and refine clauses

Follow §4.2 and Appendix A. Use a literal heading anchor and one-line metadata
comments, for example:

```markdown
## Frame admission on ingress {#FWD-ADM-001}
<!-- ndf: kind=req level=must layer=L1 status=stable since=0.3 -->

When a frame arrives, the switch MUST admit it only if it passes
FCS validation ([[ING-FCS-002]]).
```

The example's referenced clause must actually exist before the live check passes.
Generate a fresh ID under a declared area prefix with `ndf new-id`. Keep it across
moves/edits; never renumber it or reuse a retired ID for a different clause. Retain existing numeric IDs. See the
tool guide for its UUID-suffix extension; ID generation prints an ID and does not
insert a clause or reserve persistent allocator state.

Retain every metadata concept: `kind`, `level`, `layer`, `status`, `since`; typed
links; `model`; source edition/section and `origin-status`; decision/question
fields; and option fields. The proposal's kinds are `req`, `def`, `arch`,
`constraint`, `option`, `verif`, `info`, plus `decision`/`question` in its examples.
Levels are `must`, `should`, `may`, `tbd`; lifecycle includes `draft`, `stable`,
`deprecated`, and `superseded-by=ID`. Keep `since` consistent with current substance.

Use `[[ID]]` or `[[ID | display text]]`; record `refines`, `depends-on`,
`conflicts-with`, `verifies`, `derived-from`, `couples-with` and other original
metadata links as appropriate. Resolve references and inspect backlinks.
MUST/SHOULD/MAY/MUST NOT follow RFC-2119 conventions in `req` clauses. Material
outside clauses, `info` content, examples and `> rationale:` do not silently
become requirements. One testable obligation per requirement is a useful
heuristic, not an excuse for unreadable fragmentation.

Preserve the refinement ladder (§4.6): **L0 intent; L1 behavioral contract; L2
mechanism; L3 executable model/acceptance**. Respect project-renamed ordered layers.
Higher layers point to their lower-layer parents with `refines=`. Keep all layers
alive; do not delete intent because mechanism exists. Review changed parents and
children together; deliberately reconcile whichever level actually changed.
Recorded refinement is traceability, not proof of correct refinement.

## Make uncertainty and design space explicit

Follow §§4.7–4.8 without converting all uncertainty into blocking errors:

- Mark real holes with `level=tbd` or `⟨TBD: ...⟩`. A vague L0/L1 skeleton is valid.
- Put unresolved questions in `open/` with `Q-` IDs, affected/blocked clauses and a
  resolution field. Record known contradictions with `conflicts-with` plus a
  question; do not silently choose a winner. Known conflicts warn, not fail.
- Use an `option` for a bounded design choice: `default`, `explore`, optional
  `unit`, dependencies and `couples-with`. An open option normally has
  `level=tbd status=draft`; its default lets modeling/early implementation proceed.
  Record which default/baseline was used. A constant to the RTL implementer can
  remain a variable for the model developer.
- State causal/trade-off coupling in prose and treat coupling bookkeeping as
  symmetric; explore coupled choices jointly. Retain inline
  `⟨DSE: <name> default=X range=… → PRM-ID⟩` markers where appropriate.
- Resolve a question with its decision record and affected clause edit in the
  same commit. Close an option with a decision and clause edit in the same commit:
  choose `default`, retain/narrow `explore`, move `level=tbd → must` and
  `status=draft → stable`. Keep links to the exploration and implementation value.

## Preserve executable authority and verify separately

Read §4.5, §7 item 4, and Appendices B–C. Mark authoritative code islands with
`ndf:normative`; unmarked code is illustrative. Link `model=models/...` to a
runnable authoritative model and keep the inline digest consistent with it.
Reference models/acceptance checks remain distinct from shipping code/RTL;
never collapse the layered spec into only the product.

Author `verif` acceptance clauses with `verifies=` links. Each must-level L1
contract should eventually have an L3 acceptance criterion. Preserve the PICS-like
checklist, directed/golden-vector/randomized/invariant checks suited to the
behavior, clause IDs in failures, and model tests in the spec build. Inspect
coverage and run tests separately: a link is not an implemented or passing test.
For non-Python models, run the project's real runner as well. A failing test that
exposes ambiguity produces a `Q-` item; it does not authorize invented behavior.

## Compile feedback and preserve history

Apply §§5 and 7:

> any human instruction to an agent that changes design intent must terminate as either a clause edit or a decision record (usually both), in the same commit.

Distill prompts/corrections into decision records containing context, the decision,
alternatives rejected, source/session/date, affected IDs and supersession of earlier
guidance. Raw chat is not the canonical spec. Optional cold archives can preserve
context that distillation loses. Keep implementation/review commits linked to IDs.

When replacing a clause, keep the old one with `status=superseded-by=NEW-ID`;
retain its history and reasoning. Use branches, merges, baselines, clause logs and
semantic changelogs. Split ownership by subtree, use generated IDs, run checks in
CI after merges, and review related clauses even when Git merges text cleanly.
A merge has multiple parents; never flatten away either side's intent silently.

Humans retain authority over normative changes; agents propose and cross-check.
Follow the user's authorization and the project's review process. Prepare the
reviewable clause/decision changes together; use existing commit authorization
rather than inventing extra approval gates. The same-commit discipline governs
what is committed, not permission to commit or publish without authorization.

## Ingest references and publish derived views

Preserve §6 even though `ndf ingest` is not implemented. Import the **needed
projection**, not whole standards by default. Extract source text/tables/figures;
segment and classify; restate into linked NDF clauses; audit. Keep original image
assets with normative prose restatements and tables/code where possible. Every
projection carries exact source edition/section in `origin` and
`origin-status=verbatim|paraphrase|interpretation`. Review interpretation especially
carefully, including possible errata. Apply source licensing constraints when
redistributing reference content. Use `ndf deps` when a standard changes.

Preserve §7 item 6 and §8 publication: generate a human-readable HTML/PDF book with resolved
links, backlinks, trace matrices and per-baseline changelogs from the canonical
files. Rendering is distinct from external hosting/distribution. Keep these outputs
derived. `ndf publish` is not implemented; use appropriate available tooling when
requested and report what was actually generated. Never fabricate command output.

## Check, review and judge success

Use [the installed tool](references/ndf-tool.md) for structural checks, traversal,
coverage/status/options, dependency reports, history/diff, export and explicit
model-test execution. Retain all §8 capabilities in the plan even when manual or
other project tools currently supply them. Do not claim that an unavailable
command, automated semantic comparison, or unrun verification succeeded.

Review precision using the glossary, undefined capitalized terms, declared
synonyms, ambiguity words and optional EARS suggestions (§4.4). Treat wording
pressure as advisory. Structural dangling refs/duplicates are different from
review judgments. Let projects choose release gates; do not make all TBDs,
options, known conflicts or coverage gaps universal build blockers.

Account for all §9 limitations: prose consistency is empirical/social, prompt
compilation is lossy, conventions decay, clause size needs judgment, diagrams are
hard to normalize, `refines` is not verified, and ecosystem/adoption affect payoff.
Semantic comparison is agent/human review, not a required embedded LLM service.

For methodology/tool rollout, retain all §10 phases: format freeze/self-hosting,
minimum tools and CI, real-design pilot, reference ingestion, and retrospective.
Judge §11's six outcomes: a canonical bible exists; provenance is queryable;
agents work from baselines; evolution is legible; incompleteness is visible and
trending; specification effort stays a modest fraction of design effort. If spec
maintenance rivals design work, reduce rigor rather than recreating total
formalization. Use the proposal map to check scope before claiming completeness.
