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
from datetime import date

import requests

TODAYS_ORDERS_QUERY = """
query TodaysOrders($query: String!) {
  orders(first: 50, query: $query) {
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


def get_todays_tracking_numbers(client=None):
    """
    Tracking numbers for every fulfillment on every order placed today.
    Hands off to the Australia Post connector for live status per number.
    """
    client = client or ShopifyClient()
    today = date.today().isoformat()
    data = client.graphql(TODAYS_ORDERS_QUERY, {"query": f"created_at:>={today}"})

    tracking_numbers = []
    for order_edge in data["orders"]["edges"]:
        for fo_edge in order_edge["node"]["fulfillmentOrders"]["edges"]:
            for info in fo_edge["node"]["trackingInfo"]:
                if info.get("number"):
                    tracking_numbers.append(info["number"])
    return tracking_numbers
