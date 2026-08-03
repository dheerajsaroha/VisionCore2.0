/**
 * AICopilotHubPage.jsx — AI Copilot Hub
 * Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework
 */
import React, { useState, useRef, useEffect } from 'react';
import aiService from '../services/aiService';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Select } from '../components/ui/Select';
import { Spinner } from '../components/ui/Spinner';
import { Badge } from '../components/ui/Badge';

const COPILOT_DOMAINS = [
  { id: 'hr', label: 'HR Copilot', icon: '👥', description: 'Leave, attendance, payroll, employee management' },
  { id: 'recruitment', label: 'Recruitment Copilot', icon: '🎯', description: 'Talent acquisition, candidates, hiring' },
  { id: 'policy', label: 'Policy Copilot', icon: '📋', description: 'Company policies, compliance, regulations' },
  { id: 'performance', label: 'Performance Copilot', icon: '⭐', description: 'Reviews, goals, KPIs, development' },
  { id: 'asset', label: 'Asset Copilot', icon: '💻', description: 'Inventory, assignments, maintenance' },
  { id: 'operations', label: 'Operations Copilot', icon: '⚙️', description: 'System health, monitoring, incidents' },
  { id: 'executive', label: 'Executive Copilot', icon: '📊', description: 'Platform insights, strategy, analytics' },
];

const AICopilotHubPage = () => {
  const [domain, setDomain] = useState('hr');
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    setMessages([]);
    setConversationId(null);
  }, [domain]);

  const handleSend = async () => {
    if (!input.trim()) return;
    const userMessage = { role: 'user', content: input, timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setError('');

    try {
      const result = await aiService.copilotQuery({
        domain,
        query: userMessage.content,
        conversation_id: conversationId,
      });
      setConversationId(result.conversation_id);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: result.answer,
        suggestions: result.suggestions,
        data_sources: result.data_sources,
        timestamp: new Date().toISOString(),
      }]);
    } catch (err) {
      setError(err.message || 'Failed to get copilot response');
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${err.message}`,
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const domainInfo = COPILOT_DOMAINS.find(d => d.id === domain);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">AI Copilot Hub</h1>
        <p className="text-gray-400 mt-1">Intelligent assistants for every business domain</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <Card className="lg:col-span-1">
          <h3 className="text-lg font-semibold text-white mb-4">Domains</h3>
          <div className="space-y-2">
            {COPILOT_DOMAINS.map(d => (
              <button
                key={d.id}
                onClick={() => setDomain(d.id)}
                className={`w-full text-left p-3 rounded-lg transition-colors ${
                  domain === d.id
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                }`}
              >
                <span className="text-xl mr-2">{d.icon}</span>
                <span className="font-medium text-sm">{d.label}</span>
              </button>
            ))}
          </div>
        </Card>

        <Card className="lg:col-span-3">
          <div className="flex items-center gap-3 mb-4 pb-4 border-b border-gray-700">
            <span className="text-2xl">{domainInfo?.icon}</span>
            <div>
              <h3 className="text-lg font-semibold text-white">{domainInfo?.label}</h3>
              <p className="text-gray-400 text-sm">{domainInfo?.description}</p>
            </div>
          </div>

          <div className="h-96 overflow-y-auto space-y-4 mb-4 p-2">
            {messages.length === 0 && (
              <div className="text-center text-gray-500 py-12">
                <p className="text-4xl mb-4">{domainInfo?.icon}</p>
                <p>Ask me anything about {domainInfo?.description}</p>
              </div>
            )}
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] rounded-lg p-3 ${
                  msg.role === 'user'
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-800 text-gray-200'
                }`}>
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  {msg.suggestions?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {msg.suggestions.map((s, i) => (
                        <Badge key={i} variant="info" className="cursor-pointer"
                          onClick={() => { setInput(s); }}>
                          {s}
                        </Badge>
                      ))}
                    </div>
                  )}
                  {msg.data_sources?.length > 0 && (
                    <div className="mt-2 text-xs text-gray-500">
                      Sources: {msg.data_sources.join(', ')}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-gray-800 rounded-lg p-3">
                  <Spinner size="sm" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {error && (
            <div className="mb-4 p-2 bg-red-900/50 border border-red-700 rounded text-red-300 text-xs">
              {error}
            </div>
          )}

          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              placeholder={`Ask ${domainInfo?.label}...`}
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white"
              disabled={isLoading}
            />
            <Button onClick={handleSend} disabled={isLoading || !input.trim()}>
              {isLoading ? <Spinner size="sm" /> : 'Send'}
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default AICopilotHubPage;
