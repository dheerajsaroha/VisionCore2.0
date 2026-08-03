import React, { useState, useEffect } from 'react';
<<<<<<< HEAD
=======
import { motion } from 'framer-motion';
>>>>>>> refs/remotes/origin/main
import { useAuthStore } from '../store/authStore';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { Avatar } from '../components/ui/Avatar';
<<<<<<< HEAD
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/Tabs';
import { Bell, Shield, User, Building, Moon, Sun, Key, Plus, Trash2 } from 'lucide-react';
import { orgService } from '../services/orgService';

export default function Settings() {
  const { user } = useAuthStore();
  const [theme, setTheme] = useState('dark');
  const [apiKeys, setApiKeys] = useState([]);
  const [newKey, setNewKey] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [organization, setOrganization] = useState(null);
  const [orgForm, setOrgForm] = useState({ name: '', zkp_threshold: '0.98', primary_color: '#4F46E5', logo_url: '' });
  const [orgLoading, setOrgLoading] = useState(false);
  const [orgSaving, setOrgSaving] = useState(false);
  const [orgError, setOrgError] = useState('');
  const [orgSuccess, setOrgSuccess] = useState('');

  const isAdmin = user?.role?.name === 'Admin' || user?.role?.name === 'SuperAdmin';

  const loadApiKeys = async () => {
    if (!isAdmin) return;
    try {
      const keys = await orgService.getApiKeys();
      setApiKeys(keys);
    } catch (err) {
      console.error("Failed to load API keys", err);
    }
  };

  const loadOrganization = async () => {
    if (!isAdmin) return;
    setOrgLoading(true);
    setOrgError('');
    try {
      const org = await orgService.getCurrentOrganization();
      setOrganization(org);
      setOrgForm({
        name: org.name || '',
        zkp_threshold: String(org.zkp_threshold ?? 0.98),
        primary_color: org.primary_color || '#4F46E5',
        logo_url: org.logo_url || '',
      });
    } catch (err) {
      setOrgError(err.response?.data?.detail || 'Unable to load organization settings.');
    } finally {
      setOrgLoading(false);
    }
  };

  useEffect(() => {
    loadApiKeys();
    loadOrganization();
  }, [isAdmin]);

  const updateOrgField = (field, value) => {
    setOrgForm((current) => ({ ...current, [field]: value }));
    setOrgSuccess('');
  };

  const handleSaveOrganization = async (event) => {
    event.preventDefault();
    setOrgError('');
    setOrgSuccess('');
    const primaryColor = orgForm.primary_color.trim();
    if (!/^#[0-9A-Fa-f]{6}$/.test(primaryColor)) {
      setOrgError('Primary color must be a six-digit hex value, for example #4F46E5.');
      return;
    }
    const threshold = Number(orgForm.zkp_threshold);
    if (!Number.isFinite(threshold) || threshold < 0 || threshold > 1) {
      setOrgError('ZKP threshold must be between 0 and 1.');
      return;
    }
    setOrgSaving(true);
    try {
      const updated = await orgService.updateOrganization({
        name: orgForm.name.trim(),
        zkp_threshold: threshold,
        primary_color: primaryColor,
        logo_url: orgForm.logo_url.trim() || null,
      });
      setOrganization(updated);
      setOrgForm((current) => ({ ...current, logo_url: updated.logo_url || '' }));
      setOrgSuccess('Organization settings saved.');
    } catch (err) {
      setOrgError(err.response?.data?.detail || 'Unable to save organization settings.');
    } finally {
      setOrgSaving(false);
    }
  };

  const handleGenerateKey = async () => {
    setIsLoading(true);
    try {
      const res = await orgService.createApiKey({ scope: 'camera_edge', rate_limit: 60 });
      setNewKey(res.raw_key);
      await loadApiKeys();
    } catch (err) {
      console.error("Failed to generate key", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRevokeKey = async (id) => {
    try {
      await orgService.revokeApiKey(id);
      await loadApiKeys();
    } catch (err) {
      console.error("Failed to revoke key", err);
=======
import { useToast } from '../components/ui/Toast';
import { adminService } from '../services/adminService';
import {
  Bell, Shield, User, Building, Moon, Sun,
  Zap, ZapOff, Save, Key, RefreshCw, Loader2,
} from 'lucide-react';

const Section = ({ title, description, icon: Icon, children }) => (
  <Card>
    <CardHeader className="border-b border-gray-800/50 pb-4">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-xl bg-indigo-500/10 flex items-center justify-center">
          <Icon className="h-5 w-5 text-indigo-400" />
        </div>
        <div>
          <CardTitle className="text-white text-base">{title}</CardTitle>
          {description && (
            <CardDescription className="text-gray-500 text-xs mt-0.5">{description}</CardDescription>
          )}
        </div>
      </div>
    </CardHeader>
    <CardContent className="pt-5">{children}</CardContent>
  </Card>
);

const Toggle = ({ enabled, onToggle, loading, disabled }) => (
  <button
    onClick={onToggle}
    disabled={loading || disabled}
    aria-pressed={enabled}
    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed ${
      enabled ? 'bg-indigo-600' : 'bg-gray-700'
    }`}
  >
    <span className="sr-only">{enabled ? 'Disable' : 'Enable'}</span>
    <span
      className={`inline-flex h-4 w-4 items-center justify-center rounded-full bg-white shadow-md transform transition-transform duration-300 ${
        enabled ? 'translate-x-6' : 'translate-x-1'
      }`}
    >
      {loading && <Loader2 className="h-3 w-3 text-indigo-500 animate-spin" />}
    </span>
  </button>
);

const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.07 } },
};
const itemVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.35 } },
};

export default function Settings() {
  const { user } = useAuthStore();
  const toast = useToast();
  const userRole = user?.role?.name || 'Employee';
  const isSuperAdmin = userRole === 'SuperAdmin';

  const [profileForm, setProfileForm] = useState({
    full_name: user?.full_name || '',
    email: user?.email || '',
  });
  const [passwordForm, setPasswordForm] = useState({
    current: '', next: '', confirm: '',
  });
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);

  // Web3 toggle state (SuperAdmin only)
  const [web3Enabled, setWeb3Enabled] = useState(false);
  const [web3Loading, setWeb3Loading] = useState(false);
  const [web3Fetching, setWeb3Fetching] = useState(false);

  useEffect(() => {
    if (isSuperAdmin) fetchWeb3Status();
  }, [isSuperAdmin]);

  const fetchWeb3Status = async () => {
    setWeb3Fetching(true);
    try {
      const res = await adminService.getBlockchainStatus();
      setWeb3Enabled(res.data?.enabled ?? false);
    } catch {
      // backend may not be running — silently default to false
    } finally {
      setWeb3Fetching(false);
    }
  };

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    setSavingProfile(true);
    try {
      // API call would go here: await userService.updateProfile(profileForm);
      await new Promise((r) => setTimeout(r, 700)); // simulate
      toast({ message: 'Profile updated successfully.', type: 'success' });
    } catch {
      toast({ message: 'Failed to save profile. Please try again.', type: 'error' });
    } finally {
      setSavingProfile(false);
    }
  };

  const handleSavePassword = async (e) => {
    e.preventDefault();
    if (passwordForm.next !== passwordForm.confirm) {
      toast({ message: 'New passwords do not match.', type: 'error' });
      return;
    }
    if (passwordForm.next.length < 8) {
      toast({ message: 'Password must be at least 8 characters.', type: 'warning' });
      return;
    }
    setSavingPassword(true);
    try {
      // await authService.changePassword(passwordForm);
      await new Promise((r) => setTimeout(r, 700));
      toast({ message: 'Password changed successfully.', type: 'success' });
      setPasswordForm({ current: '', next: '', confirm: '' });
    } catch {
      toast({ message: 'Failed to update password.', type: 'error' });
    } finally {
      setSavingPassword(false);
    }
  };

  const handleWeb3Toggle = async () => {
    setWeb3Loading(true);
    const next = !web3Enabled;
    try {
      await adminService.toggleBlockchain(next);
      setWeb3Enabled(next);
      toast({
        message: next
          ? '✅ Blockchain anchoring enabled — transactions will consume gas.'
          : '⛔ Blockchain anchoring disabled — system in simulation mode.',
        type: next ? 'success' : 'warning',
        duration: 5000,
      });
    } catch {
      toast({ message: 'Failed to update blockchain setting.', type: 'error' });
    } finally {
      setWeb3Loading(false);
>>>>>>> refs/remotes/origin/main
    }
  };

  return (
<<<<<<< HEAD
    <div className="space-y-8 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-sm text-gray-400 mt-1">Manage your account, preferences, and organization settings.</p>
      </div>

      <Tabs defaultValue="profile">
        <TabsList className="mb-6">
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
          <TabsTrigger value="appearance">Appearance</TabsTrigger>
          {isAdmin && <TabsTrigger value="organization">Organization</TabsTrigger>}
        </TabsList>

        <TabsContent value="profile" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <User className="h-5 w-5 text-indigo-400" />
                Profile
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center gap-4">
                <Avatar name={user?.full_name} size="lg" />
                <div>
                  <p className="text-base font-semibold text-white">{user?.full_name}</p>
                  <p className="text-sm text-gray-400">{user?.email}</p>
                  <Badge variant="primary" className="mt-1">{user?.role?.name}</Badge>
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input label="Full name" defaultValue={user?.full_name} />
                <Input label="Email" type="email" defaultValue={user?.email} />
              </div>
              <Button>Save changes</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="security" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <Shield className="h-5 w-5 text-indigo-400" />
                Security
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Input label="Current password" type="password" />
              <Input label="New password" type="password" />
              <Input label="Confirm new password" type="password" />
              <Button>Update password</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="appearance" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <Moon className="h-5 w-5 text-indigo-400" />
                Appearance
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-white">Interface theme</p>
                  <p className="text-xs text-gray-400">Choose between light and dark mode</p>
                </div>
                <div className="flex bg-gray-800 rounded-lg p-1">
                  <button
                    onClick={() => setTheme('light')}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors duration-200 ${theme === 'light' ? 'bg-gray-700 text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'}`}
                  >
                    <Sun className="h-4 w-4" />
                    Light
                  </button>
                  <button
                    onClick={() => setTheme('dark')}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors duration-200 ${theme === 'dark' ? 'bg-gray-700 text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'}`}
                  >
                    <Moon className="h-4 w-4" />
                    Dark
                  </button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {isAdmin && (
          <TabsContent value="organization" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white">
                  <Building className="h-5 w-5 text-indigo-400" />
                  Branding & Config
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {orgError && <p role="alert" className="text-sm text-red-400">{orgError}</p>}
                {orgSuccess && <p role="status" className="text-sm text-green-400">{orgSuccess}</p>}
                {orgLoading ? (
                  <p className="text-sm text-gray-400">Loading organization settings…</p>
                ) : (
                <form className="space-y-4" onSubmit={handleSaveOrganization}>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Input label="Organization Name" value={orgForm.name} onChange={(event) => updateOrgField('name', event.target.value)} placeholder="Your Company" required />
                  <Input label="ZKP Threshold" type="number" min="0" max="1" step="0.01" value={orgForm.zkp_threshold} onChange={(event) => updateOrgField('zkp_threshold', event.target.value)} required />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Input label="Primary Color (Hex)" value={orgForm.primary_color} onChange={(event) => updateOrgField('primary_color', event.target.value)} placeholder="#4F46E5" required />
                  <Input label="Logo URL" type="url" value={orgForm.logo_url} onChange={(event) => updateOrgField('logo_url', event.target.value)} placeholder="https://..." />
                </div>
                <Button type="submit" isLoading={orgSaving} disabled={!organization}>Save Settings</Button>
                </form>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <Key className="h-5 w-5 text-indigo-400" />
                    API Keys
                  </CardTitle>
                  <CardDescription className="text-gray-400 mt-1">Manage edge device API keys.</CardDescription>
                </div>
                <Button onClick={handleGenerateKey} disabled={isLoading} className="flex items-center gap-2">
                  <Plus className="h-4 w-4" /> Generate Key
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {newKey && (
                  <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-4 mb-4">
                    <p className="text-sm text-green-400 font-medium mb-1">Save this key now! It will not be shown again.</p>
                    <code className="text-white bg-gray-900 px-3 py-1 rounded block mt-2 text-sm">{newKey}</code>
                  </div>
                )}

                {apiKeys.length === 0 ? (
                  <p className="text-sm text-gray-400">No API keys generated yet.</p>
                ) : (
                  <div className="divide-y divide-gray-800">
                    {apiKeys.map(key => (
                      <div key={key.id} className="py-4 flex items-center justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-white font-medium text-sm">Key ID: {key.id}</span>
                            {key.is_revoked ? (
                              <Badge variant="destructive">Revoked</Badge>
                            ) : (
                              <Badge variant="success">Active</Badge>
                            )}
                          </div>
                          <p className="text-xs text-gray-500 mt-1">Scope: {key.scope} | Limit: {key.rate_limit}/min</p>
                        </div>
                        {!key.is_revoked && (
                          <Button variant="ghost" className="text-red-400 hover:text-red-300 hover:bg-red-500/10" onClick={() => handleRevokeKey(key.id)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
=======
    <motion.div
      className="space-y-6 max-w-2xl"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Header */}
      <motion.div variants={itemVariants}>
        <h1 className="text-2xl font-bold text-white tracking-tight">Settings</h1>
        <p className="text-sm text-gray-400 mt-1">Manage your account preferences and security.</p>
      </motion.div>

      {/* Profile */}
      <motion.div variants={itemVariants}>
        <Section title="Profile" description="Your personal information" icon={User}>
          {/* Avatar row */}
          <div className="flex items-center gap-4 p-4 rounded-xl bg-gray-800/30 border border-gray-700/40 mb-5">
            <Avatar name={user?.full_name} size="lg" />
            <div>
              <p className="text-sm font-semibold text-white">{user?.full_name || '—'}</p>
              <p className="text-xs text-gray-400 mt-0.5">{user?.email || '—'}</p>
              <Badge variant="primary" className="mt-1.5 text-[10px]">
                {userRole}
              </Badge>
            </div>
          </div>

          <form onSubmit={handleSaveProfile} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="Full name"
                value={profileForm.full_name}
                onChange={(e) => setProfileForm((p) => ({ ...p, full_name: e.target.value }))}
                required
              />
              <Input
                label="Email"
                type="email"
                value={profileForm.email}
                onChange={(e) => setProfileForm((p) => ({ ...p, email: e.target.value }))}
                required
              />
            </div>
            <Button type="submit" isLoading={savingProfile} className="gap-2">
              <Save className="h-4 w-4" />
              Save changes
            </Button>
          </form>
        </Section>
      </motion.div>

      {/* Security */}
      <motion.div variants={itemVariants}>
        <Section title="Security" description="Change your account password" icon={Shield}>
          <form onSubmit={handleSavePassword} className="space-y-4">
            <Input
              label="Current password"
              type="password"
              value={passwordForm.current}
              onChange={(e) => setPasswordForm((p) => ({ ...p, current: e.target.value }))}
              required
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="New password"
                type="password"
                value={passwordForm.next}
                onChange={(e) => setPasswordForm((p) => ({ ...p, next: e.target.value }))}
                required
              />
              <Input
                label="Confirm new password"
                type="password"
                value={passwordForm.confirm}
                onChange={(e) => setPasswordForm((p) => ({ ...p, confirm: e.target.value }))}
                required
              />
            </div>
            <Button type="submit" isLoading={savingPassword} className="gap-2">
              <Key className="h-4 w-4" />
              Update password
            </Button>
          </form>
        </Section>
      </motion.div>

      {/* Notifications (placeholder) */}
      <motion.div variants={itemVariants}>
        <Section title="Notifications" description="Manage alerts and email preferences" icon={Bell}>
          <div className="space-y-4">
            {[
              { label: 'Late arrival alerts', sub: 'Get notified when employees clock in late' },
              { label: 'Daily attendance digest', sub: 'Receive a summary at end of each workday' },
              { label: 'Ticket updates', sub: 'Be alerted when your support tickets change status' },
            ].map((item) => (
              <div key={item.label} className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-white">{item.label}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{item.sub}</p>
                </div>
                <Toggle enabled={false} onToggle={() => toast({ message: 'Notification preferences coming soon.', type: 'info' })} />
              </div>
            ))}
          </div>
        </Section>
      </motion.div>

      {/* SuperAdmin — Blockchain/Web3 Toggle */}
      {isSuperAdmin && (
        <motion.div variants={itemVariants}>
          <Section
            title="Blockchain Anchoring"
            description="SuperAdmin — Global Web3 audit trail control"
            icon={web3Enabled ? Zap : ZapOff}
          >
            <div className="rounded-xl border border-gray-700/50 bg-gray-800/20 divide-y divide-gray-800/50">
              {/* Status row */}
              <div className="flex items-center justify-between p-4">
                <div className="flex items-center gap-3">
                  <div className={`h-9 w-9 rounded-xl flex items-center justify-center ${web3Enabled ? 'bg-emerald-500/10' : 'bg-gray-700/50'}`}>
                    {web3Enabled
                      ? <Zap    className="h-5 w-5 text-emerald-400" />
                      : <ZapOff className="h-5 w-5 text-gray-500"    />}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">
                      {web3Fetching ? 'Checking status…' : web3Enabled ? 'Anchoring Active' : 'Simulation Mode'}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {web3Enabled
                        ? 'Each check-in is hashed and written to Ethereum.'
                        : 'No gas is consumed. Hashes are logged locally only.'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {!web3Fetching && (
                    <span className={`text-xs font-semibold px-2 py-1 rounded-full ${web3Enabled ? 'bg-emerald-500/15 text-emerald-400' : 'bg-gray-600/30 text-gray-400'}`}>
                      {web3Enabled ? 'LIVE' : 'OFF'}
                    </span>
                  )}
                  <Toggle
                    enabled={web3Enabled}
                    onToggle={handleWeb3Toggle}
                    loading={web3Loading}
                    disabled={web3Fetching}
                  />
                </div>
              </div>

              {/* Info row */}
              <div className="px-4 py-3 flex items-center justify-between">
                <p className="text-[11px] text-gray-500">
                  Configure <code className="text-gray-400 bg-gray-800 px-1 rounded">BLOCKCHAIN_PRIVATE_KEY</code> and <code className="text-gray-400 bg-gray-800 px-1 rounded">BLOCKCHAIN_URL</code> in your environment before enabling.
                </p>
                <button
                  onClick={fetchWeb3Status}
                  disabled={web3Fetching || web3Loading}
                  className="text-gray-500 hover:text-gray-300 transition-colors disabled:opacity-40 ml-3 shrink-0"
                  aria-label="Refresh status"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${web3Fetching ? 'animate-spin' : ''}`} />
                </button>
              </div>
            </div>
          </Section>
        </motion.div>
      )}
    </motion.div>
>>>>>>> refs/remotes/origin/main
  );
}
