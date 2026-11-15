# VisionCore 2.0 — AI Coding Agent Guidelines & Incremental Indexing Protocol

> **Mandatory Guidelines for AI Coding Agents Operating in this Repository**  
> **Repository:** `VisionCore 2.0` (`face-recognition-based-attendance-system`)  
> **Scope:** Repository-wide (all directories, backend, frontend, AI microservice, infrastructure)

---

## 1. Mandatory Consultation Rule

Before proposing, planning, designing, or implementing **any** architectural, structural, database, API, dependency, or security changes:

> [!IMPORTANT]
> **Always consult [`docs/codebase-index/INDEX.md`](docs/codebase-index/INDEX.md) first.**  
> Use the master navigation matrix to inspect existing patterns, data contracts, and dependency graphs before modifying or introducing code.

### Reference Quick-Lookup:
- **Architecture & Multi-Tenancy:** Consult [`docs/codebase-index/ARCHITECTURE.md`](docs/codebase-index/ARCHITECTURE.md)
- **API Endpoints & Routing:** Consult [`docs/codebase-index/API_REFERENCE.md`](docs/codebase-index/API_REFERENCE.md)
- **Database Schema & Models:** Consult [`docs/codebase-index/DATABASE_SCHEMA.md`](docs/codebase-index/DATABASE_SCHEMA.md)
- **Internal Coupling & Dependencies:** Consult [`docs/codebase-index/DEPENDENCY_MAP.md`](docs/codebase-index/DEPENDENCY_MAP.md)
- **Environment & Configuration:** Consult [`docs/codebase-index/CONFIGURATION_GUIDE.md`](docs/codebase-index/CONFIGURATION_GUIDE.md)
- **Testing & Validation:** Consult [`docs/codebase-index/TESTING_GUIDE.md`](docs/codebase-index/TESTING_GUIDE.md)
- **Security & RBAC/EAAC Scoping:** Consult [`docs/codebase-index/SECURITY_ANALYSIS.md`](docs/codebase-index/SECURITY_ANALYSIS.md)
- **Technical Debt & Known Smells:** Consult [`docs/codebase-index/TECHNICAL_DEBT.md`](docs/codebase-index/TECHNICAL_DEBT.md)

---

## 2. Incremental Indexing Protocol

Whenever source code, dependencies, database models, API routes, configuration, or architectural boundaries change, follow this **7-step incremental update workflow**.

> [!WARNING]
> **Do NOT regenerate the entire documentation suite for small changes.**  
> Update only the specific, affected documents and diagrams according to the scope of your changes.

```
Code / Config Change
       │
       ├── Step 1: Identify affected files
       ├── Step 2: Identify downstream dependents (consult DEPENDENCY_MAP.md)
       ├── Step 3: Selectively update corresponding docs in docs/codebase-index/
       ├── Step 4: Update relevant Mermaid diagrams if boundaries/models shifted
       ├── Step 5: Validate file paths & links (python scripts/update_codebase_index.py --validate)
       ├── Step 6: Keep INDEX.md metrics synchronized if counts changed
       └── Step 7: Record architectural decisions in ARCHITECTURE.md / TECHNICAL_DEBT.md
```

### Step-by-Step Procedure:

### Step 1 — Identify Affected Modules
Identify which files were added, edited, moved, or deleted. You can run:
```bash
python scripts/update_codebase_index.py --status
```
This utility analyzes git status and automatically maps changed files to the required documentation updates.

### Step 2 — Identify Dependent Modules
Before finalizing a code change, verify what consumes the modified component:
- Consult [`docs/codebase-index/DEPENDENCY_MAP.md`](docs/codebase-index/DEPENDENCY_MAP.md) and [`docs/codebase-index/diagrams/component_relationships.mmd`](docs/codebase-index/diagrams/component_relationships.mmd).
- Check for high fan-in modules (e.g. `app.db`, `app.services`, `app.api.deps`).
- Ensure breaking signature changes are accompanied by updates to all callers across backend routers and frontend Axios services.

### Step 3 — Update Relevant Codebase Index Documentation
Selectively update only the documents directly impacted by your changes:

