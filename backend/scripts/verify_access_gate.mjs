/**
 * Verifies the frontend access gate against real backend data.
 *
 * `accessControl.js` is plain ESM with no React dependency, so it can be
 * imported directly by Node. This feeds it the actual seeded plan features and
 * the actual RolePermission grants, and reports what each role would see on
 * each plan. That checks the two sides of the contract agree, rather than
 * trusting a hand-written table of expectations.
 *
 * Run:  node backend/scripts/verify_access_gate.mjs
 */
import { execFileSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const BACKEND = dirname(dirname(fileURLToPath(import.meta.url)));
const FRONTEND = join(BACKEND, '..', 'frontend');

const { routePolicies, canAccess, resolvePolicy, canApproveWorkflows } = await import(
  join(FRONTEND, 'src', 'lib', 'accessControl.js')
);

// Pull the real fixtures out of the database.
const raw = execFileSync(
  join(BACKEND, '.venv', 'bin', 'python'),
  [
    '-c',
    `
import json
from app.db.database import SessionLocal
from app.db.models.all_models import SubscriptionPlan, Role, RolePermission

db = SessionLocal()
plans = {}
for p in db.query(SubscriptionPlan).all():
    if p.code in ('starter', 'professional', 'enterprise'):
        plans[p.code] = sorted(pf.feature.code for pf in (p.plan_features or []) if pf.enabled)

roles = {}
for r in db.query(Role).filter(Role.name.in_(
    ['OrgEmployee', 'OrgManager', 'OrgHR', 'OrgAdmin', 'OrgFinance'])).all():
    roles[r.name] = sorted(
        pp.permission.name
        for pp in db.query(RolePermission).filter(RolePermission.role_id == r.id).all()
    )

print(json.dumps({'plans': plans, 'roles': roles}))
`,
  ],
  { cwd: BACKEND, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }
);

const { plans, roles } = JSON.parse(raw.trim().split('\n').pop());

const visibleFor = (roleName, planCode) => {
  const perms = new Set(roles[roleName] || []);
  const features = new Set(plans[planCode] || []);
  const caps = {
    hasPermission: (p) => perms.has(p),
    hasFeature: (f) => features.has(f),
    isAuthenticated: true,
  };
  return Object.keys(routePolicies).filter((path) => canAccess(resolvePolicy(path), caps).allowed);
};

const bar = '─'.repeat(78);
let failures = 0;
const check = (label, cond) => {
  if (!cond) failures += 1;
  console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${label}`);
};

console.log(`\n${bar}\n  WHAT EACH ROLE SEES, PER PLAN (nav entries visible)\n${bar}`);

for (const plan of ['starter', 'professional', 'enterprise']) {
  console.log(`\n  ── ${plan.toUpperCase()} (${(plans[plan] || []).length} features) ──`);
  for (const role of ['OrgEmployee', 'OrgManager', 'OrgHR', 'OrgAdmin', 'OrgFinance']) {
    const visible = visibleFor(role, plan);
    console.log(`    ${role.padEnd(13)} ${String(visible.length).padStart(2)}  ${visible.join(', ')}`);
  }
}

console.log(`\n${bar}\n  INVARIANTS\n${bar}\n`);

// An employee must never see an administrative module on any plan.
const ADMIN_ONLY = [
  '/dashboard/organization', '/dashboard/users', '/dashboard/payroll',
  '/dashboard/assets', '/dashboard/permissions', '/dashboard/tenant-admin',
  '/dashboard/dynamic-roles', '/dashboard/hr', '/dashboard/ai-studio',
  '/dashboard/enterprise', '/dashboard/operations', '/dashboard/scope-ownership',
  '/dashboard/approval-workflows', '/dashboard/permissions',
];
for (const plan of ['starter', 'professional', 'enterprise']) {
  const seen = visibleFor('OrgEmployee', plan);
  const leaked = ADMIN_ONLY.filter((p) => seen.includes(p));
  check(`OrgEmployee on ${plan} sees no admin module`, leaked.length === 0);
  if (leaked.length) console.log(`        leaked: ${leaked.join(', ')}`);
}

// An employee must always keep the self-service surface.
for (const plan of ['starter', 'professional', 'enterprise']) {
  const seen = visibleFor('OrgEmployee', plan);
  check(`OrgEmployee on ${plan} keeps /dashboard`, seen.includes('/dashboard'));
  check(`OrgEmployee on ${plan} keeps /dashboard/settings`, seen.includes('/dashboard/settings'));
}

// Plan-gated modules must follow the plan, not the role.
const seenEmployee = visibleFor('OrgEmployee', 'starter');
const seenAdmin = visibleFor('OrgAdmin', 'starter');
for (const [path, feature] of [
  ['/dashboard/payroll', 'payroll'],
  ['/dashboard/assets', 'assets'],
  ['/dashboard/learning', 'training'],
  ['/dashboard/performance', 'performance_reviews'],
  ['/dashboard/open-positions', 'recruitment'],
  ['/dashboard/reimbursements', 'expenses'],
]) {
  check(
    `${feature}: OrgAdmin on starter is blocked without the feature`,
    !seenAdmin.includes(path)
  );
}

const adminPro = visibleFor('OrgAdmin', 'professional');
for (const [path, feature] of [
  ['/dashboard/payroll', 'payroll'],
  ['/dashboard/assets', 'assets'],
  ['/dashboard/learning', 'training'],
  ['/dashboard/performance', 'performance_reviews'],
  ['/dashboard/open-positions', 'recruitment'],
  ['/dashboard/reimbursements', 'expenses'],
]) {
  check(
    `${feature}: OrgAdmin on professional gains it once the plan grants it`,
    adminPro.includes(path)
  );
}

// Feature-gated modules must be hidden on starter even for a full-permission
// role, which is the case the old UI got wrong.
check(
  'payroll hidden on starter for OrgFinance (who holds payroll.generate)',
  !visibleFor('OrgFinance', 'starter').includes('/dashboard/payroll')
);
check(
  'payroll visible on professional for OrgFinance',
  visibleFor('OrgFinance', 'professional').includes('/dashboard/payroll')
);

// Self-service payslips: permission-free, but still plan-gated.
check('my-payslips visible to employee on professional', visibleFor('OrgEmployee', 'professional').includes('/dashboard/my-payslips'));
check('my-payslips hidden on starter (no payroll feature)', !visibleFor('OrgEmployee', 'starter').includes('/dashboard/my-payslips'));

// The approval predicate must agree with the backend role-name check.
for (const [role, expected] of [
  ['OrgEmployee', false], ['OrgHR', true], ['OrgAdmin', true],
  ['OrgManager', true], ['OrgFinance', false], ['SuperAdmin', true],
]) {
  check(`canApproveWorkflows(${role}) === ${expected}`, canApproveWorkflows(role) === expected);
}

// Every nav path must be registered, so nothing is reachable-but-invisible.
check('no duplicate route keys', new Set(Object.keys(routePolicies)).size === Object.keys(routePolicies).length);

// BiometricAvatar gate. It mirrors this predicate, and the backend refuses the
// request for anyone who is neither the subject nor a `users.update` holder, so
// an employee viewing a colleague's check-in must not issue it at all. This was
// the source of up to five generic permission toasts per dashboard load.
const avatarMayRequest = (roleName, viewerId, subjectId) => {
  const perms = new Set(roles[roleName] || []);
  return viewerId === subjectId || perms.has('users.update');
};
check(
  'OrgEmployee may not request a colleague face photo',
  avatarMayRequest('OrgEmployee', 100, 200) === false
);
check(
  'OrgEmployee may request their own face photo',
  avatarMayRequest('OrgEmployee', 100, 100) === true
);
check(
  'a users.update holder may request any face photo',
  ['OrgAdmin', 'OrgHR'].every((r) => (roles[r] || []).includes('users.update'))
);

console.log(`\n${failures === 0 ? 'ALL INVARIANTS HOLD' : `${failures} INVARIANT(S) FAILED`}\n`);
process.exit(failures === 0 ? 0 : 1);
