"""Phase 4.3: Attendance Corrections Workflow (attendance_requests/attendance_approvals)

Revision ID: 2026_06_21_phase4_3_attendance_corrections_workflow
Revises: 173d20e70930
Create Date: 2026-06-21

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision = '2026_06_21_phase4_3_attendance_corrections_workflow'
down_revision = '8b8317215b9f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # attendance_requests
    op.create_table(
        'attendance_requests',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('employee_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True),
        # Option B: target derived from requested_date + original_attendance_status (no attendance_log_id required)
        sa.Column('requested_date', sa.Date(), nullable=False),
        sa.Column('original_attendance_status', sa.String(length=30), nullable=False),
        sa.Column('reason_category', sa.String(length=100), nullable=False),
        sa.Column('request_notes', sa.Text(), nullable=False),
        sa.Column('evidence_url', sa.String(length=512), nullable=True),
        sa.Column('evidence_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            'state',
            sa.String(length=40),
            nullable=False,
            server_default=sa.text("'submitted'"),
        ),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            'org_id',
            'employee_user_id',
            'requested_date',
            'original_attendance_status',
            name='uq_attendance_requests_emp_date_status',
        ),
        sa.CheckConstraint(
            "state IN ('submitted','needs_manager_review','approved','rejected','admin_overridden','expired','cancelled')",
            name='ck_attendance_request_state',
        ),
        sa.CheckConstraint(
            "original_attendance_status IN ('on_time','late','early','absent','excused','manual_override')",
            name='ck_attendance_request_original_status',
        ),
        sa.CheckConstraint(
            "reason_category IN ('device_malfunction','forgot_phone','network_outage','camera_failure','admin_correction','other')",
            name='ck_attendance_request_reason',
        ),
    )

    op.create_index('ix_attendance_requests_org_state_submitted_at', 'attendance_requests', ['org_id', 'state', 'submitted_at'], unique=False)
    op.create_index('ix_attendance_requests_employee_date', 'attendance_requests', ['org_id', 'employee_user_id', 'requested_date'], unique=False)

    # attendance_approvals
    op.create_table(
        'attendance_approvals',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('attendance_request_id', sa.Integer(), sa.ForeignKey('attendance_requests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('manager_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('decision', sa.String(length=20), nullable=False, server_default=sa.text("'approved'")),
        sa.Column('decision_notes', sa.Text(), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.UniqueConstraint('attendance_request_id', name='uq_attendance_approvals_request'),
        sa.CheckConstraint("decision IN ('approved','rejected')", name='ck_attendance_approval_decision'),
    )

    op.create_index('ix_attendance_approvals_org_decided_at', 'attendance_approvals', ['org_id', 'decided_at'], unique=False)
    op.create_index('ix_attendance_approvals_request_id', 'attendance_approvals', ['attendance_request_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_attendance_approvals_request_id', table_name='attendance_approvals')
    op.drop_index('ix_attendance_approvals_org_decided_at', table_name='attendance_approvals')
    op.drop_table('attendance_approvals')

    op.drop_index('ix_attendance_requests_employee_date', table_name='attendance_requests')
    op.drop_index('ix_attendance_requests_org_state_submitted_at', table_name='attendance_requests')
    op.drop_table('attendance_requests')

