import json
from datetime import date, datetime, timedelta

import pytest

import report_generator as rg
from models import TrackingItem


@pytest.fixture
def config():
    return rg.load_template_config()


@pytest.fixture
def sample_items():
    return [
        TrackingItem(
            tracking_number="ABC123",
            status="In transit",
            category="in_transit",
            last_scan_time=datetime.now(),
            expected_delivery=date.today() + timedelta(days=3),
            expected_delivery_label="Fri 7 - Mon 10 Aug",
        ),
        TrackingItem(
            tracking_number="XYZ789",
            status="Awaiting collection",
            category="awaiting_collection",
            last_scan_time=datetime.now(),
            collection_location="Mount Beauty LPO",
            collection_deadline=date.today() + timedelta(days=5),
        ),
    ]


def test_build_prompt_includes_tracking_numbers(config, sample_items):
    _, shipment_block = rg.build_prompt(sample_items, config)
    assert "ABC123" in shipment_block
    assert "XYZ789" in shipment_block


def test_build_prompt_awaiting_collection_includes_deadline_not_delivery_window(
    config,
    sample_items,
):
    _, shipment_block = rg.build_prompt(sample_items, config)
    collection_line = [l for l in shipment_block.split("\n") if "XYZ789" in l][0]

    assert "Mount Beauty LPO" in collection_line
    assert "expected delivery window" not in collection_line


def test_prepare_render_context_buckets_items_correctly(config, sample_items):
    narrative = {
        "summary_headline": "test_headline",
        "items": [
            {
                "tracking_number": "ABC123",
                "narrative": "in transit narrative",
            },
            {
                "tracking_number": "XYZ789",
                "narrative": "collection narrative",
            },
        ],
    }

    context = rg._prepare_render_context(sample_items, config, narrative)

    counts = {s["label"]: s["count"] for s in context["stats"]}

    assert counts["In transit"] == 1
    assert counts["Awaiting collection"] == 1
    assert counts["Delivered"] == 0


def test_render_report_includes_narrative_text(config, sample_items):
    narrative = {
        "summary_headline": "test headline",
        "items": [
            {
                "tracking_number": "ABC123",
                "narrative": "in transit narrative",
            },
            {
                "tracking_number": "XYZ789",
                "narrative": "collection narrative",
            },
        ],
    }

    html = rg._render_report(sample_items, config, narrative)

    assert "in transit narrative" in html
    assert "ABC123" in html


def test_log_report_writes_category(config, sample_items, tmp_path):
    log_path = tmp_path / "history.jsonl"

    rg.log_report(sample_items, config, log_path=log_path)

    entry = json.loads(log_path.read_text().splitlines()[0])

    categories = {
        i["tracking_number"]: i["category"]
        for i in entry["items"]
    }

    assert categories["ABC123"] == "in_transit"
    assert categories["XYZ789"] == "awaiting_collection"


def test_call_claude_parses_json_response(mocker):
    """
    Mocked; doesn't hit the real API.
    This pattern can be reused for the Shopify and AusPost connectors.
    """

    fake_response = mocker.Mock()
    fake_response.content = [
        mocker.Mock(
            text='{"summary_headline":"ok","items":[]}'
        )
    ]

    mock_client = mocker.Mock()
    mock_client.messages.create.return_value = fake_response

    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    result = rg.call_claude("system prompt", "shipment block")

    assert result == {
        "summary_headline": "ok",
        "items": [],
    }

    mock_client.messages.create.assert_called_once()


def test_call_claude_strips_markdown_code_fence(mocker):
    """
    Real Claude responses sometimes wrap JSON in a ```json ... ``` fence
    even when asked to respond as JSON only -- confirmed against a live call.
    """

    fake_response = mocker.Mock()
    fake_response.content = [
        mocker.Mock(
            text='```json\n{"summary_headline":"ok","items":[]}\n```'
        )
    ]

    mock_client = mocker.Mock()
    mock_client.messages.create.return_value = fake_response

    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    result = rg.call_claude("system prompt", "shipment block")

    assert result == {
        "summary_headline": "ok",
        "items": [],
    }