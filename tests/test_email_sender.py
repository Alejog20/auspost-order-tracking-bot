from delivery.email_sender import send_report_email


def test_send_report_email_logs_in_and_sends(mocker):
    mock_smtp_instance = mocker.Mock()
    mock_smtp_instance.__enter__ = mocker.Mock(return_value=mock_smtp_instance)
    mock_smtp_instance.__exit__ = mocker.Mock(return_value=False)
    mock_smtp = mocker.patch("delivery.email_sender.smtplib.SMTP", return_value=mock_smtp_instance)

    send_report_email(
        subject="Daily Tracking Report",
        html_body="<p>hello</p>",
        recipient="jay@example.com",
        sender="bot@example.com",
        password="secret",
        smtp_host="smtp.example.com",
        smtp_port=587,
    )

    mock_smtp.assert_called_once_with("smtp.example.com", 587)
    mock_smtp_instance.starttls.assert_called_once()
    mock_smtp_instance.login.assert_called_once_with("bot@example.com", "secret")

    args, _ = mock_smtp_instance.sendmail.call_args
    assert args[0] == "bot@example.com"
    assert args[1] == ["jay@example.com"]
    assert "hello" in args[2]


def test_send_report_email_reads_defaults_from_env(mocker, monkeypatch):
    monkeypatch.setenv("EMAIL_RECIPIENT", "jay@example.com")
    monkeypatch.setenv("SMTP_USERNAME", "bot@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")

    mock_smtp_instance = mocker.Mock()
    mock_smtp_instance.__enter__ = mocker.Mock(return_value=mock_smtp_instance)
    mock_smtp_instance.__exit__ = mocker.Mock(return_value=False)
    mocker.patch("delivery.email_sender.smtplib.SMTP", return_value=mock_smtp_instance)

    send_report_email(subject="Daily Tracking Report", html_body="<p>hello</p>")

    mock_smtp_instance.login.assert_called_once_with("bot@example.com", "secret")
