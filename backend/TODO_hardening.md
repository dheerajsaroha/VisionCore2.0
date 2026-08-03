# Runtime Validation Suite Hardening - TODO

## Fixes (in order of application)

1. **Initialize optional variables** — `plan_code`, `reg_headers`, `token` etc.
2. **Guard every authentication** — `tc(..., sa_token is not None)` before `Bearer {sa_token}`
3. **Regression phase fix** — `reg_headers` always exists before use
4. **Bootstrap validation** — verify `starter`, `professional`, `enterprise` exist post-load
5. **Seed endpoint independence** — A.39–A.45 not nested inside previous `if`
6. **PostgreSQL constraint validation** — use `pg_constraint` for unique/index checks
7. **Seeder validation** — don't assume `dict` return type from service
8. **Performance validation** — realistic enterprise thresholds (<200ms etc.)
9. **Defensive API validation** — verify `status_code` before `.json()`
10. **JSON report robustness** — always generated with full fields
11. **Validation resilience** — eliminate all validator bugs

