import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { authService } from '../services/authService';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const submit = async (event) => {
    event.preventDefault(); setLoading(true);
    try { setResult(await authService.forgotPassword(email)); } finally { setLoading(false); }
  };
  const data = result?.data;
  return <main className="min-h-screen bg-gray-950 flex items-center justify-center px-4"><form onSubmit={submit} className="w-full max-w-md rounded-2xl border border-gray-800 bg-gray-900 p-8">
    <h1 className="text-2xl font-bold text-white">Reset your password</h1><p className="mt-2 text-sm text-gray-400">Enter your email and we’ll send reset instructions if an account exists.</p>
    <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-5 w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white" placeholder="you@company.com" />
    <button disabled={loading} className="mt-4 w-full rounded-lg bg-indigo-600 px-4 py-2 font-semibold text-white disabled:opacity-50">{loading ? 'Sending…' : 'Send reset link'}</button>
    {data && <div className="mt-4 text-sm text-emerald-300">{data.detail}{data.reset_url && <a className="mt-2 block underline" href={data.reset_url}>Open development reset link</a>}</div>}
    <Link className="mt-5 block text-sm text-indigo-400" to="/login">Back to sign in</Link>
  </form></main>;
}
