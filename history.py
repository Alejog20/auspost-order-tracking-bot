import json
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).parent

def _read_history(log_path=None):
    log_path = Path(log_path) if log_path else BASE_DIR / "report_history.jsonl"
    if not log_path.exists():
        return []
    with open(log_path) as f:
        return [json.loads(line) for line in f if line.strip()]

def first_delivered_date(tracking_number, log_path=None):
    """
    Earliest date this tracking number was logged as delivered,
    or None if it has never shown up as delivered
    """
    earliest = None

    for entry in _read_history(log_path):
        entry_date = date.fromisoformat(entry["date"])
        for item in entry.get("items", []):
            if item["tracking_number"] != tracking_number:
                continue
            if item.get("category") != "delivered":
                continue
            if earliest is None or entry_date < earliest:
                earliest = entry_date

    return earliest

def should_drop(tracking_number, drop_after_days=3, log_path=None):
    """
    True if the shipment has been delivered for longer than drop_after_days
    and should be left out of today's report
    """
    delivered_since = first_delivered_date(tracking_number, log_path)
    if delivered_since is None:
        return False
    return (date.today() - delivered_since).days > drop_after_days

def filter_dropped_items(items, drop_after_days=3, log_path=None):
    """
    Removes shipments that have been sitting as delivered for more than
    drop_after_days variable, before they reach flagging or the report
    """
    return [
        item for item in items
        if not should_drop(item.tracking_number, drop_after_days, log_path)
    ]
