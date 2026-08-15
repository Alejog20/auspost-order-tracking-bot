from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class TrackingItem:
    """The shared shape for a shipment, regardless of where its data came from."""

    tracking_number: str
    status: str
    category: str  # delivered | in_transit | awaiting_collection
    last_scan_time: datetime
    last_scan_location: str | None = None
    expected_delivery: date | None = None
    expected_delivery_label: str | None = None
    collection_deadline: date | None = None
    collection_location: str | None = None

    @property
    def days_since_scan(self) -> int:
        now = datetime.now(self.last_scan_time.tzinfo)
        return (now - self.last_scan_time).days

    def needs_attention(self, stale_after_days=2, collection_warn_days=3):
        if self.category == "delivered":
            return False

        if self.category == "awaiting_collection":
            if self.collection_deadline is None:
                return False
            return (self.collection_deadline - date.today()).days <= collection_warn_days

        if self.expected_delivery is not None and self.expected_delivery < date.today():
            return True
        return self.days_since_scan > stale_after_days
