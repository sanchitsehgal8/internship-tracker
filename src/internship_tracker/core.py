from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import smtplib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .seed_data import CompanySeed


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def safe_json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


@dataclass(slots=True)
class TrackerConfig:
    db_path: Path
    outbox_dir: Path
    alert_to_email: str
    alert_from_email: str
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = False

    @classmethod
    def from_env(cls) -> "TrackerConfig":
        project_root = Path(__file__).resolve().parents[2]
        db_path = Path(os.environ.get("INTERNSHIP_TRACKER_DB_PATH", project_root / "data" / "internship_tracker.sqlite3"))
        outbox_dir = Path(os.environ.get("INTERNSHIP_TRACKER_OUTBOX_DIR", project_root / "data" / "outbox"))
        return cls(
            db_path=db_path,
            outbox_dir=outbox_dir,
            alert_to_email=os.environ.get("INTERNSHIP_TRACKER_ALERT_TO", "alerts@localhost"),
            alert_from_email=os.environ.get("INTERNSHIP_TRACKER_ALERT_FROM", "tracker@localhost"),
            smtp_host=os.environ.get("INTERNSHIP_TRACKER_SMTP_HOST"),
            smtp_port=int(os.environ["INTERNSHIP_TRACKER_SMTP_PORT"]) if os.environ.get("INTERNSHIP_TRACKER_SMTP_PORT") else None,
            smtp_username=os.environ.get("INTERNSHIP_TRACKER_SMTP_USERNAME"),
            smtp_password=os.environ.get("INTERNSHIP_TRACKER_SMTP_PASSWORD"),
            smtp_use_tls=os.environ.get("INTERNSHIP_TRACKER_SMTP_USE_TLS", "0") == "1",
        )


@dataclass(slots=True)
class RawPosting:
    company_seed: CompanySeed
    source_posting_id: str
    title: str
    location: str
    employment_type: str
    remote_policy: str
    source_url: str
    apply_url: str
    description: str
    compensation_text: str
    released_at: str
    raw_payload: dict[str, Any]

    @property
    def source_job_key(self) -> str:
        return f"{self.company_seed.company_key}:{self.source_posting_id}"


@dataclass(slots=True)
class EligibilityDecision:
    label: str
    confidence: float
    reasons: list[str]


@dataclass(slots=True)
class CompensationEvidence:
    matched_text: str
    amount_kind: str
    source_excerpt: str


@dataclass(slots=True)
class NormalizedJob:
    company_key: str
    company_name: str
    source_type: str
    source_slug: str
    source_job_key: str
    source_posting_id: str
    title: str
    location: str
    employment_type: str
    remote_policy: str
    source_url: str
    apply_url: str
    description: str
    compensation_text: str
    released_at: str
    raw_payload_json: str
    dedupe_key: str
    is_internship: bool
    eligibility_label: str
    eligibility_confidence: float
    eligibility_reason: str


class HttpClient:
    def fetch_json(self, url: str, timeout: int = 30) -> dict[str, Any]:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 internship-tracker"})
        with urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8", "replace")
        return json.loads(payload)

    def fetch_text(self, url: str, timeout: int = 30) -> str:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 internship-tracker"})
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")


class BaseConnector:
    source_type: str

    def __init__(self, client: HttpClient | None = None) -> None:
        self.client = client or HttpClient()

    def fetch_postings(self, company_seed: CompanySeed) -> list[RawPosting]:
        raise NotImplementedError

    def _extract_embedded_json(self, html: str, marker: str) -> dict[str, Any]:
        marker_index = html.find(marker)
        if marker_index < 0:
            raise ValueError(f"marker not found: {marker}")
        start = marker_index + len(marker)
        brace_depth = 0
        end = None
        for index, char in enumerate(html[start:], start=start):
            if char == "{":
                brace_depth += 1
            elif char == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    end = index + 1
                    break
        if end is None:
            raise ValueError("could not parse embedded json")
        return json.loads(html[start:end])


