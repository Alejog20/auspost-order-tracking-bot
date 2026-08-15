# Implementation plan

Repo: https://github.com/Alejog20/auspost-order-tracking-bot

## Day 1 — done

- System architecture designed and diagrammed (`.drawio` + exported image)
- GitHub repository created, local codebase linked
- `.github/workflows/daily_report.yaml` created (schedule + secrets wiring)
- Claude API key created and tested
- Python project environment set up (uv)
- `history.py` and `.gitignore` written

## Day 2 — done

- `history.py` 3-day drop-off logic implemented and wired into `report_generator.py`
- `report_generator.py` updated: logs `category`, filters dropped items automatically before building the prompt
- `default_template.yaml` extended with `drop_after_days`
- Test suite implemented: `test_models.py`, `test_history.py`, `test_report_generator.py`, `pytest.ini`, `.github/workflows/tests.yaml`
- All 20 tests passing locally
- Decision made: email delivery via SMTP using our own address for now, Jay's preferred inbox to be swapped in once confirmed

## Day 3 — done, with one open caveat

1. **Australia Post connector** (`connectors/auspost.py`) — built against `AUTH-KEY` header + `digitalapi.auspost.com.au/shipping/v1/track`, mocked in `tests/test_auspost.py`. **Caveat:** best-effort reconstruction, not verified against Australia Post's live docs. Superseded on Day 4 — see below.
2. **Shopify connector** (`connectors/shopify.py`) — GraphQL Admin API, client credentials grant, 24h token auto-refresh built into `ShopifyClient`. Confirmed against current shopify.dev docs. Mocked in `tests/test_shopify.py`.
3. **`run_daily_report.py`** — wires Shopify connector → Australia Post connector → `report_generator.generate_report` (which applies `history.filter_dropped_items` internally) → email send. Skips items Australia Post can't find rather than failing the whole run; skips the email entirely (logs instead) if there are zero shipments for the day.
4. **Email sending module** (`delivery/email_sender.py`) — SMTP, reads `EMAIL_RECIPIENT` / `SMTP_USERNAME` / `SMTP_PASSWORD` / `SMTP_HOST` / `SMTP_PORT` from env, mocked in `tests/test_email_sender.py`.
5. All new modules mocked in tests, 34/34 passing.

## Day 4 (2026-08-15) — done, plus one production regression caught and fixed

1. **Australia Post auth scheme changed** — replaced the single `AUTH-KEY` header with the real three-part credential Australia Post's API actually expects: HTTP Basic Auth (`AUSPOST_UUID` / `AUSPOST_PASS`) plus an `Account-Number` header (`AUSPOST_ACCT`). `.env` already had these three values. **The request/response shape is still unverified against live docs** — same caveat as Day 3, just restructured around the correct credential model instead of a single key.
2. **Fixed a broken WIP commit** in `connectors/auspost.py` and `tests/test_auspost.py` — the credential-scheme migration above had been left mid-refactor: undefined variables (`tracking_number`, `consignment`), a mismatched `get_tracking_item` signature, a typo'd env var name (`AUSTPOST_ACCT`), and a test file with an unterminated string, a bad mock patch, and one test asserting values that didn't match its own fixture data. All fixed; added a new test covering the env-var credential fallback.
3. **Found and fixed a scheduling regression**: `.github/workflows/daily_report.yaml` — the actual cron job that runs the whole pipeline unattended — had been deleted entirely in commit `666ee40`, despite that commit's message describing it as removing one redundant test step. Only the CI test workflow (`tests.yaml`) remained; nothing was scheduled to run in production. Recreated the workflow, and while doing so fixed a second latent bug: **the original file never passed the SMTP/email secrets to the job at all** (`EMAIL_RECIPIENT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_HOST`), so even with a working Australia Post key the scheduled run would have failed at the send-email step with a `KeyError`. Updated secrets list: `ANTHROPIC_API_KEY`, `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, `AUSPOST_UUID`, `AUSPOST_PASS`, `AUSPOST_ACCT`, `EMAIL_RECIPIENT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_HOST`.
4. **PDF rendering exists in code but isn't a finished feature.** `report_generator.py` has `render_pdf_report` / `generate_pdf_report` and `templates/report_pdf.html`, but: it's Jinja2-rendered HTML styled for print, not an actual PDF — there's no HTML→PDF library in `pyproject.toml`; it's not wired into `run_daily_report.py` or `email_sender.py` (no attachment path); and it has **zero test coverage**, which breaks the project's testing non-negotiable. Treat PDF as unfinished, not "built, just not wired in."
5. 37/37 tests passing locally (`uv run pytest -v`).

## Known issue, not yet fixed

- `.gitignore` picked up a typo in the same commit that deleted the workflow file: `.env.` (trailing dot, matches almost nothing) where `.env.*` was almost certainly intended. Low risk since `.env` itself is still correctly ignored, but worth a one-line fix.

## Blocked — waiting on Jay

- Connecting the Australia Post connector to his real account (`AUSPOST_UUID` / `AUSPOST_PASS` / `AUSPOST_ACCT`), **and** confirming the connector's assumed request/response shape is actually correct
- Connecting the Shopify connector to his real store (staff account invite)
- A live end-to-end run against real data
- Whether a PDF format is still wanted, and if so, committing to an HTML→PDF library so it can actually be built out

## To define with Jay

- Company name, logo/emblem, and brand colors for the report template
- Which inbox the finished report should actually be sent to (currently sends from our own interim address)
- Time zone and exact hour the job should run (currently a placeholder: weekdays, 2:07pm Melbourne)
- The real values for `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, `AUSPOST_UUID`, `AUSPOST_PASS`, `AUSPOST_ACCT`
- Whether a PDF format is still wanted

## Next phase

Priority order, roughly independent of what's still blocked on Jay:

1. **Push GitHub Secrets and prove the schedule actually runs.** The interim SMTP address is already usable, so `SMTP_USERNAME` / `SMTP_PASSWORD` / `SMTP_HOST` / `EMAIL_RECIPIENT` can go into GitHub Secrets now, independent of Jay. Trigger `daily_report.yaml` manually via `workflow_dispatch` once — this validates the recreated workflow and the email-send path end-to-end, even while Shopify/Australia Post still return nothing real. Don't wait on Jay to catch further issues like the missing-secrets bug found today.
2. **Decide the PDF question, then either finish it or drop it.** Right now it's half-built code with no test coverage, sitting in a gray zone. If Jay confirms PDF is wanted: pick an HTML→PDF library, wire `generate_pdf_report` into an actual delivery path, write tests for it. If not wanted: delete `render_pdf_report` / `generate_pdf_report` / `report_pdf.html` rather than carrying dead, untested code.
3. **Fix the `.gitignore` typo** (`.env.` → `.env.*`), small standalone PR.
4. **When Shopify staff invite lands** → plug real `SHOPIFY_CLIENT_ID` / `SHOPIFY_CLIENT_SECRET` into GitHub Secrets, point the connector at his store, run once manually before trusting the schedule.
5. **When the Australia Post account lands** → plug real `AUSPOST_UUID` / `AUSPOST_PASS` / `AUSPOST_ACCT` into GitHub Secrets, manual run to confirm real tracking data comes back clean, and specifically confirm the request/response shape assumption from Day 4 against a real response (the one part of this connector still unverified).
6. **When branding/email/schedule are confirmed** → update `default_template.yaml` and the cron line in `daily_report.yaml` in one small PR, nothing else in the codebase should need to change for this.
7. **All inputs landed together** → first full live run, watch it together before calling it done.
