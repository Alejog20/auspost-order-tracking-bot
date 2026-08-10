import time

from connectors import shopify


def _client():
    return shopify.ShopifyClient(
        store_domain="test-shop.myshopify.com",
        client_id="cid",
        client_secret="csecret",
    )


def _token_response(mocker, expires_in=86399):
    response = mocker.Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"access_token": "tok_123", "expires_in": expires_in}
    return response


def test_refresh_token_posts_client_credentials(mocker):
    client = _client()
    mock_post = mocker.patch("connectors.shopify.requests.post", return_value=_token_response(mocker))

    client._ensure_token()

    mock_post.assert_called_once_with(
        "https://test-shop.myshopify.com/admin/oauth/access_token",
        data={
            "grant_type": "client_credentials",
            "client_id": "cid",
            "client_secret": "csecret",
        },
        timeout=10,
    )
    assert client._access_token == "tok_123"


def test_ensure_token_does_not_refetch_when_still_valid(mocker):
    client = _client()
    mock_post = mocker.patch("connectors.shopify.requests.post", return_value=_token_response(mocker))

    client._ensure_token()
    client._ensure_token()

    mock_post.assert_called_once()


def test_ensure_token_refreshes_when_near_expiry(mocker):
    client = _client()
    mocker.patch("connectors.shopify.requests.post", return_value=_token_response(mocker))
    client._ensure_token()

    client._expires_at = time.time() + 30  # inside the 60s refresh window
    mock_post = mocker.patch("connectors.shopify.requests.post", return_value=_token_response(mocker))
    client._ensure_token()

    mock_post.assert_called_once()


def test_graphql_sends_access_token_header(mocker):
    client = _client()
    mocker.patch("connectors.shopify.requests.post", return_value=_token_response(mocker))
    client._ensure_token()

    gql_response = mocker.Mock()
    gql_response.raise_for_status.return_value = None
    gql_response.json.return_value = {"data": {"ok": True}}
    mock_post = mocker.patch("connectors.shopify.requests.post", return_value=gql_response)

    result = client.graphql("query { ok }")

    assert result == {"ok": True}
    _, kwargs = mock_post.call_args
    assert kwargs["headers"] == {"X-Shopify-Access-Token": "tok_123"}


def test_graphql_raises_on_errors(mocker):
    client = _client()
    mocker.patch("connectors.shopify.requests.post", return_value=_token_response(mocker))
    client._ensure_token()

    gql_response = mocker.Mock()
    gql_response.raise_for_status.return_value = None
    gql_response.json.return_value = {"errors": [{"message": "bad query"}]}
    mocker.patch("connectors.shopify.requests.post", return_value=gql_response)

    try:
        client.graphql("query { bad }")
        assert False, "expected ShopifyError"
    except shopify.ShopifyError:
        pass


def test_get_todays_tracking_numbers_flattens_fulfillment_orders(mocker):
    client = mocker.Mock()
    client.graphql.return_value = {
        "orders": {
            "edges": [
                {
                    "node": {
                        "name": "#1001",
                        "fulfillmentOrders": {
                            "edges": [
                                {"node": {"trackingInfo": [{"number": "ABC123"}]}},
                                {"node": {"trackingInfo": [{"number": "XYZ789"}, {"number": None}]}},
                            ]
                        },
                    }
                }
            ]
        }
    }

    numbers = shopify.get_todays_tracking_numbers(client=client)

    assert numbers == ["ABC123", "XYZ789"]