class GreenhouseConnector(BaseConnector):
    source_type = "greenhouse"

    def fetch_postings(self, company_seed: CompanySeed) -> list[RawPosting]:
        payload = self.client.fetch_json(company_seed.jobs_url)
        postings: list[RawPosting] = []
        for item in payload.get("jobs", []):
            location_name = normalize_whitespace((item.get("location") or {}).get("name"))
            employment_type = normalize_whitespace(item.get("employment_type") or "")
            title = normalize_whitespace(item.get("title"))
            description = normalize_whitespace(item.get("content") or item.get("description") or "")
            source_url = normalize_whitespace(item.get("absolute_url") or company_seed.jobs_url)
            apply_url = source_url
            compensation_text = extract_compensation_text(f"{title} {description}")
            released_at = normalize_whitespace(item.get("updated_at") or item.get("first_published_at") or item.get("published_at") or "")
            postings.append(
                RawPosting(
                    company_seed=company_seed,
                    source_posting_id=str(item.get("id") or source_url),
                    title=title,
                    location=location_name,
                    employment_type=employment_type,
                    remote_policy=classify_remote_policy(item),
                    source_url=source_url,
                    apply_url=apply_url,
                    description=description,
                    compensation_text=compensation_text,
                    released_at=released_at,
                    raw_payload=item,
                )
            )
        return postings


class SmartRecruitersConnector(BaseConnector):
    source_type = "smartrecruiters"

    def fetch_postings(self, company_seed: CompanySeed) -> list[RawPosting]:
        payload = self.client.fetch_json(company_seed.jobs_url)
        postings: list[RawPosting] = []
        for item in payload.get("content", []):
            detail_url = item.get("ref") or f"https://api.smartrecruiters.com/v1/companies/{company_seed.source_slug}/postings/{item.get('id')}"
            detail = self.client.fetch_json(detail_url)
            title = normalize_whitespace(detail.get("name") or item.get("name") or "")
            location = normalize_whitespace((detail.get("location") or {}).get("fullLocation") or (item.get("location") or {}).get("fullLocation") or "")
            employment_type = normalize_whitespace((detail.get("typeOfEmployment") or {}).get("label") or (item.get("typeOfEmployment") or {}).get("label") or "")
            remote_policy = classify_remote_policy(detail)
            description = smartrecruiters_description(detail)
            source_url = normalize_whitespace(detail.get("postingUrl") or item.get("postingUrl") or detail.get("applyUrl") or "")
            apply_url = normalize_whitespace(detail.get("applyUrl") or item.get("applyUrl") or source_url)
            compensation_text = extract_compensation_text(f"{title} {description}")
            released_at = normalize_whitespace(detail.get("releasedDate") or item.get("releasedDate") or "")
            postings.append(
                RawPosting(
                    company_seed=company_seed,
                    source_posting_id=str(detail.get("id") or item.get("id") or source_url),
                    title=title,
                    location=location,
                    employment_type=employment_type,
                    remote_policy=remote_policy,
                    source_url=source_url,
                    apply_url=apply_url,
                    description=description,
                    compensation_text=compensation_text,
                    released_at=released_at,
                    raw_payload=detail,
                )
            )
        return postings


class AshbyConnector(BaseConnector):
    source_type = "ashby"

    def fetch_postings(self, company_seed: CompanySeed) -> list[RawPosting]:
        html = self.client.fetch_text(company_seed.jobs_url)
        app_data = self._extract_embedded_json(html, "window.__appData = ")
        job_board = app_data.get("jobBoard") or {}
        postings: list[RawPosting] = []
        for item in job_board.get("jobPostings") or []:
            if not item.get("isListed", True):
                continue
            posting_id = str(item.get("id") or "")
            if not posting_id:
                continue
            source_url = f"https://jobs.ashbyhq.com/{company_seed.source_slug}/{posting_id}"
            location = normalize_whitespace(item.get("locationName") or item.get("locationExternalName") or "")
            employment_type = normalize_whitespace(item.get("employmentType") or "")
            title = normalize_whitespace(item.get("title") or "")
            dept = normalize_whitespace(item.get("departmentName") or "")
            team = normalize_whitespace(item.get("teamName") or "")
            compensation = normalize_whitespace(item.get("compensationTierSummary") or "")
            description = normalize_whitespace(" ".join(part for part in [dept, team, compensation] if part))
            postings.append(
                RawPosting(
                    company_seed=company_seed,
                    source_posting_id=posting_id,
                    title=title,
                    location=location,
                    employment_type=employment_type,
                    remote_policy=classify_ashby_remote_policy(item),
                    source_url=source_url,
                    apply_url=source_url,
                    description=description,
                    compensation_text=extract_compensation_text(f"{title} {description}"),
                    released_at=normalize_whitespace(item.get("updatedAt") or item.get("publishedDate") or ""),
                    raw_payload=item,
                )
            )
        return postings


