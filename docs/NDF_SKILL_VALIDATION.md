# NDF skill validation

The `skills/ndf-spec` artifact combines a task-scoped operating entry point with
the complete proposal. It does not replace the original proposal with the CLI's
currently implemented subset.

## Fidelity and completeness

- English and Chinese Markdown originals are copied byte-for-byte under the skill's
  `references/`, including every section and Appendices A–C.
- `references/provenance.json` records their SHA-256 hashes and last source commits,
  plus the tool revision used for support notes.
- `references/proposal-map.md` maps every original section/subsection, workflow item,
  limitation, rollout phase, success criterion and appendix to operating guidance.
- Draft inconsistencies and incomplete examples remain verbatim in the originals;
  compatibility notes are separate rather than silent edits.
- The original English/Chinese root files and PDFs are unchanged.

Executed checks:

```sh
python3 tools/check_ndf_skill.py
python3 /home/boran/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/ndf-spec
```

The first check verifies full reference-byte fidelity, provenance hashes and local
reference closure. The skill-creator validator checks the actual skill format and
unfinished scaffold markers. Neither is presented as proof of agent behavior.
The format validator is environment-provided; the repository checker has no
third-party dependencies and also runs in CI.

## Independent forward test

Before the entrypoint simplification described below, an independent CLI tester
was given the completed skill and a realistic raw user
request, not the intended answer or suspected failure: create a retrying telemetry
sender spec, retain a queue-depth option (default4, explore4/8), project the supplied
Toy Clock rev1 §2 definition, leave an unknown acknowledgement deadline open,
then incorporate a reset-priority clarification while preserving Git history.
All generated files/commits were isolated under `/tmp`; no source repo, user skill
installation, original proposal, or remote service was changed.

It used the actual PATH `ndf` executable rather than this repository's script.
Observed artifacts/results:

| Item | Actual outcome |
| --- | --- |
| Initial baseline | `spec-v0.1`, 18 clauses, structural check with no errors/warnings, five model tests passed |
| Feedback baseline | `spec-v0.2`, 20 clauses, structural check with no errors/warnings, seven model tests passed including 28 reset-priority subcases |
| Decision discipline | Clarified reset requirement, resolved question, decision, model change and acceptance committed together |
| Verification frontier | Nine L1 must clauses, eight linked; deadline remains unverified and explicitly open |
| Design space | Queue depth remains open with default4 and candidates4/8; no premature selection |
| Provenance | Actual provided source projected with exact edition/section; dependency report emitted real links |
| Commands | 47 logged invocations returned status0; trace/log/diff/deps/options/status/export and explicit model tests exercised |
| Reconciliation | `check --since spec-v0.1` emitted seven direct related-pair review flags; no claim that the checker interpreted contradictions |
| Safety/scope | No network sender or external publication; local temp Git checkout stayed clean |

The primary agent independently inspected the decision/model/tests and reran the
final structural check and seven acceptance tests successfully. Assertions cite
actual clause IDs. The executable model is not a production transport; automatic
acknowledgement deadlines/retry cadence remain unimplemented pending the decision.
Coverage links and executed tests were reported separately.

No blocking skill ambiguity or CLI failure occurred. Full first-adoption reading
is substantial for a small example, as expected for a request to retain the full
methodology; conditional source routing keeps unrelated sections out of routine
edits. UUID authoring verbosity did not justify renumbering IDs or adding hidden
allocator state. Temporary command logs are evidence from this run, not new
canonical project state or files required by the skill.

The source snapshot checker and generic skill validator should be rerun after
intentional updates. A bounded successful exercise does not guarantee every
future agent/task will interpret the methodology correctly.

## Entrypoint simplification

The revised `SKILL.md` keeps the operating loop and reading routes, with detailed
methodology supplied by the verbatim proposal. It reduces the entrypoint from
212 to 65 lines. The proposal map, CLI guide and bilingual source snapshots remain
available in full; feature retention does not depend on repeating their contents
in the entrypoint. Initial reading now covers §§2, 4.1–4.3 and 7, with additional
sections selected by the task.

The source/provenance/reference checker and generic skill validator pass for this
revision. The forward test above exercised the previous entrypoint; it has not
been repeated for the shortened version. Validation of this revision establishes
source preservation, reference closure and skill format, not new behavioral evidence.
