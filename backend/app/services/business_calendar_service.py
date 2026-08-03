"""
business_calendar_service.py — Enterprise Business Calendar Service
VisionCore 3.0 Enterprise Platform Services Layer

Provides:
- Organization calendars (working days, weekends, time zones)
- Holiday calendars (global, regional, country-specific)
- Fiscal calendars (quarters, fiscal year boundaries)
- Shift calendars (shift rotation schedules)
- Working day SLA calculation helpers for Attendance, Leave, and Payroll
- Timezone-aware date arithmetic
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)


class DayType(Enum):
    WORKING = "working"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"
    OPTIONAL_HOLIDAY = "optional_holiday"


@dataclass
class HolidayEntry:
    date: str          # ISO 8601: YYYY-MM-DD
    name: str
    type: DayType = DayType.HOLIDAY
    country_code: Optional[str] = None
    region: Optional[str] = None
    is_optional: bool = False


@dataclass
class FiscalCalendar:
    organization_id: str
    fiscal_year_start_month: int = 4          # April is common in India
    fiscal_year_start_day: int = 1
    quarter_boundaries: List[int] = field(default_factory=lambda: [1, 4, 7, 10])  # Q1 start months


@dataclass
class WorkingDayConfig:
    organization_id: str
    working_days: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])  # Mon–Fri (0=Mon)
    timezone: str = "Asia/Kolkata"
    standard_hours_per_day: float = 8.0
    start_time: str = "09:00"
    end_time: str = "18:00"


class BusinessCalendarService:
    """
    Centralized Business Calendar Service.
    Consumed by Attendance, Leave, Payroll, Shift, and Workflow modules.
    """

    def __init__(self):
        # In-memory store per organization. Production: persist in DB.
        self._holidays: Dict[str, List[HolidayEntry]] = {}
        self._working_config: Dict[str, WorkingDayConfig] = {}
        self._fiscal_config: Dict[str, FiscalCalendar] = {}
        self._register_global_defaults()

    # ------------------------------------------------------------------
    #  Configuration
    # ------------------------------------------------------------------

    def configure_working_days(self, config: WorkingDayConfig) -> None:
        """Set working day & timezone configuration for an organization."""
        self._working_config[config.organization_id] = config
        logger.info(f"Working day config set for org {config.organization_id}: {config.working_days} | tz={config.timezone}")

    def configure_fiscal_calendar(self, fiscal: FiscalCalendar) -> None:
        """Set fiscal calendar boundaries for an organization."""
        self._fiscal_config[fiscal.organization_id] = fiscal
        logger.info(f"Fiscal calendar set for org {fiscal.organization_id}: starts month {fiscal.fiscal_year_start_month}")

    def add_holiday(self, organization_id: str, entry: HolidayEntry) -> None:
        """Add a holiday to an organization's calendar."""
        if organization_id not in self._holidays:
            self._holidays[organization_id] = []
        # Avoid duplicates
        existing_dates = {h.date for h in self._holidays[organization_id]}
        if entry.date not in existing_dates:
            self._holidays[organization_id].append(entry)

    def get_holidays(self, organization_id: str, year: Optional[int] = None) -> List[HolidayEntry]:
        """Get all holidays for an organization, optionally filtered by year."""
        entries = self._holidays.get(organization_id, [])
        entries += self._holidays.get("__global__", [])
        if year:
            entries = [h for h in entries if h.date.startswith(str(year))]
        return sorted(entries, key=lambda h: h.date)

    # ------------------------------------------------------------------
    #  Working Day Logic
    # ------------------------------------------------------------------

    def is_working_day(self, check_date: date, organization_id: str) -> bool:
        """Return True if the given date is a working day for the org."""
        config = self._working_config.get(organization_id, WorkingDayConfig(organization_id))
        # Check weekday
        if check_date.weekday() not in config.working_days:
            return False
        # Check holidays
        date_str = check_date.isoformat()
        holidays = self.get_holidays(organization_id)
        holiday_dates = {h.date for h in holidays if not h.is_optional}
        return date_str not in holiday_dates

    def count_working_days(
        self,
        start: date,
        end: date,
        organization_id: str,
        inclusive: bool = True,
    ) -> int:
        """Count working days between two dates (inclusive by default)."""
        count = 0
        current = start
        last = end if inclusive else end - timedelta(days=1)
        while current <= last:
            if self.is_working_day(current, organization_id):
                count += 1
            current += timedelta(days=1)
        return count

    def get_next_working_day(self, from_date: date, organization_id: str, days_ahead: int = 1) -> date:
        """Get the N-th working day after a given date."""
        found = 0
        current = from_date + timedelta(days=1)
        while found < days_ahead:
            if self.is_working_day(current, organization_id):
                found += 1
                if found == days_ahead:
                    return current
            current += timedelta(days=1)
        return current

    def get_working_days_in_month(self, year: int, month: int, organization_id: str) -> List[date]:
        """Return all working days in a given month."""
        import calendar
        _, last_day = calendar.monthrange(year, month)
        days = []
        for d in range(1, last_day + 1):
            candidate = date(year, month, d)
            if self.is_working_day(candidate, organization_id):
                days.append(candidate)
        return days

    # ------------------------------------------------------------------
    #  Timezone Utilities
    # ------------------------------------------------------------------

    def now_in_org_timezone(self, organization_id: str) -> datetime:
        """Return current datetime in the organization's configured timezone."""
        config = self._working_config.get(organization_id, WorkingDayConfig(organization_id))
        try:
            tz = ZoneInfo(config.timezone)
            return datetime.now(tz)
        except (ZoneInfoNotFoundError, Exception):
            return datetime.now(timezone.utc)

    def convert_to_utc(self, local_dt: datetime, timezone_name: str) -> datetime:
        """Convert a local datetime to UTC."""
        try:
            tz = ZoneInfo(timezone_name)
            aware_local = local_dt.replace(tzinfo=tz)
            return aware_local.astimezone(timezone.utc)
        except Exception as e:
            logger.warning(f"Timezone conversion failed for '{timezone_name}': {e}")
            return local_dt

    # ------------------------------------------------------------------
    #  Fiscal Calendar Utilities
    # ------------------------------------------------------------------

    def get_fiscal_year(self, for_date: date, organization_id: str) -> Dict[str, Any]:
        """Return the fiscal year start and end dates for a given date."""
        fiscal = self._fiscal_config.get(organization_id, FiscalCalendar(organization_id))
        sm = fiscal.fiscal_year_start_month
        sd = fiscal.fiscal_year_start_day

        if for_date.month > sm or (for_date.month == sm and for_date.day >= sd):
            fy_start = date(for_date.year, sm, sd)
            fy_end = date(for_date.year + 1, sm, sd) - timedelta(days=1)
            label = f"FY{for_date.year}-{str(for_date.year + 1)[-2:]}"
        else:
            fy_start = date(for_date.year - 1, sm, sd)
            fy_end = date(for_date.year, sm, sd) - timedelta(days=1)
            label = f"FY{for_date.year - 1}-{str(for_date.year)[-2:]}"

        return {"label": label, "start": fy_start.isoformat(), "end": fy_end.isoformat()}

    def get_fiscal_quarter(self, for_date: date, organization_id: str) -> Dict[str, Any]:
        """Return the fiscal quarter for a given date."""
        fiscal = self._fiscal_config.get(organization_id, FiscalCalendar(organization_id))
        fy = self.get_fiscal_year(for_date, organization_id)
        fy_start = date.fromisoformat(fy["start"])
        months_elapsed = (for_date.year - fy_start.year) * 12 + (for_date.month - fy_start.month)
        quarter = (months_elapsed // 3) + 1
        return {"quarter": f"Q{quarter}", "fiscal_year": fy["label"]}

    # ------------------------------------------------------------------
    #  Global Default Holidays
    # ------------------------------------------------------------------

    def _register_global_defaults(self) -> None:
        """Pre-seed commonly observed global public holidays."""
        global_holidays = [
            HolidayEntry("2026-01-01", "New Year's Day", DayType.HOLIDAY, country_code="GLOBAL"),
            HolidayEntry("2026-01-26", "Republic Day", DayType.HOLIDAY, country_code="IN"),
            HolidayEntry("2026-08-15", "Independence Day", DayType.HOLIDAY, country_code="IN"),
            HolidayEntry("2026-10-02", "Gandhi Jayanti", DayType.HOLIDAY, country_code="IN"),
            HolidayEntry("2026-12-25", "Christmas Day", DayType.HOLIDAY, country_code="GLOBAL"),
        ]
        self._holidays["__global__"] = global_holidays


# Singleton
business_calendar_service = BusinessCalendarService()
