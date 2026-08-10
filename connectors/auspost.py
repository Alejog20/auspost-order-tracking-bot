"""
Australia Post Shipping & Tracking API connector.

NOTE: the request/response shape below (AUTH-KEY header, digitalapi.auspost.com.au,
tracking_results/trackable_items/events) is a best-effort reconstruction from public
information, not verified against Australia Post's current live documentation --
their developer portal renders via JavaScript and couldn't be fetched directly.
Treat this as a first draft to confirm against real docs or a sample response once
AUSPOST_API_KEY is wired to a real account, same as the rest of the connector work
IMPLEMENTATION_PLAN.md already flags as blocked on live testing.
"""

import os
from datetime import date, datetime

import requests

from models import TrackingItem

API_URL = "https://digitalapi.auspost.com.au/shipping/v1/track"


class AusPostError(Exception):
    pass


def _fetch_tracking_result(tracking_number, api_key=None, api_url=API_URL):
    api_key = api_key or os.environ["AUSPOST_API_KEY"]
    response = requests.get(
        api_url,
        params={"tracking_ids": tracking_number},
        headers={"AUTH-KEY": api_key},
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

    status = trackable_item.get("status", "Unknown")
    category = _category_from_status(status)
    events = trackable_item.get("events") or []
    latest_event = events[0] if events else {}

    return TrackingItem(
        tracking_number=tracking_number,
        status=status,
        category=category,
        last_scan_time=_parse_datetime(latest_event.get("date")) or datetime.now(),
        last_scan_location=latest_event.get("location"),
        expected_delivery=_parse_date(trackable_item.get("expected_delivery_date")),
        collection_location=latest_event.get("location") if category == "awaiting_collection" else None,
    )


def get_tracking_item(tracking_number, api_key=None):
    payload = _fetch_tracking_result(tracking_number, api_key=api_key)
    return _map_to_tracking_item(tracking_number, payload)
