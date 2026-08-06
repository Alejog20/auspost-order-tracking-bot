import json
from datetime import date, datetime, timedelta

from models import TrackingItem
import history


def _item(tracking_number):
    return TrackingItem(
        tracking_number=tracking_number,
        status="test_status",
        category="in_transit",
        last_scan_time=datetime.now(),
    )


def _write_log(log_path, entries):
    with open(log_path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def test_first_delivered_date_returns_earliest_entry(tmp_path):
    log_path = tmp_path / "history.jsonl"
    _write_log(log_path, [
        {
            "date": (date.today() - timedelta(days=5)).isoformat(),
            "items": [{"tracking_number": "ABC123", "category": "delivered"}],
        },
        {
            "date": (date.today() - timedelta(days=2)).isoformat(),
            "items": [{"tracking_number": "ABC123", "category": "delivered"}],
        },
    ])

    result = history.first_delivered_date("ABC123", log_path=log_path)

    assert result == date.today() - timedelta(days=5)


def test_first_delivered_date_ignores_non_delivered_and_other_numbers(tmp_path):
    log_path = tmp_path / "history.jsonl"
    _write_log(log_path, [
        {
            "date": date.today().isoformat(),
            "items": [
                {"tracking_number": "ABC123", "category": "in_transit"},
                {"tracking_number": "XYZ789", "category": "delivered"},
            ],
        },
    ])

    assert history.first_delivered_date("ABC123", log_path=log_path) is None


def test_first_delivered_date_no_history_file_returns_none(tmp_path):
    log_path = tmp_path / "missing.jsonl"
    assert history.first_delivered_date("ABC123", log_path=log_path) is None


def test_should_drop_true_past_threshold(tmp_path):
    log_path = tmp_path / "history.jsonl"
    _write_log(log_path, [
        {
            "date": (date.today() - timedelta(days=10)).isoformat(),
            "items": [{"tracking_number": "ABC123", "category": "delivered"}],
        },
    ])

    assert history.should_drop("ABC123", drop_after_days=3, log_path=log_path) is True


def test_should_drop_false_within_threshold(tmp_path):
    log_path = tmp_path / "history.jsonl"
    _write_log(log_path, [
        {
            "date": (date.today() - timedelta(days=1)).isoformat(),
            "items": [{"tracking_number": "ABC123", "category": "delivered"}],
        },
    ])

    assert history.should_drop("ABC123", drop_after_days=3, log_path=log_path) is False


def test_should_drop_false_when_never_delivered(tmp_path):
    log_path = tmp_path / "missing.jsonl"
    assert history.should_drop("ABC123", drop_after_days=3, log_path=log_path) is False


def test_filter_dropped_items_removes_stale_delivered(tmp_path):
    log_path = tmp_path / "history.jsonl"
    _write_log(log_path, [
        {
            "date": (date.today() - timedelta(days=10)).isoformat(),
            "items": [{"tracking_number": "ABC123", "category": "delivered"}],
        },
    ])

    items = [_item("ABC123"), _item("XYZ789")]

    result = history.filter_dropped_items(items, drop_after_days=3, log_path=log_path)

    assert [i.tracking_number for i in result] == ["XYZ789"]
