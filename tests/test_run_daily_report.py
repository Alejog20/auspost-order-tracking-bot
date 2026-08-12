import run_daily_report as entry
from connectors import auspost


def test_collect_tracking_items_skips_items_auspost_cant_find(mocker):
    mock_get_numbers = mocker.patch(
        "run_daily_report.shopify.get_active_tracking_numbers",
        return_value=["ABC123", "MISSING456"],
    )

    found_item = mocker.Mock()

    def fake_get_tracking_item(tracking_number):
        if tracking_number == "MISSING456":
            raise auspost.AusPostError("not found")
        return found_item

    mocker.patch("run_daily_report.auspost.get_tracking_item", side_effect=fake_get_tracking_item)

    items = entry.collect_tracking_items(lookback_days=7)

    assert items == [found_item]
    mock_get_numbers.assert_called_once_with(lookback_days=7)


def test_main_sends_email_with_generated_report(mocker):
    mock_collect = mocker.patch("run_daily_report.collect_tracking_items", return_value=[mocker.Mock()])
    mocker.patch(
        "run_daily_report.rg.load_template_config",
        return_value={
            "company_name": "Jay's Gifts",
            "report_title": "Daily Tracking Report",
            "shipment_lookback_days": 14,
        },
    )
    mocker.patch("run_daily_report.rg.generate_report", return_value="<html>report</html>")
    mock_send = mocker.patch("run_daily_report.send_report_email")

    entry.main()

    mock_collect.assert_called_once_with(lookback_days=14)
    mock_send.assert_called_once_with(
        subject="Jay's Gifts — Daily Tracking Report",
        html_body="<html>report</html>",
    )


def test_main_skips_send_when_no_items(mocker):
    mocker.patch(
        "run_daily_report.rg.load_template_config",
        return_value={"company_name": "Jay's Gifts", "report_title": "Daily Tracking Report"},
    )
    mocker.patch("run_daily_report.collect_tracking_items", return_value=[])
    mock_send = mocker.patch("run_daily_report.send_report_email")

    entry.main()

    mock_send.assert_not_called()
