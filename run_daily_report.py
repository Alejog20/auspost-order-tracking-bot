"""
Entrypoint for the daily tracking report, run by
.github/workflows/daily_report.yaml on schedule

Shopify connector -> Australia Post connector -> report_generator
(which applies history.filter_dropped_items internally) -> email send.
"""

import logging
from datetime import date

import report_generator as rg
from dotenv import load_dotenv
from connectors import auspost, shopify
from delivery.email_sender import send_report_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def collect_tracking_items(lookback_days=10):
    tracking_numbers = shopify.get_active_tracking_numbers(lookback_days=lookback_days)
    items = []
    for tracking_number in tracking_numbers:
        try:
            items.append(auspost.get_tracking_item(tracking_number))
        except auspost.AusPostError:
            logger.warning("No Australia Post tracking result for %s, skipping", tracking_number)
    return items


def main():
    config = rg.load_template_config()
    items = collect_tracking_items(lookback_days=config.get("shipment_lookback_days", 10))

    if not items:
        logger.info("No shipments to report today, skipping email send")
        return

    html = rg.generate_report(items)
    if html is None:
        logger.info("All shipments already reported as delivered, skipping email send")
        return

    spreadsheet = rg.generate_status_spreadsheet(items)

    send_report_email(
        subject=f"{config['company_name']} — {config['report_title']}",
        html_body=html,
        logo_path=config.get("logo_path"),
        attachment_bytes=spreadsheet,
        attachment_filename=f"tracking-status-{date.today().isoformat()}.xlsx",
    )
    logger.info("Sent daily report for %d shipment(s)", len(items))


if __name__ == "__main__":
    load_dotenv()
    main()
