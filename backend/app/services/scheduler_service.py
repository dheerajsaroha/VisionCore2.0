"""
scheduler_service.py — Enterprise Scheduler & Background Job Framework
Sprint 5 — Phase C: Enterprise Platform Operations

Supports:
- Cron Jobs, Delayed Jobs, Periodic Jobs
- Retry Policies, Failed Job Queue, Job History
- Job Priorities, Job Dependencies
- Manual Execution, Job Cancellation

Integrates with:
- Event Bus (publishes job.* events)
- Notification Service (job failure alerts)
- Audit Service (job action audit trail)
- EAAC (permission-aware job management)
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

from app.events.event_bus import event_bus
from app.events.event_types import DomainEvent, EventPriority
from app.services.notification_service import NotificationChannel, notification_service
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    SCHEDULED = "scheduled"
    BLOCKED = "blocked"  # waiting on dependency


class JobPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class JobType(Enum):
    IMMEDIATE = "immediate"
    DELAYED = "delayed"
    PERIODIC = "periodic"
    CRON = "cron"


@dataclass
class Job:
    """Represents a background job."""
    id: str = ""
    name: str = ""
    job_type: JobType = JobType.IMMEDIATE
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
    module: str = ""
    task: str = ""
    params: dict = field(default_factory=dict)
    cron_expr: str = ""  # "*/5 * * * *"
    interval_seconds: int = 0
    delay_seconds: int = 0
    max_retries: int = 3
    retry_count: int = 0
    retry_delay: int = 5  # seconds between retries
    depends_on: list[str] = field(default_factory=list)
    timeout: int = 300  # max execution seconds
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    last_error: Optional[str] = None
    result: Optional[dict] = None
    organization_id: str = ""
    created_by_user_id: Optional[int] = None


# =============================================================================
#  Predefined Job Definitions
# =============================================================================

JOB_DEFINITIONS: dict[str, dict] = {
    "attendance.auto_close": {
        "name": "Attendance Auto Close",
        "module": "attendance",
        "task": "auto_close_attendance",
        "description": "Auto-close attendance logs at end of day",
        "default_cron": "55 23 * * *",
        "default_priority": JobPriority.NORMAL,
    },
    "payroll.monthly_generate": {
        "name": "Monthly Payroll Generation",
        "module": "payroll",
        "task": "generate_payroll",
        "description": "Generate monthly payroll for all employees",
        "default_cron": "0 2 1 * *",
        "default_priority": JobPriority.CRITICAL,
    },
    "leave.balance_reset": {
        "name": "Leave Balance Reset",
        "module": "leave",
        "task": "reset_leave_balances",
        "description": "Reset annual leave balances at year start",
        "default_cron": "0 0 1 1 *",
        "default_priority": JobPriority.NORMAL,
    },
    "reminder.notifications": {
        "name": "Reminder Notifications",
        "module": "notifications",
        "task": "process_reminders",
        "description": "Process and send pending reminder notifications",
        "default_cron": "*/30 * * * *",
        "default_priority": JobPriority.NORMAL,
    },
    "asset.maintenance_check": {
        "name": "Asset Maintenance Check",
        "module": "asset",
        "task": "check_maintenance_due",
        "description": "Check for assets due for maintenance",
        "default_cron": "0 6 * * *",
        "default_priority": JobPriority.NORMAL,
    },
    "compliance.daily_scan": {
        "name": "Compliance Daily Scan",
        "module": "compliance",
        "task": "run_compliance_scan",
        "description": "Run daily compliance checks across all modules",
        "default_cron": "0 5 * * *",
        "default_priority": JobPriority.HIGH,
    },
    "policy.reminder": {
        "name": "Policy Reminder",
        "module": "policy",
        "task": "process_policy_reminders",
        "description": "Send policy acknowledgement reminders",
        "default_cron": "0 8 * * *",
        "default_priority": JobPriority.NORMAL,
    },
    "performance.review_reminder": {
        "name": "Performance Review Reminder",
        "module": "performance",
        "task": "send_review_reminders",
        "description": "Send reminders for pending performance reviews",
        "default_cron": "0 9 * * 1",
        "default_priority": JobPriority.NORMAL,
    },
    "subscription.renewal_check": {
        "name": "Subscription Renewal Check",
        "module": "subscription",
        "task": "check_subscription_renewals",
        "description": "Check for subscriptions nearing expiry",
        "default_cron": "0 4 * * *",
        "default_priority": JobPriority.HIGH,
    },
    "license.expiry_check": {
        "name": "License Expiry Check",
        "module": "asset",
        "task": "check_license_expiry",
        "description": "Check for software licenses nearing expiry",
        "default_cron": "0 7 * * *",
        "default_priority": JobPriority.NORMAL,
    },
    "workflow.sla_monitor": {
        "name": "Workflow SLA Monitor",
        "module": "workflow",
        "task": "check_workflow_slas",
        "description": "Monitor workflow approval SLAs and escalate",
        "default_cron": "*/15 * * * *",
        "default_priority": JobPriority.HIGH,
    },
}


# =============================================================================
#  Scheduler Service
# =============================================================================

class SchedulerService:
    """
    Enterprise background job scheduler.
    
    Features:
    - Immediate, delayed, periodic, and cron job execution
    - Retry with exponential backoff
    - Job dependency resolution
    - Job history tracking
    - Failed job queue (dead letter)
    - Priority-based execution
    """

    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._history: list[Job] = []
        self._failed_queue: list[Job] = []
        self._running: set[str] = set()
        self._max_history: int = 10000
        self._periodic_tasks: dict[str, asyncio.Task] = {}
        self._scheduler_running: bool = False
        self._handlers: dict[str, Callable] = {}

    # ------------------------------------------------------------------
    #  Handler Registration
    # ------------------------------------------------------------------

    def register_handler(self, task_name: str, handler: Callable) -> None:
        """Register a handler function for a task."""
        self._handlers[task_name] = handler
        logger.info(f"Registered handler for task: {task_name}")

    # ------------------------------------------------------------------
    #  Job Management
    # ------------------------------------------------------------------

    def create_job(
        self,
        name: str,
        job_type: JobType = JobType.IMMEDIATE,
        module: str = "",
        task: str = "",
        params: dict | None = None,
        cron_expr: str = "",
        interval_seconds: int = 0,
        delay_seconds: int = 0,
        priority: JobPriority = JobPriority.NORMAL,
        max_retries: int = 3,
        depends_on: list[str] | None = None,
        timeout: int = 300,
        organization_id: str = "",
        created_by_user_id: int | None = None,
    ) -> Job:
        """Create a new job."""
        job = Job(
            id=str(uuid.uuid4()),
            name=name,
            job_type=job_type,
            module=module,
            task=task,
            params=params or {},
            cron_expr=cron_expr,
            interval_seconds=interval_seconds,
            delay_seconds=delay_seconds,
            priority=priority,
            max_retries=max_retries,
            depends_on=depends_on or [],
            timeout=timeout,
            organization_id=organization_id,
            created_by_user_id=created_by_user_id,
        )

        # If has dependencies, check if they're completed
        if job.depends_on:
            deps_completed = all(
                dep in self._history and self._history[-1].status == JobStatus.COMPLETED
                for dep in job.depends_on
            )
            if not deps_completed:
                job.status = JobStatus.BLOCKED

        self._jobs[job.id] = job

        # Audit
        audit_service.record(
            module="scheduler",
            action="job_created",
            entity_type="job",
            entity_id=job.id,
            summary=f"Job '{name}' created ({job_type.value})",
            details={"task": task, "params": params},
            organization_id=organization_id,
            actor_user_id=created_by_user_id,
        )

        # Publish event
        event_bus.publish(JobCreatedEvent(
            job_id=job.id,
            job_name=name,
            job_type=job_type.value,
            module=module,
            task=task,
            organization_id=organization_id,
        ))

        logger.info(f"Job created: {job.id} - {name} ({job_type.value})")
        return job

    def create_cron_job(
        self,
        name: str,
        module: str,
        task: str,
        cron_expr: str,
        params: dict | None = None,
        **kwargs,
    ) -> Job:
        """Create a cron-triggered job."""
        return self.create_job(
            name=name,
            job_type=JobType.CRON,
            module=module,
            task=task,
            cron_expr=cron_expr,
            params=params,
            **kwargs,
        )

    def create_delayed_job(
        self,
        name: str,
        module: str,
        task: str,
        delay_seconds: int,
        params: dict | None = None,
        **kwargs,
    ) -> Job:
        """Create a delayed job."""
        return self.create_job(
            name=name,
            job_type=JobType.DELAYED,
            module=module,
            task=task,
            delay_seconds=delay_seconds,
            params=params,
            **kwargs,
        )

    def create_periodic_job(
        self,
        name: str,
        module: str,
        task: str,
        interval_seconds: int,
        params: dict | None = None,
        **kwargs,
    ) -> Job:
        """Create a periodic job."""
        return self.create_job(
            name=name,
            job_type=JobType.PERIODIC,
            module=module,
            task=task,
            interval_seconds=interval_seconds,
            params=params,
            **kwargs,
        )

    def get_job(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def cancel_job(self, job_id: str, user_id: int | None = None) -> bool:
        """Cancel a pending or running job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED):
            return False
        job.status = JobStatus.CANCELLED
        if job.id in self._running:
            self._running.discard(job.id)
        
        audit_service.record(
            module="scheduler",
            action="job_cancelled",
            entity_type="job",
            entity_id=job.id,
            summary=f"Job '{job.name}' cancelled",
            actor_user_id=user_id,
        )
        return True

    def retry_job(self, job_id: str) -> bool:
        """Retry a failed job."""
        job = self._jobs.get(job_id)
        if not job or job.status != JobStatus.FAILED:
            return False
        job.status = JobStatus.PENDING
        job.retry_count = 0
        job.last_error = None
        return True

    def get_failed_jobs(self) -> list[Job]:
        """Get all failed jobs."""
        return [j for j in self._jobs.values() if j.status == JobStatus.FAILED]

    def list_jobs(
        self,
        status: JobStatus | None = None,
        job_type: JobType | None = None,
        module: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List jobs with filtering, newest first.

        The `/operations/jobs` endpoint called `list_jobs`, which did not exist,
        so the job list 500'd. The service had per-status helpers
        (`get_pending_jobs` and friends) but no way to filter and page over the
        live set, which is what a list endpoint needs.
        """
        jobs = list(self._jobs.values())
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        if job_type is not None:
            jobs = [j for j in jobs if j.job_type == job_type]
        if module:
            jobs = [j for j in jobs if j.module == module]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        window = jobs[offset:offset + limit]
        return [self._job_to_dict(j) for j in window]

    def get_running_jobs(self) -> list[Job]:
        """Get all currently running jobs."""
        return [j for j in self._jobs.values() if j.status == JobStatus.RUNNING]

    def get_pending_jobs(self) -> list[Job]:
        """Get all pending jobs."""
        return [j for j in self._jobs.values() if j.status == JobStatus.PENDING]

    def get_jobs_by_module(self, module: str) -> list[Job]:
        """Get all jobs for a module."""
        return [j for j in self._jobs.values() if j.module == module]

    def get_job_history(
        self,
        limit: int = 100,
        offset: int = 0,
        module: str | None = None,
        status: JobStatus | None = None,
    ) -> list[dict]:
        """Get job history with filtering."""
        results = list(self._history)
        if module:
            results = [j for j in results if j.module == module]
        if status:
            results = [j for j in results if j.status == status]
        results.sort(key=lambda j: j.completed_at or j.created_at, reverse=True)
        return [self._job_to_dict(j) for j in results[offset:offset + limit]]

    # ------------------------------------------------------------------
    #  Job Execution
    # ------------------------------------------------------------------

    async def execute_job(self, job_id: str) -> Job:
        """Execute a job by ID."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        return await self._run_job(job)

    async def _run_job(self, job: Job) -> Job:
        """Internal job execution with retry logic."""
        if job.status == JobStatus.CANCELLED:
            return job

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc).isoformat()
        self._running.add(job.id)

        handler = self._handlers.get(job.task)
        if not handler:
            job.status = JobStatus.FAILED
            job.last_error = f"No handler registered for task: {job.task}"
            self._record_completion(job)
            return job

        last_error = None
        for attempt in range(1, job.max_retries + 1):
            try:
                logger.info(f"Executing job {job.id} - {job.name} (attempt {attempt})")
                
                # Execute with timeout
                if asyncio.iscoroutinefunction(handler):
                    result = await asyncio.wait_for(handler(job.params), timeout=job.timeout)
                else:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(handler, job.params), timeout=job.timeout
                    )

                job.status = JobStatus.COMPLETED
                job.result = result if isinstance(result, dict) else {"output": str(result)}
                job.completed_at = datetime.now(timezone.utc).isoformat()
                self._running.discard(job.id)
                self._record_completion(job)

                # Publish completion event
                event_bus.publish(JobCompletedEvent(
                    job_id=job.id,
                    job_name=job.name,
                    module=job.module,
                    task=job.task,
                    status="completed",
                    organization_id=job.organization_id,
                ))

                return job

            except asyncio.TimeoutError:
                last_error = f"Job timed out after {job.timeout}s"
                logger.warning(f"Job {job.id} - {job.name} timed out (attempt {attempt})")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Job {job.id} - {job.name} failed (attempt {attempt}): {e}")

            # Retry with exponential backoff
            if attempt < job.max_retries:
                wait = job.retry_delay * (2 ** (attempt - 1))
                job.status = JobStatus.RETRYING
                job.retry_count = attempt
                await asyncio.sleep(wait)

        # All retries exhausted
        job.status = JobStatus.FAILED
        job.last_error = last_error
        job.retry_count = job.max_retries
        job.completed_at = datetime.now(timezone.utc).isoformat()
        self._running.discard(job.id)
        self._record_completion(job)

        # Send notification for failed job
        notification_service.send(
            user_id=job.created_by_user_id or 0,
            organization_id=job.organization_id,
            channel=NotificationChannel.IN_APP,
            title=f"Job Failed: {job.name}",
            message=f"Job '{job.name}' failed after {job.max_retries} attempts: {last_error}",
            source_module="scheduler",
            source_event="job.failed",
            source_id=job.id,
            priority="high",
        )

        # Publish failure event
        event_bus.publish(JobFailedEvent(
            job_id=job.id,
            job_name=job.name,
            module=job.module,
            task=job.task,
            error=last_error,
            retry_count=job.max_retries,
            organization_id=job.organization_id,
        ))

        # Audit
        audit_service.record(
            module="scheduler",
            action="job_failed",
            entity_type="job",
            entity_id=job.id,
            summary=f"Job '{job.name}' failed: {last_error}",
            severity="warning",
            details={"retries": job.max_retries, "task": job.task},
            organization_id=job.organization_id,
        )

        return job

    def _record_completion(self, job: Job) -> None:
        """Record job in history."""
        self._history.append(job)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        # Move from active jobs to history if completed/failed/cancelled
        if job.id in self._jobs and job.status in (
            JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED
        ):
            del self._jobs[job.id]

    # ------------------------------------------------------------------
    #  Scheduler Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._scheduler_running:
            return
        self._scheduler_running = True
        logger.info("Scheduler started")
        
        # Start periodic task checker
        asyncio.create_task(self._scheduler_loop())

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._scheduler_running = False
        # Cancel all periodic tasks
        for task in self._periodic_tasks.values():
            task.cancel()
        self._periodic_tasks.clear()
        logger.info("Scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop for periodic and cron jobs."""
        while self._scheduler_running:
            try:
                now = datetime.now(timezone.utc)
                
                # Check periodic jobs
                for job in list(self._jobs.values()):
                    if job.job_type == JobType.PERIODIC and job.status == JobStatus.SCHEDULED:
                        asyncio.create_task(self._run_job(job))
                    elif job.job_type == JobType.DELAYED and job.status == JobStatus.PENDING:
                        created = datetime.fromisoformat(job.created_at)
                        if (now - created).total_seconds() >= job.delay_seconds:
                            asyncio.create_task(self._run_job(job))
                    elif job.job_type == JobType.IMMEDIATE and job.status == JobStatus.PENDING:
                        asyncio.create_task(self._run_job(job))

                # Check cron jobs (simplified — in production, use croniter)
                for job in list(self._jobs.values()):
                    if job.job_type == JobType.CRON and job.status == JobStatus.SCHEDULED:
                        asyncio.create_task(self._run_job(job))

            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")

            await asyncio.sleep(5)  # Check every 5 seconds

    # ------------------------------------------------------------------
    #  Default Job Handlers
    # ------------------------------------------------------------------

    def register_default_handlers(self) -> None:
        """Register built-in job handlers."""
        # These are placeholder handlers that log execution
        # Real implementations should be registered by each module
        
        async def _placeholder_handler(params: dict) -> dict:
            logger.info(f"Executing task with params: {params}")
            return {"status": "executed", "params": params}

        for def_name, definition in JOB_DEFINITIONS.items():
            task_name = definition["task"]
            if task_name not in self._handlers:
                self.register_handler(task_name, _placeholder_handler)

    def create_default_jobs(self, organization_id: str = "") -> list[Job]:
        """Create all predefined jobs."""
        jobs = []
        for def_name, definition in JOB_DEFINITIONS.items():
            job = self.create_cron_job(
                name=definition["name"],
                module=definition["module"],
                task=definition["task"],
                cron_expr=definition["default_cron"],
                priority=definition["default_priority"],
                organization_id=organization_id,
            )
            job.status = JobStatus.SCHEDULED  # Start as scheduled
            jobs.append(job)
        return jobs

    # ------------------------------------------------------------------
    #  Utility
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get scheduler statistics."""
        all_jobs = list(self._jobs.values()) + self._history
        return {
            "total_jobs": len(all_jobs),
            "active_jobs": len(self._jobs),
            "running": len(self._running),
            "pending": sum(1 for j in self._jobs.values() if j.status == JobStatus.PENDING),
            "completed": sum(1 for j in self._history if j.status == JobStatus.COMPLETED),
            "failed": sum(1 for j in all_jobs if j.status == JobStatus.FAILED),
            "cancelled": sum(1 for j in all_jobs if j.status == JobStatus.CANCELLED),
            "scheduled": sum(1 for j in self._jobs.values() if j.status == JobStatus.SCHEDULED),
            "handlers_registered": len(self._handlers),
            "job_definitions": len(JOB_DEFINITIONS),
        }

    @staticmethod
    def _job_to_dict(job: Job) -> dict:
        return {
            "id": job.id,
            "name": job.name,
            "job_type": job.job_type.value,
            "status": job.status.value,
            "priority": job.priority.value,
            "module": job.module,
            "task": job.task,
            "params": job.params,
            "cron_expr": job.cron_expr,
            "interval_seconds": job.interval_seconds,
            "delay_seconds": job.delay_seconds,
            "max_retries": job.max_retries,
            "retry_count": job.retry_count,
            "depends_on": job.depends_on,
            "timeout": job.timeout,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "last_error": job.last_error,
            "result": job.result,
            "organization_id": job.organization_id,
        }


# =============================================================================
#  Job Events
# =============================================================================

@dataclass
class JobCreatedEvent(DomainEvent):
    event_type: str = "job.created"
    source_module: str = "scheduler"
    job_id: str = ""
    job_name: str = ""
    job_type: str = ""
    module: str = ""
    task: str = ""


@dataclass
class JobCompletedEvent(DomainEvent):
    event_type: str = "job.completed"
    source_module: str = "scheduler"
    job_id: str = ""
    job_name: str = ""
    module: str = ""
    task: str = ""
    status: str = ""


@dataclass
class JobFailedEvent(DomainEvent):
    event_type: str = "job.failed"
    source_module: str = "scheduler"
    job_id: str = ""
    job_name: str = ""
    module: str = ""
    task: str = ""
    error: str = ""
    retry_count: int = 0


# Singleton
scheduler_service = SchedulerService()
