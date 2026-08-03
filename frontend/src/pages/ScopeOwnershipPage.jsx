import React, { useState, useEffect } from 'react';
import scopeService from '../services/scopeService';

const SCOPE_COLORS = {
  platform: '#a78bfa',
  multi_org: '#818cf8',
  organization: '#60a5fa',
  business_unit: '#34d399',
  department: '#fbbf24',
  team: '#fb923c',
  project: '#f472b6',
  location: '#94a3b8',
  reporting_hierarchy: '#22d3ee',
  self: '#4ade80',
  custom: '#d1d5db',
};

const Badge = ({ label, color }) => (
  <span style={{
    background: `${color}22`,
    color,
    border: `1px solid ${color}44`,
    padding: '2px 10px',
    borderRadius: 999,
    fontSize: 12,
    fontWeight: 600,
    letterSpacing: 0.3,
  }}>
    {label}
  </span>
);

const Card = ({ title, subtitle, children, accent = '#60a5fa' }) => (
  <div style={{
    background: 'linear-gradient(135deg, #1e1e2e 0%, #181825 100%)',
    border: `1px solid #313244`,
    borderRadius: 16,
    padding: '1.5rem',
    position: 'relative',
    overflow: 'hidden',
  }}>
    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 3, background: `linear-gradient(90deg, ${accent}, transparent)` }} />
    {title && <h3 style={{ margin: '0 0 4px', color: '#cdd6f4', fontSize: 15, fontWeight: 700 }}>{title}</h3>}
    {subtitle && <p style={{ margin: '0 0 1rem', color: '#6c7086', fontSize: 12 }}>{subtitle}</p>}
    {children}
  </div>
);

const StatPill = ({ value, label, color }) => (
  <div style={{ textAlign: 'center', padding: '0.75rem 1.25rem', background: '#1e1e2e', borderRadius: 12, border: '1px solid #313244', minWidth: 90 }}>
    <div style={{ fontSize: 26, fontWeight: 800, color }}>{value}</div>
    <div style={{ fontSize: 11, color: '#6c7086', marginTop: 2, fontWeight: 500 }}>{label}</div>
  </div>
);

const ScopeHierarchyBar = ({ scopes }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
    {[...scopes].sort((a, b) => b.scope_level - a.scope_level).map(scope => {
      const color = SCOPE_COLORS[scope.code] || '#6c7086';
      return (
        <div key={scope.id} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 10, height: 10, borderRadius: '50%', background: color, flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
              <span style={{ color: '#cdd6f4', fontSize: 12, fontWeight: 600 }}>{scope.name}</span>
              <span style={{ color, fontSize: 11, fontWeight: 700 }}>L{scope.scope_level}</span>
            </div>
            <div style={{ height: 4, background: '#313244', borderRadius: 999 }}>
              <div style={{ height: '100%', width: `${scope.scope_level}%`, background: color, borderRadius: 999, transition: 'width 0.6s ease' }} />
            </div>
          </div>
        </div>
      );
    })}
  </div>
);

const TabBar = ({ tabs, active, onSelect }) => (
  <div style={{ display: 'flex', gap: 4, background: '#181825', borderRadius: 12, padding: 4, border: '1px solid #313244', flexWrap: 'wrap' }}>
    {tabs.map(tab => (
      <button key={tab.id} onClick={() => onSelect(tab.id)} style={{
        padding: '7px 14px', border: 'none', cursor: 'pointer', borderRadius: 8, fontSize: 12, fontWeight: 600, transition: 'all 0.2s',
        background: active === tab.id ? 'linear-gradient(135deg, #89b4fa, #74c7ec)' : 'transparent',
        color: active === tab.id ? '#1e1e2e' : '#6c7086',
      }}>
        {tab.icon} {tab.label}
      </button>
    ))}
  </div>
);

