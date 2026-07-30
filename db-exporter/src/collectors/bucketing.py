"""Shared histogram approximation used by every vendor collector.

None of the four vendors' system views expose a true per-call latency
distribution -- only aggregates (mean/total exec time, call count) per
query/statement digest. This mirrors postgres_exporter's own well-known
approach: approximate a histogram by placing each digest's entire call count
into the smallest fixed bucket boundary >= its own mean duration, then merge
across all digests into one job-level histogram (matching how every
db_*.yml recording rule expects a single unlabeled query-duration series
per job, with no `by()` grouping). Placing each digest at its OWN mean
before merging (rather than collapsing to one overall weighted mean first)
preserves a bimodal fast/slow query mix instead of hiding it in an
artificial "average of averages."
"""
from prometheus_client.core import HistogramMetricFamily

# Matches the boundaries already observed in this repo's other histograms
# (see sample-scrape-files/dotnet-api-scrape.dat) so quantile comparisons
# across app/db layers use a familiar scale.
BUCKET_BOUNDARIES = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)


def build_query_duration_histogram(
    metric_name: str,
    help_text: str,
    rows: list[tuple[float, int, float]],
) -> HistogramMetricFamily:
    """rows: list of (mean_seconds, count, sum_seconds) -- one tuple per
    query/statement digest. Returns a single unlabeled, merged cumulative
    histogram series."""
    cumulative = [0.0] * len(BUCKET_BOUNDARIES)
    total_count = 0
    total_sum = 0.0

    for mean_seconds, count, sum_seconds in rows:
        total_count += count
        total_sum += sum_seconds
        for i, boundary in enumerate(BUCKET_BOUNDARIES):
            if mean_seconds <= boundary:
                cumulative[i] += count

    buckets = [(str(boundary), cumulative[i]) for i, boundary in enumerate(BUCKET_BOUNDARIES)]
    buckets.append(("+Inf", float(total_count)))

    family = HistogramMetricFamily(metric_name, help_text)
    family.add_metric([], buckets=buckets, sum_value=total_sum)
    return family
