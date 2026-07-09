# Requirements

Revised plan v2 after critical review for missing companies, unsupported scraping assumptions, false eligibility classifications, stale postings, source failures, and operational cost.

## Product Goal

Build an internship-tracking system that maximizes recall of relevant internships while remaining maintainable, source-compliant, and operationally affordable. The system must prioritize finding real openings early, preserve history as postings change, and keep the user informed with high-signal alerts.

## Target User Profile

- Primary user: a 2028 graduate student.
- Primary use case: discover internships that are plausibly eligible for a student graduating in 2028, across software, AI/ML, product, data, research, and adjacent technical roles.
- Secondary use case: track saved opportunities, application status, and evidence supporting why a role was surfaced.

## Functional Requirements

### 1. Company-universe discovery

- Maintain a living company universe rather than a fixed seed list.
- Discover employers from ATS job boards, company career pages, aggregators, alumni-influenced sources, and periodic curated lists.
- Support broad recall with controlled expansion from known companies to subsidiaries, portfolio companies, and emerging startups.
- Record why each company entered the universe and when it was last validated.

### 2. ATS connectors and source ingestion

- Support ATS-backed sources through a connector framework.
- Initial connector targets should include the major systems commonly used for internships: Greenhouse, Lever, Ashby, Workday, SmartRecruiters, iCIMS, SuccessFactors, BambooHR, Oracle-based career portals, and custom pages with embedded job data.
- Ingest structured job metadata when available, but fall back to resilient page parsing when only HTML is exposed.
- Respect source terms, robots directives, rate limits, and authentication boundaries.
- Avoid assuming that every source can be scraped; unsupported sources must degrade to manual or semi-manual capture.

### 3. Job discovery pipeline

- Run scheduled discovery on a configurable cadence.
- Normalize all job records into a common schema.
- Extract title, company, location, remote policy, employment type, internship term, experience level, posting date, application URL, source URL, source type, and raw evidence.
- Detect new jobs, changed jobs, closed jobs, and re-opened jobs.
- Preserve raw snapshots for auditability and post-mortem analysis.

### 4. Eligibility engine

- Classify roles for a 2028 graduate using explicit rule sets and evidence, not guesswork.
- Use conservative defaults when education requirements are ambiguous.
- Handle school-year wording, graduation year ranges, student status requirements, visa wording, location restrictions, and program-specific constraints.
- Output a rationale, confidence level, and evidence trail for each classification.
- Distinguish between hard ineligible, likely eligible, possibly eligible, and unknown.

### 5. Compensation-evidence layer

- Capture compensation evidence from postings when present.
- Link salary, stipend, housing, relocation, and bonus claims to the exact source text or structured field.
- Allow a job to have compensation evidence even when exact numbers are absent, by storing ranges, perks, and implied signals separately.
- Never invent compensation values.

### 6. Deduplication

- Deduplicate jobs across repeated crawls, mirrored career pages, ATS mirrors, and reposts.
- Use a combination of stable identifiers, normalized URLs, source fingerprints, title/company/location similarity, and text similarity.
- Preserve lineage so a reopened or edited posting can be traced back to earlier versions.

### 7. Historical state tracking

- Track job lifecycle states over time: discovered, updated, eligible, alert-worthy, saved, applied, rejected, expired, and closed.
- Store source snapshot history and change diffs.
- Keep a timeline for each opportunity so alerts can explain what changed.

### 8. Email alerts

- Send alert emails for newly discovered jobs, changed eligibility, deadline changes, compensation updates, and saved-job reminders.
- Batch alerts to reduce noise and cost.
- Allow user-configurable alert frequency and filtering.

### 9. Application tracker

- Provide a tracker for saved jobs and applications.
- Store application stage, deadline, referral status, notes, follow-up dates, and evidence links.
- Support manual overrides when the user knows a job is stale, closed, or not relevant.

## Non-Functional Requirements

- Recall first: prefer not missing real opportunities over perfect precision, but keep false positives explainable and bounded.
- Maintainability: prefer a modular connector architecture and shared normalization pipeline.
- Compliance: respect source terms and avoid brittle or aggressive scraping assumptions.
- Reliability: tolerate source outages, parser failures, and partial ingestion.
- Cost control: use incremental crawling, cache aggressively, and avoid unnecessary browser automation.
- Auditability: preserve raw source evidence for each normalized record.
- Extensibility: adding a new source should require minimal code changes.

## Constraints And Assumptions

- The system must not assume privileged API access unless explicitly configured.
- Some job sources will only be partially machine-readable.
- Some employers will change ATS vendors over time.
- Many internships will be posted and removed quickly, so freshness matters.
- Compensation data will often be incomplete or absent.

## Explicitly Out Of Scope For The First Planning Pass

- Automated application submission.
- Credential storage beyond what is needed for email or read-only user settings.
- Aggressive anti-bot bypass techniques.
- Perfect compensation prediction.

## Critical Review Notes And Revision Outcomes

- Missing companies: solved by a living universe with multi-source discovery and periodic expansion, not a one-time seed list.
- Unsupported scraping assumptions: solved by source capability flags and graceful fallback modes.
- False eligibility classifications: solved by conservative rule tiers, confidence scores, and evidence-backed rationales.
- Stale postings: solved by lifecycle tracking, reopen detection, and freshness-aware alerts.
- Source failures: solved by retry policies, dead-source marking, and alternate source discovery.
- Operational cost: solved by incremental crawling, batching, dedupe before expensive work, and avoiding browser automation unless required.