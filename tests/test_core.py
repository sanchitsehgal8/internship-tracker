from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from internship_tracker.core import (
    AlertService,
    PipelineRunner,
    SQLiteStore,
    TrackerConfig,
    build_dedupe_key,
    classify_eligibility,
    extract_compensation_text,
    normalize_job,
    RawPosting,
)
from internship_tracker.seed_data import CompanySeed


class CoreTests(unittest.TestCase):
    def test_compensation_extraction(self) -> None:
        text = "Salary $220K - $330K and bonus £12K"
        extracted = extract_compensation_text(text)
        self.assertIn("$220K - $330K", extracted)

    def test_eligibility_detects_internships(self) -> None:
        decision = classify_eligibility("Machine Learning Engineer Intern", "Intern", "")
        self.assertEqual(decision.label, "likely_eligible")
        self.assertGreater(decision.confidence, 0.8)

    def test_eligibility_rejects_full_time_roles(self) -> None:
        decision = classify_eligibility("Senior Backend Engineer", "Full-time", "")
        self.assertEqual(decision.label, "not_eligible")

    def test_dedupe_key_changes_when_fields_change(self) -> None:
        seed = CompanySeed("Demo", "greenhouse", "demo", "https://example.com")
        raw_a = RawPosting(seed, "1", "Intern", "Remote", "Intern", "Remote", "https://example.com/a", "https://example.com/a", "desc", "", "", {"id": 1})
        raw_b = RawPosting(seed, "1", "Intern", "New York", "Intern", "Remote", "https://example.com/a", "https://example.com/a", "desc", "", "", {"id": 1})
        self.assertNotEqual(build_dedupe_key(raw_a), build_dedupe_key(raw_b))

    def test_normalize_job_sets_internship_flag(self) -> None:
        seed = CompanySeed("Demo", "greenhouse", "demo", "https://example.com")
        raw = RawPosting(seed, "1", "Data Science Intern", "Remote", "Intern", "Remote", "https://example.com/a", "https://example.com/a", "Summer internship", "$1000", "2026-01-01", {"id": 1})
        job = normalize_job(raw)
        self.assertTrue(job.is_internship)
        self.assertEqual(job.eligibility_label, "likely_eligible")

    def test_store_and_alert_outbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            db_path = tmp / "tracker.sqlite3"
            outbox = tmp / "outbox"
            config = TrackerConfig(db_path=db_path, outbox_dir=outbox, alert_to_email="a@example.com", alert_from_email="b@example.com")
            store = SQLiteStore(db_path)
            store.initialize()
            seed = CompanySeed("Demo", "greenhouse", "demo", "https://example.com")
            store.record_company_check(seed, "ok", 1)
            raw = RawPosting(seed, "1", "Data Science Intern", "Remote", "Intern", "Remote", "https://example.com/a", "https://example.com/a", "Summer internship", "$1000", "2026-01-01", {"id": 1})
            job = normalize_job(raw)
            job_id, created, _ = store.upsert_job(job)
            self.assertTrue(created)
            alert = AlertService(config)
            row = store.connection.execute(
                "SELECT jobs.*, companies.company_name FROM jobs JOIN companies USING(company_key) WHERE jobs.id = ?",
                (job_id,),
            ).fetchone()
            subject, body_text, body_html = alert.build_message(row)
            email_id = store.queue_email(job_id, config.alert_to_email, config.alert_from_email, subject, body_text, body_html)
            self.assertGreater(email_id, 0)
            paths = alert.send_pending(store)
            self.assertEqual(len(paths), 1)
            self.assertTrue(paths[0].exists())
            stats = store.stats()
            self.assertEqual(stats["jobs"], 1)


if __name__ == "__main__":
    unittest.main()
