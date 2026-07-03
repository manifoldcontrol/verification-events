"""VerificationEvent: an atomic, hashed, replayable record of a verification act.

Schema: verification-event-v1 (see SPEC.md - the spec is normative, this file
is the reference implementation).

Design rules the schema enforces:
- An event never confers standing and never grants identity; it records that a
  check happened, what it judged, and what it touched.
- Event identity is a content hash over the fields that define the *act*
  (target, kind, outcome, typed failure, verifier incl. version, inputs,
  outputs, grounding). Volatile fields (timestamp, run id, parent links,
  credit) are excluded, so re-emitting the identical act dedups.
- The verifier dict MUST carry a "version" (toolchain/model/ruleset version):
  the same check under a different toolchain is a DIFFERENT act. make()
  raises ValueError otherwise - this is spec conformance, not pedantry.
"""
from __future__ import annotations
import hashlib, json, time
from dataclasses import dataclass, field, asdict

SCHEMA = "verification-event-v1"

_HASH_KEYS = ("target_type", "target_id", "event_kind", "outcome",
              "typed_failure", "verifier", "inputs", "outputs", "grounding")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LeafProfile:
    """Describes a reality-contacting leaf (the thing that makes a check
    grounded rather than social). Supplied by the integrating system."""
    leaf_type: str                      # e.g. "Lean_kernel", "pytest", "sensor"
    axiom_consts: frozenset = frozenset()
    defect_estimate: float | None = None


LEAN_KERNEL = LeafProfile(
    leaf_type="Lean_kernel",
    axiom_consts=frozenset({"Classical.choice", "propext", "Quot.sound", "sorryAx"}),
    defect_estimate=1e-6,
)


def grounding(leaf: LeafProfile | None, accepted: bool,
              uses_leakage: bool = False, surface=()) -> dict:
    """Build the grounding block. A check contacts reality iff a leaf profile
    is present, the outcome is an accept, and no leakage (sorry/mock/stub)
    was reported."""
    if leaf is None:
        return {"reality_contacting_leaf": False, "leaf_type": "none"}
    is_leaf = accepted and not uses_leakage
    return {
        "reality_contacting_leaf": is_leaf,
        "leaf_type": leaf.leaf_type if is_leaf else "none",
        "leaf_defect_estimate": leaf.defect_estimate if is_leaf else None,
        "uses_leakage": uses_leakage,
        "axioms_used": sorted(set(surface) & set(leaf.axiom_consts)),
    }


@dataclass
class VerificationEvent:
    event_id: str
    event_kind: str
    target_id: str | None
    target_type: str = "claim"
    schema: str = SCHEMA
    outcome: str | None = None
    typed_failure: str = "none"
    actor: dict = field(default_factory=dict)
    verifier: dict = field(default_factory=dict)
    inputs: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    adequacy: dict = field(default_factory=lambda: {"adequacy_state": "unknown"})
    grounding: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    credit: dict = field(default_factory=lambda: {"reward_status": "unpaid",
                                                  "contribution_type": None})
    integrity: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "VerificationEvent":
        return VerificationEvent(**d)


def make(event_kind, target_id, outcome=None, typed_failure="none",
         actor=None, verifier=None, inputs=None, outputs=None,
         adequacy=None, grounding=None, contribution_type=None,
         run_id=None, parent_event_ids=None, target_type="claim",
         component_id=None) -> VerificationEvent:
    """Create a content-addressed event. See SPEC.md for field semantics.

    Raises ValueError when a non-empty verifier dict lacks "version" - event
    identity must distinguish toolchain versions (a re-check after a version
    bump is a new act, and must not dedup away).
    """
    verifier = dict(verifier or {})
    if verifier and "version" not in verifier:
        raise ValueError(
            'verifier dict must include a "version" key (toolchain/model/'
            "ruleset version); event identity depends on it")
    body = {
        "target_type": target_type, "target_id": target_id,
        "event_kind": event_kind, "outcome": outcome,
        "typed_failure": typed_failure or "none",
        "verifier": verifier, "inputs": inputs or {},
        "outputs": outputs or {}, "grounding": grounding or {},
    }
    h = _sha(json.dumps({k: body[k] for k in _HASH_KEYS}, sort_keys=True,
                        default=str))
    return VerificationEvent(
        event_id="ve_" + h[:12],
        event_kind=event_kind, target_id=target_id, target_type=target_type,
        outcome=outcome, typed_failure=typed_failure or "none",
        actor=actor or {}, verifier=verifier,
        inputs=inputs or {}, outputs=outputs or {},
        adequacy=adequacy or {"adequacy_state": "unknown"},
        grounding=grounding or {},
        provenance={"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "run_id": run_id,
                    "parent_event_ids": list(parent_event_ids or [])},
        credit={"reward_status": "unpaid", "contribution_type": contribution_type},
        integrity={"normalized_hash": "sha256:" + h[:32], "version": "v1",
                   "component": component_id},
    )


