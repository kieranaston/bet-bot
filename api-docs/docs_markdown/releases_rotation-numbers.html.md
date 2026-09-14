<!-- Source: https://the-odds-api.com/releases/rotation-numbers.html -->

Title: Rotation Numbers

URL Source: https://the-odds-api.com/releases/rotation-numbers.html

Markdown Content:
2025-November-04

Rotation numbers are now available in The Odds API. Home team and away team rotation numbers are returned in the API response by providing the `includeRotationNumbers=true` parameter when using the following endpoints:

*   [Odds](https://the-odds-api.com/liveapi/guides/v4/#get-odds)
*   [Events](https://the-odds-api.com/liveapi/guides/v4/#get-events)
*   [Event-odds](https://the-odds-api.com/liveapi/guides/v4/#get-event-odds)
*   [Historical odds](https://the-odds-api.com/liveapi/guides/v4/#get-historical-odds)
*   [Historical events](https://the-odds-api.com/liveapi/guides/v4/#get-historical-events)
*   [Historical event-odds](https://the-odds-api.com/liveapi/guides/v4/#get-historical-event-odds)

## [#](https://the-odds-api.com/releases/rotation-numbers.html#availability) Availability

Rotation numbers are populated on a best-effort basis and can be null in some situations.

*   Rotation numbers can be null when new games first appear in the API. We use a variety of sources for game and rotation number information, and game listings on these sources won't always be in sync.

*   Rotation numbers can be null for games listed far out. The API can return games that are months away if sportsbooks have odds available. These games can have null rotation numbers until they are closer to the game date.

*   Rotation numbers are only available for the top US sports, including: NFL, NCAAF, MLB, NBA, NCAAB, WNBA and NHL.

## [#](https://the-odds-api.com/releases/rotation-numbers.html#examples) Examples

**Example Request**

```
https://api.the-odds-api.com/v4/sports/americanfootball_nfl/events?apiKey={apiKey}&includeRotationNumbers=true
```

**Example Response**

```
[
    {
        "id": "13bdffda97e8fb13179fe3f2f69d66f8",
        "sport_key": "americanfootball_nfl",
        "sport_title": "NFL",
        "commence_time": "2025-11-07T01:15:00Z",
        "home_team": "Denver Broncos",
        "away_team": "Las Vegas Raiders",
        "home_rotation": 110,
        "away_rotation": 109
    },
    {
        "id": "42473c1ddf8f424069ff3f264dd8dca4",
        "sport_key": "americanfootball_nfl",
        "sport_title": "NFL",
        "commence_time": "2025-11-09T14:30:00Z",
        "home_team": "Indianapolis Colts",
        "away_team": "Atlanta Falcons",
        "home_rotation": 252,
        "away_rotation": 251
    },
    ...
```

## [#](https://the-odds-api.com/releases/rotation-numbers.html#get-started) Get Started

For more info on getting started, [see the docs](https://the-odds-api.com/liveapi/guides/4/).

To get started with a free API key, [see our plans](https://the-odds-api.com/#get-access).
