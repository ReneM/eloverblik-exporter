# eloverblik-exporter
Fetches hourly meter data for the previous week, then exports them as metrics to any Prometheus pushgateway

# Available environment variables
* API_URL: Url to the Eloverblik.dk API, defaults to `https://api.eloverblik.dk/customerapi/api`
* REFRESH_TOKEN: Required to log in and access meter data
* METERING_POINTS: Comma-separated list of meter ids to fetch data from
* PUSH_GATEWAY_URL: Url where the metrics should be pushed. VictoriaMetrics is recommended over Prometheus, since it supports adding old metrics with timestamps, and the application currently fetches the previous weeks worth of meter data. Defaults to http://victoria-metrics:8428/api/v1/import/prometheus.

Saves the data-access token (valid for 1 day) in a txt file.

Dockerfile and cron schedule included.
