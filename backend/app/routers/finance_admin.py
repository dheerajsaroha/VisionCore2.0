"""
finance_admin.py — PI-6 Finance Administration Router

Endpoints for managing financial configuration:
  - Expense Categories (tenant-scoped CRUD)
  - Salary Components (tenant-scoped CRUD)
  - Tax Configurations (tenant-scoped CRUD)
  - Statutory Rules (tenant-scoped CRUD)
  - PayrollPeriod management (create, list, status transitions)
  - PayrollRun management (create, list, approve, finalize)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.db.database import get_db
from app.db.models.all_models import (
    ExpenseCategory,
    PayrollPeriod,
    PayrollRun,
    SalaryComponent,
    StatutoryRule,
    TaxConfiguration,
    User,
)
from app.services.audit_service import audit_service

# ── Auth helpers ──────────────────────────────────────────────────────────────
# We use deps.require_permission(...) via Depends in the endpoints
# rather than manual role string checks.


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas (inline — may be migrated to schema/ later)
# ─────────────────────────────────────────────────────────────────────────────

class ExpenseCategoryCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None

class ExpenseCategoryOut(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool
    class Config: from_attributes = True


class SalaryComponentCreate(BaseModel):
    component_code: str
    component_name: str
    component_type: str = "earning"  # earning | deduction | statutory
    is_taxable: bool = True

class SalaryComponentOut(BaseModel):
    id: int
    component_code: str
    component_name: str
    component_type: str
    is_taxable: bool
    is_active: bool
    class Config: from_attributes = True


class StatutoryRuleCreate(BaseModel):
    rule_code: str
    rule_name: str
    parameter_json: str = "{}"
    effective_from: datetime
    effective_to: Optional[datetime] = None

class StatutoryRuleOut(BaseModel):
    id: int
    rule_code: str
    rule_name: str
    parameter_json: str
    effective_from: datetime
    effective_to: Optional[datetime]
    is_active: bool
    class Config: from_attributes = True


class TaxConfigCreate(BaseModel):
    country_code: str = "IN"
    region: Optional[str] = None
    configuration_json: str = "{}"
    effective_from: datetime
    effective_to: Optional[datetime] = None

class TaxConfigOut(BaseModel):
    id: int
    country_code: str
    region: Optional[str]
    configuration_json: str
    effective_from: datetime
    effective_to: Optional[datetime]
    is_active: bool
    class Config: from_attributes = True


class PayrollPeriodCreate(BaseModel):
    period_name: str
    start_date: datetime
    end_date: datetime
    pay_date: datetime

class PayrollPeriodOut(BaseModel):
    id: int
    period_name: str
    start_date: datetime
    end_date: datetime
    pay_date: datetime
    status: str
    class Config: from_attributes = True


class PayrollRunCreate(BaseModel):
    payroll_period_id: int
    run_name: str
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2020)

class PayrollRunOut(BaseModel):
    id: int
    payroll_period_id: int
    run_name: str
    status: str
    total_gross: float
    total_deductions: float
    total_net: float
    class Config: from_attributes = True


router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Expense Categories
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/expense-categories", response_model=List[ExpenseCategoryOut], tags=["finance-admin"])
def list_expense_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("finance.view")),
) -> Any:
    return (
        db.query(ExpenseCategory)
        .filter(ExpenseCategory.organization_id == current_user.org_id)
        .all()
    )


@router.post("/expense-categories", response_model=ExpenseCategoryOut, status_code=201, tags=["finance-admin"])
def create_expense_category(
    payload: ExpenseCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("finance.manage")),
) -> Any:
    obj = ExpenseCategory(
        organization_id=current_user.org_id,
        **payload.model_dump(),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    
    audit_service.log_event(
        actor=current_user,
        action="create",
        target_type="expense_category",
        target_id=str(obj.id),
        after_state=payload.model_dump(),
    )
    return obj


@router.delete("/expense-categories/{category_id}", status_code=204, tags=["finance-admin"])
def delete_expense_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("finance.manage")),
) -> None:
    obj = db.query(ExpenseCategory).filter(
        ExpenseCategory.id == category_id,
        ExpenseCategory.organization_id == current_user.org_id,
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Expense category not found.")
    obj.is_active = False
    db.commit()

    audit_service.log_event(
        actor=current_user,
        action="deactivate",
        target_type="expense_category",
        target_id=str(category_id),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Salary Components
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/salary-components", response_model=List[SalaryComponentOut], tags=["finance-admin"])
def list_salary_components(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("finance.view")),
) -> Any:
    return (
        db.query(SalaryComponent)
        .filter(SalaryComponent.organization_id == current_user.org_id)
        .all()
    )


@router.post("/salary-components", response_model=SalaryComponentOut, status_code=201, tags=["finance-admin"])
def create_salary_component(
    payload: SalaryComponentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("finance.manage")),
) -> Any:
    if payload.component_type not in {"earning", "deduction", "statutory"}:
        raise HTTPException(status_code=422, detail="Invalid component_type.")
    obj = SalaryComponent(
        organization_id=current_user.org_id,
        **payload.model_dump(),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    
    audit_service.log_event(
        actor=current_user,
        action="create",
        target_type="salary_component",
        target_id=str(obj.id),
        after_state=payload.model_dump(),
    )
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# Statutory Rules
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/statutory-rules", response_model=List[StatutoryRuleOut], tags=["finance-admin"])
def list_statutory_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("finance.view")),
) -> Any:
    return (
        db.query(StatutoryRule)
        .filter(StatutoryRule.organization_id == current_user.org_id)
        .all()
    )


@router.post("/statutory-rules", response_model=StatutoryRuleOut, status_code=201, tags=["finance-admin"])
def create_statutory_rule(
    payload: StatutoryRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("finance.manage")),
) -> Any:
    obj = StatutoryRule(
        organization_id=current_user.org_id,
        **payload.model_dump(),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)

    audit_service.log_event(
        actor=current_user,
        action="create",
        target_type="statutory_rule",
        target_id=str(obj.id),
        after_state={"rule_code": payload.rule_code},
    )
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# Tax Configurations
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/tax-configurations", response_model=List[TaxConfigOut], tags=["finance-admin"])
def list_tax_configurations(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("finance.view")),
) -> Any:
    return (
        db.query(TaxConfiguration)
        .filter(TaxConfiguration.organization_id == current_user.org_id)
        .all()
    )


@router.post("/tax-configurations", response_model=TaxConfigOut, status_code=201, tags=["finance-admin"])
def create_tax_configuration(
    payload: TaxConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("finance.manage")),
) -> Any:
    obj = TaxConfiguration(
        organization_id=current_user.org_id,
        **payload.model_dump(),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)

    audit_service.log_event(
        actor=current_user,
        action="create",
        target_type="tax_configuration",
        target_id=str(obj.id),
    )
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# Payroll Periods
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/payroll-periods", response_model=List[PayrollPeriodOut], tags=["finance-admin"])
def list_payroll_periods(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("payroll.view", "finance.view")),
) -> Any:
    return (
        db.query(PayrollPeriod)
        .filter(PayrollPeriod.organization_id == current_user.org_id)
        .order_by(PayrollPeriod.start_date.desc())
        .all()
    )


@router.post("/payroll-periods", response_model=PayrollPeriodOut, status_code=201, tags=["finance-admin"])
def create_payroll_period(
    payload: PayrollPeriodCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("payroll.manage")),
) -> Any:
    obj = PayrollPeriod(
        organization_id=current_user.org_id,
        **payload.model_dump(),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)

    audit_service.log_event(
        actor=current_user,
        action="create",
        target_type="payroll_period",
        target_id=str(obj.id),
        after_state={"period_name": payload.period_name},
    )
    return obj


@router.patch("/payroll-periods/{period_id}/status", response_model=PayrollPeriodOut, tags=["finance-admin"])
def update_payroll_period_status(
    period_id: int,
    status_update: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("payroll.manage")),
) -> Any:
    valid_statuses = {"draft", "processing", "pending_approval", "approved", "finalized", "cancelled", "locked"}
    new_status = status_update.get("status")
    if new_status not in valid_statuses:
        raise HTTPException(status_code=422, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    obj = db.query(PayrollPeriod).filter(
        PayrollPeriod.id == period_id,
        PayrollPeriod.organization_id == current_user.org_id,
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Payroll period not found.")
        
    # Optional state validation for period could go here
    old_status = obj.status
    obj.status = new_status
    db.commit()
    db.refresh(obj)

    audit_service.log_event(
        actor=current_user,
        action="update_status",
        target_type="payroll_period",
        target_id=str(obj.id),
        before_state={"status": old_status},
        after_state={"status": new_status},
    )
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# Payroll Runs
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/payroll-runs", response_model=List[PayrollRunOut], tags=["finance-admin"])
def list_payroll_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("payroll.view", "finance.view")),
) -> Any:
    return (
        db.query(PayrollRun)
        .filter(PayrollRun.organization_id == current_user.org_id)
        .order_by(PayrollRun.id.desc())
        .all()
    )


@router.post("/payroll-runs", response_model=PayrollRunOut, status_code=201, tags=["finance-admin"])
def create_and_execute_payroll_run(
    payload: PayrollRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("payroll.generate")),
) -> Any:
    """
    Creates a PayrollRun and immediately executes the PayrollEngine
    for all active users in the organization for the given month/year.
    """
    period = db.query(PayrollPeriod).filter(
        PayrollPeriod.id == payload.payroll_period_id,
        PayrollPeriod.organization_id == current_user.org_id,
    ).first()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found.")

    run = PayrollRun(
        organization_id=current_user.org_id,
        payroll_period_id=payload.payroll_period_id,
        run_name=payload.run_name,
        status="processing",
        total_gross=0.0,
        total_deductions=0.0,
        total_net=0.0,
        executed_by_user_id=current_user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    audit_service.log_event(
        actor=current_user,
        action="create",
        target_type="payroll_run",
        target_id=str(run.id),
        after_state={"run_name": payload.run_name},
    )

    try:
        payroll_engine.generate_payroll_for_org(
            db=db,
            org_id=current_user.org_id,
            month=payload.month,
            year=payload.year,
            executed_by_user_id=current_user.id,
            payroll_run=run,
        )
        audit_service.log_event(
            actor=current_user,
            action="calculated",
            target_type="payroll_run",
            target_id=str(run.id),
            after_state={"status": "calculated"},
        )
    except Exception as exc:
        audit_service.log_event(
            actor=current_user,
            action="failed",
            target_type="payroll_run",
            target_id=str(run.id),
            after_state={"status": "failed"},
            status="failure",
            failure_reason=str(exc)
        )
        raise HTTPException(status_code=500, detail=f"Payroll calculation failed: {exc}")

    db.refresh(run)
    return run


@router.patch("/payroll-runs/{run_id}/finalize", response_model=PayrollRunOut, tags=["finance-admin"])
def finalize_payroll_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.require_permission("payroll.finalize")),
) -> Any:
    run = db.query(PayrollRun).filter(
        PayrollRun.id == run_id,
        PayrollRun.organization_id == current_user.org_id,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found.")
    
    # State Machine check
    if run.status in {"finalized", "paid"}:
        raise HTTPException(status_code=422, detail="Run is already finalized or paid.")
    if run.status not in {"calculated", "approved"}:
        raise HTTPException(status_code=422, detail=f"Cannot finalize from state: {run.status}")
        
    old_status = run.status
    run.status = "finalized"
    run.finalized_at = datetime.now(timezone.utc)
    run.approved_by_user_id = current_user.id
    db.commit()
    db.refresh(run)

    audit_service.log_event(
        actor=current_user,
        action="finalize",
        target_type="payroll_run",
        target_id=str(run.id),
        before_state={"status": old_status},
        after_state={"status": "finalized"},
    )
    return run
