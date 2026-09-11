<!-- Source: https://the-odds-api.com/liveapi/guides/v4/ -->

Title: Documentation for sports odds API V4

URL Source: https://the-odds-api.com/liveapi/guides/v4/

Published Time: Wed, 10 Sep 2025 21:05:01 GMT

Markdown Content:
## [#](https://the-odds-api.com/liveapi/guides/v4/#overview) Overview

Get started with The Odds API in **3 steps**

**Step 1**

Get an API key via email

See plans

**Step 2**

Get a list of in-season sports

[Details](https://the-odds-api.com/liveapi/guides/v4/#get-sports)

**Step 3**

Use the sport **key** from step 2 to get a list of upcoming events and odds from different bookmakers

Use the `oddsFormat` parameter to show odds in either decimal or American format

[Details](https://the-odds-api.com/liveapi/guides/v4/#get-odds)

## [#](https://the-odds-api.com/liveapi/guides/v4/#host) Host

All requests use the host `https://api.the-odds-api.com`

Connections that require IPv6 can use `https://ipv6-api.the-odds-api.com`

## [#](https://the-odds-api.com/liveapi/guides/v4/#get-sports) GET sports

Returns a list of in-season sport objects. The sport key can be used as the `sport` parameter in other endpoints. This endpoint does not count against the usage quota.

### [#](https://the-odds-api.com/liveapi/guides/v4/#endpoint) Endpoint

**GET** /v4/sports/?apiKey={apiKey}

### [#](https://the-odds-api.com/liveapi/guides/v4/#parameters) Parameters

*   **apiKey** The API key associated with your subscription. [See usage plans](https://the-odds-api.com/#get-access)

*   **all** Optional - if this parameter is set to true (`all=true`), a list of both in and out of season sports will be returned

### [#](https://the-odds-api.com/liveapi/guides/v4/#schema) Schema

For a detailed API spec, see the [Swagger API docs(opens new window)](https://app.swaggerhub.com/apis-docs/the-odds-api/odds-api/4?view=uiDocs#/sports/get_v4_sports)

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-request) Example Request

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-response) Example Response

Calls to the /sports endpoint will not affect the quota usage. The following response headers are returned:

*   **x-requests-remaining** The usage credits remaining until the quota resets
*   **x-requests-used** The usage credits used since the last quota reset
*   **x-requests-last** The usage cost of the last API call

### [#](https://the-odds-api.com/liveapi/guides/v4/#usage-quota-costs) Usage Quota Costs

This endpoint does not count against the usage quota.

## [#](https://the-odds-api.com/liveapi/guides/v4/#get-odds) GET odds

Returns a list of upcoming and live games with recent odds for a given sport, region and market

### [#](https://the-odds-api.com/liveapi/guides/v4/#endpoint-2) Endpoint

**GET** /v4/sports/{sport}/odds/?apiKey={apiKey}&regions={regions}&markets={markets}

### [#](https://the-odds-api.com/liveapi/guides/v4/#parameters-2) Parameters

*   **sport** The sport key obtained from calling the /sports endpoint. `upcoming` is always valid, returning any live games as well as the next 8 upcoming games across all sports

*   **apiKey** The API key associated with your subscription. [See usage plans](https://the-odds-api.com/#get-access)

*   **regions** Determines the bookmakers to be returned. For example, `us`, `us2` (United States), `uk` (United Kingdom), `au` (Australia) and `eu` (Europe). Multiple regions can be specified if comma delimited. See the [list of bookmakers by region](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html).

*   **markets** Optional - Determines which odds market is returned. Defaults to `h2h` (head to head / moneyline). Valid markets are `h2h` (moneyline), `spreads` (points handicaps), `totals` (over/under) and `outrights` (futures). Multiple markets can be specified if comma delimited. `spreads` and `totals` markets are mainly available for US sports and bookmakers at this time. Each specified market costs 1 against the usage quota, for each region.

Lay odds are automatically included with `h2h` results for relevant betting exchanges (Betfair, Matchbook etc). These have a `h2h_lay` market key.

For sports with outright markets (such as Golf), the market will default to `outrights` if not specified. Lay odds for outrights (`outrights_lay`) will automatically be available for relevant exchanges.

For more info, see [descriptions of betting markets](https://the-odds-api.com/sports-odds-data/betting-markets.html).

*   **dateFormat** Optional - Determines the format of timestamps in the response. Valid values are `unix` and `iso` (ISO 8601). Defaults to `iso`.

*   **oddsFormat** Optional - Determines the format of odds in the response. Valid values are `decimal` and `american`. Defaults to `decimal`. When set to `american`, small discrepancies might exist for some bookmakers due to rounding errors.

*   **eventIds** Optional - Comma-separated game ids. Filters the response to only return games with the specified ids.

*   **bookmakers** Optional - Comma-separated list of bookmakers to be returned. If both `bookmakers` and `regions` are both specified, `bookmakers` takes priority. Bookmakers can be from any region. Every group of 10 bookmakers is the equivalent of 1 region. For example, specifying up to 10 bookmakers counts as 1 region. Specifying between 11 and 20 bookmakers counts as 2 regions.

*   **commenceTimeFrom** Optional - filter the response to show games that commence on and after this parameter. Values are in ISO 8601 format, for example 2023-09-09T00:00:00Z. This parameter has no effect if the sport is set to 'upcoming'.

*   **commenceTimeTo** Optional - filter the response to show games that commence on and before this parameter. Values are in ISO 8601 format, for example 2023-09-10T23:59:59Z. This parameter has no effect if the sport is set to 'upcoming'.

*   **includeLinks** Optional - if `true`, the response will include bookmaker links to events, markets, and betslips if available. Valid values are `true` or `false`

*   **includeSids** Optional - if `true`, the response will include source ids (bookmaker ids) for events, markets and outcomes if available. Valid values are `true` or `false`. This field can be useful to construct your own links to handle variations in state or mobile app links.

*   **includeBetLimits** Optional - if `true`, the response will include the bet limit of each betting option, mainly available for betting exchanges. Valid values are `true` or `false`

*   **includeRotationNumbers** Optional - if `true`, the response will include the home and away rotation numbers if available. See [this link](https://the-odds-api.com/releases/rotation-numbers.html) for details. Valid values are `true` or `false`.

### [#](https://the-odds-api.com/liveapi/guides/v4/#schema-2) Schema

For a detailed API spec, see the [Swagger API docs (opens new window)](https://app.swaggerhub.com/apis-docs/the-odds-api/odds-api/4?view=uiDocs#/current%20events/get_v4_sports__sport__odds)

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-request-2) Example Request

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-response-2) Example Response

The following response headers are returned

*   **x-requests-remaining** The usage credits remaining until the quota resets
*   **x-requests-used** The usage credits used since the last quota reset
*   **x-requests-last** The usage cost of the last API call

### [#](https://the-odds-api.com/liveapi/guides/v4/#usage-quota-costs-2) Usage Quota Costs

The usage quota cost is 1 per region per market.

**Examples**

*   **1 market, 1 region**

Cost: 1 

Example `/v4/sports/americanfootball_nfl/odds?markets=h2h&regions=us&...`

*   **3 markets, 1 region**

Cost: 3 

Example `/v4/sports/americanfootball_nfl/odds?markets=h2h,spreads,totals&regions=us&...`

*   **1 market, 3 regions**

Cost: 3 

Example `/v4/sports/soccer_epl/odds?markets=h2h&regions=us,uk,eu&...`

*   **3 markets, 3 regions**

Cost: 9 

Example: `/v4/sports/basketball_nba/odds?markets=h2h,spreads,totals&regions=us,uk,au&...`

Keeping track of quota usage

To keep track of usage credits, every API call includes the following response headers:

*   **x-requests-remaining** The usage credits remaining until the quota resets
*   **x-requests-used** The usage credits used since the last quota reset
*   **x-requests-last** The usage cost of the last API call

### [#](https://the-odds-api.com/liveapi/guides/v4/#more-info) More info

*   The list of events returned in the /odds endpoint mirrors events that are listed by major bookmakers. This usually includes games for the current round
*   Events may temporarily become unavailable after a round, before bookmakers begin listing the next round of games
*   Events may be unavailable if the sport is not in season. For popular sports, bookmakers may begin listing new season events a few months in advance
*   If no events are returned, the request will not count against the usage quota
*   To determine if an event is in-play, the `commence_time` can be used. If `commence_time` is less than the current time, the event is in-play. The /odds endpoint does not return completed events

## [#](https://the-odds-api.com/liveapi/guides/v4/#get-scores) GET scores

Returns a list of upcoming, live and recently completed games for a given sport. Live and recently completed games contain scores. Games from up to 3 days ago can be returned using the `daysFrom` parameter. Live scores update approximately every 30 seconds.

The scores endpoint applies to selected sports and is gradually being expanded to more sports. See the current [list of covered sports and leagues](https://the-odds-api.com/sports-odds-data/sports-apis.html).

### [#](https://the-odds-api.com/liveapi/guides/v4/#endpoint-3) Endpoint

**GET** /v4/sports/{sport}/scores/?apiKey={apiKey}&daysFrom={daysFrom}&dateFormat={dateFormat}

### [#](https://the-odds-api.com/liveapi/guides/v4/#parameters-3) Parameters

*   **sport** The sport key obtained from calling the /sports endpoint.

*   **apiKey** The API key associated with your subscription. [See usage plans](https://the-odds-api.com/#get-access)

*   **daysFrom** Optional - The number of days in the past from which to return completed games. Valid values are integers from `1` to `3`. If this parameter is missing, only live and upcoming games are returned.

*   **dateFormat** Optional - Determines the format of timestamps in the response. Valid values are `unix` and `iso` (ISO 8601). Defaults to `iso`.

*   **eventIds** Optional - Comma-separated game ids. Filters the response to only return games for the specified game ids.

### [#](https://the-odds-api.com/liveapi/guides/v4/#schema-3) Schema

For the detailed API spec, see the [Swagger API docs (opens new window)](https://app.swaggerhub.com/apis-docs/the-odds-api/odds-api/4?view=uiDocs#/current%20events/get_v4_sports__sport__scores)

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-request-3) Example Request

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-response-3) Example Response

Tip

The game `id` field in the scores response matches the game `id` field in the odds response

The following response headers are returned

*   **x-requests-remaining** The usage credits remaining until the quota resets
*   **x-requests-used** The usage credits used since the last quota reset
*   **x-requests-last** The usage cost of the last API call

### [#](https://the-odds-api.com/liveapi/guides/v4/#usage-quota-costs-3) Usage Quota Costs

The usage quota cost is 2 if the `daysFrom` parameter is specified (returning completed events), otherwise the usage quota cost is 1.

**Examples**

*   **Return live and upcoming games, and games completed within the last 3 days**

Only live and completed games will have scores 

Cost: 2 

Example `/v4/sports/americanfootball_nfl/scores?daysFrom=3&apiKey=...`

*   **Return live and upcoming games**

Only live games will have scores 

Cost: 1 

Example `/v4/sports/americanfootball_nfl/scores?apiKey=...`

Keeping track of quota usage

To keep track of usage credits, every API call includes the following response headers:

*   **x-requests-remaining** The usage credits remaining until the quota resets
*   **x-requests-used** The usage credits used since the last quota reset
*   **x-requests-last** The usage cost of the last API call

## [#](https://the-odds-api.com/liveapi/guides/v4/#get-events) GET events

Returns a list of in-play and pre-match events for a specified sport or league. The response includes event id, home and away teams, and the commence time for each event. Odds are not included in the response. This endpoint does not count against the usage quota.

### [#](https://the-odds-api.com/liveapi/guides/v4/#endpoint-4) Endpoint

**GET** /v4/sports/{sport}/events?apiKey={apiKey}

### [#](https://the-odds-api.com/liveapi/guides/v4/#parameters-4) Parameters

*   **sport** The sport key obtained from calling the /sports endpoint

*   **apiKey** The API key associated with your subscription. [See usage plans](https://the-odds-api.com/#get-access)

*   **dateFormat** Optional - Determines the format of timestamps in the response. Valid values are `unix` and `iso` (ISO 8601). Defaults to `iso`.

*   **eventIds** Optional - Comma-separated game ids. Filters the response to only return games with the specified ids.

*   **commenceTimeFrom** Optional - filter the response to show games that commence on and after this parameter. Values are in ISO 8601 format, for example 2023-09-09T00:00:00Z. This parameter has no effect if the sport is set to 'upcoming'.

*   **commenceTimeTo** Optional - filter the response to show games that commence on and before this parameter. Values are in ISO 8601 format, for example 2023-09-10T23:59:59Z. This parameter has no effect if the sport is set to 'upcoming'.

*   **includeRotationNumbers** Optional - if `true`, the response will include the home and away rotation numbers if available. See [this link](https://the-odds-api.com/releases/rotation-numbers.html) for details. Valid values are `true` or `false`.

### [#](https://the-odds-api.com/liveapi/guides/v4/#schema-4) Schema

For the detailed API spec, see the [Swagger API docs(opens new window)](https://app.swaggerhub.com/apis-docs/the-odds-api/odds-api/4?view=uiDocs#/current%20events/get_v4_sports__sport__events)

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-request-4) Example Request

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-response-4) Example Response

The following response headers are returned

*   **x-requests-remaining** The usage credits remaining until the quota resets
*   **x-requests-used** The usage credits used since the last quota reset
*   **x-requests-last** The usage cost of the last API call

### [#](https://the-odds-api.com/liveapi/guides/v4/#usage-quota-costs-4) Usage Quota Costs

This endpoint does not count against the usage quota.

## [#](https://the-odds-api.com/liveapi/guides/v4/#get-event-odds) GET event odds

Returns odds for a single event. Accepts [any available betting markets](https://the-odds-api.com/sports-odds-data/betting-markets.html) using the `markets` parameter. Coverage of non-featured markets is currently limited to selected bookmakers and sports, and expanding over time.

**When to use this endpoint**: Use this endpoint to access odds for any supported market. Since the volume of data returned can be large, these requests will only query one event at a time. If you are only interested in the most popular betting markets, including head-to-head (moneyline), point spreads (handicap), over/under (totals), the main [/odds endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-odds) is simpler to integrate and more cost-effective.

### [#](https://the-odds-api.com/liveapi/guides/v4/#endpoint-5) Endpoint

**GET** /v4/sports/{sport}/events/{eventId}/odds?apiKey={apiKey}&regions={regions}&markets={markets}&dateFormat={dateFormat}&oddsFormat={oddsFormat}

### [#](https://the-odds-api.com/liveapi/guides/v4/#parameters-5) Parameters

Parameters are the same as for the [/odds endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-odds) with exceptions listed below. [All available market keys](https://the-odds-api.com/sports-odds-data/betting-markets.html) are accepted in the markets parameter.

*   **eventId** The ID of an upcoming or live game, to be used in the URL path. Event ids can be found in the "id" field in the response of the [events endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-events).

*   **includeMultipliers** Optional. Applicable to US DFS sites. If `true`, the response will include the multipliers in each bet selection outcome if available. Valid values are `true` or `false`. Defaults to `false`.

### [#](https://the-odds-api.com/liveapi/guides/v4/#schema-5) Schema

For the detailed API spec, see the [Swagger API docs(opens new window)](https://app.swaggerhub.com/apis-docs/the-odds-api/odds-api/4?view=uiDocs#/current%20events/get_v4_sports__sport__events__eventId__odds)

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-request-5) Example Request

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-response-5) Example Response

The response schema is almost the same as that of the [/odds endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-odds) with a few differces:

*   A single game is returned, determined by the `eventId` parameter.
*   The `last_update` field is only available on the market level in the response and not on the bookmaker level. This reflects the fact that markets can update on their own schedule.
*   Relevant markets will have a `description` field in their outcomes.

The following response headers are returned

*   **x-requests-remaining** The usage credits remaining until the quota resets
*   **x-requests-used** The usage credits used since the last quota reset
*   **x-requests-last** The usage cost of the last API call

### [#](https://the-odds-api.com/liveapi/guides/v4/#usage-quota-costs-5) Usage Quota Costs

The usage quota cost depends on the number of markets and regions used in the request.

**Examples of usage quota costs**

*   **1 market, 1 region**

Cost: 1 

Example `/v4/sports/americanfootball_nfl/events/a512a48a58c4329048174217b2cc7ce0/odds?markets=h2h&regions=us&...`

*   **3 markets, 1 region**

Cost: 3 

Example `/v4/sports/americanfootball_nfl/events/a512a48a58c4329048174217b2cc7ce0/odds?markets=h2h,spreads,totals&regions=us&...`

*   **1 market, 3 regions**

Cost: 3 

Example `/v4/sports/soccer_epl/events/037d7b6bb128546961e2a06680f63944/odds?markets=h2h&regions=us,uk,eu&...`

*   **3 markets, 3 regions**

Cost: 9 

Example: `/v4/sports/basketball_nba/events/0b83beff5f82f8623eea93dbc1d7cd4e/odds?markets=h2h,spreads,totals&regions=us,uk,au&...`

Keeping track of quota usage

To keep track of usage credits, every API response includes the following response headers:

*   **x-requests-remaining** The usage credits remaining until the quota resets
*   **x-requests-used** The usage credits used since the last quota reset
*   **x-requests-last** The usage cost of the last API call

### [#](https://the-odds-api.com/liveapi/guides/v4/#more-info-2) More info

*   Responses with empty data do not count towards the usage quota.
*   When calculating the market component of usage quota costs, a count of unique markets in the API response is used. For example if you specify 5 different markets and 1 region in the API call, and data is only available for 2 markets, the cost will be [2 markets] x [1 region] = 2

## [#](https://the-odds-api.com/liveapi/guides/v4/#get-event-markets) GET event markets

Returns available market keys for each bookmaker for a single event.

This endpoint only returns recently seen market keys for each bookmaker - it is not a comprehensive list of all supported markets. As an event's commence time approaches, this endpoint will return more market keys as bookmakers open more markets.

### [#](https://the-odds-api.com/liveapi/guides/v4/#endpoint-6) Endpoint

**GET** /v4/sports/{sport}/events/{eventId}/markets?apiKey={apiKey}&regions={regions}&dateFormat={dateFormat}

### [#](https://the-odds-api.com/liveapi/guides/v4/#parameters-6) Parameters

*   **sport** The sport key obtained from calling the [sports endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-sports).

*   **eventId** The ID of an upcoming or live game. Event ids can be found in the "id" field in the response of the [events endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-events).

*   **apiKey** The API key associated with your subscription. [See usage plans](https://the-odds-api.com/#get-access)

*   **regions** Determines the bookmakers to be returned. For example, `us`, `us2` (United States), `uk` (United Kingdom), `au` (Australia) and `eu` (Europe). Multiple regions can be specified if comma delimited. See the [list of bookmakers by region](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html).

*   **bookmakers** Optional - Comma-separated list of bookmakers to be returned. If both `bookmakers` and `regions` are both specified, `bookmakers` takes priority. Bookmakers can be from any region. Every group of 10 bookmakers is the equivalent of 1 region. For example, specifying up to 10 bookmakers counts as 1 region. Specifying between 11 and 20 bookmakers counts as 2 regions.

*   **dateFormat** Optional - Determines the format of timestamps in the response. Valid values are `unix` and `iso` (ISO 8601). Defaults to `iso`.

### [#](https://the-odds-api.com/liveapi/guides/v4/#schema-6) Schema

For the detailed API spec, see the [Swagger API docs(opens new window)](https://app.swaggerhub.com/apis-docs/the-odds-api/odds-api/4?view=uiDocs#/current%20events/get_v4_sports__sport__events__eventId__markets)

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-request-6) Example Request

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-response-6) Example Response

The following response headers are returned

*   **x-requests-remaining** The usage credits remaining until the quota resets
*   **x-requests-used** The usage credits used since the last quota reset
*   **x-requests-last** The usage cost of the last API call

### [#](https://the-odds-api.com/liveapi/guides/v4/#usage-quota-costs-6) Usage Quota Costs

A call to this endpoint costs 1 usage credit.

## [#](https://the-odds-api.com/liveapi/guides/v4/#get-participants) GET participants

Returns list of participants for a given sport. Depending on the sport, a participant can be either a team or an individual. For example for NBA, a list of teams is returned. For tennis, a list of players is returned.

This endpoint does not return players on a team.

The returned list should be treated as a whitelist and may include participants that are not currently active.

### [#](https://the-odds-api.com/liveapi/guides/v4/#endpoint-7) Endpoint

**GET** /v4/sports/{sport}/participants?apiKey={apiKey}

### [#](https://the-odds-api.com/liveapi/guides/v4/#parameters-7) Parameters

*   **sport** The sport key obtained from calling the /sports endpoint

*   **apiKey** The API key associated with your subscription. [See usage plans](https://the-odds-api.com/#get-access)

### [#](https://the-odds-api.com/liveapi/guides/v4/#schema-7) Schema

For the detailed API spec, see the [Swagger API docs(opens new window)](https://app.swaggerhub.com/apis-docs/the-odds-api/odds-api/4?view=uiDocs#/default/get_v4_sports__sport__participants)

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-request-7) Example Request

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-response-7) Example Response

The following response headers are returned

*   **x-requests-remaining** The usage credits remaining until the quota resets
*   **x-requests-used** The usage credits used since the last quota reset
*   **x-requests-last** The usage cost of the last API call

### [#](https://the-odds-api.com/liveapi/guides/v4/#usage-quota-costs-7) Usage Quota Costs

A call to this endpoint costs 1 usage credit.

## [#](https://the-odds-api.com/liveapi/guides/v4/#get-historical-odds) GET historical odds

Returns a snapshot of games with bookmaker odds for a given sport, region and market, at a given historical timestamp. Historical odds data is available from June 6th 2020, with snapshots taken at 10 minute intervals. From September 2022, historical odds snapshots are available at 5 minute intervals. This endpoint is only available on paid usage plans.

### [#](https://the-odds-api.com/liveapi/guides/v4/#endpoint-8) Endpoint

**GET** /v4/historical/sports/{sport}/odds?apiKey={apiKey}&regions={regions}&markets={markets}&date={date}

### [#](https://the-odds-api.com/liveapi/guides/v4/#parameters-8) Parameters

Parameters are the same as for the [/odds endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-odds), with the addition of the `date` parameter.

*   **date** The timestamp of the data snapshot to be returned, specified in ISO8601 format, for example `2021-10-18T12:00:00Z` The historical odds API will return the closest snapshot equal to or earlier than the provided `date` parameter.

### [#](https://the-odds-api.com/liveapi/guides/v4/#schema-8) Schema

For a detailed API spec, see the [Swagger API docs(opens new window)](https://app.swaggerhub.com/apis-docs/the-odds-api/odds-api/4?view=uiDocs#/historical%20events/get_v4_historical_sports__sport__odds)

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-request-8) Example Request

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-response-8) Example Response

The response schema is the same as that of the [/odds endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-odds), but wrapped in a structure that contains information about the snapshot, including:

*   timestamp: The timestamp of the snapshot. This will be the closest available timestamp equal to or earlier than the provided `date` parameter.
*   previous_timestamp: the preceding available timestamp. This can be used as the `date` parameter in a new request to move back in time.
*   next_timestamp: The next available timestamp. This can be used as the `date` parameter in a new request to move forward in time.

[More sample responses for selected sports](https://the-odds-api.com/historical-odds-data/#sample-historical-odds-data)

The following response headers are returned

*   **x-requests-remaining** The usage credits remaining until the quota resets
*   **x-requests-used** The usage credits used since the last quota reset
*   **x-requests-last** The usage cost of the last API call

### [#](https://the-odds-api.com/liveapi/guides/v4/#usage-quota-costs-8) Usage Quota Costs

The usage quota cost for historical odds is 10 per region per market.

**Examples of usage quota costs for historical odds**

*   **1 market, 1 region**

Cost: 10 

Example `/v4/historical/sports/americanfootball_nfl/odds?markets=h2h&regions=us&...`

*   **3 markets, 1 region**

Cost: 30 

Example `/v4/historical/sports/americanfootball_nfl/odds?markets=h2h,spreads,totals&regions=us&...`

*   **1 market, 3 regions**

Cost: 30 

Example `/v4/historical/sports/soccer_epl/odds?markets=h2h&regions=us,uk,eu&...`

*   **3 markets, 3 regions**

Cost: 90 

Example: `/v4/historical/sports/basketball_nba/odds?markets=h2h,spreads,totals&regions=us,uk,au&...`

Keeping track of quota usage

To keep track of usage credits, every API response includes the following response headers:

*   **x-requests-remaining** The usage credits remaining until the quota resets
*   **x-requests-used** The usage credits used since the last quota reset
*   **x-requests-last** The usage cost of the last API call

### [#](https://the-odds-api.com/liveapi/guides/v4/#more-info-3) More info

*   Responses with empty data do not count towards the usage quota.
*   Prior to Septemer 18th 2022, only decimal odds were caputred in historical snapshots. American odds before this time are calculated from decimal odds and may include small rounding errors.
*   Data errors aren't common but they can occur from time to time. We are usually quick to correct errors in the current odds API, however they can still be present in historical odds snapshots. In future we plan to remove known errors from historical snapshots.
*   Bookmakers, sports and markets will only be available in the historical odds API from the time that they were added to the current odds API.

## [#](https://the-odds-api.com/liveapi/guides/v4/#get-historical-events) GET historical events

Returns a list of historical events as they appeared in the API at the given timestamp (`date` parameter). This includes events that had odds available at the query's timestamp. The response includes event ID, home and away teams, and the commence time for each event. Odds are not included in the response. This endpoint can be used to find historical event IDs to be used in the [historical event odds endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-historical-event-odds). This endpoint is only available on paid usage plans.

### [#](https://the-odds-api.com/liveapi/guides/v4/#endpoint-9) Endpoint

**GET** /v4/historical/sports/{sport}/events?apiKey={apiKey}&date={date}

### [#](https://the-odds-api.com/liveapi/guides/v4/#parameters-9) Parameters

*   **sport** The sport key obtained from calling the /sports endpoint

*   **apiKey** The API key associated with your subscription. [See usage plans](https://the-odds-api.com/#get-access)

*   **date** The timestamp of the data snapshot to be returned, specified in ISO8601 format, for example `2021-10-18T12:00:00Z` The historical odds API will return the closest snapshot equal to or earlier than the provided `date` parameter.

*   **dateFormat** Optional - Determines the format of timestamps in the response. Valid values are `unix` and `iso` (ISO 8601). Defaults to `iso`.

*   **eventIds** Optional - Comma-separated game ids. Filters the response to only return games with the specified ids.

*   **commenceTimeFrom** Optional - filter the response to show games that commence on and after this parameter. Values are in ISO 8601 format, for example 2023-09-09T00:00:00Z. This parameter has no effect if the sport is set to 'upcoming'.

*   **commenceTimeTo** Optional - filter the response to show games that commence on and before this parameter. Values are in ISO 8601 format, for example 2023-09-10T23:59:59Z. This parameter has no effect if the sport is set to 'upcoming'.

*   **includeRotationNumbers** Optional - if `true`, the response will include the home and away rotation numbers if available. See [this link](https://the-odds-api.com/releases/rotation-numbers.html) for details. Valid values are `true` or `false`.

### [#](https://the-odds-api.com/liveapi/guides/v4/#schema-9) Schema

For the detailed API spec, see the [Swagger API docs(opens new window)](https://app.swaggerhub.com/apis-docs/the-odds-api/odds-api/4?view=uiDocs#/historical%20events/get_v4_historical_sports__sport__events)

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-request-9) Example Request

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-response-9) Example Response

The response schema is almost the same as that of the [/events endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-events), but wrapped in a structure that contains information about the snapshot, including:

*   timestamp: The timestamp of the snapshot. This will be the closest available timestamp equal to or earlier than the provided date parameter.
*   previous_timestamp: the preceding available timestamp. This can be used as the date parameter in a new request to move back in time.
*   next_timestamp: The next available timestamp. This can be used as the date parameter in a new request to move forward in time.

The following response headers are returned

*   **x-requests-remaining** The usage credits remaining until the quota resets
*   **x-requests-used** The usage credits used since the last quota reset
*   **x-requests-last** The usage cost of the last API call

### [#](https://the-odds-api.com/liveapi/guides/v4/#usage-quota-costs-9) Usage Quota Costs

This endpoint costs 1 from usage quota. If no events are found, it will not cost.

## [#](https://the-odds-api.com/liveapi/guides/v4/#get-historical-event-odds) GET historical event odds

Returns historical odds for a single event as they appeared at a specified timestamp. Accepts [any available betting markets](https://the-odds-api.com/sports-odds-data/betting-markets.html) using the `markets` parameter. Historical data for additional markets (player props, alternate lines, period markets) are available after 2023-05-03T05:30:00Z. This endpoint is only available on paid usage plans.

Tip

When querying historical odds for [featured markets](https://the-odds-api.com/sports-odds-data/betting-markets.html#featured-betting-markets), the [historical odds endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-historical-odds) is simpler to implement and more cost-effective.

### [#](https://the-odds-api.com/liveapi/guides/v4/#endpoint-10) Endpoint

**GET** /v4/historical/sports/{sport}/events/{eventId}/odds?apiKey={apiKey}&regions={regions}&markets={markets}&dateFormat={dateFormat}&oddsFormat={oddsFormat}&date={date}

### [#](https://the-odds-api.com/liveapi/guides/v4/#parameters-10) Parameters

Parameters are the same as for the [/odds endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-odds), with additional parameters listed below. [All available market keys](https://the-odds-api.com/sports-odds-data/betting-markets.html) are accepted in the markets parameter.

*   **eventId** The ID of a historical game, to be used in the URL path. Historical event ids can be found in the "id" field in the response of the [historical events endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-historical-events).

*   **date** The timestamp of the data snapshot to be returned, specified in ISO8601 format, for example `2023-11-29T22:42:00Z` The historical odds API will return the closest snapshot equal to or earlier than the provided `date` parameter. Historical data for additional markets are available after 2023-05-03T05:30:00Z. Snapshots are available at 5 minute intervals.

*   **includeMultipliers** Optional. Applicable to US DFS sites. If `true`, the response will include the multipliers in each bet selection outcome if available. Valid values are `true` or `false`. Defaults to `false`.

### [#](https://the-odds-api.com/liveapi/guides/v4/#schema-10) Schema

For the detailed API spec, see the [Swagger API docs(opens new window)](https://app.swaggerhub.com/apis-docs/the-odds-api/odds-api/4?view=uiDocs#/historical%20events/get_v4_historical_sports__sport__events__eventId__odds)

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-request-10) Example Request

### [#](https://the-odds-api.com/liveapi/guides/v4/#example-response-10) Example Response

The response schema is almost the same as that of the [/event odds endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-event-odds), but wrapped in a structure that contains information about the snapshot, including:

*   timestamp: The timestamp of the snapshot. This will be the closest available timestamp equal to or earlier than the provided date parameter.
*   previous_timestamp: the preceding available timestamp. This can be used as the date parameter in a new request to move back in time.
*   next_timestamp: The next available timestamp. This can be used as the date parameter in a new request to move forward in time.

The following response headers are returned

*   **x-requests-remaining** The usage credits remaining until the quota resets
*   **x-requests-used** The usage credits used since the last quota reset
*   **x-requests-last** The usage cost of the last API call

### [#](https://the-odds-api.com/liveapi/guides/v4/#usage-quota-costs-10) Usage Quota Costs

The usage quota cost depends on the number of markets and regions used in the request.

**Examples of usage quota costs**

*   **1 market, 1 region**

Cost: 10 

Example `/v4/historical/sports/americanfootball_nfl/events/a512a48a58c4329048174217b2cc7ce0/odds?markets=player_pass_tds&regions=us&...`

*   **3 markets, 1 region**

Cost: 30 

Example `/v4/historical/sports/americanfootball_nfl/events/a512a48a58c4329048174217b2cc7ce0/odds?markets=player_pass_tds,player_anytime_td,player_rush_longest&regions=us&...`

*   **1 market, 3 regions**

Cost: 30 

Example `/v4/historical/sports/basketball_nba/events/037d7b6bb128546961e2a06680f63944/odds?markets=player_points&regions=us,us2,au&...`

*   **3 markets, 3 regions**

Cost: 90 

Example: `/v4/historical/sports/basketball_nba/events/0b83beff5f82f8623eea93dbc1d7cd4e/odds?markets=player_points,player_assists,alternate_spreads&regions=us,us2,au&...`

Keeping track of quota usage

To keep track of usage credits, every API response includes the following response headers:

*   x-requests-used
*   x-requests-remaining
*   x-requests-last

### [#](https://the-odds-api.com/liveapi/guides/v4/#more-info-4) More info

*   Responses with empty data do not count towards the usage quota.
*   When calculating the market component of usage quota costs, a count of unique markets in the API response is used. For example if you specify 5 different markets and 1 region in the API call, and data is only available for 2 markets, the cost will be 10 x [2 markets] x [1 region] = 20

## [#](https://the-odds-api.com/liveapi/guides/v4/#rate-limiting-status-code-429) Rate Limiting (status code 429)

Requests are rate limited in order to protect our systems from sudden bursts in traffic. If you enounter the rate limit, the API will respond with a status code of 429, in which case try spacing out requests over several seconds. More information can be [found here](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#exceeded-freq-limit).

## [#](https://the-odds-api.com/liveapi/guides/v4/#code-samples) Code Samples

Get started right away with [code samples for Python and NodeJs](https://the-odds-api.com/liveapi/guides/v4/samples.html). Code samples are also available on [Github(opens new window)](https://github.com/the-odds-api)

## [#](https://the-odds-api.com/liveapi/guides/v4/#more-info-5) More Info

Stay up to date on new sports, bookmakers and features by [following us on Twitter(opens new window)](https://twitter.com/The_Odds_API)
