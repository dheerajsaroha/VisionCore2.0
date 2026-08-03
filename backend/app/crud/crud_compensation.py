"""
crud_compensation.py — CRUD & Engines for Compensation & Benefits Management System
Sprint 4 — Entity 4
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.db.models.all_models import (
    CompensationGrade, CompensationBand, SalaryRevision, BenefitsPlan,
    BenefitsEnrollment, EquityGrant, EquityVestingEvent,
    TotalRewardsStatement, CompensationReview, User
)

# Merit increase lookup by performance rating band
MERIT_TABLE = {(4.5, 5.0): 15.0, (3.5, 4.5): 10.0, (2.5, 3.5): 5.0, (0.0, 2.5): 0.0}


def _merit_pct_from_rating(rating: float) -> float:
    for (lo, hi), pct in MERIT_TABLE.items():
        if lo <= rating <= hi:
            return pct
    return 0.0


def _compa_ratio(salary: float, midpoint: float) -> float:
    if midpoint <= 0:
        return 100.0
    return round((salary / midpoint) * 100, 2)


class CRUDCompensationEngine:
    def create_grade(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> CompensationGrade:
        grade = CompensationGrade(
            organization_id=org_id,
            grade_code=obj_in["grade_code"],
            grade_name=obj_in["grade_name"],
            salary_min=obj_in["salary_min"],
            salary_mid=obj_in["salary_mid"],
            salary_max=obj_in["salary_max"],
            currency=obj_in.get("currency", "INR"),
            is_active=True
        )
        db.add(grade)
        db.commit()
        db.refresh(grade)

        for band_data in (obj_in.get("bands") or []):
            band = CompensationBand(
                grade_id=grade.id,
                band_label=band_data["band_label"],
                band_min=band_data["band_min"],
                band_max=band_data["band_max"],
                target_pct_of_midpoint=band_data.get("target_pct_of_midpoint", 100.0)
            )
            db.add(band)
        db.commit()
        return grade

    def get_grades(self, db: Session, org_id: UUID) -> List[CompensationGrade]:
        return db.query(CompensationGrade).filter(
            CompensationGrade.organization_id == org_id,
            CompensationGrade.is_active.is_(True)
        ).order_by(CompensationGrade.salary_mid).all()

    def get_compa_ratio(self, salary: float, grade: CompensationGrade) -> float:
        return _compa_ratio(salary, grade.salary_mid)


class CRUDSalaryRevisionEngine:
    def propose_revision(self, db: Session, org_id: UUID, obj_in: Dict[str, Any], proposer_id: int) -> SalaryRevision:
        prev = obj_in["previous_salary"]
        proposed = obj_in["proposed_salary"]
        increase_pct = round(((proposed - prev) / max(1, prev)) * 100, 2)

        rev = SalaryRevision(
            organization_id=org_id,
            user_id=obj_in["user_id"],
            revision_type=obj_in.get("revision_type", "merit"),
            previous_salary=prev,
            proposed_salary=proposed,
            increase_pct=increase_pct,
            status="proposed",
            justification=obj_in.get("justification"),
            performance_review_id=obj_in.get("performance_review_id")
        )
        db.add(rev)
        db.commit()
        db.refresh(rev)
        return rev

    def merit_revision_from_rating(self, db: Session, org_id: UUID, user_id: int, current_salary: float, rating: float) -> SalaryRevision:
        pct = _merit_pct_from_rating(rating)
        proposed = round(current_salary * (1 + pct / 100), 2)
        return self.propose_revision(db, org_id, {
            "user_id": user_id,
            "revision_type": "merit",
            "previous_salary": current_salary,
            "proposed_salary": proposed,
            "justification": f"Merit increase: {pct}% based on performance rating {rating}"
        }, user_id)

    def approve_revision(self, db: Session, revision_id: int, approver_id: int, approve: bool) -> SalaryRevision:
        rev = db.query(SalaryRevision).filter(SalaryRevision.id == revision_id).first()
        if rev:
            rev.status = "approved" if approve else "rejected"
            rev.approved_by_user_id = approver_id
            rev.effective_date = datetime.now(timezone.utc)
            db.commit()
            db.refresh(rev)
        return rev


class CRUDBenefitsEngine:
    def create_plan(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> BenefitsPlan:
        plan = BenefitsPlan(
            organization_id=org_id,
            plan_name=obj_in["plan_name"],
            plan_type=obj_in.get("plan_type", "health"),
            description=obj_in.get("description"),
            employer_contribution_pct=obj_in.get("employer_contribution_pct", 0.0),
            employee_contribution_pct=obj_in.get("employee_contribution_pct", 0.0),
            max_coverage_amount=obj_in.get("max_coverage_amount", 0.0),
            is_mandatory=obj_in.get("is_mandatory", False),
            is_active=True
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan

    def enroll_user(self, db: Session, org_id: UUID, user_id: int, plan_id: int, tier: str = "individual", elected_amount: float = 0.0) -> BenefitsEnrollment:
        enrollment = BenefitsEnrollment(
            organization_id=org_id,
            user_id=user_id,
            plan_id=plan_id,
            coverage_tier=tier,
            elected_amount=elected_amount,
            status="active"
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        return enrollment


class CRUDEquityEngine:
    def issue_grant(self, db: Session, org_id: UUID, obj_in: Dict[str, Any]) -> EquityGrant:
        grant = EquityGrant(
            organization_id=org_id,
            user_id=obj_in["user_id"],
            grant_type=obj_in.get("grant_type", "rsu"),
            total_shares=obj_in["total_shares"],
            vested_shares=0,
            strike_price=obj_in.get("strike_price", 0.0),
            cliff_months=obj_in.get("cliff_months", 12),
            vesting_months=obj_in.get("vesting_months", 48),
            status="active"
        )
        db.add(grant)
        db.commit()
        db.refresh(grant)

        # Generate vesting events: cliff at month 12 (25%), then monthly for rest
        total = grant.total_shares
        cliff_shares = round(total * 0.25)
        remaining = total - cliff_shares
        post_cliff_months = grant.vesting_months - grant.cliff_months
        monthly_shares = round(remaining / max(1, post_cliff_months)) if post_cliff_months > 0 else 0

        grant_dt = grant.grant_date
        # Cliff event
        cliff_date = grant_dt + timedelta(days=grant.cliff_months * 30)
        db.add(EquityVestingEvent(grant_id=grant.id, scheduled_date=cliff_date, shares_vesting=cliff_shares, vested=False))

        # Monthly events post-cliff
        for m in range(1, post_cliff_months + 1):
            vest_date = cliff_date + timedelta(days=m * 30)
            db.add(EquityVestingEvent(grant_id=grant.id, scheduled_date=vest_date, shares_vesting=monthly_shares, vested=False))

        db.commit()
        db.refresh(grant)
        return grant


class CRUDTotalRewardsEngine:
    def generate_statement(self, db: Session, org_id: UUID, user_id: int, fiscal_year: int, base_salary: float, grade_id: Optional[int] = None, bonus: float = 0.0, equity_fmv: float = 0.0) -> TotalRewardsStatement:
        # Sum active benefits value
        enrollments = db.query(BenefitsEnrollment).filter(
            BenefitsEnrollment.organization_id == org_id,
            BenefitsEnrollment.user_id == user_id,
            BenefitsEnrollment.status == "active"
        ).all()
        benefits_value = sum(e.elected_amount for e in enrollments)

        grade = db.query(CompensationGrade).filter(CompensationGrade.id == grade_id).first() if grade_id else None
        compa = _compa_ratio(base_salary, grade.salary_mid) if grade else 100.0

        total = base_salary + benefits_value + equity_fmv + bonus

        stmt = TotalRewardsStatement(
            organization_id=org_id,
            user_id=user_id,
            fiscal_year=fiscal_year,
            base_salary=base_salary,
            total_benefits_value=benefits_value,
            equity_fmv=equity_fmv,
            bonus_paid=bonus,
            total_comp=total,
            compa_ratio=compa,
            grade_id=grade_id
        )
        db.add(stmt)
        db.commit()
        db.refresh(stmt)
        return stmt


crud_compensation_engine = CRUDCompensationEngine()
crud_salary_revision_engine = CRUDSalaryRevisionEngine()
crud_benefits_engine = CRUDBenefitsEngine()
crud_equity_engine = CRUDEquityEngine()
crud_total_rewards_engine = CRUDTotalRewardsEngine()
