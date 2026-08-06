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

## Day 3 — done, with one open caveat

1. **Australia Post connector** (`connectors/auspost.py`) — built against `AUTH-KEY` header + `digitalapi.auspost.com.au/shipping/v1/track`, mocked in `tests/test_auspost.py`. **Caveat:** this is a best-effort reconstruction, not verified against Australia Post's current live docs — their developer portal renders via JavaScript and couldn't be fetched to confirm the exact request/response shape. Treat as a first draft to correct against real docs or a sample response before the live test below, not as verified-correct.
2. **Shopify connector** (`connectors/shopify.py`) — GraphQL Admin API (Shopify's REST Admin API is legacy as of 2026; new integrations use GraphQL), client credentials grant, 24h token auto-refresh built into `ShopifyClient`. Confirmed against current shopify.dev docs. Mocked in `tests/test_shopify.py`.
3. **`run_daily_report.py`** — wires Shopify connector → Australia Post connector → `report_generator.generate_report` (which applies `history.filter_dropped_items` internally) → email send. Skips items Australia Post can't find rather than failing the whole run; skips the email entirely (logs instead) if there are zero shipments for the day, to avoid a wasted Claude call and a content-free email — flagging this as a judgment call, not a spec'd behavior, in case Jay would rather always get a "nothing today" email. **Only wires the email path, not `generate_pdf_report`** — PDF delivery has no rendering pipeline decided yet (HTML → PDF needs a library choice that hasn't been made), so it's left out rather than guessed at.
4. **Email sending module** (`delivery/email_sender.py`) — SMTP, reads `EMAIL_RECIPIENT` / `SMTP_USERNAME` / `SMTP_PASSWORD` / `SMTP_HOST` / `SMTP_PORT` from env, mocked in `tests/test_email_sender.py`.
5. All new modules mocked in tests, 34/34 passing (`uv run pytest -v`).

## Blocked — waiting on Jay

- Connecting the Australia Post connector to his real API key, **and** confirming the connector's assumed request/response shape is actually correct
- Connecting the Shopify connector to his real store (staff account invite)
- A live end-to-end run against real data

## To define with Jay

- Company name, logo/emblem, and brand colors for the report template
- Which inbox the finished report should actually be sent to
- Time zone and exact hour the job should run (currently a placeholder: weekdays, 2:07pm Melbourne)
- The `.env` / GitHub Secrets values themselves: `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, `AUSPOST_API_KEY`
- SMTP sending credentials: `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_HOST` — not yet in `.env`, needed before `run_daily_report.py` can actually send anything
- Whether a PDF format is still wanted, and if so, what should render it (no HTML→PDF library is chosen yet)

## When Jay's inputs arrive

- **Shopify staff invite lands** → plug real `SHOPIFY_CLIENT_ID`/`SHOPIFY_CLIENT_SECRET` into GitHub Secrets, point the connector at his store, run it once manually (`workflow_dispatch`) before trusting the schedule.
- **Australia Post key lands** → same pattern, `AUSPOST_API_KEY` into Secrets, manual run to confirm real tracking data comes back clean.
- **Branding/email/schedule confirmed** → update `default_template.yaml` and the cron line in `daily_report.yml` in one small PR, nothing else in the codebase should need to change for this.
- **All four land together** → first full live run, watch it together before calling it done.