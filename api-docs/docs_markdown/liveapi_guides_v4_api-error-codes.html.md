<!-- Source: https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html -->

Title: API Error Codes

URL Source: https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html

Markdown Content:
This page lists API error codes and their common causes. If you encounter an error that is not documented on this page, it can be reported to [team@the-odds-api.com](mailto:team@the-odds-api.com). Be sure to include the full API URL that caused the error.

Errors can depend on the specific endpoint being called. For details on specific endpoints and example API requests, see [the docs](https://the-odds-api.com/liveapi/guides/v4/).

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#missing-key) MISSING_KEY

An `apiKey` query parameter is required for all calls to the API, for example

`https://api.the-odds-api.com/v4/sports?apiKey=YOUR_API_KEY`

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-key) INVALID_KEY

The API key was invalid or not associated with a subscription.

For sample URLs, the API key is commonly `YOUR_API_KEY` or `{apiKey}`, in which case it will need to be replaced with a valid API key associated with [a subscription](https://the-odds-api.com/#get-access).

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#deactivated-key) DEACTIVATED_KEY

The API key has been deactivated, most commonly due to subscription cancelation. To regain access to the API, a [new subscription](https://the-odds-api.com/#get-access) is required.

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#exceeded-freq-limit) EXCEEDED_FREQ_LIMIT

The request was rate-limited (HTTP status code 429). Reduce the number of API calls being sent concurrently by spacing out API calls over several seconds. The rate limit is currently 30 API calls per second.

There are a couple of reasons that 429s can occur:

*   If our system receives a large increase in traffic, it will take some time to scale up, usually in the order of minutes. Whilst this is happening, some requests might be knocked back with 429s.

*   If requests are sent at a rate close to the limit, some requests can still trigger rate limiting since our servers can receive requests at a different rate to which they are sent. For example, if you send 30 requests per second for 2 seconds, our servers might receive 25 requests in the first second, 33 in the next second (3 of which will be limited), and the remaining 2 requests after that. The rate at which our systems receive the requests will depend on network conditions, which are influenced by many factors outside of our control.

Both of these scenarios mean that 429s can occur sometimes, and they are more likely if requests are being sent close to the limit.

To handle a request that has been rate limited, consider retrying the request after a couple of seconds. Also avoid unnecessary API calls. For example, API calls to the sports or events endpoints can be made infrequently, since the responses don't change often.

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#out-of-usage-credits) OUT_OF_USAGE_CREDITS

The usage credit limit of the subscription has been reached for the month.

Usage credits can be monitored by accessing the HTTP response headers, which are returned with every API call:

*   `x-requests-remaining` The usage credits remaining until the quota resets
*   `x-requests-used` The usage credits used since the last quota reset
*   `x-requests-last` The usage cost of the last API call

Usage can be tracked and subscriptions can be changed in the [accounts portal](https://the-odds-api.com/account/). If you have not already done so, you will need to create a new account, even if you have active subscriptions. A new account can be [created here](https://the-odds-api.com/account/?initialAuthState=signUp).

### [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#troubleshooting-unexpected-usage-tracking-usage) Troubleshooting Unexpected Usage & Tracking Usage

Tips for troubleshooting unexpected usage and tracking usage can be found on [this page](https://the-odds-api.com/manage/troubleshoot-unexpected-usage.html).

### [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#upgrading-a-subscription) Upgrading a Subscription

A paid subscription can be upgraded at any time. Details on how to upgrade and upgrade behavior can be found on [this page](https://the-odds-api.com/manage/upgrade-downgrade-cancel-a-subscription.html).

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#missing-region) MISSING_REGION

The endpoint being called requires a `regions` query parameter, which specifies regions of bookmakers to be queried, for example `&regions=us,uk`

Alternatively the `bookmakers` parameter can be used, for example `&bookmakers=draftkings,pinnacle`

A list of valid bookmakers and regions can be [found here](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html).

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-region) INVALID_REGION

One or more of the specified regions is invalid. A list of valid bookmaker regions can be [found here](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html).

Multiple comma-separated regions can be specified, for example

`https://api.the-odds-api.com/v4/sports/soccer_epl/odds?apiKey=YOUR_API_KEY&markets=h2h&regions=uk,eu`

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-bookmakers) INVALID_BOOKMAKERS

The `bookmakers` parameter can be used as an alternative to the `regions` parameter. The `bookmakers` parameter is a comma-separated list of one or more bookmaker keys. A list of bookmaker keys can be [found here](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html).

Multiple comma-separated bookmaker keys can be specified. Bookmakers can be from any region, for example

`https://api.the-odds-api.com/v4/sports/basketball_nba/odds?apiKey=YOUR_API_KEY&markets=h2h&bookmakers=draftkings,fanduel,pinnacle`

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#missing-market) MISSING_MARKET

The endpoint being called requires a `markets` query parameter, which specifies betting markets to be queried. For most endpoints, this parameter is not required and will default to the `h2h` market.

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-market) INVALID_MARKET

One or more of the markets being queried are invalid or unsupported by the endpoint being used. A list of valid market keys can be [found here](https://the-odds-api.com/sports-odds-data/betting-markets.html).

This error is commonly caused when non-featured markets are used with the odds or historical odds endpoints, which only support [featured markets](https://the-odds-api.com/sports-odds-data/betting-markets.html#featured-betting-markets).

[Non-featured markets](https://the-odds-api.com/sports-odds-data/betting-markets.html#additional-markets), such as player props, period markets and alternate markets can be queried one event at a time using the [event-odds](https://the-odds-api.com/liveapi/guides/v4/#get-event-odds) or [historical-event-odds](https://the-odds-api.com/liveapi/guides/v4/#get-historical-event-odds) endpoints.

For example, this will cause an error since player_points is a non-featured market, and the odds endpoint only accepts featured markets:

`https://api.the-odds-api.com/v4/sports/basketball_nba/odds?apiKey=YOUR_API_KEY&regions=us&oddsFormat=american&markets=player_points`

The events-odds endpoint accepts any markets. In this example, b308ed60cbb2d1324946c7289190cc88 was the event id of the Timberwolves @ Nuggets game on 2024-05-04. The event id will need to be replaced with a current event id, which can be obtained from the [events](https://the-odds-api.com/liveapi/guides/v4/#get-events) endpoint.

`https://api.the-odds-api.com/v4/sports/basketball_nba/events/b308ed60cbb2d1324946c7289190cc88/odds?apiKey=YOUR_API_KEY&regions=us&oddsFormat=american&markets=player_points`

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-market-combo) INVALID_MARKET_COMBO

This error usually occurs if the sportKey represents an outrights (futures) event, in which case the valid market is `outrights`.

For example this will cause the error:

`https://api.the-odds-api.com/v4/sports/americanfootball_nfl_super_bowl_winner/odds?apiKey=YOUR_API_KEY&regions=us&oddsFormat=american&markets=h2h`

This is a valid combination

`https://api.the-odds-api.com/v4/sports/americanfootball_nfl_super_bowl_winner/odds?apiKey=YOUR_API_KEY&regions=us&oddsFormat=american&markets=outrights`

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-date-format) INVALID_DATE_FORMAT

The specified `dateFormat` query parameter is invalid. For valid formats, see the "parameters" section for the relevant endpoint in [the docs](https://the-odds-api.com/liveapi/guides/v4/).

The `dateFormat` parameter is not required for most endpoints, and will default to `iso` (ISO8601).

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-odds-format) INVALID_ODDS_FORMAT

The specified `oddsFormat` query parameter is invalid. For valid formats, see the "parameters" section for the relevant endpoint in [the docs](https://the-odds-api.com/liveapi/guides/v4/).

If this parameter is missing, the `oddsFormat` will default to `decimal`.

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-all-sports-param) INVALID_ALL_SPORTS_PARAM

The `all` query parameter must be `true` or `false`.

This will likely be relevant for the [sports endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-sports).

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-sport) INVALID_SPORT

The sport path parameter is missing or invalid. A list of valid sport keys can be [found here](https://the-odds-api.com/sports-odds-data/sports-apis.html), or by called the [sports endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-sports).

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#unknown-sport) UNKNOWN_SPORT

The specified sport is not found. A list of valid sport keys can be [found here](https://the-odds-api.com/sports-odds-data/sports-apis.html), or by called the [sports endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-sports).

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-scores-days-from) INVALID_SCORES_DAYS_FROM

The `daysFrom` parameter must be an integer greater than or equal to 1, and less the maximum specified in [the docs](https://the-odds-api.com/liveapi/guides/v4/#get-scores) (see the "parameters" section of the relevant endpoint).

For example

`https://api.the-odds-api.com/v4/sports/baseball_mlb/scores?apiKey=YOUR_API_KEY&daysFrom=2`

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-event-ids) INVALID_EVENT_IDS

The `eventIds` query parameter is invalid. For endpoints that return a list of events, this parameter is used to filter the API response to specific events. This parameter must contain comma separated event ids, each of which is 32 characters in length.

Depending on the endpoint being queried, event ids can be found by calling the [events endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-events) or the [historical events endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-historical-events).

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-event-id) INVALID_EVENT_ID

The event id parameter in the URL path is invalid. The event id must be 32 characters in length.

Depending on the endpoint being queried, event ids can be found by calling the [events endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-events) or the [historical events endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-historical-events).

For example, c163b5f5f4579c8293266956ccf3d9bd is the event id for Tampa Bay Rays @ Los Angeles Angels on 2024-04-09:

`https://api.the-odds-api.com/v4/historical/sports/baseball_mlb/events/c163b5f5f4579c8293266956ccf3d9bd/odds?apiKey=YOUR_API_KEY&markets=totals_1st_5_innings&regions=us&oddsFormat=american&date=2024-04-08T15:10:00Z`

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#event-not-found) EVENT_NOT_FOUND

The event id specified in the URL path was not found. The most common cause is that the event has concluded. This error can also occur if the event id was not correctly specified.

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#missing-historical-timestamp) MISSING_HISTORICAL_TIMESTAMP

The `date` parameter is required when querying historical endpoints. This represents the timestamp of the historical snapshot to be queried. More information can be found for the relevant endpoint in [the docs](https://the-odds-api.com/liveapi/guides/v4/).

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-historical-timestamp) INVALID_HISTORICAL_TIMESTAMP

The `date` parameter must be in ISO8601 format, for example:

`https://api.the-odds-api.com/v4/historical/sports/baseball_mlb/odds?apiKey=YOUR_API_KEY&regions=us&markets=h2h,spreads&date=2024-04-30T12:45:00Z`

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-commence-time-from) INVALID_COMMENCE_TIME_FROM

The `commenceTimeFrom` parameter must be in ISO8601 format, for example `2024-04-30T00:00:00Z`

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-commence-time-to) INVALID_COMMENCE_TIME_TO

The `commenceTimeTo` parameter must be in ISO8601 format, for example `2024-04-30T23:59:59Z`

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-commence-time-range) INVALID_COMMENCE_TIME_RANGE