def smartrecruiters_description(detail: dict[str, Any]) -> str:
    job_ad = detail.get("jobAd") or {}
    sections = job_ad.get("sections") or {}
    pieces: list[str] = []
    for section_name in ["companyDescription", "jobDescription", "qualifications", "additionalInformation"]:
        section = sections.get(section_name) or {}
        text = normalize_whitespace(section.get("text") or "")
        if text:
            pieces.append(text)
    return " ".join(pieces)


def classify_remote_policy(payload: dict[str, Any]) -> str:
    location = payload.get("location") or {}
    if location.get("remote") and location.get("hybrid"):
        return "hybrid"
    if location.get("remote"):
        return "remote"
    if location.get("hybrid"):
        return "hybrid"
    if payload.get("jobType"):
        return normalize_whitespace(str(payload.get("jobType")))
    return "onsite"


def classify_ashby_remote_policy(payload: dict[str, Any]) -> str:
    workplace_type = normalize_whitespace(payload.get("workplaceType") or "")
    lowered = workplace_type.lower()
    if "remote" in lowered:
        return "remote"
    if "hybrid" in lowered:
        return "hybrid"
    if workplace_type:
        return lowered
    return "onsite"


def extract_compensation_text(text: str) -> str:
    matches = re.findall(r"(?:[$€£]\s?\d+(?:[.,]\d+)?(?:\s?[KkMm])?(?:\s*[–-]\s*[$€£]?\s?\d+(?:[.,]\d+)?(?:\s?[KkMm])?)?)", text)
    unique_matches: list[str] = []
    for match in matches:
        normalized = normalize_whitespace(match)
        if normalized and normalized not in unique_matches:
            unique_matches.append(normalized)
    return "; ".join(unique_matches)


def extract_compensation_evidence(text: str) -> list[CompensationEvidence]:
    evidence: list[CompensationEvidence] = []
    for match in re.finditer(r"(?:[$€£]\s?\d+(?:[.,]\d+)?(?:\s?[KkMm])?(?:\s*[–-]\s*[$€£]?\s?\d+(?:[.,]\d+)?(?:\s?[KkMm])?)?)", text):
        matched_text = normalize_whitespace(match.group(0))
        if not matched_text:
            continue
        snippet_start = max(0, match.start() - 40)
        snippet_end = min(len(text), match.end() + 40)
        amount_kind = "range" if re.search(r"[–-]", matched_text) else "point"
        evidence.append(
            CompensationEvidence(
                matched_text=matched_text,
                amount_kind=amount_kind,
                source_excerpt=normalize_whitespace(text[snippet_start:snippet_end]),
            )
        )
    return evidence


def build_alert_signature(job_row: sqlite3.Row) -> str:
    signature_bits = [
        job_row["company_name"],
        job_row["title"],
        job_row["location"],
        job_row["remote_policy"],
        job_row["employment_type"],
        job_row["eligibility_label"],
        f"{job_row['eligibility_confidence']:.3f}",
        job_row["compensation_text"] or "",
    ]
    return sha256_text("|".join(signature_bits))


def normalize_job(raw: RawPosting) -> NormalizedJob:
    combined_text = f"{raw.title} {raw.description}".strip()
    decision = classify_eligibility(combined_text, raw.employment_type, raw.released_at)
    return NormalizedJob(
        company_key=raw.company_seed.company_key,
        company_name=raw.company_seed.name,
        source_type=raw.company_seed.source_type,
        source_slug=raw.company_seed.source_slug,
        source_job_key=raw.source_job_key,
        source_posting_id=raw.source_posting_id,
        title=raw.title,
        location=raw.location,
        employment_type=raw.employment_type,
        remote_policy=raw.remote_policy,
        source_url=raw.source_url,
        apply_url=raw.apply_url,
        description=raw.description,
        compensation_text=raw.compensation_text,
        released_at=raw.released_at,
        raw_payload_json=safe_json_dumps(raw.raw_payload),
        dedupe_key=build_dedupe_key(raw),
        is_internship=is_internship(combined_text),
        eligibility_label=decision.label,
        eligibility_confidence=decision.confidence,
        eligibility_reason="; ".join(decision.reasons),
    )


