import pytest

from connectors import auspost


def _payload(status, events=None, expected_delivery_date=None):
    return {
        "tracking_results": [
            {
                "trackable_items": [
                    {
                        "consignment_id": "TEST123",
                        "number_of_items": 1,
                        "items": [
                            {
                                "status": status,
                                "events": events or [],
                                "expected_delivery_date": expected_delivery_date,
                            }
                        ],
                    }
                ]
            }
        ]
    }


def test_get_tracking_item_sends_auth_header_and_tracking_id(mocker):
    mock_response = mocker.Mock()
    mock_response.json.return_value = _payload("In Transit")
    mock_response.raise_for_status.return_value = None
    mock_get = mocker.patch("connectors.auspost.requests.get", return_value=mock_response)

    auspost.get_tracking_item(
        "ABC123",
        api_key_uuid="test-uuid",
        api_key_password="test-pass",
        account_number="12345",
    )

    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    assert kwargs["headers"] == {"Account-Number": "12345"}
    assert kwargs["auth"] == ("test-uuid", "test-pass")
    assert kwargs["params"] == {"tracking_ids": "ABC123"}


def test_get_tracking_item_maps_delivered_status(mocker):
    mock_response = mocker.Mock()
    mock_response.json.return_value = _payload(
        "Delivered",
        events=[{"description": "Delivered", "location": "Melbourne VIC", "date": "2026-08-01T10:00:00Z"}],
    )
    mock_response.raise_for_status.return_value = None
    mocker.patch("connectors.auspost.requests.get", return_value=mock_response)

    item = auspost.get_tracking_item(
        "ABC123", api_key_uuid="test-uuid", api_key_password="test-pass", account_number="12345"
    )

    assert item.category == "delivered"
    assert item.last_scan_location == "Melbourne VIC"


def test_get_tracking_item_maps_awaiting_collection_status(mocker):
    mock_response = mocker.Mock()
    mock_response.json.return_value = _payload(
        "Awaiting collection",
        events=[{"description": "Awaiting collection", "location": "Mount Beauty LPO", "date": "2026-08-01T10:00:00Z"}],
    )
    mock_response.raise_for_status.return_value = None
    mocker.patch("connectors.auspost.requests.get", return_value=mock_response)

    item = auspost.get_tracking_item(
        "ABC123", api_key_uuid="test-uuid", api_key_password="test-pass", account_number="12345"
    )

    assert item.category == "awaiting_collection"
    assert item.collection_location == "Mount Beauty LPO"


def test_get_tracking_item_raises_when_no_results(mocker):
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"tracking_results": []}
    mock_response.raise_for_status.return_value = None
    mocker.patch("connectors.auspost.requests.get", return_value=mock_response)

    with pytest.raises(auspost.AusPostError):
        auspost.get_tracking_item(
            "ABC123", api_key_uuid="test-uuid", api_key_password="test-pass", account_number="12345"
        )


def test_get_tracking_item_reads_credentials_from_environment(mocker):
    mocker.patch.dict(
        "os.environ",
        {"AUSPOST_UUID": "env-uuid", "AUSPOST_PASS": "env-pass", "AUSPOST_ACCT": "99999"},
    )
    mock_response = mocker.Mock()
    mock_response.json.return_value = _payload("In Transit")
    mock_response.raise_for_status.return_value = None
    mock_get = mocker.patch("connectors.auspost.requests.get", return_value=mock_response)

    auspost.get_tracking_item("ABC123")

    _, kwargs = mock_get.call_args
    assert kwargs["headers"] == {"Account-Number": "99999"}
    assert kwargs["auth"] == ("env-uuid", "env-pass")
