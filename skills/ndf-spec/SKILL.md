---
name: ndf-spec
description: Create, maintain, review, and implement against system-lifetime NDF specifications using the Normative Language proposal and the ndf CLI. Use when a project adopts NDF, requests its structured requirements workflow, or needs clause-linked refinement, decisions, verification, reference ingestion, and design-space exploration. Do not apply merely because a task edits ordinary Markdown.
---

# NDF development workflow

Use *Normative Language*, draft v0.1, as the methodological source for this
project's lifetime specification. The complete proposal is bundled verbatim:
[English](references/normative_language.md) / [Chinese](references/normative_language_cn.md).
Choose one language. Follow the user's instructions and adopted project conventions;
identify local extensions explicitly.

## Read for the task

Use the [proposal map](references/proposal-map.md) to locate the original sections
needed for the work. Read those sections before applying unfamiliar parts of the
method; examples supply syntax and context, not ready-made project requirements.
For first adoption, read §§2, 4.1–4.3 and 7, then follow the task routes as needed.
For routine work, start with the project's existing specification and consult the
proposal where the task requires it.

Read the [CLI guide](references/ndf-tool.md) before first using `ndf`, and when a
command's behavior or compatibility matters. It documents installation, arguments,
implemented checks and gaps. The proposal's full methodology still applies where
the CLI supplies no automation.

## Work from the specification

1. Find the existing spec root, `ndf.yaml`, project instructions and Git state.
   For a new spec, establish scope and charter using §4.1 and §7; use `ndf init`
   only for a new root.
2. Frame the task against a baseline and relevant clause IDs (§7). Keep the
   baseline reference in the task context (prompt, issue or work order), using
   a supplied tag or the starting checkout's commit. This does not require a new
   spec entry: do not add routine commit hashes or working-tree inventories to
   clauses. Record artifact baselines in implementation/verification records when
   needed (§5.1). Read the charter/glossary and affected clauses with their
   refinement, dependency, verification, decision and question context.
3. Determine whether the work implements existing intent or changes it. Apply the
   relevant proposal sections to coordinate clauses, decisions, questions, options,
   models, acceptance criteria and implementation as needed. Compile feedback
   that changes design intent into durable spec artifacts under §5.2. Keep related
   resolutions and edits together in the same commit, within existing authorization.
4. Check structure with `ndf --root <root> check`; use `check --since <baseline>`
   for changed refinement relationships. Select trace, coverage, status, options,
   dependency and history reports according to the task. Run applicable model and
   implementation tests. Review meaning and refinement explicitly: structural
   checks and verification links do not establish semantic consistency or passing tests.
5. Report affected IDs, design decisions, actual verification results and remaining
   questions or gaps. Cite clause IDs in implementation commits and reviews.

Preserve clause identity and the refinement layers while editing. Keep the
specification tree canonical and generated views derived. Use the original
proposal for the detailed rules, syntax and examples; unresolved behavior remains
explicit rather than being invented to complete an implementation.

Authoring preference: state required behavior directly. Add a negative clarification
only when it resolves a plausible ambiguity grounded in the design, distinguishes
a real competing interpretation, or expresses a necessary prohibition/invariant.
Avoid automatically pairing a positive statement with an unrelated “does not” or
“MUST NOT,” or inventing a misconception just to refute it. Preserve substantive
negative requirements; judge clarifications by their value to an implementer.

Use the project's glossary terms consistently in discussions with the human,
explanations and reports. When introducing an unfamiliar term, connect it to the
defined vocabulary; avoid inventing synonyms for established concepts.

## Consult when needed

- Authoring, refinement, uncertainty, design options or executable authority:
  §§4.2–4.8, Appendix A; Appendices B–C for worked examples.
- Feedback, decisions, supersession, branches or merges: §5 and §7.
- External reference projections and their audit: §6.
- Verification and publication: §7 and §8, with the CLI guide for available tools.
- Adoption choices, limitations, rollout or evaluation: §§1–3 and 9–11.

The [proposal map](references/proposal-map.md) also records draft ambiguities.
[Provenance](references/provenance.json) identifies the bundled source snapshots.