def is_internship(text: str) -> bool:
    return bool(re.search(r"\b(intern|internship|co-?op|returnship|apprentice|student researcher)\b", text, re.I))


def classify_eligibility(text: str, employment_type: str, released_at: str) -> EligibilityDecision:
    reasons: list[str] = []
    lowered = text.lower()
    internship = is_internship(text)
    if internship:
        reasons.append("contains internship-like language")
    if re.search(r"\bnew grad|graduate program|full[- ]time\b", lowered) and not internship:
        reasons.append("looks like a full-time or graduate role")
        return EligibilityDecision(label="not_eligible", confidence=0.92, reasons=reasons)
    if re.search(r"\bclass of 202[0-7]\b|must graduate|graduation year|graduating in 202[0-7]\b", lowered):
        reasons.append("mentions an earlier graduation constraint")
        return EligibilityDecision(label="not_eligible", confidence=0.96, reasons=reasons)
    if internship:
        if re.search(r"\bphd\b", lowered):
            reasons.append("phd internship wording is specialized")
            return EligibilityDecision(label="maybe_eligible", confidence=0.66, reasons=reasons)
        if employment_type and "intern" in employment_type.lower():
            reasons.append("employment type confirms internship")
            return EligibilityDecision(label="likely_eligible", confidence=0.94, reasons=reasons)
        reasons.append("title or description indicates internship")
        return EligibilityDecision(label="likely_eligible", confidence=0.88, reasons=reasons)
    if employment_type and "intern" in employment_type.lower():
        reasons.append("employment type suggests internship")
        return EligibilityDecision(label="likely_eligible", confidence=0.86, reasons=reasons)
    reasons.append("no internship signal found")
    return EligibilityDecision(label="not_eligible", confidence=0.9, reasons=reasons)