The `commenceTimeTo` parameter must be later than `commenceTimeFrom`

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#historical-unavailable-on-free-usage-plan) HISTORICAL_UNAVAILABLE_ON_FREE_USAGE_PLAN

Historical data is only accessible on [paid usage plans](https://the-odds-api.com/#get-access).

Sample historical data can be [found here](https://the-odds-api.com/historical-odds-data/#sample-historical-odds-data).

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-participant-id) INVALID_PARTICIPANT_ID

The participant id is invalid. It must start with `par_`, for example `par_01hqmkq6fceknv7cwebesgrx03`

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-include-links) INVALID_INCLUDE_LINKS

The `includeLinks` parameter determines whether links to bookmaker websites will be included in the API response.

If `includeLinks` is provided, it must be either `true` or `false`.

If `includeLinks` is not provided, it will default to `false`.

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-include-sids) INVALID_INCLUDE_SIDS

The `includeSids` parameter determines whether source ids (sids) will be included in the API response. An example of a sid includes a bookmaker's id for an event, market or betting selection.

If `includeSids` is provided, it must be either `true` or `false`.

If `includeSids` is not provided, it will default to `false`.

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-include-bet-limits) INVALID_INCLUDE_BET_LIMITS

The `includeBetLimits` parameter determines whether a bookmaker's bet limits will be returned in each betting outcome in the API response.

If `includeBetLimits` is provided, it must be either `true` or `false`.

If `includeBetLimits` is not provided, it will default to `false`.

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-include-multipliers) INVALID_INCLUDE_MULTIPLIERS

The `includeMultipliers` parameter determines whether a betting outcome's multiplier is included in the the API response. This is only applicable to DFS sites (`us_dfs` region).

If `includeMultipliers` is provided, it must be either `true` or `false`.

If `includeMultipliers` is not provided, it will default to `false`.

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-include-rotation-numbers) INVALID_INCLUDE_ROTATION_NUMBERS

The `includeRotationNumbers` parameter determines whether to include rotation numbers in the API response, if available.

If `includeRotationNumbers` is provided, it must be either `true` or `false`.

If `includeRotationNumbers` is not provided, it will default to `false`.

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#historical-markets-unavailable-at-date) HISTORICAL_MARKETS_UNAVAILABLE_AT_DATE

One or more of the requested market keys are not available at the timestamp of the "date" parameter. The specific market keys will be listed in the API's error message response.

## [#](https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#invalid-status) INVALID_STATUS

The `status` parameter is invalid. This should be a comma-separated list of game statuses, for example `&status=pre,live`. A list valid status values will be returned in the API error message.
