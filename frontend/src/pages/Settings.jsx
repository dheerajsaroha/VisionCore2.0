import React, { useState, useEffect } from 'react';
import { useAuthStore } from '../store/authStore';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { Avatar } from '../components/ui/Avatar';
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
    }
  };

  return (
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
  );
}