def build_dedupe_key(raw: RawPosting) -> str:
    parts = [
        raw.company_seed.company_key,
        slugify(raw.title),
        slugify(raw.location),
        slugify(raw.employment_type),
        slugify(raw.remote_policy),
        sha256_text(normalize_whitespace(raw.description)[:1000]),
        sha256_text(normalize_whitespace(raw.apply_url) or normalize_whitespace(raw.source_url)),
    ]
    return sha256_text("|".join(parts))


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self.connection.close()

    def initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS companies (
                company_key TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_slug TEXT NOT NULL,
                jobs_url TEXT NOT NULL,
                verified_at TEXT,
                last_seen_at TEXT,
                last_job_count INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'unknown',
                notes TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS source_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_key TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                status TEXT NOT NULL,
                job_count INTEGER NOT NULL DEFAULT 0,
                error TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(company_key) REFERENCES companies(company_key)
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dedupe_key TEXT NOT NULL UNIQUE,
                company_key TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_slug TEXT NOT NULL,
                source_job_key TEXT NOT NULL,
                source_posting_id TEXT NOT NULL,
                source_job_keys_json TEXT NOT NULL,
                title TEXT NOT NULL,
                location TEXT NOT NULL,
                employment_type TEXT NOT NULL,
                remote_policy TEXT NOT NULL,
                source_url TEXT NOT NULL,
                apply_url TEXT NOT NULL,
                description TEXT NOT NULL,
                compensation_text TEXT NOT NULL,
                released_at TEXT NOT NULL,
                raw_payload_json TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                is_internship INTEGER NOT NULL DEFAULT 0,
                eligibility_label TEXT NOT NULL,
                eligibility_confidence REAL NOT NULL,
                eligibility_reason TEXT NOT NULL,
                alert_signature TEXT NOT NULL DEFAULT '',
                alert_sent_at TEXT,
                FOREIGN KEY(company_key) REFERENCES companies(company_key)
            );

            CREATE TABLE IF NOT EXISTS job_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                source_job_key TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                snapshot_hash TEXT NOT NULL,
                raw_payload_json TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            );

            CREATE TABLE IF NOT EXISTS job_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                old_value TEXT NOT NULL,
                new_value TEXT NOT NULL,
                details_json TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            );

            CREATE TABLE IF NOT EXISTS compensation_evidence (
                job_id INTEGER PRIMARY KEY,
                source_text_hash TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            );

            CREATE TABLE IF NOT EXISTS email_outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                to_email TEXT NOT NULL,
                from_email TEXT NOT NULL,
                subject TEXT NOT NULL,
                body_text TEXT NOT NULL,
                body_html TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                sent_at TEXT,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            );
            """
        )
        self._run_schema_migrations()
        self.connection.commit()

    def _run_schema_migrations(self) -> None:
        self._ensure_column("jobs", "alert_signature", "TEXT NOT NULL DEFAULT ''")

    def _ensure_column(self, table_name: str, column_name: str, column_sql: str) -> None:
        cursor = self.connection.execute(f"PRAGMA table_info({table_name})")
        columns = {row["name"] for row in cursor.fetchall()}
        if column_name in columns:
            return
        self.connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")

    def record_company_check(self, seed: CompanySeed, status: str, job_count: int, error: str = "") -> None:
        now = iso_now()
        self.connection.execute(
            """
            INSERT INTO companies(company_key, company_name, source_type, source_slug, jobs_url, verified_at, last_seen_at, last_job_count, status, notes)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, '')
            ON CONFLICT(company_key) DO UPDATE SET
                company_name=excluded.company_name,
                source_type=excluded.source_type,
                source_slug=excluded.source_slug,
                jobs_url=excluded.jobs_url,
                verified_at=excluded.verified_at,
                last_seen_at=excluded.last_seen_at,
                last_job_count=excluded.last_job_count,
                status=excluded.status
            """,
            (seed.company_key, seed.name, seed.source_type, seed.source_slug, seed.jobs_url, now, now, job_count, status),
        )
        self.connection.execute(
            "INSERT INTO source_checks(company_key, checked_at, status, job_count, error) VALUES (?, ?, ?, ?, ?)",
            (seed.company_key, now, status, job_count, error),
        )
        self.connection.commit()

    def upsert_job(self, job: NormalizedJob) -> tuple[int, bool, bool]:
        now = iso_now()
        cursor = self.connection.execute("SELECT * FROM jobs WHERE dedupe_key = ?", (job.dedupe_key,))
        row = cursor.fetchone()
        if row:
            aliases = json.loads(row["source_job_keys_json"])
            if job.source_job_key not in aliases:
                aliases.append(job.source_job_key)
            eligibility_changed = row["eligibility_label"] != job.eligibility_label
            was_inactive = not bool(row["active"])
            self.connection.execute(
                """
                UPDATE jobs SET
                    source_job_keys_json = ?,
                    last_seen_at = ?,
                    title = ?,
                    location = ?,
                    employment_type = ?,
                    remote_policy = ?,
                    source_url = ?,
                    apply_url = ?,
                    description = ?,
                    compensation_text = ?,
                    released_at = ?,
                    raw_payload_json = ?,
                    active = 1,
                    is_internship = ?,
                    eligibility_label = ?,
                    eligibility_confidence = ?,
                    eligibility_reason = ?
                WHERE id = ?
                """,
                (
                    safe_json_dumps(aliases),
                    now,
                    job.title,
                    job.location,
                    job.employment_type,
                    job.remote_policy,
                    job.source_url,
                    job.apply_url,
                    job.description,
                    job.compensation_text,
                    job.released_at,
                    job.raw_payload_json,
                    1 if job.is_internship else 0,
                    job.eligibility_label,
                    job.eligibility_confidence,
                    job.eligibility_reason,
                    row["id"],
                ),
            )
            if was_inactive:
                self.connection.execute(
                    "INSERT INTO job_events(job_id, event_type, old_value, new_value, details_json, occurred_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (row["id"], "reopened", "inactive", "active", safe_json_dumps({"dedupe_key": job.dedupe_key}), now),
                )
            self.connection.execute(
                "INSERT INTO job_events(job_id, event_type, old_value, new_value, details_json, occurred_at) VALUES (?, ?, ?, ?, ?, ?)",
                (row["id"], "updated", row["title"], job.title, safe_json_dumps({"dedupe_key": job.dedupe_key}), now),
            )
            self.connection.execute(
                "INSERT INTO job_snapshots(job_id, source_job_key, fetched_at, snapshot_hash, raw_payload_json) VALUES (?, ?, ?, ?, ?)",
                (row["id"], job.source_job_key, now, sha256_text(job.raw_payload_json), job.raw_payload_json),
            )
            self.record_compensation_evidence(row["id"], f"{job.title} {job.description}")
            self.connection.commit()
            return int(row["id"]), False, eligibility_changed or was_inactive

        cursor = self.connection.execute(
            """
            INSERT INTO jobs(
                dedupe_key, company_key, source_type, source_slug, source_job_key, source_posting_id,
                source_job_keys_json, title, location, employment_type, remote_policy, source_url,
                apply_url, description, compensation_text, released_at, raw_payload_json, first_seen_at,
                last_seen_at, active, is_internship, eligibility_label, eligibility_confidence,
                eligibility_reason, alert_signature, alert_sent_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                job.dedupe_key,
                job.company_key,
                job.source_type,
                job.source_slug,
                job.source_job_key,
                job.source_posting_id,
                safe_json_dumps([job.source_job_key]),
                job.title,
                job.location,
                job.employment_type,
                job.remote_policy,
                job.source_url,
                job.apply_url,
                job.description,
                job.compensation_text,
                job.released_at,
                job.raw_payload_json,
                now,
                now,
                1,
                1 if job.is_internship else 0,
                job.eligibility_label,
                job.eligibility_confidence,
                job.eligibility_reason,
                "",
            ),
        )
        job_id = int(cursor.lastrowid)
        self.connection.execute(
            "INSERT INTO job_snapshots(job_id, source_job_key, fetched_at, snapshot_hash, raw_payload_json) VALUES (?, ?, ?, ?, ?)",
            (job_id, job.source_job_key, now, sha256_text(job.raw_payload_json), job.raw_payload_json),
        )
        self.connection.execute(
            "INSERT INTO job_events(job_id, event_type, old_value, new_value, details_json, occurred_at) VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, "created", "", job.title, safe_json_dumps({"dedupe_key": job.dedupe_key}), now),
        )
        self.record_compensation_evidence(job_id, f"{job.title} {job.description}")
        self.connection.commit()
        return job_id, True, True

    def record_compensation_evidence(self, job_id: int, source_text: str) -> None:
        evidence = extract_compensation_evidence(source_text)
        evidence_json = safe_json_dumps([dataclasses.asdict(entry) for entry in evidence])
        captured_at = iso_now()
        self.connection.execute(
            """
            INSERT INTO compensation_evidence(job_id, source_text_hash, evidence_json, raw_text, captured_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                source_text_hash = excluded.source_text_hash,
                evidence_json = excluded.evidence_json,
                raw_text = excluded.raw_text,
                captured_at = excluded.captured_at
            """,
            (job_id, sha256_text(source_text), evidence_json, source_text, captured_at),
        )

    def queue_email(self, job_id: int, to_email: str, from_email: str, subject: str, body_text: str, body_html: str) -> int:
        now = iso_now()
        cursor = self.connection.execute(
            """
            INSERT INTO email_outbox(job_id, to_email, from_email, subject, body_text, body_html, status, error, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', '', ?)
            """,
            (job_id, to_email, from_email, subject, body_text, body_html, now),
        )
        self.connection.execute("UPDATE jobs SET alert_sent_at = ? WHERE id = ?", (now, job_id))
        self.connection.commit()
        return int(cursor.lastrowid)

    def fetch_pending_emails(self) -> list[sqlite3.Row]:
        cursor = self.connection.execute("SELECT * FROM email_outbox WHERE status = 'pending' ORDER BY id ASC")
        return list(cursor.fetchall())

    def mark_email_sent(self, email_id: int, error: str = "") -> None:
        now = iso_now()
        status = "sent" if not error else "failed"
        self.connection.execute(
            "UPDATE email_outbox SET status = ?, error = ?, sent_at = ? WHERE id = ?",
            (status, error, now, email_id),
        )
        self.connection.commit()

    def set_alert_signature(self, job_id: int, signature: str) -> None:
        self.connection.execute("UPDATE jobs SET alert_signature = ? WHERE id = ?", (signature, job_id))
        self.connection.commit()

    def mark_stale_jobs(self, company_keys: Sequence[str], seen_dedupe_keys: set[str]) -> int:
        if not company_keys:
            return 0
        placeholders = ",".join("?" for _ in company_keys)
        params: list[Any] = list(company_keys)
        query = f"SELECT id, title, dedupe_key FROM jobs WHERE active = 1 AND company_key IN ({placeholders})"
        if seen_dedupe_keys:
            seen_placeholders = ",".join("?" for _ in seen_dedupe_keys)
            query += f" AND dedupe_key NOT IN ({seen_placeholders})"
            params.extend(sorted(seen_dedupe_keys))
        cursor = self.connection.execute(query, params)
        rows = cursor.fetchall()
        now = iso_now()
        for row in rows:
            self.connection.execute("UPDATE jobs SET active = 0 WHERE id = ?", (row["id"],))
            self.connection.execute(
                "INSERT INTO job_events(job_id, event_type, old_value, new_value, details_json, occurred_at) VALUES (?, ?, ?, ?, ?, ?)",
                (row["id"], "stale", row["title"], "inactive", safe_json_dumps({"dedupe_key": row["dedupe_key"]}), now),
            )
        self.connection.commit()
        return len(rows)

    def stats(self) -> dict[str, int]:
        cursor = self.connection.execute("SELECT COUNT(*) AS count FROM jobs")
        jobs = int(cursor.fetchone()["count"])
        cursor = self.connection.execute("SELECT COUNT(*) AS count FROM jobs WHERE active = 1")
        active = int(cursor.fetchone()["count"])
        cursor = self.connection.execute("SELECT COUNT(*) AS count FROM jobs WHERE is_internship = 1")
        internships = int(cursor.fetchone()["count"])
        cursor = self.connection.execute("SELECT COUNT(*) AS count FROM email_outbox")
        emails = int(cursor.fetchone()["count"])
        cursor = self.connection.execute("SELECT COUNT(*) AS count FROM compensation_evidence")
        compensation = int(cursor.fetchone()["count"])
        return {"jobs": jobs, "active": active, "internships": internships, "emails": emails, "compensation_evidence": compensation}


