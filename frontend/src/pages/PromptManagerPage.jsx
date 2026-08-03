import React, { useState, useEffect } from 'react';
import aiService from '../services/aiService';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Modal } from '../components/ui/Modal';
import { EmptyState } from '../components/ui/EmptyState';
import { Badge } from '../components/ui/Badge';
import { Tabs } from '../components/ui/Tabs';

const PromptManagerPage = () => {
  const [prompts, setPrompts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [activeTab, setActiveTab] = useState('all');
  const [newPrompt, setNewPrompt] = useState({
    name: '', template: '', category: 'general',
    temperature: 0.7, max_tokens: 1024, version: '1.0',
  });

  useEffect(() => { loadPrompts(); }, []);

  const loadPrompts = async () => {
    setIsLoading(true);
    try {
      const category = activeTab !== 'all' ? activeTab : undefined;
      const data = await aiService.getPrompts(category);
      setPrompts(data || []);
    } catch (err) { setError(err.message); }
    finally { setIsLoading(false); }
  };

  useEffect(() => { loadPrompts(); }, [activeTab]);

  const handleCreate = async () => {
    if (!newPrompt.name.trim() || !newPrompt.template.trim()) return;
    try {
      await aiService.registerPrompt(newPrompt);
      setShowCreateModal(false);
      setNewPrompt({ name: '', template: '', category: 'general', temperature: 0.7, max_tokens: 1024, version: '1.0' });
      await loadPrompts();
    } catch (err) { setError(err.message); }
  };

  const categories = ['general', 'hr', 'recruitment', 'policy', 'performance', 'asset', 'operations', 'executive', 'rag', 'workflow'];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white">Prompt Manager</h1>
          <p className="text-gray-400 mt-1">Manage AI prompt templates across categories</p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>Create Prompt</Button>
      </div>

      <Tabs tabs={[{ id: 'all', label: 'All' }, ...categories.map(c => ({ id: c, label: c.charAt(0).toUpperCase() + c.slice(1) }))]}
        activeTab={activeTab} onChange={setActiveTab} />

      {error && <div className="p-3 bg-red-900/50 border border-red-700 rounded-lg text-red-300 text-sm">{error}</div>}

      {isLoading ? (
        <div className="text-center py-8"><p className="text-gray-500">Loading prompts...</p></div>
      ) : prompts.length === 0 ? (
        <EmptyState message="No prompt templates found. Create your first prompt!" />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {prompts.map(p => (
            <Card key={p.id}>
              <div className="flex justify-between items-start mb-2">
                <h3 className="text-white font-semibold">{p.name}</h3>
                <Badge variant="default">v{p.version}</Badge>
              </div>
              <p className="text-gray-400 text-sm mb-2">{p.category}</p>
              <pre className="bg-gray-900 rounded p-2 text-xs text-gray-300 max-h-24 overflow-y-auto">{p.template}</pre>
              <div className="flex gap-2 mt-2 text-xs text-gray-500">
                <span>Temp: {p.temperature}</span>
                <span>Max: {p.max_tokens}</span>
              </div>
            </Card>
          ))}
        </div>
      )}

      {showCreateModal && (
        <Modal onClose={() => setShowCreateModal(false)} title="Create Prompt Template">
          <div className="space-y-4">
            <Input label="Name" value={newPrompt.name} onChange={(e) => setNewPrompt({...newPrompt, name: e.target.value})} placeholder="e.g., HR Leave Policy Q&A" />
            <div>
              <label className="block text-sm text-gray-400 mb-1">Category</label>
              <Select value={newPrompt.category} onChange={(e) => setNewPrompt({...newPrompt, category: e.target.value})}
                options={categories.map(c => ({ value: c, label: c }))} />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Template (use {`{variable}`} for placeholders)</label>
              <textarea value={newPrompt.template} onChange={(e) => setNewPrompt({...newPrompt, template: e.target.value})}
                rows={6} className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input label="Temperature" type="number" value={newPrompt.temperature} step="0.1" min="0" max="2"
                onChange={(e) => setNewPrompt({...newPrompt, temperature: parseFloat(e.target.value)})} />
              <Input label="Max Tokens" type="number" value={newPrompt.max_tokens}
                onChange={(e) => setNewPrompt({...newPrompt, max_tokens: parseInt(e.target.value)})} />
            </div>
            <Input label="Version" value={newPrompt.version} onChange={(e) => setNewPrompt({...newPrompt, version: e.target.value})} />
            <Button onClick={handleCreate} disabled={!newPrompt.name.trim() || !newPrompt.template.trim()}>Create</Button>
          </div>
        </Modal>
      )}
    </div>
  );
};

export default PromptManagerPage;

