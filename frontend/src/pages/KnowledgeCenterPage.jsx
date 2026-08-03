/**
 * KnowledgeCenterPage.jsx — Knowledge Center
 * Sprint 7 — Enterprise AI Platform & Intelligent Automation Framework
 */
import React, { useState, useEffect } from 'react';
import knowledgeService from '../services/knowledgeService';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Spinner } from '../components/ui/Spinner';
import { Tabs } from '../components/ui/Tabs';
import { Modal } from '../components/ui/Modal';
import { EmptyState } from '../components/ui/EmptyState';
import { Badge } from '../components/ui/Badge';

const KnowledgeCenterPage = () => {
  const [collections, setCollections] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [selectedCollection, setSelectedCollection] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('collections');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [newCollection, setNewCollection] = useState({ name: '', description: '' });
  const [uploadFile, setUploadFile] = useState(null);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    loadCollections();
    loadStats();
  }, []);

  useEffect(() => {
    if (selectedCollection) {
      loadDocuments(selectedCollection);
    }
  }, [selectedCollection]);

  const loadCollections = async () => {
    try {
      const data = await knowledgeService.getCollections();
      setCollections(data || []);
    } catch (err) {
      console.error('Failed to load collections:', err);
    }
  };

  const loadDocuments = async (collectionId) => {
    try {
      const data = await knowledgeService.getDocuments(collectionId);
      setDocuments(data || []);
    } catch (err) {
      console.error('Failed to load documents:', err);
    }
  };

  const loadStats = async () => {
    try {
      const data = await knowledgeService.getStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  };

  const handleCreateCollection = async () => {
    if (!newCollection.name.trim()) return;
    try {
      await knowledgeService.createCollection(newCollection);
      setShowCreateModal(false);
      setNewCollection({ name: '', description: '' });
      await loadCollections();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleUploadDocument = async () => {
    if (!uploadFile || !selectedCollection) return;
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('collection', selectedCollection);
      await knowledgeService.ingestDocument(formData);
      setShowUploadModal(false);
      setUploadFile(null);
      await loadDocuments(selectedCollection);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setIsLoading(true);
    try {
      const results = await knowledgeService.search(searchQuery, [selectedCollection]);
      setSearchResults(results.results || []);
      setActiveTab('search');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteDocument = async (docId) => {
    try {
      await knowledgeService.deleteDocument(docId);
      await loadDocuments(selectedCollection);
    } catch (err) {
      setError(err.message);
    }
  };

  return React.createElement('div', { className: 'space-y-6' },
    React.createElement('div', { className: 'flex justify-between items-center' },
      React.createElement('div', null,
        React.createElement('h1', { className: 'text-2xl font-bold text-white' }, 'Knowledge Center'),
        React.createElement('p', { className: 'text-gray-400 mt-1' }, 'Manage knowledge collections, documents, and search')
      ),
      React.createElement('div', { className: 'flex gap-2' },
        React.createElement(Button, { onClick: () => setShowCreateModal(true) }, 'Create Collection'),
        React.createElement(Button, { variant: 'outline', onClick: () => setShowUploadModal(true), disabled: !selectedCollection }, 'Upload Document')
      )
    ),
    stats ? React.createElement('div', { className: 'grid grid-cols-1 md:grid-cols-4 gap-4' },
      React.createElement(Card, null,
        React.createElement('p', { className: 'text-gray-400 text-sm' }, 'Collections'),
        React.createElement('p', { className: 'text-2xl font-bold text-white' }, stats.collections || 0)
      ),
      React.createElement(Card, null,
        React.createElement('p', { className: 'text-gray-400 text-sm' }, 'Documents'),
        React.createElement('p', { className: 'text-2xl font-bold text-white' }, stats.documents || 0)
      ),
      React.createElement(Card, null,
        React.createElement('p', { className: 'text-gray-400 text-sm' }, 'Chunks'),
        React.createElement('p', { className: 'text-2xl font-bold text-white' }, stats.chunks || 0)
      ),
      React.createElement(Card, null,
        React.createElement('p', { className: 'text-gray-400 text-sm' }, 'Searches'),
        React.createElement('p', { className: 'text-2xl font-bold text-white' }, stats.searches || 0)
      )
    ) : null,
    React.createElement(Card, null,
      React.createElement('div', { className: 'flex gap-4 items-end' },
        React.createElement('div', { className: 'flex-1' },
          React.createElement('label', { className: 'block text-sm text-gray-400 mb-1' }, 'Collection'),
          React.createElement(Select, {
            value: selectedCollection,
            onChange: (e) => setSelectedCollection(e.target.value),
            options: (collections || []).map(c => ({
              value: c.id,
              label: c.name + ' (' + (c.document_count || 0) + ' docs)'
            }))
          })
        ),
        React.createElement('div', { className: 'flex-1' },
          React.createElement('label', { className: 'block text-sm text-gray-400 mb-1' }, 'Search'),
          React.createElement('div', { className: 'flex gap-2' },
            React.createElement(Input, {
              value: searchQuery,
              onChange: (e) => setSearchQuery(e.target.value),
              placeholder: 'Search knowledge base...',
              onKeyDown: (e) => { if (e.key === 'Enter') handleSearch(); }
            }),
            React.createElement(Button, { onClick: handleSearch, disabled: isLoading || !searchQuery.trim() },
              isLoading ? React.createElement(Spinner, { size: 'sm' }) : 'Search'
            )
          )
        )
      )
    ),
    error ? React.createElement('div', { className: 'p-3 bg-red-900/50 border border-red-700 rounded-lg text-red-300 text-sm' }, error) : null,
    React.createElement(Tabs, {
      tabs: [
        { id: 'collections', label: 'Collections' },
        { id: 'documents', label: 'Documents (' + documents.length + ')' },
        { id: 'search', label: 'Search Results (' + searchResults.length + ')' }
      ],
      activeTab: activeTab,
      onChange: setActiveTab
    }),
    activeTab === 'collections' ? React.createElement('div', { className: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4' },
      collections.length === 0
        ? React.createElement('div', { className: 'col-span-full' },
            React.createElement(EmptyState, { title: 'No collections', description: 'Create your first knowledge collection!' })
          )
        : collections.map(col => React.createElement(Card, { key: col.id, className: 'cursor-pointer hover:border-indigo-500 transition-colors', onClick: () => { setSelectedCollection(col.id); setActiveTab('documents'); } },
            React.createElement('h3', { className: 'text-white font-semibold' }, col.name),
            col.description ? React.createElement('p', { className: 'text-gray-400 text-sm mt-1' }, col.description) : null,
            React.createElement('div', { className: 'flex gap-2 mt-3' },
              React.createElement(Badge, { variant: 'info' }, col.document_count || 0, ' documents'),
              React.createElement(Badge, { variant: 'default' }, col.chunk_count || 0, ' chunks')
            )
          ))
    ) : null,
    activeTab === 'documents' ? React.createElement(Card, null,
      documents.length === 0
        ? React.createElement(EmptyState, { title: 'No documents', description: 'Upload your first document!' })
        : React.createElement('div', { className: 'space-y-2' },
            documents.map(doc => React.createElement('div', { key: doc.id, className: 'flex justify-between items-center p-3 bg-gray-800 rounded-lg' },
              React.createElement('div', null,
                React.createElement('p', { className: 'text-white text-sm font-medium' }, doc.filename),
                React.createElement('p', { className: 'text-gray-500 text-xs' }, doc.content_type, ' - ', doc.chunk_count, ' chunks')
              ),
              React.createElement(Button, { variant: 'destructive', size: 'sm', onClick: () => handleDeleteDocument(doc.id) }, 'Delete')
            ))
          )
    ) : null,
    activeTab === 'search' ? React.createElement(Card, null,
      searchResults.length === 0
        ? React.createElement(EmptyState, { title: 'No results', description: 'No results found for your query.' })
        : React.createElement('div', { className: 'space-y-3' },
            searchResults.map((result, idx) => React.createElement('div', { key: idx, className: 'bg-gray-800 rounded-lg p-4' },
              React.createElement('div', { className: 'flex justify-between text-xs text-gray-500 mb-1' },
                React.createElement('span', null, 'Score: ' + (result.score * 100).toFixed(1) + '%'),
                React.createElement('span', null, result.metadata ? result.metadata.filename : 'unknown')
              ),
              React.createElement('p', { className: 'text-white text-sm' }, result.text)
            ))
          )
    ) : null,
    showCreateModal ? React.createElement(Modal, { onClose: () => setShowCreateModal(false), title: 'Create Collection', isOpen: true },
      React.createElement('div', { className: 'space-y-4' },
        React.createElement(Input, { label: 'Collection Name', value: newCollection.name, onChange: (e) => setNewCollection({ ...newCollection, name: e.target.value }), placeholder: 'e.g., HR Policies' }),
        React.createElement(Input, { label: 'Description (optional)', value: newCollection.description, onChange: (e) => setNewCollection({ ...newCollection, description: e.target.value }), placeholder: 'Collection description' }),
        React.createElement(Button, { onClick: handleCreateCollection, disabled: !newCollection.name.trim() }, 'Create')
      )
    ) : null,
    showUploadModal ? React.createElement(Modal, { onClose: () => setShowUploadModal(false), title: 'Upload Document', isOpen: true },
      React.createElement('div', { className: 'space-y-4' },
        React.createElement('input', { type: 'file', onChange: (e) => setUploadFile(e.target.files[0]), className: 'w-full text-white', accept: '.pdf,.docx,.doc,.xlsx,.xls,.txt,.csv' }),
        React.createElement('p', { className: 'text-gray-500 text-xs' }, 'Supported: PDF, DOCX, XLSX, TXT, CSV'),
        React.createElement(Button, { onClick: handleUploadDocument, disabled: !uploadFile }, 'Upload and Index')
      )
    ) : null
  );
};

export default KnowledgeCenterPage;
