import React, { useState, useEffect } from 'react';
import { Shield, Users, Building2, CreditCard, Settings as SettingsIcon, AlertCircle, Search, Plus } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import '../components/ui/Avatar';
import { EmptyState } from '../components/ui/EmptyState';

export default function TenantAdminPage() {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 500);
    return () => clearTimeout(timer);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="xl" className="text-indigo-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Tenant Administration</h1>
          <p className="text-gray-400 mt-1">Manage organizations, subscriptions, and tenant settings</p>
        </div>
        <Button className="bg-indigo-600 hover:bg-indigo-500 text-white">
          <Plus className="h-4 w-4 mr-2" />
          Add Tenant
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4 bg-gray-900 border-gray-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-indigo-500/10 flex items-center justify-center">
              <Building2 className="h-5 w-5 text-indigo-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">12</p>
              <p className="text-xs text-gray-500">Active Organizations</p>
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-900 border-gray-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-green-500/10 flex items-center justify-center">
              <Users className="h-5 w-5 text-green-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">1,247</p>
              <p className="text-xs text-gray-500">Total Users</p>
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-900 border-gray-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-yellow-500/10 flex items-center justify-center">
              <CreditCard className="h-5 w-5 text-yellow-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">8</p>
              <p className="text-xs text-gray-500">Active Subscriptions</p>
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-900 border-gray-800">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-red-500/10 flex items-center justify-center">
              <AlertCircle className="h-5 w-5 text-red-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">3</p>
              <p className="text-xs text-gray-500">Pending Actions</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Tenant Table */}
      <Card className="bg-gray-900 border-gray-800">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Organization List</h2>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
              <input
                type="text"
                placeholder="Search tenants..."
                className="bg-gray-800 border border-gray-700 rounded-lg pl-10 pr-4 py-2 text-sm text-gray-200 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              />
            </div>
          </div>
        </div>

        <div className="p-6">
          <EmptyState
            icon={Building2}
            title="Tenant management interface"
            description="Organization provisioning, subscription management, and tenant settings are configured through the administration panel."
            action={<Button variant="outline" className="border-gray-700 text-gray-300">View Documentation</Button>}
          />
        </div>
      </Card>

      {/* Tenant Config */}
      <Card className="bg-gray-900 border-gray-800">
        <div className="p-4 border-b border-gray-800">
          <h2 className="text-lg font-semibold text-white">Tenant Configuration</h2>
        </div>
        <div className="p-6 space-y-4">
          <div className="flex items-center justify-between p-3 bg-gray-800 rounded-lg">
            <div className="flex items-center gap-3">
              <SettingsIcon className="h-5 w-5 text-gray-400" />
              <div>
                <p className="text-sm font-medium text-white">Default Authentication Policy</p>
                <p className="text-xs text-gray-500">SSO, MFA, password policies</p>
              </div>
            </div>
            <Badge variant="success" className="bg-green-500/10 text-green-400">Active</Badge>
          </div>
          <div className="flex items-center justify-between p-3 bg-gray-800 rounded-lg">
            <div className="flex items-center gap-3">
              <Shield className="h-5 w-5 text-gray-400" />
              <div>
                <p className="text-sm font-medium text-white">Data Isolation Rules</p>
                <p className="text-xs text-gray-500">Tenant-scoped data access</p>
              </div>
            </div>
            <Badge variant="success" className="bg-green-500/10 text-green-400">Active</Badge>
          </div>
          <div className="flex items-center justify-between p-3 bg-gray-800 rounded-lg">
            <div className="flex items-center gap-3">
              <CreditCard className="h-5 w-5 text-gray-400" />
              <div>
                <p className="text-sm font-medium text-white">Subscription & Billing</p>
                <p className="text-xs text-gray-500">Plan management, invoicing</p>
              </div>
            </div>
            <Badge variant="warning" className="bg-yellow-500/10 text-yellow-400">Needs Setup</Badge>
          </div>
        </div>
      </Card>
    </div>
  );
}

