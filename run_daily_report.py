"""
Production entrypoint for the daily tracking report, run by
.github/workflows/daily_report.yaml on schedule.

Shopify connector -> Australia Post connector -> report_generator
(which applies history.filter_dropped_items internally) -> email send.
"""

import logging

import report_generator as rg
from connectors import auspost, shopify
from delivery.email_sender import send_report_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def collect_tracking_items():
    tracking_numbers = shopify.get_todays_tracking_numbers()
    items = []
    for tracking_number in tracking_numbers:
        try:
            items.append(auspost.get_tracking_item(tracking_number))
        except auspost.AusPostError:
            logger.warning("No Australia Post tracking result for %s, skipping", tracking_number)
    return items


def main():
    items = collect_tracking_items()

    if not items:
        logger.info("No shipments to report today, skipping email send")
        return

    config = rg.load_template_config()
    html = rg.generate_report(items)
    send_report_email(
        subject=f"{config['company_name']} — {config['report_title']}",
        html_body=html,
    )
    logger.info("Sent daily report for %d shipment(s)", len(items))


if __name__ == "__main__":
    main()
