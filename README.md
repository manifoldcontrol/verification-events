# verification-events

a small schema plus reference implementation for verification provenance. every verification act (a check, a repair, a gate decision, an adequacy audit, a counterexample, a revocation) becomes a content-hashed event in an append-only log.

the schema lives in [SPEC.md](SPEC.md). the python here (~300 lines, stdlib only) implements it.

## why

systems that generate candidate claims faster than anyone can check them need an audit trail: what was checked, by which verifier at which version, what failed and how it was typed, what was repaired, what got revoked. three rules hold throughout:

- events record standing decisions but never confer standing
- events reference identities but never mint them
- credit is derived from events but never feeds back into standing

## use

```python
from verification_events import make, check_event, EventLog, LeafProfile, grounding

V = {"verifier_type": "Lean", "version": "4.30.0"}   # version is required

ev = check_event("my_thm", "accept", V, attempt=0,
                 artifact="theorem my_thm : ... := by simp",
                 grounding_block=grounding(LeafProfile("Lean_kernel"), accepted=True))
log = EventLog("events/events.jsonl")
log.append(ev)   # identical re-emission later dedups, returns 0
```

identity is a content hash: the same act gets the same id and dedups. bump the verifier version and the same check becomes a new act. the hash contract is in SPEC.md.

## tests

`python tests/test_events.py` (pytest also works)

## related

[csr-seed](https://github.com/manifoldcontrol/csr-seed) (identity: documents define, a registry identifies) and [lean-introspect](https://github.com/manifoldcontrol/lean-introspect) (a lean proof-term leakage report, one source of grounding evidence). each is usable on its own.