# --- generic act factories (domain-neutral; rename freely via event_kind) ---

def check_event(target_id, outcome, verifier, typed_failure="none",
                attempt=None, artifact=None, grounding_block=None,
                run_id=None, parent=None, **kw) -> VerificationEvent:
    """A verifier judged a candidate (accept / reject / verifier_error)."""
    inputs = {"attempt": attempt}
    if artifact is not None:
        inputs["input_artifact_hash"] = "sha256:" + _sha(artifact)[:16]
    return make("check", target_id, outcome=outcome, typed_failure=typed_failure,
                actor={"actor_role": "verifier"},
                verifier=verifier, inputs=inputs,
                grounding=grounding_block or {}, run_id=run_id,
                parent_event_ids=[parent] if parent else None, **kw)


def repair_event(target_id, detail, typed_failure, contribution_type,
                 run_id=None, parent=None, **kw) -> VerificationEvent:
    """A typed repair was applied; outcome is always needs_reverification."""
    return make("repair", target_id, outcome="needs_reverification",
                typed_failure=typed_failure,
                actor={"actor_role": "maintainer"},
                inputs=dict(detail), contribution_type=contribution_type,
                run_id=run_id, parent_event_ids=[parent] if parent else None, **kw)


def gate_decision_event(target_id, standing, reason, run_id=None, parent=None,
                        **kw) -> VerificationEvent:
    """Records a governor's decision. It does NOT confer the standing."""
    return make("gate_decision", target_id, outcome=standing,
                actor={"actor_role": "governor"},
                inputs={"reason": reason}, run_id=run_id,
                parent_event_ids=[parent] if parent else None, **kw)


def adequacy_audit_event(target_id, adequacy_state, auditor_id=None,
                         notes=None, run_id=None, parent=None, **kw):
    """Human/LLM audit: does the formal claim match the intended one?"""
    return make("adequacy_audit", target_id,
                outcome=("mismatch" if adequacy_state == "mismatch" else "partial"),
                typed_failure=("adequacy" if adequacy_state == "mismatch" else "none"),
                actor={"actor_role": "auditor", "actor_id": auditor_id},
                adequacy={"adequacy_state": adequacy_state,
                          "adequacy_auditor_id": auditor_id,
                          "adequacy_notes_hash":
                          ("sha256:" + _sha(notes)[:16]) if notes else None},
                contribution_type="adequacy_audit",
                run_id=run_id, parent_event_ids=[parent] if parent else None, **kw)


def counterexample_event(target_id, artifact_hash=None, valid=True,
                         actor_id=None, parent=None, **kw):
    return make("counterexample", target_id,
                outcome=("counterexample" if valid else "reject"),
                actor={"actor_role": "challenger", "actor_id": actor_id},
                outputs={"counterexample_hash": artifact_hash},
                contribution_type="counterexample",
                parent_event_ids=[parent] if parent else None, **kw)


def revocation_event(target_id, reason, parent=None, **kw):
    return make("revocation_check", target_id, outcome="revoked",
                actor={"actor_role": "maintainer"},
                inputs={"reason": reason}, contribution_type="revocation",
                parent_event_ids=[parent] if parent else None, **kw)
