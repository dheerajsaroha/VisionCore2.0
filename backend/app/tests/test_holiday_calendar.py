"""
Tests for holiday calendar scoping and persistence.

Three defects are covered here:

* Indian national holidays were applied to every tenant worldwide, because
  `is_working_day` never looked at an entry's `country_code` or `region`.
* The calendar store was process-local, so holidays vanished on restart.
* Deleting a holiday removed the database row but left the entry cached, so it
  kept excluding working days for the life of the process.
"""
import uuid
from datetime import date

import pytest

from app.db.database import SessionLocal
from app.db.models.all_models import (
    HolidayCalendar,
    HolidayEntry,
    Organization,
    Role,
    User,
)
from app.services.business_calendar_service import (
    DayType,
    HolidayEntry as CalendarHoliday,
    business_calendar_service,
)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def org(db):
    row = Organization(
        name=f"Holiday Org {uuid.uuid4().hex[:6]}",
        legal_id=f"TEST-HOL-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def calendar_service():
    """A fresh service per test so the in-memory store cannot leak between them."""
    from app.services.business_calendar_service import BusinessCalendarService

    return BusinessCalendarService()


class TestRegionalScoping:
    def test_indian_holiday_does_not_apply_to_a_us_org(self, calendar_service):
        calendar_service._holidays["us-org"] = [
            CalendarHoliday("2026-03-04", "Holi", DayType.HOLIDAY, country_code="IN",
                           region="Maharashtra"),
        ]
        calendar_service.set_org_region("us-org", "US", "California")

        # A US organisation must still work on the Indian festival day.
        assert calendar_service.is_working_day(date(2026, 3, 4), "us-org") is True

    def test_a_holiday_does_apply_to_its_own_country(self, calendar_service):
        calendar_service._holidays["us-org"] = [
            CalendarHoliday("2026-07-04", "Independence Day", DayType.HOLIDAY,
                            country_code="US", region="California"),
        ]
        calendar_service.set_org_region("us-org", "US", "California")

        assert calendar_service.is_working_day(date(2026, 7, 4), "us-org") is False

    def test_regional_holiday_does_not_leak_to_another_state(self, calendar_service):
        calendar_service._holidays["in-ka"] = []
        calendar_service.set_org_region("in-ka", "IN", "Karnataka")

        # The Maharashtra Holi in the shared global bucket must not apply.
        assert calendar_service.is_working_day(date(2026, 3, 4), "in-ka") is True

    def test_global_holidays_apply_everywhere(self, calendar_service):
        calendar_service.set_org_region("in-ka", "IN", "Karnataka")
        calendar_service.set_org_region("us-org", "US", "California")

        # New Year's Day is registered as GLOBAL and must exclude both.
        assert calendar_service.is_working_day(date(2026, 1, 1), "in-ka") is False
        assert calendar_service.is_working_day(date(2026, 1, 1), "us-org") is False

    def test_optional_holidays_never_exclude_a_working_day(self, calendar_service):
        calendar_service._holidays["in-org"] = [
            CalendarHoliday("2026-03-05", "Optional off", DayType.OPTIONAL_HOLIDAY,
                            country_code="IN", is_optional=True),
        ]
        calendar_service.set_org_region("in-org", "IN", "Karnataka")

        assert calendar_service.is_working_day(date(2026, 3, 5), "in-org") is True

    def test_weekends_are_never_working_days(self, calendar_service):
        calendar_service.set_org_region("us-org", "US", "California")
        # 7 March 2026 is a Saturday.
        assert calendar_service.is_working_day(date(2026, 3, 7), "us-org") is False

    def test_holiday_cache_is_invalidated_on_mutation(self, calendar_service):
        calendar_service.set_org_region("in-org", "IN", "Karnataka")
        calendar_service._holidays["in-org"] = []
        assert calendar_service.is_working_day(date(2026, 5, 1), "in-org") is True

        calendar_service.add_holiday(
            "in-org",
            CalendarHoliday("2026-05-01", "Labour Day", DayType.HOLIDAY, country_code="IN"),
        )
        assert calendar_service.is_working_day(date(2026, 5, 1), "in-org") is False


class TestRemoveHoliday:
    def test_removing_an_entry_restores_the_working_day(self, calendar_service):
        calendar_service.set_org_region("in-org", "IN", "Karnataka")
        calendar_service._holidays["in-org"] = [
            CalendarHoliday("2026-05-01", "Labour Day", DayType.HOLIDAY, country_code="IN"),
        ]
        assert calendar_service.is_working_day(date(2026, 5, 1), "in-org") is False

        assert calendar_service.remove_holiday("in-org", "2026-05-01") is True
        assert calendar_service.is_working_day(date(2026, 5, 1), "in-org") is True

    def test_removing_an_absent_date_reports_no_change(self, calendar_service):
        assert calendar_service.remove_holiday("nope-org", "2026-05-01") is False


class TestMemoryGrowthRegression:
    def test_repeated_reads_do_not_grow_the_stored_list(self, calendar_service):
        """
        Regression guard.

        `get_holidays` used `entries += self._holidays["__global__"]`, appending
        the five global entries into the organisation's own list on every call.
        It is invoked once per candidate day from the leave-day loops, so the
        list grew without bound.
        """
        calendar_service._holidays["grow-org"] = [
            CalendarHoliday("2026-05-01", "Labour Day", DayType.HOLIDAY, country_code="IN"),
        ]
        stored = calendar_service._holidays["grow-org"]

        for _ in range(50):
            calendar_service.get_holidays("grow-org")

        assert len(stored) == 1
        assert len(calendar_service.get_holidays("grow-org")) == 6  # 1 org + 5 global


class TestDatabaseLoading:
    def test_holidays_survive_a_restart(self, db, org, calendar_service):
        """A holiday stored in the database must be visible to a fresh service."""
        cal = HolidayCalendar(
            org_id=org.id,
            name=f"Test Calendar {uuid.uuid4().hex[:6]}",
            country_code="IN",
            region="Karnataka",
            is_active=True,
        )
        db.add(cal)
        db.commit()
        db.refresh(cal)

        db.add(HolidayEntry(
            org_id=org.id,
            calendar_id=cal.id,
            name="Kannada Rajyotsava",
            holiday_date=date(2026, 11, 1),
            holiday_type="NATIONAL",
            is_recurring=False,
        ))
        db.commit()

        fresh = type(calendar_service)()
        loaded = fresh.load_from_db(db)

        assert loaded >= 1
        key = str(org.id)
        assert fresh._org_region[key] == ("IN", "Karnataka")
        assert fresh.is_working_day(date(2026, 11, 1), key) is False

    def test_optional_entries_load_as_optional(self, db, org, calendar_service):
        cal = HolidayCalendar(
            org_id=org.id,
            name=f"Opt Calendar {uuid.uuid4().hex[:6]}",
            country_code="IN",
            is_active=True,
        )
        db.add(cal)
        db.commit()
        db.refresh(cal)

        db.add(HolidayEntry(
            org_id=org.id,
            calendar_id=cal.id,
            name="Floating Holiday",
            holiday_date=date(2026, 12, 24),
            holiday_type="OPTIONAL",
            is_recurring=False,
        ))
        db.commit()

        fresh = type(calendar_service)()
        fresh.load_from_db(db)
        key = str(org.id)
        # 24 Dec 2026 is a Thursday and not a pre-seeded global holiday.
        assert fresh.is_working_day(date(2026, 12, 24), key) is True

    def test_other_tenants_holidays_are_not_loaded(self, db, org, calendar_service):
        other = Organization(
            name=f"Other {uuid.uuid4().hex[:6]}",
            legal_id=f"TEST-HOL-{uuid.uuid4().hex[:8].upper()}",
        )
        db.add(other)
        db.commit()
        db.refresh(other)

        cal = HolidayCalendar(
            org_id=other.id,
            name=f"Theirs {uuid.uuid4().hex[:6]}",
            country_code="IN",
            is_active=True,
        )
        db.add(cal)
        db.commit()
        db.refresh(cal)
        db.add(HolidayEntry(
            org_id=other.id,
            calendar_id=cal.id,
            name="Theirs Only",
            holiday_date=date(2026, 6, 1),
            holiday_type="NATIONAL",
            is_recurring=False,
        ))
        db.commit()

        fresh = type(calendar_service)()
        fresh.load_from_db(db)

        assert fresh.is_working_day(date(2026, 6, 1), str(org.id)) is True
        assert fresh.is_working_day(date(2026, 6, 1), str(other.id)) is False


class TestSchemaContract:
    def test_invalid_holiday_type_is_rejected_before_the_database(self):
        """
        The UI previously offered REGIONAL and COMPANY, which the
        ck_holiday_entry_type CHECK constraint rejects with an IntegrityError.
        """
        from pydantic import ValidationError

        from app.routers.workforce_router import HolidayEntryCreate

        for bad in ("REGIONAL", "COMPANY", "nonsense"):
            with pytest.raises(ValidationError):
                HolidayEntryCreate(holiday_date=date(2026, 5, 1), name="x", holiday_type=bad)

        for good in ("NATIONAL", "OPTIONAL", "RESTRICTED", "ORG_SPECIFIC"):
            assert HolidayEntryCreate(
                holiday_date=date(2026, 5, 1), name="x", holiday_type=good
            ).holiday_type == good

    def test_calendar_can_carry_country_and_region(self):
        from app.routers.workforce_router import HolidayCalendarCreate

        cal = HolidayCalendarCreate(name="India — Karnataka", country_code="in", region="Karnataka")
        assert cal.country_code == "in"
        assert cal.region == "Karnataka"

    def test_entry_can_target_a_specific_calendar(self):
        from app.routers.workforce_router import HolidayEntryCreate

        assert HolidayEntryCreate(
            holiday_date=date(2026, 5, 1), name="x", calendar_id=7
        ).calendar_id == 7
