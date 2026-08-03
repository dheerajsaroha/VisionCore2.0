import React, { useState, useEffect } from 'react';
import aiService from '../services/aiService';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Modal } from '../components/ui/Modal';
import { EmptyState } from '../components/ui/EmptyState';
import { Badge } from '../components/ui/Badge';

const CAPABILITIES = ['chat', 'completion', 'embedding', 'image_generation', 'code_generation', 'function_calling'];

const ModelManagerPage = () => {
  const [models, setModels] = useState([]);
  const [providers, setProviders] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [newModel, setNewModel] = useState({
    name: '', provider_id: '', capabilities: ['chat'],
    context_window: 4096, max_output_tokens: 2048,
    cost_per_1k_input_tokens: 0, cost_per_1k_output_tokens: 0,
  });

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [modelsData, providersData] = await Promise.all([
        aiService.getModels(), aiService.getProviders(),
      ]);
      setModels(modelsData || []);
      setProviders(providersData || []);
    } catch (err) { setError(err.message); }
    finally { setIsLoading(false); }
  };

  const handleRegister = async () => {
    if (!newModel.name.trim() || !newModel.provider_id) return;
    try {
      await aiService.registerModel(newModel);
      setShowRegisterModal(false);
      setNewModel({ name: '', provider_id: '', capabilities: ['chat'], context_window: 4096, max_output_tokens: 2048, cost_per_1k_input_tokens: 0, cost_per_1k_output_tokens: 0 });
      await loadData();
    } catch (err) { setError(err.message); }
  };

  const toggleCapability = (cap) => {
    setNewModel(prev => ({
      ...prev,
      capabilities: prev.capabilities.includes(cap)
        ? prev.capabilities.filter(c => c !== cap)
        : [...prev.capabilities, cap],
    }));
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white">Model Manager</h1>
          <p className="text-gray-400 mt-1">Register and manage AI models across providers</p>
        </div>
        <Button onClick={() => setShowRegisterModal(true)}>Register Model</Button>
      </div>

      {/* Providers Overview */}
      <Card>
        <h3 className="text-lg font-semibold text-white mb-4">Providers</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {providers.map(p => (
            <div key={p.id} className="bg-gray-800 rounded-lg p-3">
              <p className="text-white font-medium text-sm">{p.name}</p>
              <p className="text-gray-500 text-xs">{p.provider_type}</p>
              <Badge variant={p.is_active ? 'success' : 'error'}>{p.is_active ? 'Active' : 'Inactive'}</Badge>
              <p className="text-gray-500 text-xs mt-1">{p.models_count || 0} models</p>
            </div>
          ))}
          {providers.length === 0 && <p className="text-gray-500 text-sm col-span-4">No providers registered</p>}
        </div>
      </Card>

      {error && <div className="p-3 bg-red-900/50 border border-red-700 rounded-lg text-red-300 text-sm">{error}</div>}

      {/* Models */}
      <Card>
        <h3 className="text-lg font-semibold text-white mb-4">Registered Models ({models.length})</h3>
        {isLoading ? (
          <p className="text-gray-500 text-center py-4">Loading...</p>
        ) : models.length === 0 ? (
          <EmptyState message="No models registered. Register your first AI model!" />
        ) : (
          <div className="space-y-3">
            {models.map(m => (
              <div key={m.id} className="bg-gray-800 rounded-lg p-4">
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="text-white font-medium">{m.name}</h4>
                    <p className="text-gray-500 text-xs">Provider: {m.provider_name || m.provider_id}</p>
                  </div>
                  <Badge variant={m.is_active ? 'success' : 'error'}>{m.is_active ? 'Active' : 'Inactive'}</Badge>
                </div>
                <div className="flex gap-2 mt-2">
                  {(m.capabilities || []).map(cap => (
                    <Badge key={cap} variant="info">{cap}</Badge>
                  ))}
                </div>
                <div className="flex gap-4 mt-2 text-xs text-gray-500">
                  <span>Context: {m.context_window}</span>
                  <span>Max output: {m.max_output_tokens}</span>
                  <span>${(m.cost_per_1k_input_tokens || 0).toFixed(6)}/1K in</span>
                  <span>${(m.cost_per_1k_output_tokens || 0).toFixed(6)}/1K out</span>
                  <span>{m.total_requests || 0} requests</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {showRegisterModal && (
        <Modal onClose={() => setShowRegisterModal(false)} title="Register AI Model">
          <div className="space-y-4">
            <Input label="Model Name" value={newModel.name} onChange={(e) => setNewModel({...newModel, name: e.target.value})} placeholder="e.g., gpt-4o" />
            <div>
              <label className="block text-sm text-gray-400 mb-1">Provider</label>
              <Select value={newModel.provider_id} onChange={(e) => setNewModel({...newModel, provider_id: e.target.value})}
                options={providers.map(p => ({ value: p.id, label: p.name }))} />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-2">Capabilities</label>
              <div className="flex flex-wrap gap-2">
                {CAPABILITIES.map(cap => (
                  <button key={cap} onClick={() => toggleCapability(cap)}
                    className={`px-3 py-1 rounded-full text-xs ${
                      newModel.capabilities.includes(cap)
                        ? 'bg-indigo-600 text-white' : 'bg-gray-700 text-gray-400'
                    }`}>
                    {cap}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input label="Context Window" type="number" value={newModel.context_window}
                onChange={(e) => setNewModel({...newModel, context_window: parseInt(e.target.value)})} />
              <Input label="Max Output Tokens" type="number" value={newModel.max_output_tokens}
                onChange={(e) => setNewModel({...newModel, max_output_tokens: parseInt(e.target.value)})} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input label="Cost per 1K Input Tokens ($)" type="number" value={newModel.cost_per_1k_input_tokens} step="0.000001"
                onChange={(e) => setNewModel({...newModel, cost_per_1k_input_tokens: parseFloat(e.target.value)})} />
              <Input label="Cost per 1K Output Tokens ($)" type="number" value={newModel.cost_per_1k_output_tokens} step="0.000001"
                onChange={(e) => setNewModel({...newModel, cost_per_1k_output_tokens: parseFloat(e.target.value)})} />
            </div>
            <Button onClick={handleRegister} disabled={!newModel.name.trim() || !newModel.provider_id}>Register</Button>
          </div>
        </Modal>
      )}
    </div>
  );
};

export default ModelManagerPage;

