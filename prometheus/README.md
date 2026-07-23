
These files are for the Prometheus and Alertmanager containers.

Prometheus decides if an alert condition is true.
It evaluates rules like up{job="auth-service"} == 0.
It marks alerts as firing/resolved.

Alertmanager decides what to do with those alerts.
where to send them (Lambda webhook, email, etc.)
grouping and dedup (don’t spam one message per timeseries)
timing controls (group_wait, repeat_interval)
silences and inhibition rules (mute noisy alerts, suppress lower severity)
