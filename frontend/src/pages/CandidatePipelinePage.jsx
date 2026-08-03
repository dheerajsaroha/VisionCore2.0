import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { Users, CheckCircle, Clock, XCircle } from 'lucide-react';
import { useAuthStore } from '../store/authStore';

const STAGE_COLORS = {
  new: 'default',
  screening: 'warning',
  interview: 'primary',
  offer: 'success',
  hired: 'success',
  rejected: 'destructive',
};

export default function CandidatePipelinePage() {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const { token } = useAuthStore();

  useEffect(() => {
    const loadCandidates = async () => {
      try {
        const response = await fetch('/api/v1/recruitment/candidates', {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (response.ok) {
          const data = await response.json();
          setCandidates(Array.isArray(data) ? data : []);
        }
      } catch (err) {
        console.error('Failed to load candidates:', err);
      } finally {
        setLoading(false);
      }
    };
    loadCandidates();
  }, [token]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="xl" className="text-indigo-500" />
      </div>
    );
  }

  const stages = ['new', 'screening', 'interview', 'offer', 'hired', 'rejected'];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Candidate Pipeline</h1>
        <p className="text-sm text-gray-400 mt-1">
          Track candidates through the recruitment pipeline.
        </p>
      </div>

      {candidates.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Users className="h-12 w-12 text-gray-600 mx-auto mb-4" />
            <p className="text-gray-400">No candidates in the pipeline.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {stages.map((stage) => {
            const stageCandidates = candidates.filter(
              (c) => (c.stage || 'new').toLowerCase() === stage
            );
            return (
              <Card key={stage}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-400 capitalize">
                    {stage}
                  </CardTitle>
                  <p className="text-2xl font-bold text-white">
                    {stageCandidates.length}
                  </p>
                </CardHeader>
                <CardContent className="space-y-2">
                  {stageCandidates.slice(0, 3).map((c) => (
                    <div
                      key={c.id}
                      className="text-sm text-gray-300 truncate py-1"
                    >
                      {c.name || `Candidate #${c.id}`}
                    </div>
                  ))}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

