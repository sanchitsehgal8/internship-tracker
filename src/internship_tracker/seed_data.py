from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompanySeed:
    name: str
    source_type: str
    source_slug: str
    jobs_url: str

    @property
    def company_key(self) -> str:
        return f"{self.source_type}:{self.source_slug}"


GREENHOUSE_SEEDS = [
    CompanySeed("Airbnb", "greenhouse", "airbnb", "https://boards-api.greenhouse.io/v1/boards/airbnb/jobs?content=true"),
    CompanySeed("Airtable", "greenhouse", "airtable", "https://boards-api.greenhouse.io/v1/boards/airtable/jobs?content=true"),
    CompanySeed("Amplitude", "greenhouse", "amplitude", "https://boards-api.greenhouse.io/v1/boards/amplitude/jobs?content=true"),
    CompanySeed("Asana", "greenhouse", "asana", "https://boards-api.greenhouse.io/v1/boards/asana/jobs?content=true"),
    CompanySeed("Brex", "greenhouse", "brex", "https://boards-api.greenhouse.io/v1/boards/brex/jobs?content=true"),
    CompanySeed("Coursera", "greenhouse", "coursera", "https://boards-api.greenhouse.io/v1/boards/coursera/jobs?content=true"),
    CompanySeed("Databricks", "greenhouse", "databricks", "https://boards-api.greenhouse.io/v1/boards/databricks/jobs?content=true"),
    CompanySeed("Datadog", "greenhouse", "datadog", "https://boards-api.greenhouse.io/v1/boards/datadog/jobs?content=true"),
    CompanySeed("Discord", "greenhouse", "discord", "https://boards-api.greenhouse.io/v1/boards/discord/jobs?content=true"),
    CompanySeed("Doctolib", "greenhouse", "doctolib", "https://boards-api.greenhouse.io/v1/boards/doctolib/jobs?content=true"),
    CompanySeed("Dropbox", "greenhouse", "dropbox", "https://boards-api.greenhouse.io/v1/boards/dropbox/jobs?content=true"),
    CompanySeed("Figma", "greenhouse", "figma", "https://boards-api.greenhouse.io/v1/boards/figma/jobs?content=true"),
    CompanySeed("Gusto", "greenhouse", "gusto", "https://boards-api.greenhouse.io/v1/boards/gusto/jobs?content=true"),
    CompanySeed("Instacart", "greenhouse", "instacart", "https://boards-api.greenhouse.io/v1/boards/instacart/jobs?content=true"),
    CompanySeed("Lyft", "greenhouse", "lyft", "https://boards-api.greenhouse.io/v1/boards/lyft/jobs?content=true"),
    CompanySeed("Reddit", "greenhouse", "reddit", "https://boards-api.greenhouse.io/v1/boards/reddit/jobs?content=true"),
    CompanySeed("Robinhood", "greenhouse", "robinhood", "https://boards-api.greenhouse.io/v1/boards/robinhood/jobs?content=true"),
    CompanySeed("Roblox", "greenhouse", "roblox", "https://boards-api.greenhouse.io/v1/boards/roblox/jobs?content=true"),
    CompanySeed("Stripe", "greenhouse", "stripe", "https://boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true"),
    CompanySeed("Chime", "greenhouse", "chime", "https://boards-api.greenhouse.io/v1/boards/chime/jobs?content=true"),
    CompanySeed("MongoDB", "greenhouse", "mongodb", "https://boards-api.greenhouse.io/v1/boards/mongodb/jobs?content=true"),
    CompanySeed("Okta", "greenhouse", "okta", "https://boards-api.greenhouse.io/v1/boards/okta/jobs?content=true"),
    CompanySeed("PagerDuty", "greenhouse", "pagerduty", "https://boards-api.greenhouse.io/v1/boards/pagerduty/jobs?content=true"),
    CompanySeed("Postman", "greenhouse", "postman", "https://boards-api.greenhouse.io/v1/boards/postman/jobs?content=true"),
    CompanySeed("Twilio", "greenhouse", "twilio", "https://boards-api.greenhouse.io/v1/boards/twilio/jobs?content=true"),
]

SMARTRECRUITERS_SEEDS = [
    CompanySeed("Visa", "smartrecruiters", "visa", "https://api.smartrecruiters.com/v1/companies/visa/postings?limit=100"),
    CompanySeed("Uber", "smartrecruiters", "uber", "https://api.smartrecruiters.com/v1/companies/uber/postings?limit=100"),
    CompanySeed("LVMH", "smartrecruiters", "lvmh", "https://api.smartrecruiters.com/v1/companies/lvmh/postings?limit=100"),
]

ALL_COMPANY_SEEDS = GREENHOUSE_SEEDS + SMARTRECRUITERS_SEEDS