// ── Tab: Scope Dashboard ────────────────────────────────────────
const ScopeDashboardTab = () => {
  const [scopes, setScopes] = useState([]);
  const [roleMappings, setRoleMappings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([scopeService.getDataScopes(), scopeService.getRoleDataScopes()])
      .then(([s, r]) => { setScopes(s.data_scopes || []); setRoleMappings(r.role_data_scopes || []); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ color: '#6c7086', textAlign: 'center', padding: '3rem' }}>Loading scope hierarchy…</div>;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
      <Card title="Scope Hierarchy Levels" subtitle="Enterprise data access tiers" accent="#89b4fa">
        <ScopeHierarchyBar scopes={scopes} />
      </Card>
      <Card title="Role Scope Bindings" subtitle="Active role → scope mappings" accent="#a6e3a1">
        {roleMappings.length === 0
          ? <p style={{ color: '#6c7086', fontSize: 13 }}>No role-scope bindings found. Run seed to populate.</p>
          : roleMappings.map(m => (
            <div key={m.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid #313244' }}>
              <span style={{ color: '#cdd6f4', fontSize: 12, fontWeight: 600 }}>{m.role_name || `Role #${m.role_id}`}</span>
              <Badge label={m.data_scope_code || '—'} color={SCOPE_COLORS[m.data_scope_code] || '#6c7086'} />
            </div>
          ))
        }
      </Card>
      <div style={{ gridColumn: '1 / -1', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {scopes.slice(0, 6).map(s => (
          <StatPill key={s.id} value={`L${s.scope_level}`} label={s.code} color={SCOPE_COLORS[s.code] || '#6c7086'} />
        ))}
      </div>
    </div>
  );
};

// ── Tab: Ownership Dashboard ────────────────────────────────────
const OwnershipDashboardTab = () => {
  const [ownerships, setOwnerships] = useState([]);
  const [history, setHistory] = useState([]);
  const [delegations, setDelegations] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      scopeService.getOwnerships({ limit: 10 }),
      scopeService.getOwnershipHistory({ limit: 10 }),
      scopeService.getDelegations({ limit: 10 }),
    ]).then(([o, h, d]) => {
      setOwnerships(o.ownerships || []);
      setHistory(h.history || []);
      setDelegations(d.delegations || []);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const ACTION_COLORS = { assigned: '#a6e3a1', transferred: '#89dceb', delegated: '#cba6f7', revoked: '#f38ba8', expired: '#fab387', recovered: '#f9e2af' };

  if (loading) return <div style={{ color: '#6c7086', textAlign: 'center', padding: '3rem' }}>Loading ownership data…</div>;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
      <Card title="Recent Ownership Records" subtitle="Latest resource ownership entries" accent="#cba6f7">
        {ownerships.length === 0
          ? <p style={{ color: '#6c7086', fontSize: 13 }}>No ownership records yet.</p>
          : ownerships.map(o => (
            <div key={o.id} style={{ padding: '8px 0', borderBottom: '1px solid #313244' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: '#89b4fa', fontSize: 12, fontWeight: 700 }}>{o.entity_type}</span>
                <Badge label={o.owner_type} color="#cba6f7" />
              </div>
              <div style={{ color: '#6c7086', fontSize: 11, marginTop: 2 }}>
                Entity: {o.entity_id.slice(0, 12)}… | Owner: {o.owner_name || o.owner_email || `#${o.owner_user_id}`}
              </div>
            </div>
          ))
        }
      </Card>
      <Card title="Ownership Audit Trail" subtitle="Recent ownership changes" accent="#f38ba8">
        {history.length === 0
          ? <p style={{ color: '#6c7086', fontSize: 13 }}>No audit history yet.</p>
          : history.map(h => (
            <div key={h.id} style={{ padding: '7px 0', borderBottom: '1px solid #313244', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span style={{ color: '#cdd6f4', fontSize: 12 }}>{h.entity_type}:{h.entity_id.slice(0, 8)}</span>
                <div style={{ color: '#6c7086', fontSize: 11 }}>{h.reason?.slice(0, 40)}</div>
              </div>
              <Badge label={h.action} color={ACTION_COLORS[h.action] || '#6c7086'} />
            </div>
          ))
        }
      </Card>
      <Card title="Active Delegations" subtitle="Temporary access delegations" accent="#89b4fa" style={{ gridColumn: '1 / -1' }}>
        {delegations.length === 0
          ? <p style={{ color: '#6c7086', fontSize: 13 }}>No active delegations found.</p>
          : delegations.map(d => (
            <div key={d.id} style={{ padding: '8px 0', borderBottom: '1px solid #313244', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span style={{ color: '#cdd6f4', fontSize: 12, fontWeight: 600 }}>{d.delegator_name} → {d.delegatee_name}</span>
                <div style={{ color: '#6c7086', fontSize: 11 }}>{d.reason}</div>
              </div>
              <Badge label={d.is_active ? 'Active' : 'Expired'} color={d.is_active ? '#a6e3a1' : '#f38ba8'} />
            </div>
          ))
        }
      </Card>
    </div>
  );
};

// ── Tab: Authorization Inspector ───────────────────────────────
const AuthInspectorTab = () => {
  const [permCode, setPermCode] = useState('attendance.read');
  const [userId, setUserId] = useState('');
  const [orgId, setOrgId] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const inspect = async () => {
    setLoading(true);
    setResult(null);
    try {
      const data = await scopeService.inspectAuthorization({ user_id: Number(userId), organization_id: orgId, permission_code: permCode });
      setResult(data);
    } catch (e) {
      setResult({ error: e.response?.data?.detail || 'Inspection failed' });
    } finally {
      setLoading(false);
    }
  };

  const [scopeResult, setScopeResult] = useState(null);
  const getSelfScope = async () => {
    try {
      const data = await scopeService.getEffectiveScope(permCode);
      setScopeResult(data);
    } catch (e) {
      setScopeResult({ error: e.response?.data?.detail || 'Failed' });
    }
  };

  const inputStyle = {
    width: '100%', padding: '8px 12px', background: '#181825', border: '1px solid #313244',
    borderRadius: 8, color: '#cdd6f4', fontSize: 13, outline: 'none', boxSizing: 'border-box',
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
      <Card title="Authorization Inspector" subtitle="Evaluate Permission → Scope → Ownership chain" accent="#f5c2e7">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div>
            <label style={{ color: '#6c7086', fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 4 }}>USER ID (int)</label>
            <input style={inputStyle} placeholder="e.g. 1" value={userId} onChange={e => setUserId(e.target.value)} />
          </div>
          <div>
            <label style={{ color: '#6c7086', fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 4 }}>ORGANIZATION UUID</label>
            <input style={inputStyle} placeholder="org UUID" value={orgId} onChange={e => setOrgId(e.target.value)} />
          </div>
          <div>
            <label style={{ color: '#6c7086', fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 4 }}>PERMISSION CODE</label>
            <input style={inputStyle} placeholder="e.g. attendance.read" value={permCode} onChange={e => setPermCode(e.target.value)} />
          </div>
          <button onClick={inspect} disabled={loading} style={{
            padding: '10px 0', background: 'linear-gradient(135deg, #f5c2e7, #cba6f7)', border: 'none', borderRadius: 8,
            color: '#1e1e2e', fontWeight: 700, fontSize: 13, cursor: 'pointer', marginTop: 4,
          }}>
            {loading ? 'Inspecting…' : '🔍 Inspect Authorization'}
          </button>
        </div>
        {result && (
          <div style={{ marginTop: 14, padding: '12px', background: '#181825', borderRadius: 10, border: '1px solid #313244' }}>
            {result.error
              ? <p style={{ color: '#f38ba8', fontSize: 12 }}>⚠️ {result.error}</p>
              : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#6c7086', fontSize: 12 }}>Decision</span>
                    <Badge label={result.allowed ? '✅ ALLOWED' : '🚫 DENIED'} color={result.allowed ? '#a6e3a1' : '#f38ba8'} />
                  </div>
                  {[
                    ['Scope', `${result.resolved_scope_code} (L${result.resolved_scope_level})`],
                    ['Ownership', result.ownership_matched ? '✓ Matched' : '✗ None'],
                    ['Delegation', result.delegation_active ? '✓ Active' : '✗ None'],
                  ].map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: '#6c7086', fontSize: 12 }}>{k}</span>
                      <span style={{ color: '#cdd6f4', fontSize: 12, fontWeight: 600 }}>{v}</span>
                    </div>
                  ))}
                  {result.denial_reason && <p style={{ color: '#fab387', fontSize: 11, marginTop: 4 }}>⚠️ {result.denial_reason}</p>}
                </div>
              )
            }
          </div>
        )}
      </Card>
      <Card title="My Effective Scope" subtitle="Real-time scope resolution for current user" accent="#89b4fa">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div>
            <label style={{ color: '#6c7086', fontSize: 11, fontWeight: 600, display: 'block', marginBottom: 4 }}>PERMISSION</label>
            <input style={inputStyle} value={permCode} onChange={e => setPermCode(e.target.value)} />
          </div>
          <button onClick={getSelfScope} style={{
            padding: '10px 0', background: 'linear-gradient(135deg, #89b4fa, #74c7ec)', border: 'none', borderRadius: 8,
            color: '#1e1e2e', fontWeight: 700, fontSize: 13, cursor: 'pointer',
          }}>
            🌐 Resolve My Scope
          </button>
        </div>
        {scopeResult && (
          <div style={{ marginTop: 14, padding: '12px', background: '#181825', borderRadius: 10, border: '1px solid #313244' }}>
            {scopeResult.error
              ? <p style={{ color: '#f38ba8', fontSize: 12 }}>⚠️ {scopeResult.error}</p>
              : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: '#6c7086', fontSize: 12 }}>Resolved Scope</span>
                    <Badge label={scopeResult.scope_code} color={SCOPE_COLORS[scopeResult.scope_code] || '#6c7086'} />
                  </div>
                  {[
                    ['Level', scopeResult.scope_level],
                    ['Platform Admin', scopeResult.is_platform_admin ? '✓ Yes' : '✗ No'],
                    ['Org Admin', scopeResult.is_org_admin ? '✓ Yes' : '✗ No'],
                    ['Active Delegations', scopeResult.active_delegations?.length || 0],
                    ['Dept IDs', (scopeResult.department_ids || []).join(', ') || '—'],
                    ['Subordinate Users', scopeResult.subordinate_user_ids?.length || 0],
                  ].map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: '#6c7086', fontSize: 12 }}>{k}</span>
                      <span style={{ color: '#cdd6f4', fontSize: 12, fontWeight: 600 }}>{v}</span>
                    </div>
                  ))}
                </div>
              )
            }
          </div>
        )}
      </Card>
    </div>
  );
};

