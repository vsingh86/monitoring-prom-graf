#!/bin/sh
set -eu

if [ -z "${HRIS_CARD_BE_METRICS_TOKEN:-}" ]; then
  echo "HRIS_CARD_BE_METRICS_TOKEN is required for card-service metrics scrape" >&2
  exit 1
fi

if [ -z "${HRIS_CARD_BE_METRICS_TOKEN:-}" ]; then
  echo "HRIS_CARD_BE_METRICS_TOKEN is required for card-service metrics scrape" >&2
  exit 1
fi

if [ -z "${HRIS_HIMS_FE_METRICS_TOKEN:-}" ]; then
  echo "HRIS_HIMS_FE_METRICS_TOKEN is required for HIMS web metrics scrape" >&2
  exit 1
fi

if [ -z "${HRIS_HIMS_BE_METRICS_TOKEN:-}" ]; then
  echo "HRIS_HIMS_BE_METRICS_TOKEN is required for HIMS webservice metrics scrape" >&2
  exit 1
fi

if [ -z "${PROMETHEUS_SERVER:-}" ]; then
  echo "PROMETHEUS_SERVER is required for Prometheus external URL" >&2
  exit 1
fi

printf '%s' "$HRIS_CARD_BE_METRICS_TOKEN" > /tmp/HRIS_CARD_BE_METRICS_TOKEN
printf '%s' "$HRIS_AUTHAPI_BE_METRICS_TOKEN" > /tmp/HRIS_AUTHAPI_BE_METRICS_TOKEN
printf '%s' "$HRIS_HIMS_FE_METRICS_TOKEN" > /tmp/HRIS_HIMS_FE_METRICS_TOKEN
printf '%s' "$HRIS_HIMS_BE_METRICS_TOKEN" > /tmp/HRIS_HIMS_BE_METRICS_TOKEN

exec /bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --web.external-url=${PROMETHEUS_SERVER}/prometheus/ \
  --web.route-prefix=/prometheus/ \
  --web.enable-lifecycle \
  --storage.tsdb.retention.time=30d
