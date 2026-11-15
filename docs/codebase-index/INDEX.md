# VisionCore 2.0 — Codebase Index & Architectural Knowledge Base

> **Authoritative Architectural Index and Technical Knowledge Base**  
> **Repository:** VisionCore 2.0 (`face-recognition-based-attendance-system`)  
> **Target Audience:** Principal Architects, Senior Developers, Security Engineers, DevOps/SRE, and QA Engineers  
> **Status:** Fully Indexed & Verified  

---

## 1. Executive Summary

VisionCore 2.0 is an enterprise-grade, multi-tenant AI workforce attendance, biometric presence intelligence, and comprehensive Human Capital Management (HCM) operations platform. It combines a real-time face-recognition pipeline (using 128-dimensional deep embeddings and PostgreSQL `pgvector` HNSW index similarity search) with fine-grained Enterprise Adaptive Access Control (EAAC / RBAC), an approval workflow orchestration engine, statutory payroll processing, leave lifecycle management, and enterprise integration capabilities.

This codebase index is the result of deep static analysis, symbol extraction, route compilation, database schema reverse-engineering, dependency graph resolution, and security auditing across all 1,271 tracked repository files.

---

## 2. Key Repository Metrics

| Metric | Measured Value | Verification Source |
|---|---|---|
| **Total Git-Tracked Files** | 1,271 files | `git ls-files` |
| **Analyzed Source & Configuration Files** | 755 files | Filtered (excluding 516 test upload artifacts) |
| **Generated / Test Artifact Files** | 516 PDF files | `backend/app_data/uploads/` (offer letters & payslips) |
| **Total Lines of Code (Raw)** | 272,130 lines | Physical repository line count |
| **Python Source Files** | 491 files | AST Static Parser (137,965 lines) |
| **Frontend Source Files** | 178 files (130 JSX, 47 JS, 1 TS) | Node/Vite Source Tree (33,248 lines) |
| **Python Classes** | 1,551 classes | Python AST Body Walker |
| **Python Top-Level Functions** | 2,542 functions | Python AST Walker |
| **Python Class Methods** | 2,619 methods | Python AST ClassDef Walker |
| **Database Models & Tables** | 224 tables / models | `backend/app/db/models/all_models.py` |
| **Database Columns** | 2,424 columns | SQLAlchemy 2.0 `mapped_column` declarations |
| **Database Foreign Key Relationships** | 545 relationships | SQLAlchemy `relationship()` definitions |
| **Alembic Database Migrations** | 44 migration revisions | `backend/alembic/versions/` |
| **Total API Endpoints Defined** | 827 endpoints | Routers AST analysis (818 backend + 6 AI service + 3 root) |
| **Mounted API Endpoints** | 765 endpoints (756 router + 6 AI + 3 root) | `backend/app/routers/__init__.py` & `main.py` |
| **Unmounted / Orphaned Endpoints** | 62 endpoints | 5 unmounted router modules (`benefits`, `billing`, etc.) |
| **Automated Test Cases** | 847 test cases | 71 test files in `backend/app/tests` and `ai-service/tests` |
| **Runtime Validation Suites** | 19 validation scripts | `backend/runtime_validation_*.py` |

---

## 3. Master Navigation Matrix

The codebase knowledge base is divided into 16 specialized documentation guides and 5 standalone Mermaid architecture diagrams:

### Core Documentation

