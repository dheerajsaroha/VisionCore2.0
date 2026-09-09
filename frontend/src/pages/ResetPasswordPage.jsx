import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { authService } from '../services/authService';

export default function ResetPasswordPage() {
  const [params] = useSearchParams(); const navigate = useNavigate();
  const [password, setPassword] = useState(''); const [message, setMessage] = useState(''); const [loading, setLoading] = useState(false);
  const submit = async (event) => { event.preventDefault(); setLoading(true); setMessage(''); try { await authService.resetPassword(params.get('token'), password); navigate('/login', { state: { reset: true } }); } catch (error) { setMessage(error.response?.data?.detail || 'Unable to reset password.'); } finally { setLoading(false); } };
  if (!params.get('token')) return <main className="min-h-screen bg-gray-950 flex items-center justify-center text-gray-200">Invalid reset link. <Link className="ml-2 text-indigo-400" to="/forgot-password">Request another</Link></main>;
  return <main className="min-h-screen bg-gray-950 flex items-center justify-center px-4"><form onSubmit={submit} className="w-full max-w-md rounded-2xl border border-gray-800 bg-gray-900 p-8"><h1 className="text-2xl font-bold text-white">Choose a new password</h1><input required minLength="8" type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-5 w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white" placeholder="New password" /><button disabled={loading} className="mt-4 w-full rounded-lg bg-indigo-600 px-4 py-2 font-semibold text-white disabled:opacity-50">{loading ? 'Resetting…' : 'Reset password'}</button>{message && <p className="mt-4 text-sm text-red-300">{message}</p>}</form></main>;
}