class AlertService:
    def __init__(self, config: TrackerConfig) -> None:
        self.config = config
        self.config.outbox_dir.mkdir(parents=True, exist_ok=True)

    def build_message(self, job_row: sqlite3.Row) -> tuple[str, str, str]:
        subject = f"[{job_row['company_name']}] {job_row['title']}"
        body_text = "\n".join(
            [
                f"Company: {job_row['company_name']}",
                f"Title: {job_row['title']}",
                f"Location: {job_row['location']}",
                f"Employment: {job_row['employment_type']}",
                f"Remote: {job_row['remote_policy']}",
                f"Eligibility: {job_row['eligibility_label']} ({job_row['eligibility_confidence']:.2f})",
                f"Reason: {job_row['eligibility_reason']}",
                f"Apply: {job_row['apply_url']}",
                f"Source: {job_row['source_url']}",
                f"Compensation: {job_row['compensation_text'] or 'not stated'}",
            ]
        )
        body_html = "<br>".join(body_text.splitlines())
        return subject, body_text, body_html

    def write_outbox_file(self, job_id: int, subject: str, body_text: str) -> Path:
        timestamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
        path = self.config.outbox_dir / f"{timestamp}-{job_id}.eml"
        path.write_text(f"Subject: {subject}\n\n{body_text}\n", encoding="utf-8")
        return path

    def send_pending(self, store: SQLiteStore) -> list[Path]:
        written: list[Path] = []
        pending = store.fetch_pending_emails()
        for row in pending:
            if self.config.smtp_host:
                self._send_via_smtp(row)
                store.mark_email_sent(int(row["id"]))
            else:
                subject = row["subject"]
                body_text = row["body_text"]
                written.append(self.write_outbox_file(int(row["job_id"]), subject, body_text))
                store.mark_email_sent(int(row["id"]))
        return written

    def _send_via_smtp(self, row: sqlite3.Row) -> None:
        assert self.config.smtp_host
        port = self.config.smtp_port or 587
        msg = EmailMessage()
        msg["Subject"] = row["subject"]
        msg["From"] = row["from_email"]
        msg["To"] = row["to_email"]
        msg.set_content(row["body_text"])
        msg.add_alternative(row["body_html"], subtype="html")
        with smtplib.SMTP(self.config.smtp_host, port, timeout=30) as server:
            if self.config.smtp_use_tls:
                server.starttls()
            if self.config.smtp_username and self.config.smtp_password:
                server.login(self.config.smtp_username, self.config.smtp_password)
            server.send_message(msg)


