# verification-event-v1 — specification

**Status:** v1, normative. The reference implementation is
`src/verification_events/`; where they disagree, this document wins and the
code has a bug.

## Purpose

A **VerificationEvent** is an atomic, hashed, replayable record of one
verification act: a check, a repair, a gate decision, an adequacy audit, a
counterexample, a revocation. The event layer is the provenance substrate of
a verification system. Two rules define its place:

1. **An event never confers standing.** Whether a claim is accepted into a
   corpus is a governor's decision, recorded as (not constituted by) a
   `gate_decision` event.
2. **An event never grants identity.** Names and versions belong to a
   registry; events reference `target_id`s, they do not define them.

Payment/credit follows provenance; standing follows verification; identity
follows registration. The event layer is only the first of the three.

## Event identity (the hash contract)

`event_id = "ve_" + sha256(canonical_json(hash_body))[:12]`, where
`hash_body` is exactly these fields, JSON-serialized with sorted keys:

| hashed | field | notes |
|---|---|---|
| yes | `target_type` | `"claim"` default; domain-specific types allowed |
| yes | `target_id` | registry id or stable name of the thing checked |
| yes | `event_kind` | `check`, `repair`, `gate_decision`, `adequacy_audit`, `counterexample`, `revocation_check`, or domain-defined |
| yes | `outcome` | act-specific verdict (see below) |
| yes | `typed_failure` | failure vocabulary is domain-pluggable; `"none"` when absent |
| yes | `verifier` | **MUST include `version`** (see below) |
| yes | `inputs` | what was judged (artifact hashes, attempt index, ...) |
| yes | `outputs` | what the act produced (proof-term hash, counterexample hash, ...) |
| yes | `grounding` | the reality-contact block (see below) |
| no | `actor` | who performed the act (role, id) |
| no | `adequacy` | adequacy state block |
| no | `provenance` | timestamp, `run_id`, `parent_event_ids` |
| no | `credit` | advisory; a derived view, never a standing input |
| no | `integrity` | normalized hash, schema version, component id |

**Consequences (these are the contract):**

- **Dedup:** re-emitting a byte-identical act yields the same `event_id`;
  logs skip it. Raw event counts cannot be inflated by repetition
  (anti-gaming). Corollary: re-running an identical check under an identical
  verifier is *not representable* as a new event — by design. If the
  re-check matters, something material changed (version, inputs), and then
  it hashes differently.
- **Verifier version is identity.** `verifier` MUST carry a `version` key
  (toolchain / model / ruleset version). The same check under a bumped
  toolchain is a *different act* — exactly the event a version-bump
  re-verification campaign needs to record. Implementations MUST reject a
  non-empty verifier dict without `version` (the reference `make()` raises
  `ValueError`).
- **Volatile fields are free.** Timestamps, run ids, and parent links can be
  attached or rewritten without changing identity. Parent links express
  trajectory (attempt chains); identity expresses the act.

## Blocks

**`outcome` vocabulary** (per `event_kind`): `check` → `accept | reject |
verifier_error | timeout` — `verifier_error` means the *courtroom* failed
(no judgment was rendered) and MUST be excluded from claim statistics;
`repair` → `needs_reverification` (a repair never certifies itself);
`gate_decision` → the governor's standing vocabulary; `adequacy_audit` →
`mismatch | partial`; `counterexample` → `counterexample | reject`;
`revocation_check` → `revoked`.

**`grounding`** — records whether the act contacted a *reality-contacting
leaf*: a checker whose verdict does not depend on anyone's opinion (a proof
kernel, a test suite against a fixed harness, a sensor). Fields:
`reality_contacting_leaf` (bool), `leaf_type`, `leaf_defect_estimate`
(honest probability the leaf itself is wrong), `uses_leakage` (the artifact
smuggled in an escape hatch — `sorry`, a mocked assertion, a stubbed
sensor), `axioms_used` (surface ∩ the leaf's axiom set). A leaf claim
requires: accepted outcome AND no leakage. Leaf profiles are supplied by the
integrating system (`LeafProfile`); this spec ships `LEAN_KERNEL` as an
example, not a default.

**`typed_failure`** — a single token from the integrator's failure typology.
The typology itself is out of scope for v1 (one is the BCV axis set:
language / hypothesis / cover / composition / transport / reuse / search);
the spec only requires that the token be stable, since it is hashed.

**`credit`** — advisory. `reward_status` and `contribution_type` exist so a
credit layer can be *derived* from the event graph (downstream-weighted,
revocation-aware). A conforming system never reads credit when deciding
standing. This firewall is the point of the schema.

## Log format

JSONL, append-only, one event per line, deduplicated by `event_id` at append
time. No rewriting: revocation is a new event (`revocation_check`,
parent-linked), never a deletion.

## Versioning

The schema string (`verification-event-v1`) and the integrity block's
`version` bump together. Any change to the hash body set, the canonical
serialization, or required keys is **breaking** and bumps the major version;
new optional non-hashed fields are non-breaking. v0 (unversioned verifier
hash; Lean-coupled grounding) was internal to MathSolver and is superseded.
