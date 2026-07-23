#!/bin/sh
set -eu

if [ -z "${HRIS_AUTH_API_METRICS_TOKEN:-}" ]; then
  echo "HRIS_AUTH_API_METRICS_TOKEN is required for auth-service metrics scrape" >&2
  exit 1
fi

if [ -z "${HRIS_CARD_API_DEV_METRICS_TOKEN:-}" ]; then
  echo "HRIS_CARD_API_DEV_METRICS_TOKEN is required for card-service metrics scrape" >&2
  exit 1
fi

if [ -z "${HIMS_WEB_DEV_METRICS_TOKEN:-}" ]; then
  echo "HIMS_WEB_DEV_METRICS_TOKEN is required for HIMS web metrics scrape" >&2
  exit 1
fi

if [ -z "${HIMS_WEBSERVICE_DEV_METRICS_TOKEN:-}" ]; then
  echo "HIMS_WEBSERVICE_DEV_METRICS_TOKEN is required for HIMS webservice metrics scrape" >&2
  exit 1
fi

if [ -z "${PROMETHEUS_SERVER:-}" ]; then
  echo "PROMETHEUS_SERVER is required for Prometheus external URL" >&2
  exit 1
fi

printf '%s' "$HRIS_CARD_API_DEV_METRICS_TOKEN" > /tmp/hris_card_api_dev_metrics_token
printf '%s' "$HRIS_AUTH_API_METRICS_TOKEN" > /tmp/hris_auth_api_metrics_token
printf '%s' "$HIMS_WEB_DEV_METRICS_TOKEN" > /tmp/hims_web_dev_metrics_token
printf '%s' "$HIMS_WEBSERVICE_DEV_METRICS_TOKEN" > /tmp/hims_webservice_dev_metrics_token

exec /bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --web.external-url=${PROMETHEUS_SERVER}/prometheus/ \
  --web.route-prefix=/prometheus/ \
  --web.enable-lifecycle \
  --storage.tsdb.retention.time=30d
