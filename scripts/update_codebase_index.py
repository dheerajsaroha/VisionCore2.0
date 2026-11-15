#!/usr/bin/env python3
"""
scripts/update_codebase_index.py
Incremental Codebase Index Maintenance & Validation Utility for VisionCore 2.0.

Usage:
    python scripts/update_codebase_index.py --status      # Check what changed in git and map to affected index docs
    python scripts/update_codebase_index.py --metrics     # Recalculate and output updated repository metrics
    python scripts/update_codebase_index.py --validate    # Validate all file paths and symbols in codebase-index
"""

import os
import sys
import subprocess
import argparse
import ast
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_INDEX_DIR = os.path.join(REPO_ROOT, "docs", "codebase-index")

# Mapping of source path patterns to relevant codebase-index documentation
CHANGE_MAPPING = [
    {
        "patterns": ["backend/app/routers/", "ai-service/app/routers/"],
        "docs": ["API_REFERENCE.md", "MODULE_INDEX.md"],
        "diagrams": ["application_flow.mmd"],
        "description": "API Routes / HTTP Controller changes"
    },
    {
        "patterns": ["backend/app/db/models/", "backend/alembic/", "ai-service/app/models/"],
        "docs": ["DATABASE_SCHEMA.md", "SYMBOL_INDEX.md"],
        "diagrams": ["database_erd.mmd"],
        "description": "Database models, columns, tables, or migrations"
    },
    {
        "patterns": ["backend/pyproject.toml", "backend/requirements.txt", "frontend/package.json", "ai-service/requirements.txt"],
        "docs": ["TECHNOLOGY_STACK.md", "DEPENDENCY_MAP.md"],
        "diagrams": ["dependency_graph.mmd"],
        "description": "External dependencies or package manifest changes"
    },
    {
        "patterns": ["backend/app/core/config.py", "backend/.env.example", "frontend/.env.example"],
        "docs": ["CONFIGURATION_GUIDE.md", "SECURITY_ANALYSIS.md"],
        "diagrams": [],
        "description": "Environment variables, settings, or security configs"
    },
    {
        "patterns": ["backend/app/services/", "backend/app/crud/", "backend/app/repositories/"],
        "docs": ["MODULE_INDEX.md", "SYMBOL_INDEX.md", "DATA_FLOW.md", "ARCHITECTURE.md"],
        "diagrams": ["component_relationships.mmd", "system_architecture.mmd"],
        "description": "Domain service logic, CRUD helpers, or repositories"
    },
    {
        "patterns": ["backend/app/api/deps.py", "backend/app/middleware/"],
        "docs": ["ARCHITECTURE.md", "SECURITY_ANALYSIS.md", "EXECUTION_FLOW.md", "SYMBOL_INDEX.md"],
        "diagrams": ["component_relationships.mmd"],
        "description": "Auth, RBAC/EAAC guards, tenant isolation, or middleware"
    },
    {
        "patterns": ["deploy/", "infrastructure/", "Dockerfile", "docker-compose"],
        "docs": ["DEPLOYMENT_GUIDE.md", "CONFIGURATION_GUIDE.md"],
        "diagrams": ["system_architecture.mmd"],
        "description": "Containers, Compose orchestration, or deployment manifests"
    },
    {
        "patterns": ["backend/app/tests/", "ai-service/tests/"],
        "docs": ["TESTING_GUIDE.md"],
        "diagrams": [],
        "description": "Automated test suites or fixtures"
    },
    {
        "patterns": ["frontend/src/"],
        "docs": ["MODULE_INDEX.md", "ARCHITECTURE.md"],
        "diagrams": ["component_relationships.mmd"],
        "description": "Frontend UI components, stores, services, or pages"
    }
]


