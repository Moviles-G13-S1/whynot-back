"""Admin analytics: one secured callable that serves every dashboard BQ."""

from .endpoint import METRICS, get_admin_analytics, require_admin

__all__ = ["METRICS", "get_admin_analytics", "require_admin"]
