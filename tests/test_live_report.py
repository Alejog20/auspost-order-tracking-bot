"""
Live smoke test: Australia Post -> report_generator -> email_sender, using
TEST_ORDERS instead of the Shopify connector.

Hits real external services (Australia Post API, Claude API, real SMTP send)
and is excluded from the default test run by the `live` marker. Run it
explicitly:

    uv run pytest -m live tests/test_live_report.py -v -s
"""

import os

import pytest
from dotenv import load_dotenv

import report_generator as rg
from connectors import auspost
from delivery.email_sender import send_report_email

pytestmark = pytest.mark.live


def _tracking_numbers_from_env():
    load_dotenv()
    raw = os.environ["TEST_ORDERS"]
    return [t.strip() for t in raw.split(",") if t.strip()]


def _collect_tracking_items(tracking_numbers):
    items = []
    for tracking_number in tracking_numbers:
        try:
            items.append(auspost.get_tracking_item(tracking_number))
        except auspost.AusPostError:
            pytest.fail(f"No Australia Post tracking result for {tracking_number}")
    return items


def test_sends_live_report_for_test_orders():
    tracking_numbers = _tracking_numbers_from_env()
    assert tracking_numbers, "TEST_ORDERS is empty -- set it in .env to real tracking numbers"

    items = _collect_tracking_items(tracking_numbers)
    assert items

    config = rg.load_template_config()
    html = rg.generate_report(items)

    send_report_email(
        subject=f"{config['company_name']} — {config['report_title']} (TEST)",
        html_body=html,
    )
