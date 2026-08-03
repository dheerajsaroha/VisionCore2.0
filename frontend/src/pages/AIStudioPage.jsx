/**
 * AIStudioPage.jsx — AI Studio
 * Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework
 */
import React, { useState, useEffect, useRef } from 'react';
import aiService from '../services/aiService';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Spinner } from '../components/ui/Spinner';
import { Tabs } from '../components/ui/Tabs';

const AIStudioPage = () => {
  const [models, setModels] = useState([]);
  const [providers, setProviders] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedProvider, setSelectedProvider] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('You are a helpful enterprise AI assistant.');
  const [userPrompt, setUserPrompt] = useState('');
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(2048);
  const [response, setResponse] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState([]);
  const [activeTab, setActiveTab] = useState('playground');
  const responseRef = useRef(null);

  useEffect(() => { loadModelsAndProviders(); }, []);

  const loadModelsAndProviders = async () => {
    try {
      const [modelsData, providersData] = await Promise.all([
        aiService.getModels(), aiService.getProviders(),
      ]);
      setModels(modelsData || []);
      setProviders(providersData || []);
    } catch (err) { console.error('Failed to load models/providers:', err); }
  };

  const handleSubmit = async () => {
    if (!userPrompt.trim()) return;
    setIsLoading(true);
    setError('');
    setResponse('');
    try {
      const result = await aiService.complete({
        prompt: userPrompt,
        model_id: selectedModel || undefined,
        provider_id: selectedProvider || undefined,
        system_prompt: systemPrompt,
        temperature,
        max_tokens: maxTokens,
      });
      setResponse(result.content);
      setHistory(prev => [{
        id: Date.now(), prompt: userPrompt, response: result.content,
        model: result.model, provider: result.provider,
        timestamp: new Date().toISOString(),
      }, ...prev].slice(0, 50));
    } catch (err) { setError(err.message || 'Failed to get AI response'); }
    finally { setIsLoading(false); }
  };

  const clearHistory = () => setHistory([]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">AI Studio</h1>
        <p className="text-gray-400 mt-1">Interactive AI playground for testing prompts and models</p>
      </div>

      <Tabs tabs={[
        { id: 'playground', label: 'Playground' },
        { id: 'history', label: 'History (' + history.length + ')' },
      ]} activeTab={activeTab} onChange={setActiveTab} />

      {activeTab === 'playground' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Configuration</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Provider</label>
                <Select value={selectedProvider} onChange={(e) => setSelectedProvider(e.target.value)}
                  options={[
                    { value: '', label: 'Auto-select' },
                    ...(providers || []).map(p => ({ value: p.id, label: p.name + ' (' + p.provider_type + ')' })),
                  ]} />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Model</label>
                <Select value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)}
                  options={[
                    { value: '', label: 'Default model' },
                    ...(models || []).map(m => ({ value: m.id, label: m.name })),
                  ]} />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Temperature: {temperature}</label>
                <input type="range" min="0" max="2" step="0.1" value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))} className="w-full" />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Max Tokens</label>
                <Input type="number" value={maxTokens} onChange={(e) => setMaxTokens(parseInt(e.target.value))} min={16} max={100000} />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">System Prompt</label>
                <textarea value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} rows={3}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm" />
              </div>
            </div>
          </Card>

          <Card>
            <h3 className="text-lg font-semibold text-white mb-4">Prompt</h3>
            <textarea value={userPrompt} onChange={(e) => setUserPrompt(e.target.value)}
              placeholder="Enter your prompt here..." rows={6}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white mb-4" />
            <Button onClick={handleSubmit} disabled={isLoading || !userPrompt.trim()}>
              {isLoading ? <span className="flex items-center gap-2"><Spinner size="sm" /> Generating...</span> : 'Send'}
            </Button>

            {error && <div className="mt-4 p-3 bg-red-900/50 border border-red-700 rounded-lg text-red-300 text-sm">{error}</div>}

            {response && (
              <div ref={responseRef} className="mt-6">
                <h4 className="text-sm font-semibold text-gray-400 mb-2">Response</h4>
                <div className="bg-gray-800 rounded-lg p-4 text-white whitespace-pre-wrap text-sm leading-relaxed">{response}</div>
              </div>
            )}
          </Card>
        </div>
      )}

      {activeTab === 'history' && (
        <Card>
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-semibold text-white">Query History</h3>
            <Button variant="outline" size="sm" onClick={clearHistory}>Clear History</Button>
          </div>
          {history.length === 0
            ? <p className="text-gray-500 text-center py-8">No queries yet. Try the playground!</p>
            : <div className="space-y-3">
                {history.map((entry) => (
                  <div key={entry.id} className="bg-gray-800 rounded-lg p-4">
                    <div className="flex justify-between text-xs text-gray-500 mb-2">
                      <span>{entry.model} ({entry.provider})</span>
                      <span>{new Date(entry.timestamp).toLocaleString()}</span>
                    </div>
                    <p className="text-white text-sm font-medium mb-1">Q: {entry.prompt}</p>
                    <p className="text-gray-300 text-sm">A: {entry.response?.slice(0, 200)}...</p>
                  </div>
                ))}
              </div>
          }
        </Card>
      )}
    </div>
  );
};

export default AIStudioPage;
