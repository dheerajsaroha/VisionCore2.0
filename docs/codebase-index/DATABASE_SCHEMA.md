# Database Schema & Relational Models

> **Phase 5 — Database Indexing**  
> **Extraction Source:** Static inspection of `backend/app/db/models/all_models.py` (224 models, 2,424 columns, 545 foreign key relationships) and 44 Alembic migration scripts.

---

## 1. Database Architecture & PostgreSQL Extensions

VisionCore 2.0 uses PostgreSQL 15+ as its primary relational engine, relying on three fundamental database extensions enabled during system initialization (`app/util/init.py:9-13`):

1. **`vector` (`pgvector`):** Enables native vector data types and cosine similarity search (`<->` operator) for 128-dimensional facial embeddings.
2. **`uuid-ossp`:** Provides native UUID generation functions (`uuid_generate_v4()`).
3. **`pgcrypto`:** Provides server-side cryptographic hashing and random byte generation (`gen_random_bytes()`).

### HNSW Cosine Index Configuration
To ensure real-time biometric search across large employee databases, an Approximate Nearest Neighbor (ANN) index is created on `face_embeddings`:
```sql
CREATE INDEX IF NOT EXISTS idx_face_embeddings_hnsw 
ON face_embeddings 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```
- **`m = 16`:** Bi-directional link factor per node in the Hierarchical Navigable Small World graph.
- **`ef_construction = 64`:** Search depth during index construction, balancing build time and recall accuracy.
- **`vector_cosine_ops`:** Optimizes vector comparison for cosine distance ($\text{distance} = 1 - \cos(\theta)$), suitable for normalized unit vectors.

---

## 2. Relational Schema Domain Catalog (224 Tables)

All 224 tables inherit from SQLAlchemy's declarative `Base` and map directly to corresponding ORM classes in `backend/app/db/models/all_models.py`:

### 2.1 Identity, Authentication & RBAC (14 Tables)
- `roles`: System and organization roles (`id`, `name`, `tier`, `is_system`, `description`).
- `permissions`: Fine-grained permission taxonomy (`id`, `name`, `module`, `action`, `description`).
- `role_permissions`: Role-to-permission mapping table.
- `system_settings`: Key-value global platform configuration.
- `user_roles`: Many-to-many user-to-role assignments.
- `users`: Core employee and user identity accounts.
- `user_sessions`: Active JWT sessions with JTI token binding.
- `password_reset_tokens`: 30-minute password reset link tokens.
- `password_reset_requests`: 10-minute 6-digit OTP reset attempts with rate limits.
- `employee_invites`: Organization onboarding invitation tokens.
- `organizations`: Multi-tenant organization boundaries.
- `org_api_keys`: Machine-to-machine API authentication keys.
- `departments`: Functional organizational departments.
- `shifts`: Work shifts with start/end times and grace periods.

### 2.2 Biometrics & Attendance Pipeline (15 Tables)
- `face_embeddings`: Enrolled 128-dim biometric vectors with HNSW index.
- `enrollment_events`: Audit logs for face registration and photo uploads.
- `spoof_detection_logs`: Anti-spoofing heuristic scores and photo attack flags.
- `recognition_events`: Raw camera stream facial recognition attempts.
- `emotion_logs`: Facial expression sentiment analysis logs.
- `attendance_logs`: Official check-in and check-out attendance records.
- `manual_overrides`: Manager override entries for missed or manual attendance.
- `attendance_corrections`: Employee-initiated attendance time adjustment requests.
- `offline_sync_queue`: Edge device offline attendance record queue.
- `attendance_devices`: Authorized hardware clock-in terminals and IP bindings.
- `geofence_zones`: Geographic latitude/longitude boundaries and radii for mobile clock-in.
- `attendance_policies`: Organization attendance enforcement rules.
- `attendance_sessions`: Daily attendance session aggregator.
- `attendance_events`: Real-time presence transition events.
- `attendance_requests`: Formal attendance approval requests.

### 2.3 Workforce Management, Scheduling & Time Tracking (15 Tables)
- `shift_templates`: Reusable shift definitions and scheduling patterns.
- `shift_assignments`: Schedule assignments linking employees to shifts.
- `rosters`: Master schedule plans for operational units.
- `roster_entries`: Individual daily roster allocations.
- `shift_swap_requests`: Peer-to-peer employee shift exchange requests.
- `time_entries`: Project/task-level time tracking logs.
- `break_logs`: Rest and meal break start/end logs.
- `overtime_records`: Approved overtime hours and multipliers.
- `comp_off_balances`: Compensatory off credit balances.
- `holiday_calendars`: Organization holiday group calendars.
- `holiday_entries`: Specific calendar holiday dates and descriptions.
- `headcount_plans`: Annual or quarterly staffing targets.
- `capacity_snapshots`: Operational workforce utilization metrics.
- `bench_records`: Unassigned employee bench tracking.
- `workforce_forcasts`: AI-driven predictive staffing forecasts.