| Document | Primary Focus | Target Audience |
|---|---|---|
| [REPOSITORY_STRUCTURE.md](REPOSITORY_STRUCTURE.md) | Recursive directory hierarchy, file classification, excluded artifacts | All Engineers |
| [TECHNOLOGY_STACK.md](TECHNOLOGY_STACK.md) | Manifest-extracted languages, frameworks, libraries, database engines | DevOps / Backend |
| [ARCHITECTURE.md](ARCHITECTURE.md) | High-level patterns, multi-tenancy model, RBAC/EAAC, component boundaries | Architects / Leads |
| [MODULE_INDEX.md](MODULE_INDEX.md) | Comprehensive catalog of backend, frontend, AI, and deploy modules | Developers |
| [SYMBOL_INDEX.md](SYMBOL_INDEX.md) | Key classes, interfaces, entry points, functions, schemas, and parameters | Backend / Frontend |
| [DEPENDENCY_MAP.md](DEPENDENCY_MAP.md) | Package coupling matrix, external dependencies, circular imports, hotspots | Architects / Tech Leads |
| [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | 224 tables, columns, indexes, pgvector HNSW, foreign keys, migrations | Database / Backend |
| [API_REFERENCE.md](API_REFERENCE.md) | 827 endpoints, HTTP verbs, auth requirements, parameters, unmounted routes | API Consumers / Frontend |
| [DATA_FLOW.md](DATA_FLOW.md) | Data paths: Biometrics, Multi-tenant isolation, Leave, Payroll, Invites | Backend / Architects |
| [EXECUTION_FLOW.md](EXECUTION_FLOW.md) | App startup, request lifecycle, auth sequence, check-in flow, shutdown | Backend / SRE |
| [TESTING_GUIDE.md](TESTING_GUIDE.md) | 847 tests, fixtures, rate-limit bypassing, runtime validation suites | QA / Developers |
| [SECURITY_ANALYSIS.md](SECURITY_ANALYSIS.md) | Auth, token rotation, RBAC scope, biometrics security, audit findings | Security / Auditing |
| [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md) | Exhaustive environment variables, validation rules, runtime profiles | DevOps / SRE |
| [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) | Dockerfiles, Compose prod/dev, Kubernetes manifests, AWS CI/CD | DevOps / SRE |
| [TECHNICAL_DEBT.md](TECHNICAL_DEBT.md) | Code smells, dead routes, coupling violations, prioritized remediation | Tech Leads / Managers |

### Architectural Diagrams (Mermaid)

| Diagram File | Description |
|---|---|
| [system_architecture.mmd](diagrams/system_architecture.mmd) | End-to-end system topology: Client, Ingress, Backend, AI Microservice, Persistence |
| [component_relationships.mmd](diagrams/component_relationships.mmd) | Detailed coupling between Routers, DI, Core, Services, Repositories, Models |
| [database_erd.mmd](diagrams/database_erd.mmd) | Entity-Relationship Diagram covering core domains and relational foreign keys |
| [dependency_graph.mmd](diagrams/dependency_graph.mmd) | Internal package-to-package dependency flow and external library bindings |
| [application_flow.mmd](diagrams/application_flow.mmd) | Sequence diagram of biometric clock-in, pgvector cosine search, and audit log |

---

## 4. Reading Pathways by Engineering Role

### For Principal Architects & System Leads
1. Start with [ARCHITECTURE.md](ARCHITECTURE.md) to understand the Modular Monolith pattern and multi-tenant data boundaries.
2. Review [diagrams/system_architecture.mmd](diagrams/system_architecture.mmd) and [diagrams/component_relationships.mmd](diagrams/component_relationships.mmd).
3. Inspect [DEPENDENCY_MAP.md](DEPENDENCY_MAP.md) and [TECHNICAL_DEBT.md](TECHNICAL_DEBT.md) to evaluate architectural hotspots and structural refactoring priorities.

### For Backend & API Engineers
1. Study [API_REFERENCE.md](API_REFERENCE.md) for route signatures, authorization dependencies, and unmounted router audits.
2. Review [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for table layouts, relations, and pgvector HNSW indexing.
3. Consult [EXECUTION_FLOW.md](EXECUTION_FLOW.md) and [SYMBOL_INDEX.md](SYMBOL_INDEX.md) when implementing or extending domain services.

### For Frontend Engineers
1. Review [MODULE_INDEX.md](MODULE_INDEX.md) (Frontend Section) for page routing, Zustand store state, and component architecture.
2. Consult [API_REFERENCE.md](API_REFERENCE.md) to match Axios API service wrappers against backend route paths and payload schemas.
3. Check [DATA_FLOW.md](DATA_FLOW.md) for client-side webcam frame capture and MediaPipe landmark integration.

### For DevOps, SRE & Platform Engineers
1. Review [CONFIGURATION_GUIDE.md](CONFIGURATION_GUIDE.md) for all environment variables, connection strings, and security flags.
2. Study [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for Docker builds, Compose production topologies, and AWS EC2/ECR pipelines.
3. Check [SECURITY_ANALYSIS.md](SECURITY_ANALYSIS.md) for production hardening, Nginx configuration, and CORS policies.

### For QA & Security Engineers
1. Review [TESTING_GUIDE.md](TESTING_GUIDE.md) for test execution, fixtures, and runtime validation execution.
2. Inspect [SECURITY_ANALYSIS.md](SECURITY_ANALYSIS.md) for confirmed vulnerabilities, token lifecycle, and cryptographic guarantees.

---

## 5. Repository Identification & Structure Summary

- **Repository Root:** `/home/dheeraj/Development/Projects/VisionCore2.0`
- **Primary Applications:**
  - `backend/`: FastAPI modular monolith hosting 48 active routers, 128 services, 224 database models.
  - `ai-service/`: Standalone FastAPI microservice providing facial embedding extraction, emotion classification, and strict liveness detection.
  - `frontend/`: React 19 single-page application built with Vite 8, Tailwind CSS v4, Zustand 5, and MediaPipe.
  - `deploy/`: Production infrastructure configurations (Nginx reverse proxy, PostgreSQL pgvector, Redis, Docker Compose).
  - `infrastructure/`: Local development orchestration and Kubernetes manifests (`k8s/`).
  - `scripts/`: Operational scripts for database seeding, password recovery, documentation generation, and EC2 deployment.

---

## 6. Incremental Indexing Protocol & Automation

Whenever source code, dependencies, database models, API routes, configuration, or architectural boundaries change, AI coding agents MUST follow the **7-step incremental update procedure** defined in [AGENTS.md](../../AGENTS.md):

1. **Identify affected modules:** Run `python scripts/update_codebase_index.py --status`.
2. **Identify dependent modules:** Consult [DEPENDENCY_MAP.md](DEPENDENCY_MAP.md) and [diagrams/component_relationships.mmd](diagrams/component_relationships.mmd).
3. **Selectively update relevant docs:** Update only the affected files in `docs/codebase-index/` (do not regenerate everything).
4. **Update diagrams when necessary:** Update `docs/codebase-index/diagrams/*.mmd` if component boundaries or models shift.
5. **Validate file paths & symbols:** Run `python scripts/update_codebase_index.py --validate`.
6. **Keep metrics synchronized:** Run `python scripts/update_codebase_index.py --metrics` and update the Key Metrics table.
7. **Record architectural decisions:** Record significant architectural changes in [ARCHITECTURE.md](ARCHITECTURE.md) or [TECHNICAL_DEBT.md](TECHNICAL_DEBT.md).

All documentation in this knowledge base must remain strictly evidence-based and verified against real code AST and manifest files.