| Changed Component Area | Documents to Update in `docs/codebase-index/` |
|---|---|
| **API Routers / HTTP Endpoints** (`app/routers/`) | [`API_REFERENCE.md`](docs/codebase-index/API_REFERENCE.md), [`MODULE_INDEX.md`](docs/codebase-index/MODULE_INDEX.md) |
| **Database Models / Migrations** (`app/db/models/`, `alembic/`) | [`DATABASE_SCHEMA.md`](docs/codebase-index/DATABASE_SCHEMA.md), [`SYMBOL_INDEX.md`](docs/codebase-index/SYMBOL_INDEX.md) |
| **Dependencies / Manifests** (`pyproject.toml`, `package.json`) | [`TECHNOLOGY_STACK.md`](docs/codebase-index/TECHNOLOGY_STACK.md), [`DEPENDENCY_MAP.md`](docs/codebase-index/DEPENDENCY_MAP.md) |
| **Configuration / Settings** (`core/config.py`, `.env`) | [`CONFIGURATION_GUIDE.md`](docs/codebase-index/CONFIGURATION_GUIDE.md), [`SECURITY_ANALYSIS.md`](docs/codebase-index/SECURITY_ANALYSIS.md) |
| **Domain Services / CRUD** (`app/services/`, `app/crud/`) | [`MODULE_INDEX.md`](docs/codebase-index/MODULE_INDEX.md), [`SYMBOL_INDEX.md`](docs/codebase-index/SYMBOL_INDEX.md), [`DATA_FLOW.md`](docs/codebase-index/DATA_FLOW.md) |
| **Auth / Guards / Middleware** (`app/api/deps.py`, `middleware/`) | [`ARCHITECTURE.md`](docs/codebase-index/ARCHITECTURE.md), [`SECURITY_ANALYSIS.md`](docs/codebase-index/SECURITY_ANALYSIS.md), [`EXECUTION_FLOW.md`](docs/codebase-index/EXECUTION_FLOW.md) |
| **Deployment / Containers** (`deploy/`, `Dockerfile`, `k8s/`) | [`DEPLOYMENT_GUIDE.md`](docs/codebase-index/DEPLOYMENT_GUIDE.md), [`CONFIGURATION_GUIDE.md`](docs/codebase-index/CONFIGURATION_GUIDE.md) |
| **Automated Tests** (`app/tests/`, `ai-service/tests/`) | [`TESTING_GUIDE.md`](docs/codebase-index/TESTING_GUIDE.md) |
| **Frontend UI / Pages / Stores** (`frontend/src/`) | [`MODULE_INDEX.md`](docs/codebase-index/MODULE_INDEX.md), [`ARCHITECTURE.md`](docs/codebase-index/ARCHITECTURE.md) |

### Step 4 — Update Architecture & Dependency Diagrams
If structural boundaries or relational entities change, update the corresponding Mermaid diagram file:
- System topology shifts: [`docs/codebase-index/diagrams/system_architecture.mmd`](docs/codebase-index/diagrams/system_architecture.mmd)
- Component coupling shifts: [`docs/codebase-index/diagrams/component_relationships.mmd`](docs/codebase-index/diagrams/component_relationships.mmd)
- New tables or foreign keys: [`docs/codebase-index/diagrams/database_erd.mmd`](docs/codebase-index/diagrams/database_erd.mmd)
- New package imports: [`docs/codebase-index/diagrams/dependency_graph.mmd`](docs/codebase-index/diagrams/dependency_graph.mmd)
- Request execution sequence: [`docs/codebase-index/diagrams/application_flow.mmd`](docs/codebase-index/diagrams/application_flow.mmd)

### Step 5 — Validate File Paths and Symbol References
Run the automated index validator:
```bash
python scripts/update_codebase_index.py --validate
```
Fix any broken markdown links or non-existent file references immediately.

### Step 6 — Keep INDEX.md Synchronized
If table counts, endpoint counts, test counts, or major features changed:
1. Run `python scripts/update_codebase_index.py --metrics` to obtain verified numbers.
2. Update the Key Repository Metrics table in [`docs/codebase-index/INDEX.md`](docs/codebase-index/INDEX.md).

### Step 7 — Record Significant Architectural Changes
- For structural, architectural, or security design changes, add an entry to the Architectural Decisions or Pattern Overview in [`docs/codebase-index/ARCHITECTURE.md`](docs/codebase-index/ARCHITECTURE.md).
- If introducing an intentional temporary compromise or technical debt, document it with remediation steps in [`docs/codebase-index/TECHNICAL_DEBT.md`](docs/codebase-index/TECHNICAL_DEBT.md).

---

## 3. Strict Development Rules

1. **Evidence-Based Guarantee:** Never fabricate routes, database models, permissions, or dependencies. All documentation must reflect actual source files and AST symbols on disk.
2. **Multi-Tenant Protection:** Every query against tenant-scoped data must enforce `org_id == current_user.org_id`. Never remove tenant isolation filters.
3. **Permission Taxonomy:** Enforce RBAC permissions using the standard `module.action` convention via `deps.require_permission(...)`.
4. **No Hardcoded Secrets:** Never add fallback credentials or API keys directly in code or compose files; declare them in `Settings` and `.env`.
5. **No Layering Inversions:** Routers may import Services and CRUD; Services must **never** import from Routers.