def get_git_changed_files():
    """Detect uncommitted and recently committed changes in git."""
    changed = set()
    try:
        # Check unstaged and staged files
        res = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True)
        for line in res.stdout.strip().splitlines():
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                path = parts[1].strip()
                if " -> " in path:
                    path = path.split(" -> ")[1].strip()
                changed.add(path)
        # Check against HEAD~1 if working tree clean
        if not changed:
            res_diff = subprocess.run(["git", "diff", "--name-only", "HEAD~1", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True)
            for line in res_diff.stdout.strip().splitlines():
                if line.strip():
                    changed.add(line.strip())
    except Exception as e:
        print(f"Warning: git command failed ({e})")
    return sorted(changed)


def analyze_affected_docs(changed_files):
    """Map changed files to required documentation updates."""
    affected_docs = set()
    affected_diagrams = set()
    matched_reasons = []

    for f in changed_files:
        if f.startswith("docs/codebase-index/"):
            continue
        for mapping in CHANGE_MAPPING:
            if any(pat in f for pat in mapping["patterns"]):
                for doc in mapping["docs"]:
                    affected_docs.add(doc)
                for diag in mapping["diagrams"]:
                    affected_diagrams.add(diag)
                matched_reasons.append((f, mapping["description"]))

    return affected_docs, affected_diagrams, matched_reasons


def compute_metrics():
    """Calculate verified quantitative metrics across the repository."""
    metrics = {}
    
    # Git tracked files
    res = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True)
    tracked_files = [f for f in res.stdout.splitlines() if f.strip()]
    metrics["total_tracked_files"] = len(tracked_files)
    
    # Uploads test artifacts count
    upload_dir = os.path.join(REPO_ROOT, "backend", "app_data", "uploads")
    pdf_count = 0
    if os.path.exists(upload_dir):
        pdf_count = sum(len(files) for _, _, files in os.walk(upload_dir))
    metrics["excluded_test_artifacts"] = pdf_count
    metrics["source_files_analyzed"] = len(tracked_files) - pdf_count
    
    # Python files & lines
    py_files = [f for f in tracked_files if f.endswith(".py")]
    metrics["python_files"] = len(py_files)
    py_lines = 0
    py_classes = 0
    py_functions = 0
    py_methods = 0
    
    for pf in py_files:
        fp = os.path.join(REPO_ROOT, pf)
        try:
            with open(fp, "r", errors="ignore") as fobj:
                content = fobj.read()
                py_lines += len(content.splitlines())
                tree = ast.parse(content, filename=fp)
                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                        py_classes += 1
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                py_methods += 1
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        py_functions += 1
        except Exception:
            pass
            
    metrics["python_lines"] = py_lines
    metrics["python_classes"] = py_classes
    metrics["python_functions"] = py_functions
    metrics["python_methods"] = py_methods
    
    # Database tables from all_models.py
    models_path = os.path.join(REPO_ROOT, "backend", "app", "db", "models", "all_models.py")
    db_tables = 0
    db_cols = 0
    db_rels = 0
    if os.path.exists(models_path):
        with open(models_path, "r", errors="ignore") as fobj:
            tree = ast.parse(fobj.read(), filename=models_path)
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    has_table = False
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name) and target.id == "__tablename__":
                                    has_table = True
                        elif isinstance(item, ast.AnnAssign):
                            val = item.value
                            if val and isinstance(val, ast.Call):
                                fname = getattr(val.func, "id", getattr(val.func, "attr", ""))
                                if fname == "mapped_column":
                                    db_cols += 1
                                elif fname == "relationship":
                                    db_rels += 1
                    if has_table:
                        db_tables += 1
                        
    metrics["database_tables"] = db_tables
    metrics["database_columns"] = db_cols
    metrics["database_relationships"] = db_rels

    # Alembic migrations count
    versions_dir = os.path.join(REPO_ROOT, "backend", "alembic", "versions")
    if os.path.exists(versions_dir):
        metrics["alembic_migrations"] = len([f for f in os.listdir(versions_dir) if f.endswith(".py")])
        
    # Backend endpoints count
    routers_dir = os.path.join(REPO_ROOT, "backend", "app", "routers")
    endpoints = 0
    for r in os.listdir(routers_dir):
        if r.endswith(".py") and r != "__init__.py":
            with open(os.path.join(routers_dir, r), "r", errors="ignore") as fobj:
                try:
                    tree = ast.parse(fobj.read())
                    for node in tree.body:
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            for dec in node.decorator_list:
                                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                                    if dec.func.attr.lower() in ["get", "post", "put", "patch", "delete"]:
                                        endpoints += 1
                except Exception:
                    pass
    metrics["backend_endpoints"] = endpoints
    
    # Test cases count
    tests_dir = os.path.join(REPO_ROOT, "backend", "app", "tests")
    test_cases = 0
    test_files_cnt = 0
    for root, _, files in os.walk(tests_dir):
        for f in files:
            if f.startswith("test_") and f.endswith(".py"):
                test_files_cnt += 1
                with open(os.path.join(root, f), "r", errors="ignore") as fobj:
                    try:
                        tree = ast.parse(fobj.read())
                        for node in tree.body:
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                                test_cases += 1
                            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                                for item in node.body:
                                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test_"):
                                        test_cases += 1
                    except Exception:
                        pass
    metrics["test_files"] = test_files_cnt
    metrics["test_cases"] = test_cases

    return metrics


