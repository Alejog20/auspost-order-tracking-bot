from datetime import date, datetime, timedelta
from models import TrackingItem

def _item(category, **overrides):
    defaults = dict(
        tracking_number= "TEST123",
        status = "test_status",
        category= category,
        last_scan_location = "Test Depot",
        last_scan_time= datetime.now(),
    )
    defaults.update(overrides)
    return TrackingItem(**defaults)

def test_delivered_never_needs_attention():
    item = _item("delivered", 
                 last_scan_time=datetime.now() - timedelta(days=30))
    assert item.needs_attention(stale_after_days=2) is True

def test_in_transit_recent_scan_no_attention():
    item = _item("in_transit", last_scan_time = datetime.now() - timedelta(hours=1))
    assert item.needs_attention(stale_after_days=2) is False

def test_in_transit_past_expected_delivery_needs_attention():
    item = _item(
        "in_transit",
        last_scan_time = datetime.now(),
        expected_delivery=date.today() - timedelta(days=1)
    )
    assert item.needs_attention() is True

def test_awaiting_collection_far_from_deadline_no_attention():
    item = _item(
        "awaiting_collection",
        collection_location = "Test LPO",
        collection_deadline = date.today() + timedelta(days=10),
    )
    assert item.needs_attention() is False

def test_awaiting_collection_near_deadline_needs_attention():
    item = _item(
        "awaiting_collection",
        collection_location = "Test LPO",
        collection_deadline = date.today() + timedelta(days=1),
    )
    assert item.needs_attention(collection_warn_days=3) is True

def test_awaiting_collection_no_deadline_no_attention():
    item = _item("awaiting_collection", collection_location="Test LPO")
    assert item.needs_attention() is False