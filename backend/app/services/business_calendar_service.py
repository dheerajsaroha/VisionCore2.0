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
        # org id -> (country_code, region), so regional holidays can be scoped.
        self._org_region: Dict[str, Any] = {}
        # Derived from _holidays; invalidated on any mutation.
        self._holiday_cache: Dict[str, set] = {}
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
        self._holiday_cache.pop(str(organization_id), None)

    def get_holidays(self, organization_id: str, year: Optional[int] = None) -> List[HolidayEntry]:
        """Get all holidays for an organization, optionally filtered by year."""
        # Build a new list. Using `+=` on the stored list appended the global
        # entries into the organisation's own list in place, so every call grew
        # it by five more and duplicated them — and this runs once per candidate
        # day inside leave-day loops.
        entries = list(self._holidays.get(organization_id, []))
        entries.extend(self._holidays.get("__global__", []))
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
        return check_date.isoformat() not in self._mandatory_holiday_dates(organization_id)

    def _mandatory_holiday_dates(self, organization_id: str) -> set:
        """
        Non-optional holiday dates that actually apply to this organisation.

        Scoped by country and region: without this, an org's own calendar and the
        pre-seeded Indian national holidays were applied to every tenant
        worldwide, so a US or UK organisation silently lost working days.
        Cached per organisation and invalidated on mutation, because this is
        called once per candidate day from the leave-day loops.
        """
        cached = self._holiday_cache.get(organization_id)
        if cached is not None:
            return cached

        org_country, org_region = self._org_region.get(organization_id, (None, None))
        dates = set()
        for entry in self.get_holidays(organization_id):
            if entry.is_optional:
                continue
            if not self._entry_applies(entry, org_country, org_region):
                continue
            dates.add(entry.date)

        self._holiday_cache[organization_id] = dates
        return dates

    @staticmethod
    def _entry_applies(
        entry: HolidayEntry, org_country: Optional[str], org_region: Optional[str]
    ) -> bool:
        """Whether a holiday entry is in scope for an organisation."""
        code = (entry.country_code or "").upper()
        if code in ("", "GLOBAL", "*"):
            # Unscoped or explicitly global: applies everywhere.
            if entry.region:
                return org_region is not None and entry.region == org_region
            return True
        if org_country is None:
            # The organisation has not declared a country. Applying a
            # country-specific holiday would guess, so keep the conservative
            # existing behaviour of honouring it only when unscoped.
            return False
        if code != org_country.upper():
            return False
        if entry.region and org_region and entry.region != org_region:
            return False
        return True

    def set_org_region(
        self, organization_id: str, country_code: Optional[str], region: Optional[str]
    ) -> None:
        """Declare an organisation's country/region so regional holidays can be scoped."""
        key = str(organization_id)
        self._org_region[key] = (
            (country_code or "").upper() or None,
            region or None,
        )
        self._holiday_cache.pop(key, None)

    def load_from_db(self, db: Any) -> int:
        """
        Populate the in-memory calendar from the `holiday_entries` table.

        The store used to be process-local, so holidays vanished on restart and
        were invisible to any other worker. The database is authoritative; this
        makes each process reflect it.

        Returns the number of entries loaded.
        """
        from app.db.models.all_models import HolidayCalendar, HolidayEntry as HolidayRow

        try:
            calendars = db.query(HolidayCalendar).all()
        except Exception:
            logger.warning("Holiday calendars unavailable; keeping built-in defaults", exc_info=True)
            return 0

        by_org: Dict[str, Any] = {}
        for calendar in calendars:
            by_org[calendar.org_id] = calendar
            self.set_org_region(
                str(calendar.org_id),
                calendar.country_code,
                calendar.region,
            )

        loaded = 0
        for org_key, calendar in by_org.items():
            org_str = str(org_key)
            rows = (
                db.query(HolidayRow)
                .filter(HolidayRow.org_id == org_key)
                .all()
            )
            for row in rows:
                raw = row.holiday_date
                iso = raw.isoformat() if hasattr(raw, "isoformat") else str(raw)[:10]
                self._holidays.setdefault(org_str, [])
                existing = {h.date for h in self._holidays[org_str]}
                if iso in existing:
                    continue
                optional = row.holiday_type in ("OPTIONAL",)
                self._holidays[org_str].append(
                    HolidayEntry(
                        date=iso,
                        name=row.name,
                        type=DayType.OPTIONAL_HOLIDAY if optional else DayType.HOLIDAY,
                        country_code=calendar.country_code,
                        region=calendar.region,
                        is_optional=optional,
                    )
                )
                loaded += 1
            self._holiday_cache.pop(org_str, None)

        if loaded:
            logger.info("Loaded %d holiday entries from database", loaded)
        return loaded

    def remove_holiday(self, organization_id: str, iso_date: str) -> bool:
        """
        Drop a holiday from the in-memory store.

        Deleting the database row alone left the entry in memory, so a removed
        holiday kept excluding working days for the life of the process.
        """
        key = str(organization_id)
        entries = self._holidays.get(key)
        if not entries:
            return False
        before = len(entries)
        self._holidays[key] = [h for h in entries if h.date != iso_date]
        self._holiday_cache.pop(key, None)
        return len(self._holidays[key]) != before

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