// ── Tab: Rules & Policies ──────────────────────────────────────
const RulesPoliciesTab = () => {
  const [rules, setRules] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([scopeService.getRules(), scopeService.getPolicies()])
      .then(([r, p]) => { setRules(r.rules || []); setPolicies(p.policies || []); })
      .catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ color: '#6c7086', textAlign: 'center', padding: '3rem' }}>Loading…</div>;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
      <Card title="Ownership Rules" subtitle="Automatic ownership assignment rules" accent="#a6e3a1">
        {rules.length === 0
          ? <p style={{ color: '#6c7086', fontSize: 13 }}>No rules seeded. Run /scope/seed first.</p>
          : rules.map(r => (
            <div key={r.id} style={{ padding: '8px 0', borderBottom: '1px solid #313244' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: '#cdd6f4', fontSize: 12, fontWeight: 700 }}>{r.name}</span>
                <Badge label={r.default_owner_type} color="#a6e3a1" />
              </div>
              <div style={{ color: '#6c7086', fontSize: 11, marginTop: 2 }}>
                Entity: <strong style={{ color: '#89b4fa' }}>{r.entity_type}</strong> | Creator: {r.auto_assign_creator ? '✓' : '✗'} | Manager: {r.auto_assign_manager ? '✓' : '✗'}
              </div>
            </div>
          ))
        }
      </Card>
      <Card title="Ownership Policies" subtitle="Governance policies for ownership & delegation" accent="#fab387">
        {policies.length === 0
          ? <p style={{ color: '#6c7086', fontSize: 13 }}>No policies found. Run /scope/seed first.</p>
          : policies.map(p => (
            <div key={p.id} style={{ padding: '8px 0', borderBottom: '1px solid #313244' }}>
              <span style={{ color: '#cdd6f4', fontSize: 12, fontWeight: 700 }}>{p.name}</span>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6 }}>
                <Badge label={`Max ${p.max_delegation_days}d delegation`} color="#fab387" />
                {p.allow_cross_dept_delegation && <Badge label="Cross-dept ✓" color="#a6e3a1" />}
                {p.require_approval_for_transfer && <Badge label="Transfer approval" color="#cba6f7" />}
              </div>
            </div>
          ))
        }
      </Card>
    </div>
  );
};

