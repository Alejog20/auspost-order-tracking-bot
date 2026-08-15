"""
Australia Post Shipping & Tracking API connector.
"""

import os
from datetime import date, datetime
import requests
from models import TrackingItem

API_URL = "https://digitalapi.auspost.com.au/shipping/v1/track"


class AusPostError(Exception):
    pass


def _fetch_tracking_result(
    tracking_number,
    api_key_uuid=None,
    api_key_password=None,
    account_number=None,
    api_url=API_URL,
):
    api_key_uuid = api_key_uuid or os.environ["AUSPOST_UUID"]
    api_key_password = api_key_password or os.environ["AUSPOST_PASS"]
    account_number = account_number or os.environ["AUSPOST_ACCT"]

    response = requests.get(
        api_url,
        params={"tracking_ids": tracking_number},
        headers={"Account-Number": account_number},
        auth=(api_key_uuid, api_key_password),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def _category_from_status(status):
    normalized = (status or "").lower()
    if "delivered" in normalized:
        return "delivered"
    if "collect" in normalized:
        return "awaiting_collection"
    return "in_transit"


def _parse_datetime(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_date(value):
    if not value:
        return None
    return date.fromisoformat(value[:10])


def _map_to_tracking_item(tracking_number, payload):
    results = payload.get("tracking_results") or []
    if not results:
        raise AusPostError(f"No tracking result returned for {tracking_number}")

    trackable_items = results[0].get("trackable_items") or [{}]
    trackable_item = trackable_items[0]

    items = trackable_item.get("items") or [{}]
    item = items[0]

    status = item.get("status", "Unknown")
    category = _category_from_status(status)
    events = item.get("events") or []
    latest_event = events[0] if events else {}

    return TrackingItem(
        tracking_number=tracking_number,
        status=status,
        category=category,
        last_scan_time=_parse_datetime(latest_event.get("date")) or datetime.now(),
        last_scan_location=latest_event.get("location"),
        expected_delivery=_parse_date(item.get("expected_delivery_date")),
        collection_location=latest_event.get("location") if category == "awaiting_collection" else None,
    )


def get_tracking_item(
    tracking_number,
    api_key_uuid=None,
    api_key_password=None,
    account_number=None,
):
    payload = _fetch_tracking_result(
        tracking_number,
        api_key_uuid=api_key_uuid,
        api_key_password=api_key_password,
        account_number=account_number,
    )
    return _map_to_tracking_item(tracking_number, payload)
