"""Configured local date and time helpers for NutriPulse."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone


DEFAULT_UTC_OFFSET_HOURS = 5.0


def utc_offset_hours() -> float:
    """Return the configured offset with safe timezone bounds."""
    try:
        configured = float(
            os.getenv("NUTRIPULSE_UTC_OFFSET_HOURS", str(DEFAULT_UTC_OFFSET_HOURS))
            or DEFAULT_UTC_OFFSET_HOURS
        )
    except ValueError:
        configured = DEFAULT_UTC_OFFSET_HOURS
    return min(14.0, max(-12.0, configured))


def local_now(moment: datetime | None = None) -> datetime:
    """Return a timezone-aware datetime in the configured NutriPulse timezone."""
    source = moment or datetime.now(timezone.utc)
    if source.tzinfo is None:
        source = source.replace(tzinfo=timezone.utc)
    return source.astimezone(timezone(timedelta(hours=utc_offset_hours())))


def local_today(moment: datetime | None = None) -> date:
    """Return today's date in the configured NutriPulse timezone."""
    return local_now(moment).date()


def local_week_start(moment: datetime | None = None) -> date:
    """Return Monday of the configured local week."""
    today = local_today(moment)
    return today - timedelta(days=today.weekday())
