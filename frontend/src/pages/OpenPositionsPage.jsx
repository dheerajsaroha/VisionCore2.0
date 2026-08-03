import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import { Briefcase, MapPin, Clock, Users } from 'lucide-react';
import { useAuthStore } from '../store/authStore';

export default function OpenPositionsPage() {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const { token } = useAuthStore();

  useEffect(() => {
    const loadPositions = async () => {
      try {
        const response = await fetch('/api/v1/recruitment/positions', {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (response.ok) {
          const data = await response.json();
          setPositions(Array.isArray(data) ? data : []);
        }
      } catch (err) {
        console.error('Failed to load positions:', err);
      } finally {
        setLoading(false);
      }
    };
    loadPositions();
  }, [token]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="xl" className="text-indigo-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Open Positions</h1>
        <p className="text-sm text-gray-400 mt-1">
          Browse and manage active job openings.
        </p>
      </div>

      {positions.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Briefcase className="h-12 w-12 text-gray-600 mx-auto mb-4" />
            <p className="text-gray-400">No open positions at this time.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {positions.map((pos) => (
            <Card key={pos.id} className="hover:border-indigo-500/30 transition-colors">
              <CardHeader>
                <CardTitle className="text-white text-lg">{pos.title}</CardTitle>
                <div className="flex items-center gap-2 text-sm text-gray-400">
                  <MapPin className="h-4 w-4" />
                  {pos.location || 'Remote'}
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4 text-sm text-gray-400">
                  <span className="flex items-center gap-1">
                    <Clock className="h-4 w-4" />
                    {pos.type || 'Full-time'}
                  </span>
                  <span className="flex items-center gap-1">
                    <Users className="h-4 w-4" />
                    {pos.applicants_count || 0} applicants
                  </span>
                </div>
                <Badge variant="success" className="mt-3">
                  {pos.status || 'Open'}
                </Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

