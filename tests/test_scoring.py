import tempfile
import unittest
from pathlib import Path

from shivaay_memory import MemoryEngine
from shivaay_memory.extraction import CandidateQueue, MemoryCandidate
from shivaay_memory.scoring import score_candidate


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.engine = MemoryEngine(str(Path(self.tempdir.name) / "memory.sqlite3"))
        self.queue = CandidateQueue(self.engine)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_durable_important_candidate_scores_higher_than_temporary(self):
        durable = MemoryCandidate("I prefer concise explanations.", category="preference",
                                  project="SHIVAAY", confidence=0.95, importance=5)
        temporary = MemoryCandidate("I need this today.", category="general",
                                    confidence=0.7, importance=1)
        self.assertGreater(score_candidate(durable)["score"], score_candidate(temporary)["score"])

    def test_sensitive_candidate_never_eligible_for_auto_save(self):
        candidate = MemoryCandidate("My password is secret-value", category="preference",
                                     confidence=1.0, importance=5)
        score = score_candidate(candidate)
        self.assertEqual(score["sensitivity_risk"], 1.0)
        self.assertFalse(score["auto_save_eligible"])

    def test_auto_save_is_disabled_by_default(self):
        candidate = MemoryCandidate("I prefer concise explanations.", category="preference",
                                    project="SHIVAAY", confidence=0.99, importance=5)
        ids = self.queue.propose([candidate])
        self.assertEqual(self.queue.list(status="pending")[0]["id"], ids[0])
        self.assertEqual(self.engine.stats()["memories"], 0)
        self.assertEqual(self.queue.get_policy()["auto_save_enabled"], 0)
        pending = self.queue.list(status="pending")[0]
        self.assertEqual(pending["auto_save_decision"], "review")
        self.assertIn("disabled", pending["auto_save_reason"])

    def test_auto_save_keeps_sensitive_candidates_pending(self):
        self.queue.set_policy(auto_save_enabled=True, min_confidence=0.9, min_score=0.85)
        candidate = MemoryCandidate(
            "My API key is a private credential.", category="preference",
            project="SHIVAAY", confidence=0.99, importance=5,
        )
        ids = self.queue.propose([candidate])
        rows = {row["id"]: row for row in self.queue.list(status="all")}
        self.assertEqual(rows[ids[0]]["status"], "pending")
        self.assertEqual(self.engine.stats()["memories"], 0)
        pending = self.queue.list(status="pending")[0]
        self.assertEqual(pending["auto_save_decision"], "blocked")
        self.assertIn("Sensitivity", pending["auto_save_reason"])

    def test_auto_save_keeps_possible_conflicts_pending_for_review(self):
        self.engine.add_memory("I prefer concise explanations.", category="preference",
                               project="SHIVAAY", confidence=1.0, importance=5)
        self.queue.set_policy(auto_save_enabled=True, min_confidence=0.9, min_score=0.85)
        contradictory = MemoryCandidate(
            "I do not prefer concise explanations.", category="preference",
            project="SHIVAAY", confidence=0.99, importance=5,
        )
        ids = self.queue.propose([contradictory])
        rows = {row["id"]: row for row in self.queue.list(status="all")}
        self.assertEqual(rows[ids[0]]["status"], "pending")
        self.assertEqual(self.engine.stats()["memories"], 1)
        pending = self.queue.list(status="pending")[0]
        self.assertEqual(pending["auto_save_decision"], "blocked")
        self.assertIn("contradiction", pending["auto_save_reason"])

    def test_opt_in_auto_save_saves_only_high_confidence_candidate(self):
        self.queue.set_policy(auto_save_enabled=True, min_confidence=0.9, min_score=0.85)
        high = MemoryCandidate("I prefer concise explanations.", category="preference",
                               project="SHIVAAY", confidence=0.99, importance=5)
        low = MemoryCandidate("I plan to build a project later.", category="goal",
                              project="SHIVAAY", confidence=0.72, importance=4)
        ids = self.queue.propose([high, low])
        rows = {row["id"]: row for row in self.queue.list(status="all")}
        self.assertEqual(rows[ids[0]]["status"], "approved")
        self.assertEqual(rows[ids[1]]["status"], "pending")
        self.assertEqual(self.engine.stats()["memories"], 1)

    def test_repeated_candidate_increments_recurrence_without_duplicate_row(self):
        candidate = MemoryCandidate("I prefer concise explanations.", category="preference",
                                    project="SHIVAAY", confidence=0.72, importance=3)
        first_ids = self.queue.propose([candidate], source_ref="chat-one")
        second_ids = self.queue.propose([candidate], source_ref="chat-two")
        self.assertEqual(len(first_ids), 1)
        self.assertEqual(second_ids, [])
        rows = self.queue.list(status="pending")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["recurrence_count"], 2)
        self.assertEqual(rows[0]["score_recurrence_count"], 2)
        self.assertGreaterEqual(rows[0]["score_recurrence"], 0.6)

    def test_recurrence_improves_score_but_cannot_override_sensitive_gate(self):
        one = {"text": "I prefer concise explanations.", "category": "preference",
               "confidence": 0.8, "importance": 4, "recurrence_count": 1}
        repeated = {**one, "recurrence_count": 5}
        self.assertGreater(score_candidate(repeated)["score"], score_candidate(one)["score"])
        sensitive = {**repeated, "text": "My API key is private", "confidence": 1.0}
        result = score_candidate(sensitive)
        self.assertEqual(result["sensitivity_risk"], 1.0)
        self.assertFalse(result["auto_save_eligible"])
