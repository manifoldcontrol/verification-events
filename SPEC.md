# verification-event-v1

status: v1, normative. the reference implementation is `src/verification_events/`; where they disagree, this document wins and the code has a bug.

## purpose

a verification event is an atomic, hashed, replayable record of one verification act: a check, a repair, a gate decision, an adequacy audit, a counterexample, a revocation. the event layer is the provenance substrate of a verification system. two rules define its place:

1. an event never confers standing. whether a claim is accepted into a corpus is a governor's decision, recorded as (not constituted by) a `gate_decision` event.
2. an event never grants identity. names and versions belong to a registry; events reference `target_id`s, they do not define them.

credit follows provenance; standing follows verification; identity follows registration. the event layer is only the first of the three.

## event identity (the hash contract)

`event_id = "ve_" + sha256(canonical_json(hash_body))[:12]`, where `hash_body` is exactly these fields, json-serialized with sorted keys:

| hashed | field | notes |
|---|---|---|
| yes | `target_type` | `"claim"` default; domain-specific types allowed |
| yes | `target_id` | registry id or stable name of the thing checked |
| yes | `event_kind` | `check`, `repair`, `gate_decision`, `adequacy_audit`, `counterexample`, `revocation_check`, or domain-defined |
| yes | `outcome` | act-specific verdict (see below) |
| yes | `typed_failure` | failure vocabulary is domain-pluggable; `"none"` when absent |
| yes | `verifier` | must include `version` (see below) |
| yes | `inputs` | what was judged (artifact hashes, attempt index, ...) |
| yes | `outputs` | what the act produced (proof-term hash, counterexample hash, ...) |
| yes | `grounding` | the reality-contact block (see below) |
| no | `actor` | who performed the act (role, id) |
| no | `adequacy` | adequacy state block |
| no | `provenance` | timestamp, `run_id`, `parent_event_ids` |
| no | `credit` | advisory; a derived view, never a standing input |
| no | `integrity` | normalized hash, schema version, component id |

consequences:

- dedup: re-emitting a byte-identical act yields the same `event_id`; logs skip it. raw event counts cannot be inflated by repetition. corollary: re-running an identical check under an identical verifier is not representable as a new event, by design. if the re-check matters, something material changed (version, inputs), and then it hashes differently.
- verifier version is identity. `verifier` must carry a `version` key (toolchain / model / ruleset version). the same check under a bumped toolchain is a different act, which is exactly the event a version-bump re-verification campaign needs to record. implementations must reject a non-empty verifier dict without `version` (the reference `make()` raises `ValueError`).
- volatile fields are free. timestamps, run ids, and parent links can be attached or rewritten without changing identity. parent links express trajectory (attempt chains); identity expresses the act.

## blocks

`outcome` vocabulary per `event_kind`: `check` yields `accept | reject | verifier_error | timeout`. `verifier_error` means the checking apparatus failed (no judgment was rendered) and must be excluded from claim statistics. `repair` yields `needs_reverification` (a repair never certifies itself). `gate_decision` carries the governor's standing vocabulary. `adequacy_audit` yields `mismatch | partial`. `counterexample` yields `counterexample | reject`. `revocation_check` yields `revoked`.

`grounding` records whether the act contacted a reality-contacting leaf: a checker whose verdict does not depend on anyone's opinion (a proof kernel, a test suite against a fixed harness, a sensor). fields: `reality_contacting_leaf` (bool), `leaf_type`, `leaf_defect_estimate` (honest probability the leaf itself is wrong), `uses_leakage` (the artifact smuggled in an escape hatch: `sorry`, a mocked assertion, a stubbed sensor), `axioms_used` (surface intersected with the leaf's axiom set). a leaf claim requires an accepted outcome and no leakage. leaf profiles are supplied by the integrating system (`LeafProfile`); this spec ships `LEAN_KERNEL` as an example, not a default.

`typed_failure` is a single token from the integrator's failure typology. the typology itself is out of scope for v1 (one example is the bcv axis set: language / hypothesis / cover / composition / transport / reuse / search); the spec only requires that the token be stable, since it is hashed.

`credit` is advisory. `reward_status` and `contribution_type` exist so a credit layer can be derived from the event graph (downstream-weighted, revocation-aware). a conforming system never reads credit when deciding standing.

## log format

jsonl, append-only, one event per line, deduplicated by `event_id` at append time. no rewriting: revocation is a new event (`revocation_check`, parent-linked), never a deletion.

## versioning

the schema string (`verification-event-v1`) and the integrity block's `version` bump together. any change to the hash body set, the canonical serialization, or required keys is breaking and bumps the major version; new optional non-hashed fields are non-breaking. v0 (unversioned verifier hash, lean-coupled grounding) was internal to a predecessor project and is superseded.
