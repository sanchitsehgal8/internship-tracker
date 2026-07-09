# Tasks

Revised plan v2 after critical review. This sequence is intentionally implementation-neutral and should be used as the build order once coding begins.

## Milestone 1: Live Vertical Slice

- Status: completed
- Scope delivered: canonical data model, live Greenhouse and SmartRecruiters ingestion, SQLite storage, deduplication, conservative eligibility classification, and email outbox generation.
- Verification: unit tests passed and the live pipeline ran successfully against 28 real company seeds.
- Notes: the first slice intentionally used a modest company set to prove the architecture before expanding source coverage.

## Milestone 2: Broader Connector Coverage

- Status: not started
- Goal: add more ATS families or richer parsing paths where public, permitted sources are available.
- Focus: improve recall while keeping source capability metadata explicit.

## Phase 0: Foundations

1. Define the canonical data model for companies, sources, jobs, snapshots, eligibility decisions, compensation evidence, state events, and applications.
2. Define compliance rules for source handling, rate limiting, robots respect, and unsupported-source fallback behavior.
3. Define source capability metadata so each connector can declare exactly what it supports.

## Phase 1: Company And Source Discovery

1. Build the company-universe store with discovery provenance and validation status.
2. Add expansion logic for subsidiaries, portfolio companies, ATS host discovery, and related-employer hints.
3. Add source registry entries for priority ATS families and custom pages.
4. Add blind-spot logging so missed companies can be fed back into discovery.

## Phase 2: Connector Framework

1. Implement the common connector interface for listing jobs, fetching details, and capturing snapshots.
2. Add the highest-priority ATS connectors first.
3. Add fallback parsing for custom pages and embedded structured data.
4. Add source-specific health reporting and capability flags.

## Phase 3: Normalization And Snapshots

1. Normalize source payloads into a canonical job schema.
2. Store raw snapshots and checksums for every fetch.
3. Preserve provenance on normalized fields wherever possible.
4. Reject or mark incomplete records instead of inventing missing fields.

## Phase 4: Deduplication And History

1. Build identity resolution using stable IDs, URLs, and similarity signals.
2. Store lineage for reposts, edits, and mirrors.
3. Add job lifecycle events and change diffs.
4. Add reopen and stale-posting detection.

## Phase 5: Eligibility Engine

1. Implement rule tiers for a 2028 graduate.
2. Add confidence levels and evidence-backed explanations.
3. Add conservative unknown handling for ambiguous posts.
4. Create regression fixtures for common false-positive patterns.

## Phase 6: Compensation Evidence

1. Extract structured and unstructured compensation evidence.
2. Store exact source text and field-level provenance.
3. Keep evidence separate from inferred interpretation.

## Phase 7: Alerts And Application Tracking

1. Build alert generation from state changes, not raw crawl events.
2. Add email batching, dedupe, and digest scheduling.
3. Build the saved-job and application tracker.
4. Add manual overrides for stale, closed, or deprioritized jobs.

## Phase 8: Testing And Validation

1. Write unit tests for parsing, dedupe, eligibility, and evidence extraction.
2. Write connector fixture tests for each supported ATS family.
3. Write end-to-end tests for discovery, normalization, dedupe, eligibility, and alerting.
4. Add failure-mode tests for HTML changes, timeouts, stale postings, and empty result sets.

## Phase 9: Deployment And Operations

1. Package the backend and worker processes for a low-maintenance deployment.
2. Add observability for crawl volume, source failures, alert volume, and processing cost.
3. Add retry, backoff, and quarantine behavior for broken sources.
4. Add a periodic review workflow for source coverage and blind spots.

## Phase 10: Review Loop

1. Review missed internships weekly at first, then adjust the universe and rules.
2. Review false eligibility classifications and tighten or relax rules as needed.
3. Review alert cost and noise, then tune batching and dedupe thresholds.
4. Review source coverage quarterly and add new connectors or fallback methods where recall is weak.