import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';

export default function AccessDeniedPage() {
  return (
    <main className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <section className="max-w-md text-center rounded-2xl border border-gray-800 bg-gray-900 p-8 shadow-xl">
        <ShieldAlert className="mx-auto h-12 w-12 text-amber-400" />
        <h1 className="mt-4 text-2xl font-bold text-white">Access denied</h1>
        <p className="mt-2 text-sm text-gray-400">Your account is signed in, but does not have access to this resource.</p>
        <Link to="/dashboard" className="mt-6 inline-flex rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">
          Return to dashboard
        </Link>
      </section>
    </main>
  );
}
