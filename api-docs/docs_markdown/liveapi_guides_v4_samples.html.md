<!-- Source: https://the-odds-api.com/liveapi/guides/v4/samples.html -->

Title: Odds API Code Samples V4

URL Source: https://the-odds-api.com/liveapi/guides/v4/samples.html

Markdown Content:
The Odds API is easy to use with your favorite coding language. We've included simple Python and Node.js code examples to help you get started.

Be sure to specify your api key in order for the examples to work. Get a [free API key here](https://the-odds-api.com/#get-access).

For more details, see the [API docs](https://the-odds-api.com/liveapi/guides/v4/index.html). Code samples are also available on [Github(opens new window)](https://github.com/the-odds-api)

## [#](https://the-odds-api.com/liveapi/guides/v4/samples.html#python) Python

Security Tip for Repl.it users

This example uses [Repl.it(opens new window)](https://repl.it/)* to run live code. If you continue coding using a free Repl.it account, anyone visiting your Repl.it repo might see your api key.

To make sure it stays secret, create a file called `.env` containing `api_key=YOUR_API_KEY`

Back in main.py, bring in your api key with:

```
import os
api_key = os.getenv("api_key")
```

For more info, see the [Repl.it docs(opens new window)](https://repl.it/site/docs/repls/secret-keys)

* The Odds API is not affiliated with Repl.it in any way

This code sample can also be found on [Github(opens new window)](https://github.com/the-odds-api/samples-python)

## [#](https://the-odds-api.com/liveapi/guides/v4/samples.html#node-js) Node.js

Security Tip for Repl.it users

This example uses [Repl.it(opens new window)](https://repl.it/)* to run live code. If you continue coding using a free Repl.it account, anyone visiting your Repl.it repo might see your api key.

To make sure it stays secret, create a file called `.env` containing `api_key=YOUR_API_KEY`

Back in index.js, bring in your api key with:

```
const api_key = process.env.api_key
```

For more info, see the [Repl.it docs(opens new window)](https://repl.it/site/docs/repls/secret-keys)

* The Odds API is not affiliated with Repl.it in any way

This code sample can also be found on [Github(opens new window)](https://github.com/the-odds-api/samples-nodejs)
