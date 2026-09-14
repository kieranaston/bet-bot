<!-- Source: https://the-odds-api.com/historical-odds-data/ -->

Title: Historical Sports Odds Data API

URL Source: https://the-odds-api.com/historical-odds-data/

Markdown Content:
Historical odds data is available for all sports and bookmakers covered by The Odds API. Historical data is available as snapshots, which include events and bookmaker odds as they were at a point in time.

Historical odds data for [featured markets](https://the-odds-api.com/sports-odds-data/betting-markets.html#featured-betting-markets) is available from June 6th 2020, with snapshots taken at 10 minute intervals. From September 2022, historical odds snapshots are available at 5 minute intervals.

Historical odds data for [additional markets](https://the-odds-api.com/sports-odds-data/betting-markets.html#additional-markets), including player props, period markets and more, is available from May 3rd, 2023. Snapshots are available at 5 minute intervals.

Historical data is only available on paid usage plans.

## [#](https://the-odds-api.com/historical-odds-data/#how-to-access-historical-odds-data) How to access historical odds data

### [#](https://the-odds-api.com/historical-odds-data/#historical-odds-data-for-featured-markets) Historical odds data for featured markets

[Featured markets](https://the-odds-api.com/sports-odds-data/betting-markets.html) include the most popular betting markets and are prominently displayed by bookmakers. Historical odds data for featured markets is available in JSON format using the API's [historical odds endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-historical-odds).

##### [#](https://the-odds-api.com/historical-odds-data/#example-api-request) Example API Request

The input parameters are the same as those of the [v4 odds API endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-odds), with the addition of a `date` parameter which represents the timestamp of the snapshot to be queried. The historical odds API will return the closest snapshot equal to or earlier than the provided `date` parameter. The usage quota cost for the historical odds endpoint is 10 per region per market ([more info](https://the-odds-api.com/liveapi/guides/v4/#usage-quota-costs-6)).

##### [#](https://the-odds-api.com/historical-odds-data/#example-api-response) Example API Response

The response schema is the same as that of the [v4 odds API endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-odds), but wrapped in a structure that contains information about the snapshot, including:

*   timestamp: The timestamp of the snapshot. This will be the closest available timestamp equal to or earlier than the provided `date` parameter.
*   previous_timestamp: the preceding available timestamp. This can be used as the `date` parameter in a new request to move back in time.
*   next_timestamp: The next available timestamp. This can be used as the `date` parameter in a new request to move forward in time.

### [#](https://the-odds-api.com/historical-odds-data/#historical-odds-data-for-additional-markets) Historical odds data for additional markets

Historical odds data for [additional markets](https://the-odds-api.com/sports-odds-data/betting-markets.html#additional-markets), including player props, half/quarter time markets and more, can be queried one game at a time using the [historical event odds endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-historical-event-odds).

##### [#](https://the-odds-api.com/historical-odds-data/#example-api-request-2) Example API Request

The input parameters are the same as those of the [v4 event-odds API endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-event-odds), with the addition of a `date` parameter which represents the timestamp of the snapshot to be queried. The historical odds API will return the closest snapshot equal to or earlier than the provided `date` parameter. The usage quota cost for the historical event-odds endpoint is 10 per region per market per event ([more info](https://the-odds-api.com/liveapi/guides/v4/#usage-quota-costs-8)).

In this example, da359da99aa27e97d38f2df709343998 is the id of the Lakers @ Pistons game on 2023-11-30. The [historical events endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-historical-events) can be used to find event ids.

##### [#](https://the-odds-api.com/historical-odds-data/#example-api-response-2) Example API Response

The response schema is the same as that of the [v4 event-odds API endpoint](https://the-odds-api.com/liveapi/guides/v4/#get-event-odds), but wrapped in a structure that contains information about the snapshot, including:

*   timestamp: The timestamp of the snapshot. This will be the closest available timestamp equal to or earlier than the provided `date` parameter.
*   previous_timestamp: the preceding available timestamp. This can be used as the `date` parameter in a new request to move back in time.
*   next_timestamp: The next available timestamp. This can be used as the `date` parameter in a new request to move forward in time.

## [#](https://the-odds-api.com/historical-odds-data/#sample-historical-odds-data) Sample Historical Odds Data

The historical odds API is only available on paid subscriptions at this time. This section provides examples of API requests and responses to demonstrate usage of the historical odds API.

This section only covers a small selection of sports. Historical odds data is available for all sports covered in the API from the time the sport was added to the API. [See the full list of sports.(opens new window)](https://the-odds-api.com/sports-odds-data/sports-apis.html).

#### [#](https://the-odds-api.com/historical-odds-data/#historical-nfl-odds-data) Historical NFL odds data

*   Moneyline (h2h), point spreads (spreads) and over/under (totals)
*   US bookmakers
*   Snapshot date 2021-11-25T12:00:00Z
*   American odds format

Request:

Response: [Download historical odds API response for NFL](https://public-odds-api-sample-data.s3.amazonaws.com/historical-nfl.json)

#### [#](https://the-odds-api.com/historical-odds-data/#historical-epl-odds-data) Historical EPL odds data

*   1x2 (h2h)
*   UK bookmakers
*   Date 2021-10-30T00:00:00Z
*   Decimal odds format

Request:

Response: [Download historical odds API response for EPL](https://public-odds-api-sample-data.s3.amazonaws.com/historical-epl.json)

#### [#](https://the-odds-api.com/historical-odds-data/#historical-german-bundesliga-odds-data) Historical German Bundesliga odds data

*   1x2 (h2h)
*   EU bookmakers
*   Date 2022-10-18T02:00:00Z
*   Decimal odds format

Request:

Response: [Download historical odds API response for Bundesliga](https://public-odds-api-sample-data.s3.amazonaws.com/historical-bundesliga.json)

#### [#](https://the-odds-api.com/historical-odds-data/#historical-afl-odds-data) Historical AFL odds data

*   Head to head (h2h)
*   AU bookmakers
*   Date 2022-04-25T00:00:00Z
*   Decimal odds format

Request:

Response: [Download historical odds API response for AFL](https://public-odds-api-sample-data.s3.amazonaws.com/historical-afl.json)

#### [#](https://the-odds-api.com/historical-odds-data/#historical-us-presidential-elections-winner-odds-data) Historical US presidential elections winner odds data

*   Futures (outrights)
*   US bookmakers
*   Date 2020-10-31T00:00:00Z (note coverage of US bookmakers was limited in 2020)
*   American odds format

Request:

Response: [Download historical odds API response for US Presidential Election Winner](https://public-odds-api-sample-data.s3.amazonaws.com/historical-us-presidential-election-winner.json)

## [#](https://the-odds-api.com/historical-odds-data/#earliest-historical-timestamps) Earliest Historical Timestamps

Historical data will only be available from the time that coverage is added for a sport, bookmaker or market. The list below shows the earliest available timestamp of historical odds for each covered sport.

| Group | League / Tournament | Sport Key (use in the API) | Start of Historical Data |
| --- | --- | --- | --- |
| American Football | CFL | americanfootball_cfl | 2022-07-02T00:45:00Z |
| American Football | [NCAAF](https://the-odds-api.com/sports/ncaaf-odds.html) | americanfootball_ncaaf | 2020-06-06T10:05:00Z |
| American Football | [NCAAF FCS](https://the-odds-api.com/sports/ncaaf-odds.html) | americanfootball_ncaaf_fcs | 2026-08-28T13:10:38Z |
| American Football | NCAAF Championship Winner | americanfootball_ncaaf_championship_winner | 2023-10-24T05:40:42Z |
| American Football | [NFL](https://the-odds-api.com/sports/nfl-odds.html) | americanfootball_nfl | 2020-06-06T10:05:00Z |
| American Football | [NFL Preseason](https://the-odds-api.com/sports/nfl-preseason-odds.html) | americanfootball_nfl_preseason | 2022-07-29T12:05:00Z |
| American Football | NFL Super Bowl Winner | americanfootball_nfl_super_bowl_winner | 2020-06-06T10:05:00Z |
| American Football | [UFL](https://the-odds-api.com/sports/ufl-odds.html) | americanfootball_ufl | 2023-02-21T21:00:39Z |
| Aussie Rules | [AFL](https://the-odds-api.com/sports/afl-odds.html) | aussierules_afl | 2020-06-06T10:05:00Z |
| Aussie Rules | AFL Women's | aussierules_aflw | 2026-08-07T02:35:38Z |
| Baseball | [MLB](https://the-odds-api.com/sports/mlb-odds.html) | baseball_mlb | 2020-06-30T20:55:00Z |
| Baseball | MLB Preseason | baseball_mlb_preseason | 2023-02-28T11:10:39Z |
| Baseball | MLB World Series Winner | baseball_mlb_world_series_winner | 2021-11-07T09:55:00Z |
| Baseball | Minor League Baseball | baseball_milb | 2024-04-10T01:40:39Z |
| Baseball | NPB | baseball_npb | 2024-03-28T21:10:40Z |
| Baseball | KBO League | baseball_kbo | 2024-03-28T21:10:40Z |
| Baseball | [NCAA Baseball](https://the-odds-api.com/sports/ncaa-baseball-odds.html) | baseball_ncaa | 2023-05-03T22:50:40Z |
| Basketball | Basketball Euroleague | basketball_euroleague | 2020-09-24T00:25:00Z |
| Basketball | [NBA](https://the-odds-api.com/sports/nba-odds.html) | basketball_nba | 2020-06-27T03:55:00Z |
| Basketball | NBA Preseason | basketball_nba_preseason | 2022-10-07T00:05:40Z |
| Basketball | NBA All Star | basketball_nba_all_stars | 2024-02-17T08:20:39Z |
| Basketball | NBA Summer League | basketball_nba_summer_league | 2025-07-05T05:55:38Z |
| Basketball | NBA Championship Winner | basketball_nba_championship_winner | 2021-11-07T09:55:00Z |
| Basketball | [WNBA](https://the-odds-api.com/sports/wnba-odds.html) | basketball_wnba | 2022-05-21T09:05:00Z |
| Basketball | [NCAAB](https://the-odds-api.com/sports/ncaab-odds.html) | basketball_ncaab | 2020-11-16T09:15:00Z |
| Basketball | [WNCAAB](https://the-odds-api.com/sports/wncaab-odds.html) | basketball_wncaab | 2024-11-12T21:15:38Z |
| Basketball | NCAAB Championship Winner | basketball_ncaab_championship_winner | 2023-10-24T05:45:43Z |
| Basketball | NBL (Australia) | basketball_nbl | 2024-09-24T05:05:38Z |
| Boxing | [Boxing](https://the-odds-api.com/sports/boxing-odds.html) | boxing_boxing | 2023-05-30T01:10:40Z |
| Cricket | [Asia Cup](https://the-odds-api.com/sports/cricket-odds.html) | cricket_asia_cup | 2022-08-10T09:45:00Z |
| Cricket | [Big Bash](https://the-odds-api.com/sports/cricket-odds.html) | cricket_big_bash | 2020-11-06T10:55:00Z |
| Cricket | [Caribbean Premier League](https://the-odds-api.com/sports/cricket-odds.html) | cricket_caribbean_premier_league | 2022-09-13T00:15:00Z |
| Cricket | [ICC Champions Trophy](https://the-odds-api.com/sports/cricket-odds.html) | cricket_icc_trophy | 2025-02-22T10:55:39Z |
| Cricket | [ICC World Cup](https://the-odds-api.com/sports/cricket-odds.html) | cricket_icc_world_cup | 2022-09-13T00:25:00Z |
| Cricket | [ICC Women's World Cup](https://the-odds-api.com/sports/cricket-odds.html) | cricket_icc_world_cup_womens | 2022-09-13T00:25:00Z |
| Cricket | [International Twenty20](https://the-odds-api.com/sports/cricket-odds.html) | cricket_international_t20 | 2022-08-10T09:45:00Z |
| Cricket | [IPL](https://the-odds-api.com/sports/cricket-odds.html) | cricket_ipl | 2020-09-18T11:55:00Z |
| Cricket | [One Day Internationals](https://the-odds-api.com/sports/cricket-odds.html) | cricket_odi | 2020-07-06T18:15:00Z |
| Cricket | [Pakistan Super League](https://the-odds-api.com/sports/cricket-odds.html) | cricket_psl | 2023-02-10T23:35:38Z |
| Cricket | [T20 Blast](https://the-odds-api.com/sports/cricket-odds.html) | cricket_t20_blast | 2023-06-07T06:50:38Z |
| Cricket | [T20 World Cup](https://the-odds-api.com/sports/cricket-odds.html) | cricket_t20_world_cup | 2026-02-05T14:50:37Z |
| Cricket | [T20 Women's World Cup Odds](https://the-odds-api.com/sports/cricket-odds.html) | cricket_t20_world_cup_womens | 2026-06-16T03:15:36Z |
| Cricket | [Test Matches](https://the-odds-api.com/sports/cricket-odds.html) | cricket_test_match | 2020-06-06T10:05:00Z |
| Cricket | [The Hundred](https://the-odds-api.com/sports/cricket-odds.html) | cricket_the_hundred | 2022-08-10T09:45:00Z |
| Cricket | [The Hundred - Women's](https://the-odds-api.com/sports/cricket-odds.html) | cricket_the_hundred_womens | 2026-07-27T08:25:38Z |
| Golf | [Masters Tournament Winner](https://the-odds-api.com/sports/golf-odds.html) | golf_masters_tournament_winner | 2020-06-06T10:05:00Z |
| Golf | [PGA Championship Winner](https://the-odds-api.com/sports/golf-odds.html) | golf_pga_championship_winner | 2020-06-06T10:05:00Z |
| Golf | [The Open Winner](https://the-odds-api.com/sports/golf-odds.html) | golf_the_open_championship_winner | 2021-04-06T22:05:00Z |
| Golf | [US Open Winner](https://the-odds-api.com/sports/golf-odds.html) | golf_us_open_winner | 2020-06-06T10:05:00Z |
| Handball | Handball-Bundesliga | handball_germany_bundesliga | 2025-10-11T08:25:39Z |
| Ice Hockey | [NHL](https://the-odds-api.com/sports/nhl-odds.html) | icehockey_nhl | 2020-06-29T19:25:00Z |
| Ice Hockey | NHL Preseason | icehockey_nhl_preseason | 2025-09-29T20:15:39Z |
| Ice Hockey | [AHL](https://the-odds-api.com/sports/ahl-odds.html) | icehockey_ahl | 2025-02-10T05:20:37Z |
| Ice Hockey | NHL Championship Winner | icehockey_nhl_championship_winner | 2021-11-07T09:55:00Z |
| Ice Hockey | Finnish Liiga | icehockey_liiga | 2025-02-10T06:30:38Z |
| Ice Hockey | Finnish Mestis | icehockey_mestis | 2025-02-10T06:30:38Z |
| Ice Hockey | SHL | icehockey_sweden_hockey_league | 2021-11-06T00:25:00Z |
| Ice Hockey | HockeyAllsvenskan | icehockey_sweden_allsvenskan | 2021-11-06T00:25:00Z |
| Lacrosse | [Premier Lacrosse League](https://the-odds-api.com/sports/pll-odds.html) | lacrosse_pll | 2024-05-27T12:10:38Z |
| Lacrosse | [NCAA Lacrosse](https://the-odds-api.com/sports/ncaa-lacrosse-odds.html) | lacrosse_ncaa | 2025-02-01T04:40:38Z |
| Mixed Martial Arts | [MMA](https://the-odds-api.com/sports/mma-ufc-odds.html) | mma_mixed_martial_arts | 2020-06-06T10:05:00Z |
| Politics | US Presidential Elections Winner | politics_us_presidential_election_winner | 2020-06-06T10:05:00Z |
| Rugby League | NRL | rugbyleague_nrl | 2020-06-06T10:05:00Z |
| Women's Rugby League | NRLW | rugbyleague_nrlw | 2026-07-28T14:00:37Z |
| Rugby League | NRL State of Origin | rugbyleague_nrl_state_of_origin | 2025-05-19T03:00:37Z |
| Rugby Union | Six Nations | rugbyunion_six_nations | 2025-01-31T05:45:38Z |
| Soccer | Africa Cup of Nations | soccer_africa_cup_of_nations | 2022-01-14T07:05:00Z |
| Soccer | Primera División - Argentina | soccer_argentina_primera_division | 2020-10-30T15:15:00Z |
| Soccer | A-League | soccer_australia_aleague | 2020-06-24T13:05:00Z |
| Soccer | Austrian Football Bundesliga | soccer_austria_bundesliga | 2023-02-10T23:45:38Z |
| Soccer | Belgium First Div | soccer_belgium_first_div | 2020-07-24T00:05:00Z |
| Soccer | Brazil Série A | soccer_brazil_campeonato | 2020-07-28T22:15:00Z |
| Soccer | Brazil Série B | soccer_brazil_serie_b | 2022-06-30T01:05:00Z |
| Soccer | Primera División - Chile | soccer_chile_campeonato | 2022-06-30T01:05:00Z |
| Soccer | Super League - China | soccer_china_superleague | 2020-07-15T22:15:00Z |
| Soccer | Denmark Superliga | soccer_denmark_superliga | 2020-06-06T10:05:00Z |
| Soccer | Championship | soccer_efl_champ | 2020-06-08T13:15:00Z |
| Soccer | EFL Cup | soccer_england_efl_cup | 2021-11-06T00:25:00Z |
| Soccer | League 1 | soccer_england_league1 | 2020-06-12T15:25:00Z |
| Soccer | League 2 | soccer_england_league2 | 2020-06-09T15:15:00Z |
| Soccer | [EPL](https://the-odds-api.com/sports/epl-odds.html) | soccer_epl | 2020-06-06T10:05:00Z |
| Soccer | FA Cup | soccer_fa_cup | 2020-06-06T10:05:00Z |
| Soccer | [FIFA World Cup](https://the-odds-api.com/sports/fifa-world-cup-odds.html) | soccer_fifa_world_cup | 2022-04-03T00:45:00Z |
| Soccer | FIFA World Cup Qualifiers - Europe | soccer_fifa_world_cup_qualifiers_europe | 2025-03-24T08:25:38Z |
| Soccer | FIFA World Cup Qualifiers - South America | soccer_fifa_world_cup_qualifiers_south_america | 2025-03-24T07:30:38Z |
| Soccer | FIFA Women's World Cup | soccer_fifa_world_cup_womens | 2023-06-07T06:45:38Z |
| Soccer | FIFA World Cup Winner | soccer_fifa_world_cup_winner | 2022-03-29T23:35:00Z |
| Soccer | FIFA Club World Cup | soccer_fifa_club_world_cup | 2025-05-27T03:35:37Z |
| Soccer | Veikkausliiga - Finland | soccer_finland_veikkausliiga | 2020-06-18T22:15:00Z |
| Soccer | Coupe de France | soccer_france_coupe_de_france | 2026-02-26T13:35:37Z |
| Soccer | Ligue 1 - France | soccer_france_ligue_one | 2020-07-16T00:55:00Z |
| Soccer | Ligue 2 - France | soccer_france_ligue_two | 2020-07-16T01:45:00Z |
| Soccer | Bundesliga - Germany | soccer_germany_bundesliga | 2020-06-06T10:05:00Z |
| Soccer | Bundesliga 2 - Germany | soccer_germany_bundesliga2 | 2020-06-06T10:05:00Z |
| Soccer | Frauen-Bundesliga | soccer_germany_bundesliga_women | 2026-02-15T11:50:37Z |
| Soccer | DFB-Pokal | soccer_germany_dfb_pokal | 2026-02-26T08:35:37Z |
| Soccer | 3. Liga - Germany | soccer_germany_liga3 | 2023-02-10T23:40:38Z |
| Soccer | Super League - Greece | soccer_greece_super_league | 2023-02-10T23:55:38Z |
| Soccer | Coppa Italia | soccer_italy_coppa_italia | 2026-02-22T13:35:37Z |
| Soccer | Serie A - Italy | soccer_italy_serie_a | 2020-06-06T10:05:00Z |
| Soccer | Serie B - Italy | soccer_italy_serie_b | 2020-06-10T14:25:00Z |
| Soccer | J League | soccer_japan_j_league | 2020-06-23T00:25:00Z |
| Soccer | K League 1 | soccer_korea_kleague1 | 2020-06-06T10:05:00Z |
| Soccer | League of Ireland | soccer_league_of_ireland | 2020-07-29T08:45:00Z |
| Soccer | Liga MX | soccer_mexico_ligamx | 2020-07-15T17:25:00Z |
| Soccer | Dutch Eredivisie | soccer_netherlands_eredivisie | 2020-09-04T16:15:00Z |
| Soccer | Eliteserien - Norway | soccer_norway_eliteserien | 2020-06-06T10:05:00Z |
| Soccer | Ekstraklasa - Poland | soccer_poland_ekstraklasa | 2022-06-30T01:05:00Z |
| Soccer | Primeira Liga - Portugal | soccer_portugal_primeira_liga | 2020-06-06T10:05:00Z |
| Soccer | Premier League - Russia | soccer_russia_premier_league | 2025-12-01T00:40:37Z |
| Soccer | Copa del Rey | soccer_spain_copa_del_rey | 2026-02-15T11:50:37Z |
| Soccer | La Liga - Spain | soccer_spain_la_liga | 2020-06-06T10:05:00Z |
| Soccer | La Liga 2 - Spain | soccer_spain_segunda_division | 2020-06-06T10:05:00Z |
| Soccer | Saudi Pro League | soccer_saudi_arabia_pro_league | 2026-02-15T11:50:37Z |
| Soccer | Premiership - Scotland | soccer_spl | 2020-07-17T13:55:00Z |
| Soccer | Allsvenskan - Sweden | soccer_sweden_allsvenskan | 2020-06-06T10:05:00Z |
| Soccer | Superettan - Sweden | soccer_sweden_superettan | 2020-06-06T10:05:00Z |
| Soccer | Swiss Superleague | soccer_switzerland_superleague | 2020-06-06T10:05:00Z |
| Soccer | Turkey Super League | soccer_turkey_super_league | 2020-06-06T10:05:00Z |
| Soccer | UEFA Europa Conference League | soccer_uefa_europa_conference_league | 2022-10-23T01:50:38Z |
| Soccer | UEFA Champions League | soccer_uefa_champs_league | 2020-07-10T16:15:00Z |
| Soccer | UEFA Champions League Qualification | soccer_uefa_champs_league_qualification | 2023-07-22T06:50:40Z |
| Soccer | UEFA Women's Champions League | soccer_uefa_champs_league_women | 2025-03-24T07:45:38Z |
| Soccer | UEFA Europa League | soccer_uefa_europa_league | 2020-06-22T18:25:00Z |
| Soccer | UEFA Euro 2024 | soccer_uefa_european_championship | 2021-05-19T05:25:00Z |
| Soccer | UEFA Euro Qualification | soccer_uefa_euro_qualification | 2023-10-12T12:40:40Z |
| Soccer | UEFA Nations League | soccer_uefa_nations_league | 2022-06-11T00:25:00Z |
| Soccer | CONCACAF Gold Cup | soccer_concacaf_gold_cup | 2025-06-09T07:10:37Z |
| Soccer | CONCACAF Leagues Cup | soccer_concacaf_leagues_cup | 2025-07-25T11:45:38Z |
| Soccer | Copa América | soccer_conmebol_copa_america | 2024-04-10T03:05:38Z |
| Soccer | Copa Libertadores | soccer_conmebol_copa_libertadores | 2022-06-11T00:45:00Z |
| Soccer | Copa Sudamericana | soccer_conmebol_copa_sudamericana | 2025-03-24T07:30:38Z |
| Soccer | MLS | soccer_usa_mls | 2020-06-27T03:05:00Z |
| Tennis | [ATP Australian Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_aus_open_singles | 2021-02-06T11:45:00Z |
| Tennis | [ATP Barcelona Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_barcelona_open | 2026-04-13T13:05:37Z |
| Tennis | [ATP Canadian Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_canadian_open | 2024-08-06T04:10:38Z |
| Tennis | [ATP China Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_china_open | 2024-09-24T19:25:39Z |
| Tennis | [ATP Cincinnati Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_cincinnati_open | 2024-08-12T01:50:38Z |
| Tennis | [ATP Dubai Championships](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_dubai | 2025-02-24T01:15:38Z |
| Tennis | [ATP French Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_french_open | 2020-09-24T22:55:00Z |
| Tennis | [ATP Hamburg Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_hamburg_open | 2026-05-17T03:30:37Z |
| Tennis | [ATP Halle Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_halle_open | 2026-06-15T03:45:36Z |
| Tennis | [ATP Indian Wells](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_indian_wells | 2025-03-04T22:20:40Z |
| Tennis | [ATP Italian Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_italian_open | 2025-05-06T10:45:38Z |
| Tennis | [ATP Madrid Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_madrid_open | 2025-04-22T05:55:38Z |
| Tennis | [ATP Miami Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_miami_open | 2025-03-17T21:55:38Z |
| Tennis | [ATP Monte-Carlo Masters](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_monte_carlo_masters | 2025-04-06T09:30:38Z |
| Tennis | [ATP Munich](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_munich | 2026-04-13T13:05:37Z |
| Tennis | [ATP Paris Masters](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_paris_masters | 2024-10-28T04:10:37Z |
| Tennis | [ATP Qatar Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_qatar_open | 2025-02-16T10:00:38Z |
| Tennis | [ATP Queen's Club Championships](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_queens_club_champ | 2026-06-15T03:45:36Z |
| Tennis | [ATP Shanghai Masters](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_shanghai_masters | 2024-10-05T03:55:38Z |
| Tennis | [ATP US Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_us_open | 2020-08-28T10:05:00Z |
| Tennis | [ATP Washington Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_washington_open | 2026-07-27T01:40:38Z |
| Tennis | [ATP Wimbledon](https://the-odds-api.com/sports/tennis-odds.html) | tennis_atp_wimbledon | 2021-06-25T22:35:00Z |
| Tennis | [WTA Australian Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_aus_open_singles | 2021-02-06T11:45:00Z |
| Tennis | [WTA Bad Homburg Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_bad_homburg_open | 2026-06-21T12:35:37Z |
| Tennis | [WTA Canadian Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_canadian_open | 2024-08-06T04:10:38Z |
| Tennis | [WTA Charleston Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_charleston_open | 2026-03-30T07:00:37Z |
| Tennis | [WTA China Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_china_open | 2024-09-24T05:00:38Z |
| Tennis | [WTA Cincinnati Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_cincinnati_open | 2024-08-12T01:50:38Z |
| Tennis | [WTA Dubai Championships](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_dubai | 2025-02-16T10:25:38Z |
| Tennis | [WTA French Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_french_open | 2020-09-24T22:55:00Z |
| Tennis | [WTA German Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_german_open | 2026-06-15T03:45:36Z |
| Tennis | [WTA Indian Wells](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_indian_wells | 2025-03-04T23:30:39Z |
| Tennis | [WTA Italian Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_italian_open | 2025-05-06T10:45:38Z |
| Tennis | [WTA Madrid Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_madrid_open | 2025-04-22T05:55:38Z |
| Tennis | [WTA Miami Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_miami_open | 2025-03-17T21:45:37Z |
| Tennis | [WTA Monterrey Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_monterrey_open | 2026-08-23T14:10:37Z |
| Tennis | [WTA Qatar Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_qatar_open | 2025-02-10T05:10:37Z |
| Tennis | [WTA Queen's Club Championships](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_queens_club_champ | 2026-06-08T07:25:36Z |
| Tennis | [WTA Internationaux de Strasbourg](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_strasbourg | 2026-05-17T04:15:37Z |
| Tennis | [WTA Stuttgart Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_stuttgart_open | 2026-04-13T13:05:37Z |
| Tennis | [WTA US Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_us_open | 2020-08-28T10:05:00Z |
| Tennis | [WTA Washington Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_washington_open | 2026-07-27T01:40:38Z |
| Tennis | [WTA Wimbledon](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_wimbledon | 2021-06-25T22:45:00Z |
| Tennis | [WTA Wuhan Open](https://the-odds-api.com/sports/tennis-odds.html) | tennis_wta_wuhan_open | 2024-10-06T13:00:37Z |

## [#](https://the-odds-api.com/historical-odds-data/#get-access) Get Access

Historical odds data is only available for paid subscriptions. Get an API key by subscribing to a [usage plan](https://the-odds-api.com/#get-access).

Subscriptions can also be managed in the [accounts portal](https://the-odds-api.com/account/).