class PipelineRunner:
    def __init__(self, config: TrackerConfig) -> None:
        self.config = config
        self.http = HttpClient()
        self.store = SQLiteStore(config.db_path)
        self.alerts = AlertService(config)
        self.connectors = {
            "greenhouse": GreenhouseConnector(self.http),
            "smartrecruiters": SmartRecruitersConnector(self.http),
            "ashby": AshbyConnector(self.http),
        }

    def run(self, seeds: Sequence[CompanySeed]) -> dict[str, int]:
        self.store.initialize()
        processed = 0
        inserted = 0
        eligible = 0
        alerts = 0
        stale = 0
        successful_company_keys: list[str] = []
        seen_dedupe_keys: set[str] = set()
        for seed in seeds:
            connector = self.connectors.get(seed.source_type)
            if connector is None:
                self.store.record_company_check(seed, "unsupported", 0, f"unsupported source type: {seed.source_type}")
                continue
            try:
                raw_postings = connector.fetch_postings(seed)
                self.store.record_company_check(seed, "ok", len(raw_postings))
                successful_company_keys.append(seed.company_key)
            except Exception as exc:  # pragma: no cover - network errors are validated in integration runs
                self.store.record_company_check(seed, "error", 0, repr(exc))
                continue
            for raw_posting in raw_postings:
                normalized = normalize_job(raw_posting)
                processed += 1
                seen_dedupe_keys.add(normalized.dedupe_key)
                job_id, created, eligibility_changed = self.store.upsert_job(normalized)
                if created:
                    inserted += 1
                if normalized.is_internship and normalized.eligibility_label in {"likely_eligible", "maybe_eligible"}:
                    eligible += 1
                if (created or eligibility_changed) and normalized.eligibility_label in {"likely_eligible", "maybe_eligible"}:
                    job_row = self._fetch_job_row(job_id)
                    signature = build_alert_signature(job_row)
                    if job_row["alert_signature"] != signature:
                        subject, body_text, body_html = self.alerts.build_message(job_row)
                        self.store.queue_email(job_id, self.config.alert_to_email, self.config.alert_from_email, subject, body_text, body_html)
                        self.store.set_alert_signature(job_id, signature)
                        alerts += 1
        stale = self.store.mark_stale_jobs(successful_company_keys, seen_dedupe_keys)
        self.alerts.send_pending(self.store)
        stats = self.store.stats()
        stats.update({"processed": processed, "inserted": inserted, "eligible": eligible, "alerts": alerts, "stale": stale})
        return stats

    def _fetch_job_row(self, job_id: int) -> sqlite3.Row:
        cursor = self.store.connection.execute(
            """
            SELECT jobs.*, companies.company_name
            FROM jobs
            JOIN companies USING(company_key)
            WHERE jobs.id = ?
            """,
            (job_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise KeyError(job_id)
        return row


def get_default_config() -> TrackerConfig:
    return TrackerConfig.from_env()


def build_pipeline_summary(store: SQLiteStore) -> list[dict[str, Any]]:
    cursor = store.connection.execute(
        """
        SELECT company_name, source_type, COUNT(*) AS job_count, SUM(is_internship) AS internship_count
        FROM jobs
        JOIN companies USING(company_key)
        GROUP BY company_key
        ORDER BY company_name
        """
    )
    return [dict(row) for row in cursor.fetchall()]
