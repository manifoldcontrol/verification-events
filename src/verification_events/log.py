"""EventLog: append-only, content-deduplicated JSONL catalogue.

Dedup is by event_id (content hash): re-emitting an identical act is a no-op,
so raw event count cannot be inflated by repetition. Known v1 limitation: the
seen-set is re-read per append call (O(n) per call); batch appends amortize it.
"""
from __future__ import annotations
import json, os
from .event import VerificationEvent


class EventLog:
    def __init__(self, path: str = "events/events.jsonl"):
        self.path = path

    def _seen(self) -> set:
        if not os.path.exists(self.path):
            return set()
        ids = set()
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    ids.add(json.loads(line)["event_id"])
        return ids

    def append(self, events) -> int:
        """Append new events, skipping ids already logged. Returns count written."""
        if isinstance(events, VerificationEvent):
            events = [events]
        seen = self._seen()
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        written = 0
        with open(self.path, "a", encoding="utf-8") as f:
            for ev in events:
                if ev.event_id in seen:
                    continue
                f.write(json.dumps(ev.to_dict()) + "\n")
                seen.add(ev.event_id)
                written += 1
        return written

    def load_all(self) -> list:
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(VerificationEvent.from_dict(json.loads(line)))
        return out

    def by_run(self, run_id: str) -> list:
        return [e for e in self.load_all()
                if e.provenance.get("run_id") == run_id]

    def by_target(self, target_id: str) -> list:
        return [e for e in self.load_all() if e.target_id == target_id]
