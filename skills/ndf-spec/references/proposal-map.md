# Full proposal map and completeness checklist

The full English and Chinese originals are bundled byte-for-byte. This map routes
work; it does not replace or edit either source. Section numbers below refer to
[the English original](normative_language.md); use
[the Chinese original](normative_language_cn.md) when appropriate.

## Source and operating instruction coverage

| Source | Preserve / apply | Skill route and current operational responsibility |
| --- | --- | --- |
| Status, audience, translation note | Draft v0.1; hardware/protocol/large-software agentic design; paired translations remain consistent in the same commit | Read original status; keep both bundled sources verbatim and refresh them together deliberately |
| §1.1 | Normative authority distinct from implementation, test samples, tutorials and commentary | Keep the canonical specification and normative/informative boundary explicit |
| §1.2 | Human specs carry domain judgment, historical patches, partial referenced slices and fragile cross-references | Build local projections and durable links instead of leaving aggregation in a reader's head |
| §1.3 | Background docs + initial design + prompts/corrections are the actual governing aggregate; chat order silently loses supersession/context | Compile governing feedback into clauses/decisions, including provenance and superseded instructions |
| §1.4 | Incremental, versioned, converging, ingestible, hierarchical and cross-linked; human/machine readability; multi-cycle collaboration | Establish the lifetime spec root, graph, baseline and iterative workflow |
| §2.1 | Reject unstructured pure prose and prohibitive total formalization | Do not introduce rigid templates or require proofs as the entrance price |
| §2.2 | Natural-language vehicle, organizational structure, cheap code islands, engineered imperfection and monotonic improvement | Middle-path instructions, explicit holes and scoped executable models |
| §2.3 | P0→Pn layered refinement; Wirth/refinement/literate roots; no per-step proof; spec/reference models remain distinct from product | Keep summaries and all layers alive; record refinement and use tests/review to check it |
| §3 | All prior-art adoptions/rejections: RFC keywords/PICS, executable islands, advisory EARS, identity/checked links, lifetime Markdown, literate code, refinement, ADRs and Git; no one-item-per-file/YAML authoring/database | Retain the complete comparison table in the original; consult it for adoption/comparison choices |
| §4.1 | Complete suggested tree: charter/glossary, architecture, behavior subtrees, interfaces, constraints, verification, models, refs, decisions, open | Bootstrap or reuse the appropriate root; one home per clause; tree/graph/history are different structures |
| §4.2 | Stable globally unique IDs and every metadata field; kinds/levels/layers/status/since; plain/display references; typed links; keyword discipline; explicit informative default | Author clauses per original syntax; generate IDs; preserve identity; inspect backlinks and missing references |
| §4.3 | Multiple heading-anchored clauses in readable files; derived JSON can explode items without making authoring one-file-per-item | Keep authored documents human-shaped; export derived records only |
| §4.4 | Advisory EARS, glossary/capitalized terms/synonyms and ambiguity words; human discretion remains | Run available lint and review wording; do not impose universal build gates for style |
| §4.5 | `ndf:normative` code, authoritative linked executable versus inline digest, runnable model tests in build, structured data for formats/registers/state/schema | Read code scope; maintain digest/model consistency; run real tests; preserve examples as informative |
| §4.6 | L0 intent/L1 observable contract/L2 mechanism/L3 executable; configurable layers; higher refines lower; alive summaries; reconciliation; L1→L3 acceptance; valid early vagueness | Trace relationships, review changes, inspect actual criterion layers in addition to tool link counts |
| §4.7 | `Q-` items with blocks/resolution; known conflicts warn + question; inline/level TBD census; project-selected release gates; distinct design options | Keep unresolved frontier visible; resolve with decision/clause edit in same commit; do not silently guess |
| §4.8 | Default, exploration set/interval, unit, dependencies, symmetric coupling bookkeeping with directional causal prose; constant in RTL versus variable in model; inline DSE; joint exploration; recorded closure retaining range | Parameterize models and record assumed defaults; when chosen, edit default/range/level/status and decision together; queries are not DSE execution |
| §5.1 | Git branching/blame/baselines/review; clause log across moves; clause/edge/TBD/coverage changelog; retain superseded clauses | Use exact snapshots; keep old IDs/records; compare coverage separately where current diff lacks its explicit delta |
| §5.2 | Context, decision, rejected alternatives, source/session/date, affected clauses; loss-aware prompt distillation; design-intent change ends as edit/decision (usually both) in same commit | Compile feedback rather than leave new authority only in chat; retain optional raw cold archives when needed |
| §5.3 | Area ownership, generated IDs, merge CI, related refinement review even after clean text merge | Structural checks plus deliberate review; preserve Git's multiple parents and normative reasoning |
| §6.1 | Import only needed projection; exact edition/section `origin`; verbatim/paraphrase/interpretation provenance; demand-driven reference surface; dependency queries on standard revisions | Keep local projection IDs and original pointers; do not claim an unavailable source was read |
| §6.2 | Extract PDF text/tables/figures/assets; segment/classify; restate with metadata and diagrams/prose/code; independent/human audit, prioritizing paraphrase/interpretation; licensing judgment | Retain all four steps even without `ndf ingest`; perform authorized work with available tools and keep actual audit results |
| §7 item 1 | Human charter/L0/L1 bootstrap and demand-driven projection | `init` for a new root; do not overwrite an existing system spec |
| §7 item 2 | Baseline + ID work order; relevant subtree and graph neighborhood for precise retrieval | Record commit/tag; read connected context rather than arbitrary prompt fragments |
| §7 item 3 | Outputs/tests/corrections compiled into clause/refinement/decision/question commits | Close each design cycle with better-informed governing artifacts |
| §7 item 4 | PICS-like verif checklist; eventual must-L1 verification links; failures cite IDs; ambiguity becomes Q | Coverage + actual acceptance/model execution; links alone are not proof |
| §7 item 5 | RTL/physical/software work cites IDs in commits/reviews | Preserve requirement→implementation and reverse provenance |
| §7 item 6 | HTML/PDF book, resolved refs/backlinks, trace matrices and per-baseline changelogs | Generated view from canonical files; distinguish rendering from external publication |
| §7 roles | Humans/agents both read/propose; humans hold normative approval authority, agents cross-check | Use the existing authorized review process, without inventing extra approval gates |
| §8 | Every original command/runner purpose: new-id, check, trace, log, diff, coverage, deps, options, export, publish, ingest, models runner | Complete support table in [tool guide](ndf-tool.md); preserve unavailable publish/ingest purposes as manual/other-tool workflows |
| §9 items 1–7 | Unproven consistency, lossy distillation, decay, granularity judgment, diagram difficulty, refinement gap, adoption/network effects | Do not overclaim structural lint or model evidence; explicitly account for remaining limitations |
| §10 phases 1–5 | Format/schema/grammar freeze and NDF dogfood; minimal tools/CI; overlapping bounded real-design pilot; ingestion/audit cost; retrospective/reproducibility from final spec | Roadmap for adoption/tool work, not a claim phases happened or an instruction to implement all tools during ordinary spec edits |
| §11 criteria 1–6 | Canonical bible, provenance, baseline-based agents, legible evolution, trending visible incompleteness, modest spec cost | Judge actual adoption evidence; cut rigor if maintenance rivals design work |
| Appendix A | Entire informal grammar, all metadata keys, raw references, normative code, TBD/DSE/rationale notation | Original retained verbatim; tool extensions and draft inconsistencies are explicitly separate |
| Appendix B | Complete forwarding L0→L3 micro-example, retained vague intent, honest static-entry hole, golden vectors and trace/coverage | Consult for refinement; illustrative IDs/model paths must be made real in live specs |
| Appendix C.1–C.5 | Full stopwatch tree/manifest, scope/non-goals/definitions, raw asynchronous pins, debounce/reset/startstop/count/tick/BCD contracts, clock constraint | Preserve the complete worked example; do not infer every project needs these domain decisions |
| Appendix C.6–C.9 | Executable event model, randomized/directed/invariant criteria, deliberate debounce verification gap, decision superseding a prompt, Q candidate, illustrative trace/coverage payoff | Read actual code and criteria; keep model abstraction limits, gaps and provenance visible; never present sample terminal text as executed evidence |

## Draft ambiguities: retain, do not silently rewrite

The bundled originals intentionally retain their exact draft text, including
incomplete examples and tensions. Apply the method without making those quirks
invisible:

- §4.6 points at §2.4, which is not present. Imperfection is discussed in §2.2
  item 4 and §4.7. Do not invent the missing section.
- §4.6 describes contradiction flags strongly, while §9.6 explicitly says
  refinement is not verified and semantic lint is future work. Current tooling
  flags changed related pairs; agent/human review handles meaning.
- Appendix A is informal: its numeric ID grammar and key/kind lists do not fully
  express every decision/question/provenance example. Keep the full examples and
  use explicit tool compatibility notes when creating executable live specs.
- Some source examples omit metadata, carry dangling illustrative references,
  nest Markdown fences for exposition, or present proposed terminal output as if
  observed. They are teaching examples, not automatically checked evidence.
- The exact threshold between editing an existing identity and superseding it
  is not formally specified. Preserve identity/history deliberately, record the
  decision, and follow project conventions rather than inventing a universal rule.

The preservation guarantee is complete verbatim text plus explicit operating
routes. It is not a claim that the CLI implements every proposed check or that
this map resolves every editorial ambiguity in the draft.
