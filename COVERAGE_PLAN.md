# Coverage Plan

Revised plan v2 after self-review against missing companies, unsupported scraping assumptions, false eligibility classifications, stale postings, source failures, and operational cost.

## Coverage Objective

Maximize recall for internships that could matter to a 2028 graduate while keeping the system maintainable and compliant. Coverage should be measured by source diversity, company diversity, freshness, and eligibility correctness rather than by job count alone.

## Company-Universe Discovery Process

### Tier 1: High-confidence employer discovery

- Seed from known large employers, frequent internship posters, and companies already appearing in canonical ATS indices.
- Expand from each employer to its canonical domains, subdomains, and ATS hosts.
- Include repeated validation so dead companies are removed and renamed companies remain linked.

### Tier 2: Related-employer expansion

- Add subsidiaries, portfolio companies, and company groups once a parent company is known.
- Use accelerator cohorts, venture portfolios, alumni referrals, and public internship event sponsor lists.
- Surface adjacent employers from the same ATS family only after confirming distinct legal entities or distinct posting destinations.

### Tier 3: Long-tail discovery

- Use public internship aggregators, job boards, university career pages, and targeted search queries.
- Allow low-confidence candidates into the universe if they repeatedly emit internship-like roles.
- Revalidate long-tail companies on a shorter expiry interval because their pages change often.

### Tier 4: Blind-spot sweeps

- Periodically search for companies missing from the main universe by mining source domains, search engine results, and discovered company names inside job text.
- Compare against prior missed-posting logs to find recurring blind spots.

## ATS Connector Coverage

### Priority connectors

- Greenhouse
- Lever
- Ashby
- Workday
- SmartRecruiters
- iCIMS
- SuccessFactors
- BambooHR
- Oracle-based career portals
- Custom pages with embedded job JSON or schema.org data

### Secondary handling

- Custom enterprise portals with inconsistent HTML.
- University recruiting pages and branded microsites.
- Aggregator mirrors that are useful only as discovery hints.

### Coverage rule

- A source is supported only if the connector can declare its capabilities explicitly.
- If a source is only partially supported, the system must mark the unsupported portion instead of pretending coverage is complete.

## Job Discovery Pipeline Coverage

- Poll high-freshness sources frequently and slow down for sources with stable archives.
- Separate discovery from deep parsing so light checks can surface fresh openings quickly.
- Maintain a source freshness score to prioritize the next crawl.
- Capture posting dates, expiration hints, and last-seen timestamps to avoid stale alerts.

## Eligibility Coverage For A 2028 Graduate

### Positive signals to capture

- Internship, co-op, summer analyst, student researcher, returnship, or apprenticeship wording that matches student status.
- Graduation-year ranges that include 2028 or are broader than the user's current status.
- Explicit language such as rising junior, class of 2028, undergraduate, or currently enrolled.

### Negative signals to capture

- Roles requiring graduation earlier than 2028 when the requirement is explicit.
- Full-time positions with no student allowance.
- Visa, location, or seniority exclusions that the user cannot meet.

### Ambiguity handling

- If the posting language is unclear, classify it as unknown or needs-review.
- Do not infer eligibility from a similar title alone.
- Keep the rule set conservative so false eligibility is less likely than missed recall in ambiguous cases.

## Compensation-Evidence Coverage

- Extract exact amounts whenever they appear in a posting.
- Preserve range, frequency, currency, and perk wording separately.
- Record the absence of compensation as a meaningful signal only when the posting explicitly omits it.
- Avoid filling missing numbers from outside inference unless the evidence layer is explicitly marked as external and optional.

## Deduplication Coverage

- Deduplicate across repeated crawls, mirrored ATS views, company redirects, and reposted listings.
- Use stable IDs first, then URL canonicalization, then text similarity.
- Track duplicates as lineage rather than deletion so the history remains auditable.

## Historical State Coverage

- Store first seen, last seen, updated, closed, reopened, and expired events.
- Keep snapshots of changed fields so alerts can explain what changed.
- Retain stale jobs for a limited historical window so the tracker can learn from prior postings.

## Alert Coverage

- Immediate alerts for high-confidence matches.
- Daily digest for lower-priority discoveries.
- Separate alerts for new jobs, updated deadlines, compensation changes, and application reminders.
- Suppress duplicate alerts when the underlying opportunity identity has not changed.

## Operational Cost Coverage

- Prefer source-native endpoints and lightweight fetches over browser automation.
- Reuse snapshots and parse results when content hashes have not changed.
- Batch mail delivery and schedule work by priority.
- Cache source capability metadata so unsupported calls are avoided on future runs.

## Test Coverage Plan

- Unit tests for canonical parsing, canonicalization, dedupe keys, and eligibility rules.
- Fixture tests per connector using representative source samples.
- Regression tests for known false positives and false negatives.
- Snapshot tests for raw-to-normalized field mapping.
- End-to-end tests for one full discovery cycle, including alert generation.

## Review Checklist For Blind Spots

- Missing companies: compare discovered companies against prior crawl gaps and search-index blind spots.
- Unsupported scraping assumptions: verify each connector advertises only methods it can actually perform.
- False eligibility classifications: manually review ambiguous postings and update rules from error cases.
- Stale postings: confirm closure and reopen handling with real source transitions.
- Source failures: simulate timeouts, HTML changes, and empty results.
- Operational cost: measure crawl volume, parse cost, alert volume, and duplicate suppression rate.