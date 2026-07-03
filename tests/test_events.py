"""Spec-conformance tests for verification-event-v1 (plain asserts; run with
`python tests/test_events.py` or pytest)."""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from verification_events import (VerificationEvent, EventLog, LeafProfile,
                                 LEAN_KERNEL, grounding, make, check_event,
                                 revocation_event)

V = {"verifier_type": "Lean", "version": "4.30.0"}


def test_content_hash_is_stable_and_volatile_fields_are_excluded():
    a = make("check", "thm_a", outcome="accept", verifier=V, run_id="run_1")
    b = make("check", "thm_a", outcome="accept", verifier=V, run_id="run_2",
             parent_event_ids=["ve_ffffffffffff"])
    assert a.event_id == b.event_id            # same act, different run/parents
    assert a.provenance["run_id"] != b.provenance["run_id"]


def test_verifier_version_changes_identity():
    a = make("check", "thm_a", outcome="accept", verifier=V)
    b = make("check", "thm_a", outcome="accept",
             verifier={"verifier_type": "Lean", "version": "4.31.0"})
    assert a.event_id != b.event_id            # version bump = new act


def test_verifier_without_version_is_rejected():
    try:
        make("check", "thm_a", outcome="accept",
             verifier={"verifier_type": "Lean"})
    except ValueError as e:
        assert "version" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_outcome_and_kind_change_identity():
    a = make("check", "t", outcome="accept", verifier=V)
    b = make("check", "t", outcome="reject", verifier=V)
    c = make("recheck", "t", outcome="accept", verifier=V)
    assert len({a.event_id, b.event_id, c.event_id}) == 3


def test_grounding_leaf_requires_accept_and_no_leakage():
    g_ok = grounding(LEAN_KERNEL, accepted=True, uses_leakage=False,
                     surface=["Nat", "Classical.choice"])
    assert g_ok["reality_contacting_leaf"] is True
    assert g_ok["axioms_used"] == ["Classical.choice"]
    g_sorry = grounding(LEAN_KERNEL, accepted=True, uses_leakage=True)
    assert g_sorry["reality_contacting_leaf"] is False
    g_none = grounding(None, accepted=True)
    assert g_none == {"reality_contacting_leaf": False, "leaf_type": "none"}


def test_custom_leaf_profile_is_domain_neutral():
    pytest_leaf = LeafProfile(leaf_type="pytest", defect_estimate=1e-3)
    g = grounding(pytest_leaf, accepted=True)
    assert g["leaf_type"] == "pytest" and g["leaf_defect_estimate"] == 1e-3


def test_log_dedups_identical_acts_and_roundtrips():
    with tempfile.TemporaryDirectory() as d:
        log = EventLog(path=os.path.join(d, "events.jsonl"))
        e1 = make("check", "t", outcome="accept", verifier=V, run_id="r1")
        e2 = make("check", "t", outcome="accept", verifier=V, run_id="r2")
        e3 = make("check", "t", outcome="reject", verifier=V, run_id="r2")
        assert log.append([e1, e2, e3]) == 2   # e2 dedups against e1
        loaded = log.load_all()
        assert len(loaded) == 2
        assert isinstance(loaded[0], VerificationEvent)
        assert len(log.by_target("t")) == 2


def test_parent_chain_and_factories():
    c = check_event("t", "reject", V, typed_failure="language",
                    attempt=0, artifact="theorem t : X := by simp")
    r = revocation_event("t", "vacuous statement", parent=c.event_id)
    assert r.provenance["parent_event_ids"] == [c.event_id]
    assert c.inputs["input_artifact_hash"].startswith("sha256:")
    assert r.outcome == "revoked" and r.credit["contribution_type"] == "revocation"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"PASS  {fn.__name__}")
    print(f"{len(fns)} passed")
