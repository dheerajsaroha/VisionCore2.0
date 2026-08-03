import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, UserPlus, Camera, X, Mail, Shield, Building, MoreVertical, Edit, Trash2, UserX, UserCheck, ChevronLeft, ChevronRight, Hash, Clock } from 'lucide-react';
import Webcam from 'react-webcam';
import { userService } from '../services/userService';
import { departmentService } from '../services/departmentService';
import { useAuthStore } from '../store/authStore';
import { Card, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { Spinner } from '../components/ui/Spinner';
import { EmptyState } from '../components/ui/EmptyState';
import { Avatar } from '../components/ui/Avatar';
import { cn, formatDate } from '../lib/utils';

const PAGE_SIZE = 20;

export default function UserManagement() {
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const [showAdd, setShowAdd] = useState(false);
  const [editUser, setEditUser] = useState(null);
  const [selectedUser, setSelectedUser] = useState(null);
  const [enrollUser, setEnrollUser] = useState(null);
  const [actionMenu, setActionMenu] = useState(null);

  const [departments, setDepartments] = useState([]);
  const [shifts, setShifts] = useState([]);

  const webcamRef = useRef(null);
  const menuRef = useRef(null);
  const { user: currentUser } = useAuthStore();
  const isAdmin = ['Admin', 'Manager'].includes(currentUser?.role?.name);

  const [form, setForm] = useState({ full_name: '', email: '', password: '', role: 'Employee', organization: '' });
  const [editForm, setEditForm] = useState({ full_name: '', role: '', dept_id: '', shift_id: '', is_active: 1 });

  useEffect(() => { fetchUsers(); }, [page, roleFilter, statusFilter]);
  useEffect(() => { fetchMeta(); }, []);
  useEffect(() => {
    const handle = (e) => { if (menuRef.current && !menuRef.current.contains(e.target)) setActionMenu(null); };
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const params = { skip: page * PAGE_SIZE, limit: PAGE_SIZE };
      if (roleFilter) params.role = roleFilter;
      if (statusFilter !== '') params.is_active = Number(statusFilter);
      if (search) params.search = search;
      const res = await userService.getUsers(params);
      setUsers(res.data?.users || []);
      setTotal(res.data?.total || 0);
    } finally { setLoading(false); }
  };

  const fetchMeta = async () => {
    try {
      const [d, s] = await Promise.all([departmentService.getDepartments(), departmentService.getShifts()]);
      setDepartments(d.data || []);
      setShifts(s.data || []);
    } catch {}
  };

  const handleSearch = (e) => { e.preventDefault(); setPage(0); fetchUsers(); };

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await userService.createUser(form);
      setShowAdd(false);
      setForm({ full_name: '', email: '', password: '', role: 'Employee', organization: '' });
      fetchUsers();
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const handleEdit = async (e) => {
    e.preventDefault();
    try {
      const payload = {};
      if (editForm.full_name) payload.full_name = editForm.full_name;
      if (editForm.role) payload.role = editForm.role;
      if (editForm.dept_id) payload.dept_id = Number(editForm.dept_id);
      if (editForm.shift_id) payload.shift_id = Number(editForm.shift_id);
      if (editForm.is_active !== undefined) payload.is_active = Number(editForm.is_active);
      await userService.updateUser(editUser.id, payload);
      setEditUser(null);
      fetchUsers();
    } catch (err) { alert(err.response?.data?.detail || 'Update failed'); }
  };

  const handleDelete = async (u) => {
    if (!confirm(`Remove ${u.full_name}? This will deactivate and archive their account.`)) return;
    try { await userService.deleteUser(u.id); fetchUsers(); setSelectedUser(null); }
    catch (err) { alert(err.response?.data?.detail || 'Delete failed'); }
  };

  const handleToggleActive = async (u) => {
    try {
      await userService.updateUser(u.id, { is_active: u.is_active ? 0 : 1 });
      fetchUsers();
      if (selectedUser?.id === u.id) setSelectedUser({ ...u, is_active: u.is_active ? 0 : 1 });
    } catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const openEdit = (u) => {
    setEditForm({ full_name: u.full_name, role: u.role?.name || 'Employee', dept_id: u.dept_id || '', shift_id: u.shift_id || '', is_active: u.is_active });
    setEditUser(u);
    setActionMenu(null);
  };

  const handleEnroll = async () => {
    if (!webcamRef.current || !enrollUser) return;
    try {
      const mockEmbedding = Array.from({ length: 128 }, () => Math.random());
      await userService.enrollFace(enrollUser.id, mockEmbedding);
      setEnrollUser(null); fetchUsers();
    } catch (err) { alert(err.response?.data?.detail || 'Enrollment failed'); }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const roleBadgeVariant = (name) => {
    if (name === 'Admin') return 'danger';
    if (name === 'Manager') return 'warning';
    return 'primary';
  };

  return (
    <motion.div className="space-y-6 lg:space-y-8" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">Employee Directory</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{total} employees in your organization</p>
        </div>
        {isAdmin && (
          <Button onClick={() => setShowAdd(true)} className="shadow-lg shadow-primary-500/30 hover:scale-105 transition-transform">
            <UserPlus className="mr-2 h-5 w-5" /> Add Employee
          </Button>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <form onSubmit={handleSearch} className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input type="text" placeholder="Search name, email, or ID..." value={search} onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-11 pr-4 py-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 outline-none transition-all shadow-sm" />
        </form>
        <select value={roleFilter} onChange={(e) => { setRoleFilter(e.target.value); setPage(0); }}
          className="px-3 py-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-700 dark:text-slate-300 outline-none">
          <option value="">All Roles</option>
          <option value="Admin">Admin</option>
          <option value="Manager">Manager</option>
          <option value="Employee">Employee</option>
        </select>
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
          className="px-3 py-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-sm text-slate-700 dark:text-slate-300 outline-none">
          <option value="">All Status</option>
          <option value="1">Active</option>
          <option value="0">Inactive</option>
        </select>
      </div>

      {/* Table */}
      <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.1 }}>
        <Card className="overflow-hidden border-0 shadow-xl shadow-slate-200/50 dark:shadow-none">
          <CardContent className="p-0">
            {loading ? (
              <div className="flex items-center justify-center py-32"><Spinner size="xl" className="text-primary-500" /></div>
            ) : users.length === 0 ? (
              <EmptyState icon={Shield} title="No employees found" description="Try adjusting your filters or add a new employee."
                actionText="Add Employee" onAction={() => setShowAdd(true)} />
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-50/80 dark:bg-slate-800/50 border-b border-slate-100 dark:border-slate-800">
                        <th className="px-6 py-4 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Employee</th>
                        <th className="px-6 py-4 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">ID</th>
                        <th className="px-6 py-4 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Role</th>
                        <th className="px-6 py-4 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Status</th>
                        <th className="px-6 py-4 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Joined</th>
                        {isAdmin && <th className="px-6 py-4 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider text-right">Actions</th>}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 bg-white dark:bg-transparent">
                      {users.map((u) => (
                        <tr key={u.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors group cursor-pointer"
                          onClick={() => setSelectedUser(u)}>
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-4">
                              <Avatar name={u.full_name} size="md" className="shadow-sm border border-slate-100 dark:border-slate-800" />
                              <div>
                                <p className="text-sm font-semibold text-slate-900 dark:text-white group-hover:text-primary-600 dark:group-hover:text-primary-400 transition-colors">{u.full_name}</p>
                                <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1 mt-0.5"><Mail className="h-3 w-3" /> {u.email}</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4"><span className="text-xs font-mono text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded">{u.employee_id}</span></td>
                          <td className="px-6 py-4"><Badge variant={roleBadgeVariant(u.role?.name)} className="font-medium px-2.5 py-1">{u.role?.name}</Badge></td>
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-2">
                              <span className={cn('h-2.5 w-2.5 rounded-full shadow-sm', u.is_active ? 'bg-emerald-500 shadow-emerald-500/20' : 'bg-slate-300 dark:bg-slate-600')} />
                              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{u.is_active ? 'Active' : 'Inactive'}</span>
                            </div>
                          </td>
                          <td className="px-6 py-4 text-sm text-slate-500 dark:text-slate-400">{formatDate(u.created_at)}</td>
                          {isAdmin && (
                            <td className="px-6 py-4 text-right relative" onClick={(e) => e.stopPropagation()}>
                              <button onClick={() => setActionMenu(actionMenu === u.id ? null : u.id)}
                                className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
                                <MoreVertical className="h-4 w-4 text-slate-500" />
                              </button>
                              {actionMenu === u.id && (
                                <div ref={menuRef} className="absolute right-6 top-12 z-30 w-48 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-xl py-1 animate-fade-in">
                                  <button onClick={() => openEdit(u)} className="w-full text-left px-4 py-2.5 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 flex items-center gap-2"><Edit className="h-4 w-4" /> Edit Profile</button>
                                  <button onClick={() => { handleToggleActive(u); setActionMenu(null); }} className="w-full text-left px-4 py-2.5 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 flex items-center gap-2">
                                    {u.is_active ? <><UserX className="h-4 w-4" /> Suspend</> : <><UserCheck className="h-4 w-4" /> Activate</>}
                                  </button>
                                  <button onClick={() => { setEnrollUser(u); setActionMenu(null); }} className="w-full text-left px-4 py-2.5 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 flex items-center gap-2"><Camera className="h-4 w-4" /> Enroll Face</button>
                                  <hr className="my-1 border-slate-100 dark:border-slate-800" />
                                  <button onClick={() => { handleDelete(u); setActionMenu(null); }} className="w-full text-left px-4 py-2.5 text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 flex items-center gap-2"><Trash2 className="h-4 w-4" /> Remove</button>
                                </div>
                              )}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100 dark:border-slate-800">
                    <p className="text-sm text-slate-500 dark:text-slate-400">Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}</p>
                    <div className="flex items-center gap-2">
                      <button disabled={page === 0} onClick={() => setPage(page - 1)} className="p-2 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"><ChevronLeft className="h-4 w-4" /></button>
                      <span className="text-sm font-medium text-slate-700 dark:text-slate-300 px-2">{page + 1} / {totalPages}</span>
                      <button disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)} className="p-2 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"><ChevronRight className="h-4 w-4" /></button>
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </motion.div>

      {/* Employee Profile Drawer */}
      <AnimatePresence>
        {selectedUser && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 bg-gray-950/50 backdrop-blur-sm z-40" onClick={() => setSelectedUser(null)} />
            <motion.div initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }} transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="fixed right-0 top-0 h-full w-full max-w-md bg-white dark:bg-slate-900 shadow-2xl z-50 overflow-y-auto border-l border-slate-200 dark:border-slate-800">
              <div className="p-6">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-lg font-bold text-slate-900 dark:text-white">Employee Profile</h2>
                  <button onClick={() => setSelectedUser(null)} className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"><X className="h-5 w-5 text-slate-500" /></button>
                </div>
                <div className="flex flex-col items-center text-center mb-8">
                  <Avatar name={selectedUser.full_name} size="xl" className="mb-4 shadow-lg border-2 border-slate-100 dark:border-slate-800" />
                  <h3 className="text-xl font-bold text-slate-900 dark:text-white">{selectedUser.full_name}</h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400">{selectedUser.email}</p>
                  <div className="flex items-center gap-2 mt-3">
                    <Badge variant={roleBadgeVariant(selectedUser.role?.name)}>{selectedUser.role?.name}</Badge>
                    <Badge variant={selectedUser.is_active ? 'success' : 'default'}>{selectedUser.is_active ? 'Active' : 'Inactive'}</Badge>
                  </div>
                </div>
                <div className="space-y-4">
                  {[
                    { icon: Hash, label: 'Employee ID', value: selectedUser.employee_id },
                    { icon: Building, label: 'Organization', value: selectedUser.org_id?.slice(0, 8) + '...' },
                    { icon: Clock, label: 'Joined', value: formatDate(selectedUser.created_at) },
                  ].map((item) => (
                    <div key={item.label} className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                      <div className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800"><item.icon className="h-4 w-4 text-slate-500 dark:text-slate-400" /></div>
                      <div><p className="text-xs text-slate-500 dark:text-slate-400">{item.label}</p><p className="text-sm font-medium text-slate-900 dark:text-white">{item.value}</p></div>
                    </div>
                  ))}
                </div>
                {isAdmin && (
                  <div className="flex gap-3 mt-8 pt-6 border-t border-slate-100 dark:border-slate-800">
                    <Button variant="ghost" className="flex-1" onClick={() => { openEdit(selectedUser); setSelectedUser(null); }}><Edit className="mr-2 h-4 w-4" /> Edit</Button>
                    <Button variant="ghost" className="flex-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10" onClick={() => handleDelete(selectedUser)}><Trash2 className="mr-2 h-4 w-4" /> Remove</Button>
                  </div>
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Add Employee Modal */}
      <AnimatePresence>
        {showAdd && (
          <Modal isOpen={showAdd} onClose={() => setShowAdd(false)} title="Add New Employee" description="Create a new account for organization access.">
            <form onSubmit={handleCreate} className="space-y-4 mt-2">
              <Input label="Full Name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required className="bg-slate-50 dark:bg-slate-900/50" />
              <Input label="Email Address" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required className="bg-slate-50 dark:bg-slate-900/50" />
              <Input label="Temporary Password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required className="bg-slate-50 dark:bg-slate-900/50" />
              <div className="grid grid-cols-2 gap-4">
                <Select label="Role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}
                  options={[{ value: 'Employee', label: 'Employee' }, { value: 'Manager', label: 'Manager' }, { value: 'Admin', label: 'Admin' }]} />
                <Input label="Organization" value={form.organization} onChange={(e) => setForm({ ...form, organization: e.target.value })} required className="bg-slate-50 dark:bg-slate-900/50" />
              </div>
              <div className="flex gap-3 pt-6 border-t border-slate-100 dark:border-slate-800 mt-6">
                <Button type="button" variant="ghost" className="flex-1" onClick={() => setShowAdd(false)}>Cancel</Button>
                <Button type="submit" className="flex-1 shadow-lg shadow-primary-500/20">Provision Account</Button>
              </div>
            </form>
          </Modal>
        )}
      </AnimatePresence>

      {/* Edit Employee Modal */}
      <AnimatePresence>
        {editUser && (
          <Modal isOpen={!!editUser} onClose={() => setEditUser(null)} title={`Edit ${editUser.full_name}`} description="Update employee profile details.">
            <form onSubmit={handleEdit} className="space-y-4 mt-2">
              <Input label="Full Name" value={editForm.full_name} onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })} className="bg-slate-50 dark:bg-slate-900/50" />
              <Select label="Role" value={editForm.role} onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                options={[{ value: 'Employee', label: 'Employee' }, { value: 'Manager', label: 'Manager' }, { value: 'Admin', label: 'Admin' }]} />
              <div className="grid grid-cols-2 gap-4">
                <Select label="Department" value={editForm.dept_id} onChange={(e) => setEditForm({ ...editForm, dept_id: e.target.value })} placeholder="Select dept"
                  options={departments.map((d) => ({ value: d.id, label: d.name }))} />
                <Select label="Shift" value={editForm.shift_id} onChange={(e) => setEditForm({ ...editForm, shift_id: e.target.value })} placeholder="Select shift"
                  options={shifts.map((s) => ({ value: s.id, label: s.shift_name }))} />
              </div>
              <Select label="Status" value={editForm.is_active} onChange={(e) => setEditForm({ ...editForm, is_active: Number(e.target.value) })}
                options={[{ value: 1, label: 'Active' }, { value: 0, label: 'Suspended' }]} />
              <div className="flex gap-3 pt-6 border-t border-slate-100 dark:border-slate-800 mt-6">
                <Button type="button" variant="ghost" className="flex-1" onClick={() => setEditUser(null)}>Cancel</Button>
                <Button type="submit" className="flex-1 shadow-lg shadow-primary-500/20">Save Changes</Button>
              </div>
            </form>
          </Modal>
        )}
      </AnimatePresence>

      {/* Enroll Face Modal */}
      <AnimatePresence>
        {enrollUser && (
          <Modal isOpen={!!enrollUser} onClose={() => setEnrollUser(null)} title="Biometric Enrollment" description={`Register neural face template for ${enrollUser?.full_name}`}>
            <div className="space-y-6 mt-4">
              <div className="relative aspect-video bg-black/80 rounded-2xl overflow-hidden shadow-inner">
                <Webcam audio={false} ref={webcamRef} screenshotFormat="image/jpeg" className="w-full h-full object-cover" />
                <div className="absolute inset-0 border-[3px] border-emerald-500/30 rounded-2xl pointer-events-none" />
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                  <div className="w-40 h-56 border-2 border-emerald-400/50 border-dashed rounded-full shadow-[0_0_0_9999px_rgba(0,0,0,0.6)]" />
                </div>
              </div>
              <div className="bg-emerald-50 dark:bg-emerald-900/20 p-4 rounded-xl border border-emerald-100 dark:border-emerald-800/30">
                <p className="text-sm text-emerald-700 dark:text-emerald-400 flex items-start gap-2">
                  <Shield className="h-5 w-5 shrink-0" /> Ensure the face is clearly visible, well-lit, and centered within the oval.
                </p>
              </div>
              <div className="flex gap-3 pt-4 border-t border-slate-100 dark:border-slate-800">
                <Button variant="ghost" className="flex-1" onClick={() => setEnrollUser(null)}>Cancel</Button>
                <Button className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-500/20" onClick={handleEnroll}>Extract & Save Template</Button>
              </div>
            </div>
          </Modal>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
