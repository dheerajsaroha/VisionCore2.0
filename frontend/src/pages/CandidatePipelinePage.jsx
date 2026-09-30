import React, { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Spinner } from '../components/ui/Spinner';
import { EmptyState } from '../components/ui/EmptyState';
import { Users, FileText, Download, RefreshCw } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { offerLetterService } from '../services/offerLetterService';

// The backend stores these exact values on JobApplication.stage; using
// different labels here would silently drop every card into a fallback column.
const STAGES = [
  { key: 'applied', label: 'Applied', variant: 'default' },
  { key: 'screening', label: 'Screening', variant: 'warning' },
  { key: 'interview', label: 'Interview', variant: 'primary' },
  { key: 'offer', label: 'Offer', variant: 'success' },
  { key: 'hired', label: 'Hired', variant: 'success' },
  { key: 'rejected', label: 'Rejected', variant: 'danger' },
];

export default function CandidatePipelinePage() {
  // Applications, not candidates: only an application carries a pipeline
  // stage, so the candidates endpoint left every column but one empty.
  const [applications, setApplications] = useState([]);
  const [offers, setOffers] = useState({});
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState(null);
  const { token } = useAuthStore();

  const authHeaders = useCallback(
    () => ({ Authorization: `Bearer ${token}` }),
    [token]
  );

  const loadApplications = useCallback(async () => {
    try {
      const response = await fetch('/api/v1/recruitment/applications', {
        headers: authHeaders(),
      });
      if (!response.ok) throw new Error(`Failed to load pipeline (${response.status})`);
      const data = await response.json();
      setApplications(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [authHeaders]);

  // Offers are fetched separately so a failed call cannot blank the board.
  const loadOffers = useCallback(async () => {
    try {
      const response = await fetch('/api/v1/recruitment/offer-letters', {
        headers: authHeaders(),
      });
      if (!response.ok) return;
      const data = await response.json();
      const byCandidate = {};
      (Array.isArray(data) ? data : []).forEach((offer) => {
        byCandidate[offer.candidate_id] = offer;
      });
      setOffers(byCandidate);
    } catch (err) {
      console.error('Failed to load offer letters:', err);
    }
  }, [authHeaders]);

  useEffect(() => {
    setLoading(true);
    loadApplications();
    loadOffers();
  }, [loadApplications, loadOffers]);

  const moveStage = async (application, stage) => {
    if (stage === application.stage) return;
    setBusyId(application.id);
    const previous = application.stage;
    // Optimistic update so the card lands in the right column immediately.
    setApplications((current) =>
      current.map((a) => (a.id === application.id ? { ...a, stage } : a))
    );
    try {
      const response = await fetch(
        `/api/v1/recruitment/applications/${application.id}/stage`,
        {
          method: 'PATCH',
          headers: { ...authHeaders(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ stage }),
        }
      );
      if (!response.ok) throw new Error('Could not move the candidate');
      setError(null);
    } catch (err) {
      setApplications((current) =>
        current.map((a) => (a.id === application.id ? { ...a, stage: previous } : a))
      );
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const createOffer = async (application) => {
    setBusyId(application.id);
    try {
      await offerLetterService.createOffer(
        {
          candidate_id: application.candidate_id,
          application_id: application.id,
          designation: application.job_title,
          base_pay: 0,
        },
        token
      );
      await loadOffers();
      setError(null);
    } catch (err) {
      setError(
        err.message ||
          'Could not create the offer. Compensation details are required.'
      );
    } finally {
      setBusyId(null);
    }
  };

  const generateOffer = async (offer) => {
    setBusyId(offer.id);
    try {
      await offerLetterService.generate(offer.id, token);
      await loadOffers();
      setError(null);
    } catch (err) {
      setError(err.message || 'Could not generate the offer letter.');
    } finally {
      setBusyId(null);
    }
  };

  const downloadOffer = (offer) => {
    offerLetterService.downloadUrl(offer.id, token);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="xl" className="text-indigo-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Candidate Pipeline</h1>
          <p className="text-sm text-gray-400 mt-1">
            Move candidates through the hiring stages and issue offer letters.
          </p>
        </div>
        <Button
          variant="ghost"
          onClick={() => {
            setLoading(true);
            loadApplications();
            loadOffers();
          }}
          aria-label="Refresh pipeline"
        >
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300"
        >
          {error}
        </div>
      )}

      {applications.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <EmptyState
              icon={Users}
              title="No candidates in the pipeline"
              description="Applications submitted for your open roles will appear here."
            />
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {STAGES.map((stage) => {
            const stageApplications = applications.filter(
              (a) => (a.stage || 'applied').toLowerCase() === stage.key
            );
            return (
              <Card key={stage.key} className="flex flex-col">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-400">
                    {stage.label}
                  </CardTitle>
                  <p className="text-2xl font-bold text-white">
                    {stageApplications.length}
                  </p>
                </CardHeader>
                <CardContent className="space-y-3 flex-1">
                  {stageApplications.length === 0 ? (
                    <p className="text-xs text-gray-500">No candidates</p>
                  ) : (
                    stageApplications.map((application) => {
                      const offer = offers[application.candidate_id];
                      const busy = busyId === application.id;
                      return (
                        <div
                          key={application.id}
                          className="rounded-lg border border-gray-700 bg-gray-800/40 p-3 space-y-2"
                        >
                          <p className="text-sm text-gray-100 font-medium truncate">
                            {application.candidate_name}
                          </p>
                          <p className="text-xs text-gray-400 truncate">
                            {application.job_title}
                          </p>
                          {application.rating != null && (
                            <Badge variant="warning">Rated {application.rating}/5</Badge>
                          )}

                          <select
                            value={application.stage || 'applied'}
                            onChange={(e) => moveStage(application, e.target.value)}
                            disabled={busy}
                            aria-label={`Stage for ${application.candidate_name}`}
                            className="w-full rounded-md border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-gray-200 disabled:opacity-50"
                          >
                            {STAGES.map((s) => (
                              <option key={s.key} value={s.key}>
                                {s.label}
                              </option>
                            ))}
                          </select>

                          {stage.key === 'offer' && (
                            <div className="space-y-1 pt-1">
                              {offer ? (
                                <>
                                  <div className="flex items-center gap-1">
                                    <Badge variant={offer.status === 'accepted' ? 'success' : 'info'}>
                                      {offer.status}
                                    </Badge>
                                  </div>
                                  {offer.download_url ? (
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="w-full justify-start"
                                      onClick={() => downloadOffer(offer)}
                                    >
                                      <Download className="h-3 w-3 mr-1" />
                                      Download
                                    </Button>
                                  ) : (
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      className="w-full justify-start"
                                      onClick={() => generateOffer(offer)}
                                      disabled={busy || offer.id == null}
                                    >
                                      <FileText className="h-3 w-3 mr-1" />
                                      Generate PDF
                                    </Button>
                                  )}
                                </>
                              ) : (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="w-full justify-start"
                                  onClick={() => createOffer(application)}
                                  disabled={busy}
                                >
                                  <FileText className="h-3 w-3 mr-1" />
                                  Create offer
                                </Button>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