def validate_index():
    """Verify that every file path and intra-doc link in codebase-index exists."""
    errors = []
    docs = [f for f in os.listdir(DOCS_INDEX_DIR) if f.endswith(".md")]
    for doc in docs:
        fp = os.path.join(DOCS_INDEX_DIR, doc)
        with open(fp, "r", errors="ignore") as fobj:
            content = fobj.read()
            links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
            for text, target in links:
                if target.startswith("http") or target.startswith("#") or target.startswith("conversation:"):
                    continue
                clean = target.split("#")[0]
                target_local = os.path.normpath(os.path.join(DOCS_INDEX_DIR, clean))
                target_repo = os.path.normpath(os.path.join(REPO_ROOT, clean))
                if not os.path.exists(target_local) and not os.path.exists(target_repo):
                    errors.append(f"{doc}: Broken link target '{target}'")
    return errors


def main():
    parser = argparse.ArgumentParser(description="Incremental Codebase Index Maintenance Tool")
    parser.add_argument("--status", action="store_true", help="Analyze recent/uncommitted git changes and map to affected docs")
    parser.add_argument("--metrics", action="store_true", help="Recalculate repository metrics")
    parser.add_argument("--validate", action="store_true", help="Validate documentation paths and links")
    args = parser.parse_args()

    if not any([args.status, args.metrics, args.validate]):
        parser.print_help()
        sys.exit(0)

    if args.status:
        changed = get_git_changed_files()
        print(f"Detected {len(changed)} changed files in git.")
        if not changed:
            print("Working tree is clean and matches HEAD.")
        else:
            docs, diags, reasons = analyze_affected_docs(changed)
            print("\nAffected Source Files:")
            for f, reason in reasons:
                print(f"  • {f} ({reason})")
            print("\nRequired Documentation Updates (Selective):")
            for d in sorted(docs):
                print(f"  [DOC] docs/codebase-index/{d}")
            for diag in sorted(diags):
                print(f"  [DIAGRAM] docs/codebase-index/diagrams/{diag}")
            if not docs and not diags:
                print("  (No core architectural or index-tracked files were impacted)")

    if args.metrics:
        print("\nComputing repository quantitative metrics...")
        m = compute_metrics()
        for k, v in m.items():
            print(f"  {k:30}: {v}")

    if args.validate:
        print("\nValidating docs/codebase-index integrity...")
        errs = validate_index()
        if not errs:
            print("Validation PASSED: All documentation paths and internal links are intact.")
        else:
            print(f"Validation FAILED: Found {len(errs)} broken references:")
            for err in errs:
                print(f"  - {err}")
            sys.exit(1)


if __name__ == "__main__":
    main()
