from unittest.mock import MagicMock, patch

import pytest

from betbot.odds_client import OddsApiClient, OddsApiError

CLIENT = OddsApiClient(api_key="k", base_url="https://api.the-odds-api.com/v4")


def _fake_response(json_body, status=200, headers=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_body
    resp.headers = headers or {}
    resp.text = str(json_body)
    return resp


@patch("betbot.odds_client.requests.get")
def test_get_odds_requires_exactly_one_of_bookmakers_or_regions(mock_get):
    with pytest.raises(ValueError):
        CLIENT.get_odds("icehockey_nhl", ["h2h"])
    with pytest.raises(ValueError):
        CLIENT.get_odds("icehockey_nhl", ["h2h"], bookmakers="pinnacle", regions="eu")
    mock_get.assert_not_called()


@patch("betbot.odds_client.requests.get")
def test_get_odds_uses_bookmakers_param(mock_get):
    mock_get.return_value = _fake_response([])
    CLIENT.get_odds("icehockey_nhl", ["h2h", "spreads"], bookmakers="pinnacle,bet99_ca_on")
    _, kwargs = mock_get.call_args
    assert kwargs["params"]["bookmakers"] == "pinnacle,bet99_ca_on"
    assert "regions" not in kwargs["params"]
    assert kwargs["params"]["markets"] == "h2h,spreads"


@patch("betbot.odds_client.requests.get")
def test_get_odds_uses_regions_param_for_discovery(mock_get):
    mock_get.return_value = _fake_response([])
    CLIENT.get_odds("icehockey_nhl", ["h2h"], regions="eu,ca")
    _, kwargs = mock_get.call_args
    assert kwargs["params"]["regions"] == "eu,ca"
    assert "bookmakers" not in kwargs["params"]


@patch("betbot.odds_client.requests.get")
def test_get_odds_raises_on_error_status(mock_get):
    mock_get.return_value = _fake_response({"message": "bad key"}, status=401)
    with pytest.raises(OddsApiError):
        CLIENT.get_odds("icehockey_nhl", ["h2h"], bookmakers="pinnacle")


@patch("betbot.odds_client.requests.get")
def test_list_sports_hits_free_endpoint(mock_get):
    mock_get.return_value = _fake_response([{"key": "americanfootball_nfl", "active": True}])
    CLIENT.list_sports()
    args, kwargs = mock_get.call_args
    assert args[0].endswith("/sports")
    assert "all" not in kwargs["params"]


@patch("betbot.odds_client.requests.get")
def test_get_events_costs_nothing_and_passes_time_window(mock_get):
    mock_get.return_value = _fake_response([])
    import datetime as dt

    frm = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    to = dt.datetime(2026, 1, 8, tzinfo=dt.timezone.utc)
    CLIENT.get_events("icehockey_nhl", frm, to)
    args, kwargs = mock_get.call_args
    assert args[0].endswith("/sports/icehockey_nhl/events")
    assert kwargs["params"]["commenceTimeFrom"] == "2026-01-01T00:00:00Z"
    assert kwargs["params"]["commenceTimeTo"] == "2026-01-08T00:00:00Z"


@patch("betbot.odds_client.requests.get")
def test_get_scores_sets_days_from(mock_get):
    mock_get.return_value = _fake_response([])
    CLIENT.get_scores("icehockey_nhl", days_from=2)
    _, kwargs = mock_get.call_args
    assert kwargs["params"]["daysFrom"] == 2


@patch("betbot.odds_client.time.sleep")
@patch("betbot.odds_client.requests.get")
def test_get_retries_on_429_then_succeeds(mock_get, mock_sleep):
    mock_get.side_effect = [
        _fake_response({"message": "rate limited"}, status=429),
        _fake_response([]),
    ]
    result = CLIENT.get_scores("icehockey_nhl")
    assert result == []
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()


@patch("betbot.odds_client.time.sleep")
@patch("betbot.odds_client.requests.get")
def test_get_raises_after_exhausting_429_retries(mock_get, mock_sleep):
    mock_get.return_value = _fake_response({"message": "rate limited"}, status=429)
    with pytest.raises(OddsApiError):
        CLIENT.get_scores("icehockey_nhl")
    assert mock_get.call_count == 3  # initial attempt + RATE_LIMIT_RETRIES
    assert mock_sleep.call_count == 2
