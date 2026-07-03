# verification-events

A tiny, dependency-free schema + reference implementation for **verification
provenance**: every verification act — checks, repairs, gate decisions,
adequacy audits, counterexamples, revocations — becomes an atomic,
content-hashed, replayable event in an append-only log.

**[SPEC.md](SPEC.md) is the product.** The Python here (~300 lines, stdlib
only) is the reference implementation.

## Why

Systems that generate candidate claims faster than anyone can check them
(LLM proof pipelines, agentic codebases, auto-formalization) need more than
a green checkmark: they need an audit trail of *what was checked, by which
verifier at which version, what failed and how it was typed, what was
repaired, and what got revoked*. The schema's three firewalls:

- events record standing decisions but never confer standing;
- events reference identities but never mint them;
- credit is derived from events but never feeds back into standing.

## Use

```python
from verification_events import make, check_event, EventLog, LeafProfile, grounding

V = {"verifier_type": "Lean", "version": "4.30.0"}   # version is REQUIRED

ev = check_event("my_thm", "accept", V, attempt=0,
                 artifact="theorem my_thm : ... := by simp",
                 grounding_block=grounding(LeafProfile("Lean_kernel"), accepted=True))
log = EventLog("events/events.jsonl")
log.append(ev)          # identical re-emission later: dedups, returns 0
```

Identity is a content hash: same act → same id → deduped; bump the verifier
version and the same check becomes a new act (that's the point — see the
hash contract in SPEC.md).

## Tests

`python tests/test_events.py` (no pytest needed; pytest also works).

## Family

Designed as the provenance leg of a three-part verification infrastructure:
[csr-seed](https://github.com/manifoldcontrol/csr-seed) (identity: documents define, a registry identifies)
and [lean-introspect](https://github.com/manifoldcontrol/lean-introspect) (a Lean proof-term leakage report —
one source of `grounding` evidence). Each stands alone.
