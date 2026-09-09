import React, { useState, useEffect } from 'react';
import {
  Users,
  UserCheck,
  UserX,
  Shield,
  Clock,
  RefreshCw,
  Search,
  Filter,
  Activity,
  History
} from 'lucide-react';
import api from '../services/apiClient';

export default function IdentityDirectoryPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [timelineUser, setTimelineUser] = useState(null);
  const [timelineEvents, setTimelineEvents] = useState([]);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const res = await api.get('/users/');
      setUsers(Array.isArray(res.data) ? res.data : (res.data.users || []));
    } catch (err) {
      console.error('Failed to load users:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleActivate = async (userId) => {
    try {
      await api.post(`/identity/${userId}/activate`);
      fetchUsers();
    } catch (err) {
      alert(err.response?.data?.detail || 'Activation failed');
    }
  };

  const handleSuspend = async (userId) => {
    const reason = prompt('Reason for suspension:');
    if (!reason) return;
    try {
      await api.post(`/identity/${userId}/suspend`, { reason });
      fetchUsers();
    } catch (err) {
      alert(err.response?.data?.detail || 'Suspension failed');
    }
  };

  const openTimeline = async (u) => {
    setTimelineUser(u);
    try {
      const res = await api.get(`/identity/${u.id}/timeline`);
      setTimelineEvents(res.data);
    } catch (err) {
      setTimelineEvents([]);
    }
  };

  const filteredUsers = users.filter(
    (u) =>
      u.full_name?.toLowerCase().includes(search.toLowerCase()) ||
      u.email?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass p-6 rounded-2xl border border-gray-800">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Users className="h-7 w-7 text-indigo-400" />
            Enterprise Identity Directory
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Canonical lifecycle management for Employees, Contractors, Service Accounts, Vendors, and Alumni.
          </p>
        </div>
        <button
          onClick={fetchUsers}
          className="p-2.5 rounded-xl bg-gray-800 text-gray-300 hover:text-white transition self-start sm:self-auto"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      <div className="flex items-center gap-3 glass p-4 rounded-xl border border-gray-800">
        <Search className="h-4 w-4 text-gray-500" />
        <input
          type="text"
          placeholder="Search identities by name or email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="bg-transparent border-none outline-none text-sm text-gray-200 placeholder:text-gray-500 w-full"
        />
      </div>

      <div className="glass rounded-2xl border border-gray-800 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-300">
            <thead className="bg-gray-900/80 text-xs uppercase font-semibold text-gray-400 border-b border-gray-800">
              <tr>
                <th className="px-6 py-4">Identity</th>
                <th className="px-6 py-4">Role / Scope</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {filteredUsers.map((u) => (
                <tr key={u.id} className="hover:bg-gray-900/40 transition">
                  <td className="px-6 py-4 font-medium text-white flex items-center gap-3">
                    <div className="h-9 w-9 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center font-bold">
                      {u.full_name?.charAt(0) || 'U'}
                    </div>
                    <div>
                      <p className="font-semibold text-white">{u.full_name}</p>
                      <p className="text-xs text-gray-400">{u.email}</p>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col">
                      <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-gray-800 text-gray-300 w-fit">
                        {u.role?.name || 'User'}
                      </span>
                      {(u.dept_name || u.org_name) && (
                        <span className="text-xs text-gray-400 mt-1">
                          {u.dept_name || 'General'}{u.org_name ? ` • ${u.org_name}` : ''}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                        u.is_active
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : 'bg-red-500/10 text-red-400 border border-red-500/20'
                      }`}
                    >
                      {u.is_active ? 'Active' : 'Suspended'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right space-x-2">
                    <button
                      onClick={() => openTimeline(u)}
                      className="p-1.5 rounded-lg bg-gray-800 text-gray-300 hover:text-white hover:bg-gray-700 text-xs inline-flex items-center gap-1"
                      title="View Timeline"
                    >
                      <History className="h-3.5 w-3.5" />
                      Timeline
                    </button>
                    {u.is_active ? (
                      <button
                        onClick={() => handleSuspend(u.id)}
                        className="px-2.5 py-1 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 text-xs font-medium"
                      >
                        Suspend
                      </button>
                    ) : (
                      <button
                        onClick={() => handleActivate(u.id)}
                        className="px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 text-xs font-medium"
                      >
                        Activate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {timelineUser && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass w-full max-w-lg rounded-2xl border border-gray-800 p-6 space-y-4 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-gray-800 pb-3">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <History className="h-5 w-5 text-indigo-400" />
                Identity Timeline: {timelineUser.full_name}
              </h3>
              <button onClick={() => setTimelineUser(null)} className="text-gray-400 hover:text-white">
                ✕
              </button>
            </div>

            <div className="space-y-3 pt-2">
              {timelineEvents.length > 0 ? (
                timelineEvents.map((evt) => (
                  <div key={evt.id} className="p-3 bg-gray-900/60 rounded-xl border border-gray-800 text-xs space-y-1">
                    <div className="flex items-center justify-between text-indigo-400 font-bold">
                      <span>{evt.event_type}</span>
                      <span className="text-gray-500">{new Date(evt.created_at).toLocaleString()}</span>
                    </div>
                    {evt.reason && <p className="text-gray-300">Reason: {evt.reason}</p>}
                  </div>
                ))
              ) : (
                <p className="text-sm text-gray-500 text-center py-4">No recorded lifecycle events yet.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
