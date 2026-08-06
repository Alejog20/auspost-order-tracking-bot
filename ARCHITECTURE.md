# Architecture

For current task status and what's blocked on the client, see IMPLEMENTATION_PLAN.md, this file covers system design only.

## Goal

Automate the daily shipment report Jay's team currently builds by hand: check Australia Post status on every order shipped through Shopify, flag what needs a look, drop what's been sitting delivered for a while, and send a plain-English report out, on a schedule, with no one touching it.

## Why it matters, briefly

Jay's is a gift company. Recipients don't know deliveries are coming, so there's no self-service tracking fallback the way a normal e-commerce order has, someone on his side has to manually watch every shipment. This replaces that manual process, not just adds a nice-to-have report on top of one.

## Design constraints

- **Config over code.** Branding, tone, and thresholds live in `templates/default_template.yaml`, not hardcoded in Python. This is what makes the same pipeline reusable for a future client, swap the config, not the logic.
- **History must persist.** `report_history.jsonl` is committed back to the repo at the end of every scheduled run. Without that commit, the 3-day drop-off rule has no memory, GitHub Actions containers don't survive between runs.
- **No real network calls in tests.** Anthropic, Shopify, and Australia Post all get mocked in the test suite. Tests verify logic, not live services.
- **Secrets never touch the repo.** Environment variables locally, GitHub Secrets in CI, always.

## Tech stack

- Python, managed with uv
- Jinja2 for templating, PyYAML for config
- Anthropic SDK for the report narrative
- pytest for testing
- GitHub Actions for both scheduling (`daily_report.yml`) and CI (`tests.yml`)
- SMTP for email delivery (interim sender: our own address, until Jay confirms his preferred inbox)

## Data model

`TrackingItem` (`models.py`) is the shared shape every shipment takes, regardless of where its data came from, this is the seam that keeps the pipeline decoupled from any one data source:

```python
tracking_number: str
status: str                          # raw carrier status text
category: str                        # delivered | in_transit | awaiting_collection
last_scan_location: str
last_scan_time: datetime
expected_delivery: date | None       # end of the delivery window
expected_delivery_label: str | None  # human-readable window, e.g. "Fri 7 - Mon 10 Aug"
collection_deadline: date | None
collection_location: str | None
```

`needs_attention(stale_after_days, collection_warn_days)` is the only place flagging logic lives: delivered items never flag, in-transit items flag when stale or past their window, awaiting-collection items flag only as their deadline actually nears.

Config (`templates/default_template.yaml`): `company_name`, `report_title`, `stale_after_days`, `drop_after_days`, `tone`, and a `brand` block of colors per status category.

History log (`report_history.jsonl`, one JSON object per line): date plus each item's `tracking_number`, `status`, `category`, `needs_attention`, `days_since_scan`. This is what `history.py` reads to compute the 3-day drop-off, and what a future trends view would read too.

## Layers

**Extraction** (`connectors/`, not built yet) — Shopify Admin API for the day's orders and tracking numbers, Australia Post API for live status on each. Two independent sources, both documented publicly, both buildable without Jay's credentials, only *testing* against his real accounts is blocked.

**Rules** (`history.py`) — the 3-day drop-off filter, applied before anything else sees the data. Delivered-and-stale items never reach the prompt, the flagging logic, or the report.

**Reasoning** (`report_generator.py`) — builds the prompt from whatever items survive filtering, calls Claude for the plain-English narrative and headline, structured as JSON.

**Output** — two templates, deliberately different under the hood: `report_email.html` is table-based with inline styles for email-client compatibility, `report_pdf.html` uses modern CSS and proper `@page` rules for print, since neither format's constraints apply to the other.

**Delivery** (`delivery/`, not built yet) — SMTP send of whichever format(s) Jay wants once confirmed.

**Scheduling** — GitHub Actions, weekdays, currently 2:07pm Melbourne (placeholder pending Jay's actual preference), a few minutes off the hour deliberately since scheduled runs queue up at :00 across all of GitHub.

## File structure

```
auspost-order-tracking-bot/
├── .github/workflows/
│   ├── daily_report.yml       # scheduled production run
│   └── tests.yml              # CI, every push/PR
├── connectors/                # Shopify + Australia Post, next up
│   ├── shopify.py
│   └── auspost.py
├── delivery/                  # email sending, next up
│   └── email_sender.py
├── templates/
│   ├── default_template.yaml
│   ├── report_email.html
│   └── report_pdf.html
├── tests/
│   ├── test_models.py
│   ├── test_history.py
│   └── test_report_generator.py
├── models.py
├── history.py
├── report_generator.py
├── run_daily_report.py        # production entrypoint, doesn't exist yet
├── demo.py                    # local testing script with real sample data
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── .gitignore
├── CLAUDE.md
├── ARCHITECTURE.md
├── IMPLEMENTATION_PLAN.md
└── report_history.jsonl       # runtime-generated, committed back on every run
```

## Explicitly out of scope for now

- Multi-client reuse beyond the existing config file, that's already structurally supported, just not exercised yet
- Any hosting beyond GitHub Actions
- A weekly digest or trend view off `report_history.jsonl`, the data's being collected, nothing reads it that way yet
- Automated posting or writing back to Shopify or Australia Post, this system only reads from both