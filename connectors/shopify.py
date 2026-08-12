"""
Shopify Admin API connector.

Uses the GraphQL Admin API (Shopify has marked the REST Admin API as legacy;
new integrations should be built on GraphQL) and the client credentials grant,
per shopify.dev: POST client_id/client_secret to /admin/oauth/access_token,
get back a token valid for ~24h (expires_in: 86399), send it back as
X-Shopify-Access-Token on every subsequent call. Refresh is handled internally
so nothing outside this module has to think about the 24h expiry.
"""

import os
import time
from datetime import date, timedelta

import requests

ACTIVE_ORDERS_QUERY = """
query ActiveOrders($query: String!, $cursor: String) {
  orders(first: 250, after: $cursor, query: $query) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        name
        fulfillmentOrders(first: 10) {
          edges {
            node {
              trackingInfo {
                number
              }
            }
          }
        }
      }
    }
  }
}
"""


class ShopifyError(Exception):
    pass


class ShopifyClient:
    def __init__(self, store_domain=None, client_id=None, client_secret=None, api_version="2026-07"):
        self.store_domain = store_domain or os.environ["SHOPIFY_STORE_DOMAIN"]
        self.client_id = client_id or os.environ["SHOPIFY_CLIENT_ID"]
        self.client_secret = client_secret or os.environ["SHOPIFY_CLIENT_SECRET"]
        self.api_version = api_version
        self._access_token = None
        self._expires_at = 0

    def _token_url(self):
        return f"https://{self.store_domain}/admin/oauth/access_token"

    def _graphql_url(self):
        return f"https://{self.store_domain}/admin/api/{self.api_version}/graphql.json"

    def _refresh_token(self):
        response = requests.post(
            self._token_url(),
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        self._access_token = payload["access_token"]
        self._expires_at = time.time() + payload.get("expires_in", 0)

    def _ensure_token(self):
        # refresh a minute early rather than racing the real expiry
        if self._access_token is None or time.time() >= self._expires_at - 60:
            self._refresh_token()

    def graphql(self, query, variables=None):
        self._ensure_token()
        response = requests.post(
            self._graphql_url(),
            json={"query": query, "variables": variables or {}},
            headers={"X-Shopify-Access-Token": self._access_token},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if "errors" in payload:
            raise ShopifyError(str(payload["errors"]))
        return payload["data"]


def get_active_tracking_numbers(client=None, lookback_days=10):
    """
    Tracking numbers for every fulfillment on any order fulfilled (fully or
    partially) in the last `lookback_days` days.

    Replaces the old "orders created today" query: that version only ever
    looked at orders placed the same day, so a gift that shipped two days
    ago and is still in transit silently stopped being checked. This keeps
    rechecking every shipment in the lookback window until Australia Post
    reports it delivered; once delivered, history.py's drop-off filter is
    what stops it from showing up in the report, not this query.

    `lookback_days` should comfortably exceed how long a parcel normally
    takes to arrive. It's read from `shipment_lookback_days` in
    templates/default_template.yaml, so it can be tuned without a code change.
    """
    client = client or ShopifyClient()
    cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()
    search_query = (
        f"created_at:>={cutoff} AND "
        "(fulfillment_status:fulfilled OR fulfillment_status:partial)"
    )

    tracking_numbers = []
    cursor = None
    while True:
        data = client.graphql(ACTIVE_ORDERS_QUERY, {"query": search_query, "cursor": cursor})
        orders = data["orders"]
        for order_edge in orders["edges"]:
            for fo_edge in order_edge["node"]["fulfillmentOrders"]["edges"]:
                for info in fo_edge["node"]["trackingInfo"]:
                    if info.get("number"):
                        tracking_numbers.append(info["number"])

        if not orders["pageInfo"]["hasNextPage"]:
            break
        cursor = orders["pageInfo"]["endCursor"]

    return tracking_numbers