// ── Main Page Component ────────────────────────────────────────
const TABS = [
  { id: 'scope', label: 'Scope Dashboard', icon: '🌐' },
  { id: 'ownership', label: 'Ownership', icon: '🔑' },
  { id: 'inspector', label: 'Authorization Inspector', icon: '🔍' },
  { id: 'rules', label: 'Rules & Policies', icon: '📋' },
];

const ScopeOwnershipPage = () => {
  const [activeTab, setActiveTab] = useState('scope');
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState('');

  const handleSeed = async () => {
    setSeeding(true);
    setSeedMsg('');
    try {
      const res = await scopeService.seedData();
      setSeedMsg(`✅ ${res.message} (${res.scopes_seeded} scopes)`);
    } catch (e) {
      setSeedMsg(`⚠️ ${e.response?.data?.detail || 'Seed failed'}`);
    } finally {
      setSeeding(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #11111b 0%, #181825 60%, #1e1e2e 100%)',
      padding: '2rem',
      fontFamily: '"Inter", "Segoe UI", system-ui, sans-serif',
    }}>
      {/* Header */}
      <div style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 26, fontWeight: 800, background: 'linear-gradient(135deg, #89b4fa, #cba6f7, #f5c2e7)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              Data Scope & Resource Ownership
            </h1>
            <p style={{ margin: '6px 0 0', color: '#6c7086', fontSize: 13 }}>
              Enterprise authorization layer — Scope resolution, ownership management, and delegation control
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {seedMsg && <span style={{ fontSize: 11, color: seedMsg.startsWith('✅') ? '#a6e3a1' : '#f38ba8', fontWeight: 600 }}>{seedMsg}</span>}
            <button onClick={handleSeed} disabled={seeding} style={{
              padding: '8px 16px', background: 'linear-gradient(135deg, #45475a, #585b70)', border: 'none', borderRadius: 8,
              color: '#cdd6f4', fontSize: 12, fontWeight: 600, cursor: 'pointer',
            }}>
              {seeding ? '⏳ Seeding…' : '🌱 Seed Data'}
            </button>
          </div>
        </div>
        {/* EAAC Chain Indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: '1.25rem', flexWrap: 'wrap' }}>
          {['Auth', 'Subscription', 'Feature', 'Permission', '→ Scope & Ownership ←', 'Approval', 'Dynamic Roles'].map((label, i) => (
            <React.Fragment key={label}>
              <span style={{
                padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 700,
                background: label.includes('→') ? 'linear-gradient(135deg, #89b4fa33, #cba6f733)' : '#1e1e2e',
                border: label.includes('→') ? '1px solid #89b4fa' : '1px solid #313244',
                color: label.includes('→') ? '#89b4fa' : '#6c7086',
              }}>{label}</span>
              {i < 6 && <span style={{ color: '#313244', fontSize: 10 }}>›</span>}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Tab Navigation */}
      <div style={{ marginBottom: '1.5rem' }}>
        <TabBar tabs={TABS} active={activeTab} onSelect={setActiveTab} />
      </div>

      {/* Tab Content */}
      {activeTab === 'scope' && <ScopeDashboardTab />}
      {activeTab === 'ownership' && <OwnershipDashboardTab />}
      {activeTab === 'inspector' && <AuthInspectorTab />}
      {activeTab === 'rules' && <RulesPoliciesTab />}
    </div>
  );
};

export default ScopeOwnershipPage;
