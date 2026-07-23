"""Shared exact-aggregate query-duration metric builder, used by all four
vendor collectors.

Replaces the old approximated-histogram approach (bucketing each query
digest's call count at its own mean) with plain exact aggregates: count and
sum were never approximated to begin with (straight sums from each vendor's
own aggregate columns); max is a genuine per-digest maximum tracked natively
by Postgres/MySQL/SQL Server, so no approximation is needed for it either.
Oracle has no free exact source for max (v$sqlarea has no per-call max
column) -- pass max_seconds=None to omit it rather than fake it.
"""
from prometheus_client.core import GaugeMetricFamily


def build_query_stats_families(
    base_name: str,
    help_prefix: str,
    count: int,
    sum_seconds: float,
    max_seconds: float | None,
) -> list:
    count_family = GaugeMetricFamily(f"{base_name}_count", f"{help_prefix} (count).")
    count_family.add_metric([], count)

    sum_family = GaugeMetricFamily(f"{base_name}_sum", f"{help_prefix} (sum, seconds).")
    sum_family.add_metric([], sum_seconds)

    families = [count_family, sum_family]

    if max_seconds is not None:
        max_family = GaugeMetricFamily(f"{base_name}_max", f"{help_prefix} (max, seconds).")
        max_family.add_metric([], max_seconds)
        families.append(max_family)

    return families
