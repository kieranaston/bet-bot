from unittest.mock import MagicMock, patch

from betbot.telegram import TelegramClient


def _client() -> TelegramClient:
    return TelegramClient("token", "123")


def test_send_message_retries_without_parse_mode_on_failure():
    client = _client()
    fail = MagicMock(status_code=400, text='{"description":"can\'t parse entities"}')
    ok = MagicMock(status_code=200, text="{}")
    with patch("betbot.telegram.requests.post", side_effect=[fail, ok]) as post:
        assert client.send_message("*hello*") is True

    assert post.call_count == 2
    first_payload = post.call_args_list[0].kwargs["json"]
    second_payload = post.call_args_list[1].kwargs["json"]
    assert first_payload["parse_mode"] == "Markdown"
    assert "parse_mode" not in second_payload


def test_send_message_returns_false_when_plain_text_also_fails():
    client = _client()
    fail = MagicMock(status_code=400, text="bad")
    with patch("betbot.telegram.requests.post", return_value=fail):
        assert client.send_message("hello") is False


def test_get_updates_deletes_webhook_and_retries_on_409():
    client = _client()
    conflict = MagicMock(status_code=409, text="Conflict: webhook is active")
    ok = MagicMock(status_code=200)
    ok.json.return_value = {"result": [{"update_id": 1}]}
    deleted = MagicMock(status_code=200)

    with (
        patch("betbot.telegram.requests.get", side_effect=[conflict, ok]) as get,
        patch("betbot.telegram.requests.post", return_value=deleted) as post,
    ):
        updates = client.get_updates(offset=10)

    assert updates == [{"update_id": 1}]
    assert get.call_count == 2
    assert post.call_args.args[0].endswith("/deleteWebhook")
    assert get.call_args_list[0].kwargs["params"]["offset"] == 10
