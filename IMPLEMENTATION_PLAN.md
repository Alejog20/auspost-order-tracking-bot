# Implementation plan

Repo: https://github.com/Alejog20/auspost-order-tracking-bot

## Day 1 — done

- System architecture designed and diagrammed (`.drawio` + exported image)
- GitHub repository created, local codebase linked
- `.github/workflows/daily_report.yml` created (schedule + secrets wiring)
- Claude API key created and tested
- Python project environment set up (uv)
- `history.py` and `.gitignore` written

## Day 2 — done

- `history.py` 3-day drop-off logic implemented and wired into `report_generator.py`
- `report_generator.py` updated: logs `category`, filters dropped items automatically before building the prompt
- `default_template.yaml` extended with `drop_after_days`
- Test suite implemented: `test_models.py`, `test_history.py`, `test_report_generator.py`, `pytest.ini`, `.github/workflows/tests.yml`
- All 20 tests passing locally
- Decision made: email delivery via SMTP using our own address for now, Jay's preferred inbox to be swapped in once confirmed

## Day 3 — next, unblocked, doesn't need anything from Jay

These were correctly identified as unblocked on Day 1, worth being precise now that it's time to actually build them: the API docs are public, only *testing against his real account* is blocked, not writing the code itself.

1. **Australia Post connector** (`connectors/auspost.py`) — OAuth2 client against the published Shipping & Tracking API. Build against the documented schema, mock the HTTP calls in tests, structure credentials to load from `AUSPOST_API_KEY`.
2. **Shopify connector** (`connectors/shopify.py`) — Admin API client pulling orders and their fulfillment tracking numbers. Same approach: build against Shopify's public docs, mock in tests, credentials from `SHOPIFY_STORE_DOMAIN` / `SHOPIFY_CLIENT_ID` / `SHOPIFY_CLIENT_SECRET`. Remember: the access token this issues expires roughly every 24 hours (Shopify's post-January-2026 flow), the client ID and secret don't, build the refresh into the connector itself, not into anything Jay has to think about.
3. **`run_daily_report.py`** — the actual production entrypoint the workflow calls. Doesn't exist yet. Wires together: Shopify connector → Australia Post connector → `history.filter_dropped_items` → `report_generator.generate_report` / `generate_pdf_report` → email send.
4. **Email sending module** (`delivery/email_sender.py`) — SMTP, using our own address as the interim sender per the Day 2 decision. Swap to Jay's preferred setup once he confirms.
5. Test each connector against **mocked** responses matching the real APIs' documented shapes. This is what actually unblocks Day 3 without needing Jay's credentials yet, code and tests can be fully correct and verified before a single real API call happens.

## Blocked — waiting on Jay

- Connecting the Australia Post connector to his real API key
- Connecting the Shopify connector to his real store (staff account invite)
- A live end-to-end run against real data

## To define with Jay

- Company name, logo/emblem, and brand colors for the report template
- Which inbox the finished report should actually be sent to
- Time zone and exact hour the job should run (currently a placeholder: weekdays, 2:07pm Melbourne)
- The `.env` / GitHub Secrets values themselves: `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, `AUSPOST_API_KEY`

## When Jay's inputs arrive

- **Shopify staff invite lands** → plug real `SHOPIFY_CLIENT_ID`/`SHOPIFY_CLIENT_SECRET` into GitHub Secrets, point the connector at his store, run it once manually (`workflow_dispatch`) before trusting the schedule.
- **Australia Post key lands** → same pattern, `AUSPOST_API_KEY` into Secrets, manual run to confirm real tracking data comes back clean.
- **Branding/email/schedule confirmed** → update `default_template.yaml` and the cron line in `daily_report.yml` in one small PR, nothing else in the codebase should need to change for this.
- **All four land together** → first full live run, watch it together before calling it done.