### 2.4 Human Capital Management (HCM) (9 Tables)
- `hcm_employee_profiles`: Extended employee details, blood group, emergency contacts.
- `hcm_employee_educations`: Academic degree records and institutions.
- `hcm_employee_experiences`: Prior employment history and designations.
- `hcm_employee_awards`: Corporate recognitions and awards.
- `hcm_employee_licenses`: Professional certifications and expiration dates.
- `hcm_employee_emergency_contacts`: Emergency contact persons and phone numbers.
- `hcm_talent_pools`: High-potential talent groupings.
- `hcm_talent_pool_members`: Employees assigned to specific talent pools.
- `hcm_employee_documents`: Uploaded KYC, contracts, and credential documents.

### 2.5 Leave & Absence Management (8 Tables)
- `leave_templates`: Standard organization leave policy templates.
- `leave_template_items`: Itemized leave rules within a template.
- `leave_types`: Types of leave (Casual, Sick, Maternity, Paternity, Annual).
- `leave_policies`: Entitlement rules, accrual frequency, and carry-forward limits.
- `leave_balances`: Current, accrued, and consumed employee leave days.
- `leave_requests`: Leave applications with date ranges and approval status.
- `leave_adjustments`: Administrative manual additions or deductions to leave balances.
- `comp_off_balances`: Compensatory off days earned from holiday/weekend work.

### 2.6 Payroll & Financial Operations (12 Tables)
- `pay_grades`: Compensation bands and salary grade tiers.
- `salary_structures`: Base salary, allowances, and deduction formulas.
- `payroll_runs`: Monthly/bi-weekly batch payroll execution records.
- `payroll_line_items`: Itemized salary breakdown per employee per run.
- `payrolls`: Summary payroll records per employee.
- `payslips`: Generated digital payslips with PDF storage paths.
- `statutory_rules`: Legal deduction formulas (PF, ESI, Professional Tax, TDS).
- `payroll_advances`: Employee salary advance requests and balances.
- `loan_repayments`: Scheduled payroll loan deduction schedules.
- `reimbursements`: Employee expense reimbursement requests.
- `expense_categories`: Categorization for allowable business expenses.
- `reimbursement_claims`: Itemized expense claim lines with receipts.

### 2.7 SaaS Subscription, Licensing & Enterprise Billing (8 Tables)
- `subscription_plans`: Available commercial tiers (`starter`, `professional`, `enterprise`).
- `organization_subscriptions`: Active organization subscription contract.
- `features`: Catalog of platform features and capabilities.
- `plan_features`: Feature entitlements mapped per subscription tier.
- `feature_flags`: Dynamic feature flags for canary rollouts.
- `licensing_limits`: Seat, employee, and device usage ceilings.
- `subscription_invoices`: Generated billing invoices.
- `subscription_usage_records`: Metered resource usage logs.

### 2.8 Dynamic Roles & EAAC Scope (18 Tables)
- `dynamic_roles`: Tenant-created custom roles.
- `role_templates`: Reusable role definition blueprints.
- `role_inheritances`: Hierarchical role inheritance trees.
- `role_versions`: Historical snapshots of role permission changes.
- `user_role_assignments`: Temporal and scoped role assignments.
- `role_assignment_history`: Audit trail of role grants and revocations.
- `role_approvals`: Multi-person authorization for privileged role elevation.
- `role_clones`: Role duplication tracking.
- `role_import_exports`: Role package exchange records.
- `role_audits`: Security audit log for role changes.
- `data_scopes`: Bounded data visibility scopes (Self, Team, Dept, Org).
- `role_data_scopes`: Scope bindings mapped to roles.
- `resource_ownerships`: Fine-grained object ownership tracking.
- `ownership_histories`: Ownership transfer logs.
- `ownership_delegations`: Temporary delegation of data ownership.
- `ownership_rules`: Automated ownership assignment logic.
- `ownership_policies`: Tenant data access governance policies.
- `ownership_exceptions`: Explicit security bypass grants.

### 2.9 Workflow & Approval Engine (12 Tables)
- `approval_workflows`: Multi-step approval process definitions.
- `approval_stages`: Sequential or parallel stages in a workflow.
- `approval_stage_approvers`: Specific users or roles assigned to approve a stage.
- `approval_templates`: Standard workflow templates by request type.
- `approval_requests`: Active approval workflow instances.
- `approval_actions`: Recorded approve, reject, or reassign decisions.
- `approval_wf_histories`: Complete chronological audit of workflow steps.
- `approval_escalations`: Time-based automatic escalation rules.
- `approval_wf_delegations`: Out-of-office approval delegation bindings.
- `workflow_conditions`: Boolean expression evaluator for conditional branching.
- `workflow_variables`: Context variables passed during workflow execution.
- `workflow_audits`: Compliance execution logs for workflows.

### 2.10 Performance, Learning & Succession (30 Tables)
- Performance (10): `performance_cycles`, `performance_goals`, `performance_reviews`, `review_feedbacks`, `competency_matrices`, `skill_assessments`, `pip_records`, `calibration_sessions`, `review_templates`, `goal_metrics`.
- Learning & Development (10): `courses`, `course_modules`, `course_enrollments`, `learning_paths`, `certifications`, `training_budgets`, `skill_inventories`, `course_assessments`, `certification_renewals`, `learning_providers`.
- Succession (10): `succession_plans`, `succession_candidates`, `career_paths`, `job_role_matrices`, `talent_reviews`, `nine_box_placements`, `flight_risks`, `development_actions`, `critical_roles`, `bench_strengths`.

### 2.11 Policy, Compliance & Audit (15 Tables)
- Policy: `company_policies`, `policy_versions`, `policy_acknowledgments`, `policy_categories`, `policy_notifications`.
- Compliance & Security: `compliance_rules`, `compliance_records`, `compliance_audits`, `audit_logs`, `retention_policies`, `legal_holds`, `privacy_requests`, `security_event_logs`, `blockchain_audit_logs`, `monthly_growth_summary`.

### 2.12 Asset Management (15 Tables)
- `assets`, `asset_categories`, `asset_assignments`, `asset_maintenance`, `asset_depreciation`, `asset_disposals`, `asset_audits`, `asset_audit_results`, `asset_insurance`, `asset_licenses`, `vendors`, `purchase_orders`, `purchase_order_items`, `asset_consumables`, `consumable_issuances`.

### 2.13 Organization Structure & Enterprise Integrations (20 Tables)
- Org Structure: `legal_entities`, `business_units`, `branches`, `teams`, `cost_centers`, `job_positions`, `employment_records`, `identity_history`, `organization_provisionings`.
- Integrations: `integration_connectors`, `webhook_subscriptions`, `webhook_delivery_records`, `gateway_route_configs`, `api_key_metadata`.
- AI Platform: `ai_model_configs`, `prompt_templates`, `copilot_sessions`, `copilot_messages`, `ai_governance_logs`, `ai_usage_records`.
- Recruitment: `job_openings`, `candidates`, `candidate_applications`, `interview_stages`, `interview_schedules`, `interview_feedbacks`, `offer_templates`, `offer_letters`, `candidate_referrals`.

---

## 3. Core Entity Data Definitions

### `users` Table
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role_id INTEGER REFERENCES roles(id),
    department_id INTEGER REFERENCES departments(id),
    shift_id INTEGER REFERENCES shifts(id),
    employee_id VARCHAR(50) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(100) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX ix_users_org_id ON users(org_id);
CREATE INDEX ix_users_email ON users(email);
CREATE INDEX ix_users_employee_id ON users(employee_id);
```

### `face_embeddings` Table
```sql
CREATE TABLE face_embeddings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    embedding VECTOR(128) NOT NULL,
    model_name VARCHAR(50) NOT NULL DEFAULT 'Facenet',
    confidence_threshold FLOAT DEFAULT 0.40,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_face_embeddings_hnsw ON face_embeddings USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX ix_face_embeddings_user_org ON face_embeddings(user_id, org_id);
```

### `attendance_logs` Table
```sql
CREATE TABLE attendance_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    shift_id INTEGER REFERENCES shifts(id),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'present',
    verification_method VARCHAR(20) NOT NULL DEFAULT 'biometric',
    confidence_score FLOAT,
    liveness_score FLOAT,
    location VARCHAR(255),
    device_id VARCHAR(50),
    blockchain_tx_hash VARCHAR(66),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX ix_attendance_logs_user_timestamp ON attendance_logs(user_id, timestamp);
CREATE INDEX ix_attendance_logs_org_timestamp ON attendance_logs(org_id, timestamp);
```

---

## 4. Alembic Migration History (44 Revisions)

The database schema is managed through 44 Alembic migration revisions in `backend/alembic/versions/`:
- `3eaaee4c0cc5_initial_migration.py`: Foundational tables (`users`, `roles`, `organizations`, `attendance_logs`).
- `0bf7d8c13f4d_add_org_id_and_encrypted_embedding_to_.py`: Multi-tenant isolation and vector encryption.
- `14931530a9c9_phase3_enrollment_spoof_recognition_.py`: Anti-spoofing and biometric audit logging.
- `2026_06_04_phase3_rbac_analytics.py`: Advanced RBAC roles and analytic aggregation tables.
- `2026_06_21_phase4_3_attendance_corrections_workflow.py`: Attendance correction workflows.
- `36f0736b6c2a_add_approval_workflow_models.py`: Approval workflow state machine.
- `3cfe8078fdb5_add_policy_center_compliance_models.py`: Policy acknowledgment and compliance audits.
- `2a538dcbec1f_add_recruitment_models.py`: Recruitment, candidate pipelines, and offer letters.
- *(Subsequent migrations track EAAC dynamic roles, statutory payroll, workforce forecasting, and AI governance).*
