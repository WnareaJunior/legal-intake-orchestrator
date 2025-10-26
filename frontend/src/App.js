import React, { useState, useEffect } from 'react';

function App() {
  const [bulkProcessing, setBulkProcessing] = useState(false);
  const [bulkProgress, setBulkProgress] = useState(null);
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [bulkMessages, setBulkMessages] = useState('');
  const [messages, setMessages] = useState([]);
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [filter, setFilter] = useState('all');
  const [showNewMessageModal, setShowNewMessageModal] = useState(false);
  const [newMessageText, setNewMessageText] = useState('');
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState('');
  const [darkMode, setDarkMode] = useState(() => {
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return true;
    }
    return localStorage.getItem('darkMode') === 'true';
  });

  const API_URL = 'http://localhost:5000';

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('darkMode', darkMode);
  }, [darkMode]);

  useEffect(() => {
    fetchMessages();
  }, []);

  const fetchMessages = async () => {
    try {
      const res = await fetch(`${API_URL}/messages`);
      const data = await res.json();
      setMessages(data);
      setInitialLoading(false);
    } catch (err) {
      console.error('Failed to fetch messages:', err);
      setInitialLoading(false);
    }
  };

  const handleNewMessage = async () => {
    if (!newMessageText.trim()) {
      setError('Please enter a message');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const classifyRes = await fetch(`${API_URL}/classify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: newMessageText })
      });

      if (!classifyRes.ok) throw new Error('Classification failed');
      
      const classified = await classifyRes.json();
      
      // Generate draft for any agent type
      const draftRes = await fetch(`${API_URL}/generate_draft/${classified.id}`, {
        method: 'POST'
      });
      
      if (draftRes.ok) {
        const withDraft = await draftRes.json();
        setMessages([withDraft, ...messages]);
      } else {
        setMessages([classified, ...messages]);
      }

      setNewMessageText('');
      setShowNewMessageModal(false);

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleBulkProcess = async () => {
    if (!bulkMessages.trim()) {
      setError('Please enter messages (one per line)');
      return;
    }

    setBulkProcessing(true);
    setError('');

    try {
      // Split by newlines, filter empty
      const messageArray = bulkMessages
        .split('\n')
        .map(m => m.trim())
        .filter(m => m.length > 0);

      if (messageArray.length === 0) {
        setError('No valid messages found');
        setBulkProcessing(false);
        return;
      }

      if (messageArray.length > 100) {
        setError('Maximum 100 messages at once');
        setBulkProcessing(false);
        return;
      }

      const startTime = Date.now();

      const res = await fetch(`${API_URL}/process_bulk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: messageArray })
      });

      if (!res.ok) throw new Error('Bulk processing failed');

      const result = await res.json();
      const endTime = Date.now();
      const duration = ((endTime - startTime) / 1000).toFixed(2);

      setBulkProgress({
        ...result,
        actual_duration: duration
      });

      // Refresh messages
      await fetchMessages();

      setBulkMessages('');

    } catch (err) {
      setError(err.message);
    } finally {
      setBulkProcessing(false);
    }
  };

  // Load test messages
  const loadTestMessages = async () => {
    try {
      const res = await fetch(`${API_URL}/generate_test_messages`);
      const data = await res.json();
      setBulkMessages(data.messages.join('\n\n'));
    } catch (err) {
      setError('Failed to load test messages');
    }
  };

  const handleDecision = async (messageId, action, editedDraft = null) => {
    try {
      const body = { action };
      if (editedDraft) {
        body.edited_draft = editedDraft;
      }

      const res = await fetch(`${API_URL}/decision/${messageId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      if (!res.ok) throw new Error('Decision failed');
      
      const updated = await res.json();
      
      setMessages(messages.map(m => m.id === messageId ? updated : m));
      
      if (selectedMessage && selectedMessage.id === messageId) {
        setSelectedMessage(updated);
      }

    } catch (err) {
      setError(err.message);
    }
  };

  const filteredMessages = messages.filter(m => {
    if (filter === 'all') return true;
    return m.task_type === filter;
  });

  const getTaskTypeColor = (taskType) => {
    const colors = {
      records_request: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
      scheduling: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20',
      status_update: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
      other: 'bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/20'
    };
    return colors[taskType] || colors.other;
  };

  const getTaskTypeLabel = (taskType) => {
    const labels = {
      records_request: 'Records Request',
      scheduling: 'Scheduling',
      status_update: 'Status Update',
      other: 'Other'
    };
    return labels[taskType] || 'Other';
  };

  const getStatusBadge = (status) => {
    const badges = {
      draft_ready: { text: '📄 Draft Ready', color: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20' },
      approved: { text: '✓ Approved', color: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20' },
      edited: { text: '✎ Edited', color: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20' },
      rejected: { text: '✗ Rejected', color: 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20' },
      classified: { text: '⏳ Pending', color: 'bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/20' }
    };
    return badges[status] || badges.classified;
  };

  const getTimeAgo = (timestamp) => {
    const now = new Date();
    const then = new Date(timestamp);
    const diffMinutes = Math.floor((now - then) / 60000);
    
    if (diffMinutes < 1) return 'Just now';
    if (diffMinutes < 60) return `${diffMinutes} mins ago`;
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours} hours ago`;
    return `${Math.floor(diffHours / 24)} days ago`;
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 transition-colors duration-200">
      {/* Header */}
      <div className="sticky top-0 z-20 backdrop-blur-xl bg-white/80 dark:bg-gray-900/80 border-b border-gray-200 dark:border-gray-800 shadow-sm">
        <div className="container mx-auto px-4 lg:px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center text-xl shadow-lg shadow-blue-500/20">
                📨
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900 dark:text-white">
                  AI Legal Tender
                </h1>
                <p className="text-xs text-gray-600 dark:text-gray-400">
                  Multi-Agent Orchestration • Powered by Google Gemini
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setDarkMode(!darkMode)}
                className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-all duration-200"
                aria-label="Toggle dark mode"
              >
                {darkMode ? '☀️' : '🌙'}
              </button>
              
              <button
                onClick={() => setShowNewMessageModal(true)}
                className="px-4 py-2 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-700 hover:to-blue-600 text-white rounded-lg font-medium shadow-lg shadow-blue-500/30 hover:shadow-xl hover:shadow-blue-500/40 transition-all duration-200 hover:scale-[1.02]"
              >
                + New Message
              </button>
              <button
                onClick={() => setShowBulkModal(true)}
                className="px-4 py-2 bg-gradient-to-r from-purple-600 to-purple-500 hover:from-purple-700 hover:to-purple-600 text-white rounded-lg font-medium shadow-lg shadow-purple-500/30 hover:shadow-xl hover:shadow-purple-500/40 transition-all duration-200 hover:scale-[1.02]"
              >
                ⚡ Bulk Process
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="sticky top-[73px] z-10 backdrop-blur-xl bg-white/80 dark:bg-gray-900/80 border-b border-gray-200 dark:border-gray-800">
        <div className="container mx-auto px-4 lg:px-6">
          <div className="flex gap-2 py-3 overflow-x-auto">
            <FilterTab 
              active={filter === 'all'} 
              onClick={() => setFilter('all')}
              label="All Messages"
              count={messages.length}
            />
            <FilterTab 
              active={filter === 'records_request'} 
              onClick={() => setFilter('records_request')}
              label="📋 Records"
              count={messages.filter(m => m.task_type === 'records_request').length}
            />
            <FilterTab 
              active={filter === 'scheduling'} 
              onClick={() => setFilter('scheduling')}
              label="📅 Scheduling"
              count={messages.filter(m => m.task_type === 'scheduling').length}
            />
            <FilterTab 
              active={filter === 'status_update'} 
              onClick={() => setFilter('status_update')}
              label="📊 Status"
              count={messages.filter(m => m.task_type === 'status_update').length}
            />
          </div>
        </div>
      </div>

      {/* Message List */}
      <div className="container mx-auto px-4 lg:px-6 py-6 max-w-5xl">
        {initialLoading ? (
          <div className="space-y-4">
            {[1, 2, 3].map(i => <SkeletonCard key={i} />)}
          </div>
        ) : filteredMessages.length === 0 ? (
          <div className="text-center py-16">
            <div className="text-6xl mb-4">📭</div>
            <p className="text-lg text-gray-600 dark:text-gray-400 mb-4">No messages to display</p>
            <button
              onClick={() => setShowNewMessageModal(true)}
              className="text-blue-600 dark:text-blue-400 hover:underline font-medium"
            >
              Create your first message
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredMessages.map((message, idx) => (
              <MessageCard
                key={message.id}
                message={message}
                onClick={() => setSelectedMessage(message)}
                getTaskTypeColor={getTaskTypeColor}
                getTaskTypeLabel={getTaskTypeLabel}
                getStatusBadge={getStatusBadge}
                getTimeAgo={getTimeAgo}
                style={{ animationDelay: `${idx * 50}ms` }}
              />
            ))}
          </div>
        )}
      </div>

      {/* New Message Modal */}
      {showNewMessageModal && (
        <Modal onClose={() => {
          setShowNewMessageModal(false);
          setNewMessageText('');
          setError('');
        }}>
          <h2 className="text-2xl font-bold mb-6 text-gray-900 dark:text-white">New Client Message</h2>
          
          <textarea
            value={newMessageText}
            onChange={(e) => setNewMessageText(e.target.value)}
            placeholder="Paste client message here (email, text, voicemail transcript)..."
            className="w-full h-48 p-4 border border-gray-200 dark:border-gray-700 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent mb-4 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 transition-all duration-200"
          />

          {error && (
            <div className="mb-4 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-3">
            <button
              onClick={() => {
                setShowNewMessageModal(false);
                setNewMessageText('');
                setError('');
              }}
              className="px-5 py-2.5 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-all duration-200"
            >
              Cancel
            </button>
            <button
              onClick={handleNewMessage}
              disabled={loading}
              className="px-6 py-2.5 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-700 hover:to-blue-600 disabled:from-gray-400 disabled:to-gray-400 text-white rounded-lg font-medium shadow-lg shadow-blue-500/30 hover:shadow-xl hover:shadow-blue-500/40 transition-all duration-200 hover:scale-[1.02] disabled:scale-100 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="animate-spin">⚙️</span> Processing...
                </span>
              ) : 'Process Message'}
            </button>
          </div>
        </Modal>
      )}

      {/* Bulk Processing Modal */}
      {showBulkModal && (
        <Modal onClose={() => {
          setShowBulkModal(false);
          setBulkMessages('');
          setBulkProgress(null);
          setError('');
        }}>
          <h2 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">
            ⚡ Bulk Process Messages
          </h2>
          
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Process multiple messages simultaneously. Enter one message per line (max 100).
          </p>

          <div className="flex gap-2 mb-4">
            <button
              onClick={loadTestMessages}
              className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white text-sm rounded-lg transition-all duration-200"
            >
              Load 20 Test Messages
            </button>
            <button
              onClick={() => setBulkMessages('')}
              className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white text-sm rounded-lg transition-all duration-200"
            >
              Clear
            </button>
          </div>

          <textarea
            value={bulkMessages}
            onChange={(e) => setBulkMessages(e.target.value)}
            placeholder="Paste messages here (one per line)...

      Example:
      Hi I need my records from Dr. Smith. John Doe, DOB 3/20/1985.
      Can we schedule a consultation next week? - Sarah Johnson
      Checking on case status, case #12345..."
            className="w-full h-64 p-4 border border-gray-200 dark:border-gray-700 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent mb-4 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 transition-all duration-200 text-sm font-mono"
          />

          {error && (
            <div className="mb-4 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          {bulkProgress && (
            <div className="mb-4 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 rounded-xl p-4">
              <p className="text-lg font-bold text-emerald-900 dark:text-emerald-300 mb-3">
                ✓ Bulk Processing Complete!
              </p>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="text-gray-700 dark:text-gray-300">
                  <span className="font-medium">Total Messages:</span> {bulkProgress.total}
                </div>
                <div className="text-gray-700 dark:text-gray-300">
                  <span className="font-medium">Successful:</span> {bulkProgress.successful}
                </div>
                <div className="text-gray-700 dark:text-gray-300">
                  <span className="font-medium">Failed:</span> {bulkProgress.failed}
                </div>
                <div className="text-gray-700 dark:text-gray-300">
                  <span className="font-medium">Duration:</span> {bulkProgress.actual_duration}s
                </div>
                <div className="col-span-2 text-gray-700 dark:text-gray-300">
                  <span className="font-medium">Speed:</span> {bulkProgress.messages_per_second} messages/second
                </div>
                <div className="col-span-2 text-gray-700 dark:text-gray-300">
                  <span className="font-medium">Time Saved:</span> {(bulkProgress.total * 15 / 60).toFixed(1)} paralegal hours
                </div>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-3">
            <button
              onClick={() => {
                setShowBulkModal(false);
                setBulkMessages('');
                setBulkProgress(null);
                setError('');
              }}
              className="px-5 py-2.5 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-all duration-200"
            >
              Close
            </button>
            <button
              onClick={handleBulkProcess}
              disabled={bulkProcessing}
              className="px-6 py-2.5 bg-gradient-to-r from-purple-600 to-purple-500 hover:from-purple-700 hover:to-purple-600 disabled:from-gray-400 disabled:to-gray-400 text-white rounded-lg font-medium shadow-lg shadow-purple-500/30 hover:shadow-xl hover:shadow-purple-500/40 transition-all duration-200 hover:scale-[1.02] disabled:scale-100 disabled:cursor-not-allowed"
            >
              {bulkProcessing ? (
                <span className="flex items-center gap-2">
                  <span className="animate-spin">⚡</span> Processing...
                </span>
              ) : 'Process All'}
            </button>
          </div>
        </Modal>
      )}          

      {/* Message Detail Modal */}
      {selectedMessage && (
        <MessageDetailModal
          message={selectedMessage}
          onClose={() => setSelectedMessage(null)}
          onDecision={handleDecision}
          getStatusBadge={getStatusBadge}
        />
      )}
    </div>
  );
}

// Filter Tab Component
function FilterTab({ active, onClick, label, count }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-lg font-medium whitespace-nowrap transition-all duration-200 ${
        active
          ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/30'
          : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
      }`}
    >
      {label} <span className={active ? 'opacity-90' : 'opacity-60'}>({count})</span>
    </button>
  );
}

// Skeleton Loading Card
function SkeletonCard() {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5 animate-pulse">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="h-5 bg-gray-200 dark:bg-gray-800 rounded w-1/4 mb-2"></div>
          <div className="h-4 bg-gray-200 dark:bg-gray-800 rounded w-3/4"></div>
        </div>
        <div className="h-6 w-24 bg-gray-200 dark:bg-gray-800 rounded"></div>
      </div>
      <div className="h-3 bg-gray-200 dark:bg-gray-800 rounded w-1/3"></div>
    </div>
  );
}

// Message Card Component
function MessageCard({ message, onClick, getTaskTypeColor, getTaskTypeLabel, getStatusBadge, getTimeAgo, style }) {
  const statusBadge = getStatusBadge(message.status);
  
  return (
    <div
      onClick={onClick}
      style={style}
      className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 hover:border-blue-300 dark:hover:border-blue-700 hover:shadow-lg hover:shadow-blue-500/10 transition-all duration-200 cursor-pointer p-5 group animate-fadeIn"
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2 flex-wrap">
            <h3 className="font-semibold text-gray-900 dark:text-white truncate">
              {message.author}
            </h3>
            <span className={`px-2.5 py-1 rounded-lg text-xs font-medium border ${getTaskTypeColor(message.task_type)} whitespace-nowrap`}>
              {getTaskTypeLabel(message.task_type)}
            </span>
            {message.agent_used && (
              <span className="px-2.5 py-1 rounded-lg text-xs font-medium bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20 whitespace-nowrap">
                🤖 {message.agent_used.replace('Agent', '')}
              </span>
            )}
          </div>
          <p className="text-gray-700 dark:text-gray-300 font-medium mb-3 line-clamp-1">
            {message.header}
          </p>
          <div className="flex items-center gap-3 text-sm text-gray-500 dark:text-gray-400 flex-wrap">
            <span className="flex items-center gap-1">
              <span className="font-medium">{(message.confidence * 100).toFixed(0)}%</span>
              <span className="text-xs">confidence</span>
            </span>
            {message.draft?.quality_score && (
              <>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <span className={`font-medium ${message.draft.quality_score >= 0.85 ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}`}>
                    {(message.draft.quality_score * 100).toFixed(0)}%
                  </span>
                  <span className="text-xs">quality</span>
                </span>
              </>
            )}
            <span>•</span>
            <span>{getTimeAgo(message.timestamp)}</span>
            <span>•</span>
            <span className={`px-2 py-0.5 rounded text-xs font-medium border ${statusBadge.color}`}>
              {statusBadge.text}
            </span>
          </div>
        </div>
        <svg 
          className="w-5 h-5 text-gray-400 dark:text-gray-600 group-hover:text-blue-500 dark:group-hover:text-blue-400 group-hover:translate-x-1 transition-all duration-200 flex-shrink-0 ml-4" 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </div>
  );
}

// Modal Component
function Modal({ children, onClose }) {
  return (
    <div 
      className="fixed inset-0 bg-black/50 dark:bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fadeIn"
      onClick={onClose}
    >
      <div 
        className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl max-w-2xl w-full p-6 animate-slideUp"
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

// Message Detail Modal Component - NOW HANDLES ALL AGENT TYPES
function MessageDetailModal({ message, onClose, onDecision, getStatusBadge }) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedSubject, setEditedSubject] = useState(message.draft?.subject || '');
  const [editedBody, setEditedBody] = useState(message.draft?.body || '');

  const handleSaveEdit = () => {
    const editedDraft = {
      ...message.draft,
      subject: editedSubject,
      body: editedBody
    };
    onDecision(message.id, 'edit', editedDraft);
    setIsEditing(false);
  };

  const statusBadge = getStatusBadge(message.status);

  // Render different UI based on agent type
  const renderDraftContent = () => {
    if (!message.draft) {
      return (
        <div className="p-4 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 rounded-xl text-amber-800 dark:text-amber-400">
          <p className="text-sm">
            <span className="font-medium">Note:</span> No draft generated for this message type yet.
          </p>
        </div>
      );
    }

    const draft = message.draft;
    const taskType = message.task_type;

    return (
      <div className="mb-6">
        <h3 className="font-semibold mb-3 text-lg text-gray-900 dark:text-white flex items-center gap-2">
          Generated Response
          {message.agent_used && (
            <span className="text-sm font-normal px-2 py-1 rounded bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
              by {message.agent_used}
            </span>
          )}
        </h3>
        
        {/* Extracted Info - Different for each agent */}
        {draft.extracted_info && (
          <div className="mb-4 p-3 bg-emerald-50 dark:bg-emerald-500/10 rounded-xl border border-emerald-200 dark:border-emerald-500/20">
            <p className="text-xs font-semibold text-emerald-900 dark:text-emerald-400 mb-2">EXTRACTED INFORMATION:</p>
            <div className="grid grid-cols-2 gap-2 text-sm text-gray-700 dark:text-gray-300">
              {Object.entries(draft.extracted_info).map(([key, value]) => (
                <div key={key}>
                  <span className="font-medium capitalize">{key.replace('_', ' ')}:</span> {value}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Scheduling-specific: Suggested Invite */}
        {taskType === 'scheduling' && draft.suggested_invite && (
          <div className="mb-4 p-3 bg-purple-50 dark:bg-purple-500/10 rounded-xl border border-purple-200 dark:border-purple-500/20">
            <p className="text-xs font-semibold text-purple-900 dark:text-purple-400 mb-2">📅 SUGGESTED CALENDAR INVITE:</p>
            <div className="grid grid-cols-2 gap-2 text-sm text-gray-700 dark:text-gray-300">
              {Object.entries(draft.suggested_invite).map(([key, value]) => (
                <div key={key}>
                  <span className="font-medium capitalize">{key}:</span> {value}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Status-specific: Recommended Action */}
        {taskType === 'status_update' && draft.recommended_action && (
          <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-500/10 rounded-xl border border-blue-200 dark:border-blue-500/20">
            <p className="text-xs font-semibold text-blue-900 dark:text-blue-400 mb-2">💡 RECOMMENDED ACTION:</p>
            <p className="text-sm text-gray-700 dark:text-gray-300">{draft.recommended_action}</p>
          </div>
        )}

        {/* Email/Response Body */}
        <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
          <div className="bg-gray-50 dark:bg-gray-800 px-4 py-3 border-b border-gray-200 dark:border-gray-700">
            {isEditing ? (
              <input
                type="text"
                value={editedSubject}
                onChange={(e) => setEditedSubject(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-900 text-gray-900 dark:text-white"
                placeholder="Subject"
              />
            ) : (
              <p className="text-sm text-gray-700 dark:text-gray-300">
                <span className="font-medium">Subject:</span> {editedSubject}
              </p>
            )}
          </div>
          <div className="p-4 bg-white dark:bg-gray-900">
            {isEditing ? (
              <textarea
                value={editedBody}
                onChange={(e) => setEditedBody(e.target.value)}
                className="w-full h-64 p-3 border border-gray-300 dark:border-gray-600 rounded-lg text-sm font-sans bg-white dark:bg-gray-900 text-gray-900 dark:text-white"
              />
            ) : (
              <pre className="whitespace-pre-wrap text-sm font-sans text-gray-700 dark:text-gray-300">{editedBody}</pre>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div 
      className="fixed inset-0 bg-black/50 dark:bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4 overflow-y-auto animate-fadeIn"
      onClick={onClose}
    >
      <div 
        className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl max-w-4xl w-full my-8 animate-slideUp"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="border-b border-gray-200 dark:border-gray-800 px-6 py-4 flex items-center justify-between sticky top-0 bg-white dark:bg-gray-900 rounded-t-2xl">
          <div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">{message.author}</h2>
            <p className="text-gray-600 dark:text-gray-400">{message.header}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-3xl leading-none transition-colors duration-200"
          >
            ×
          </button>
        </div>

        {/* Modal Body */}
        <div className="px-6 py-4 max-h-[70vh] overflow-y-auto">
          
          {/* Original Message */}
          <div className="mb-6">
            <h3 className="font-semibold mb-3 text-gray-900 dark:text-white">Original Message</h3>
            <div className="bg-gray-50 dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700">
              <p className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{message.raw_text}</p>
            </div>
          </div>

          {/* Classification Info */}
          <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-500/10 rounded-xl border border-blue-200 dark:border-blue-500/20">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="text-gray-700 dark:text-gray-300">
                <span className="font-medium">Task Type:</span> {message.task_type}
              </div>
              <div className="text-gray-700 dark:text-gray-300">
                <span className="font-medium">Confidence:</span> {(message.confidence * 100).toFixed(0)}%
              </div>
              {message.reasoning && (
                <div className="col-span-2 text-gray-700 dark:text-gray-300">
                  <span className="font-medium">Reasoning:</span> {message.reasoning}
                </div>
              )}
              {message.agent_used && (
                <div className="col-span-2 text-gray-700 dark:text-gray-300">
                  <span className="font-medium">Processed by:</span> {message.agent_used}
                </div>
              )}
              <div className="col-span-2">
                <span className={`px-3 py-1.5 rounded-lg text-xs font-medium border ${statusBadge.color} inline-block`}>
                  {statusBadge.text}
                </span>
              </div>
            </div>
          </div>

          {message.draft?.requires_human_review && (
            <div className="mb-6 p-4 bg-red-50 dark:bg-red-500/10 rounded-xl border-2 border-red-300 dark:border-red-500/30">
              <div className="flex items-start gap-3">
                <span className="text-2xl">⚠️</span>
                <div className="flex-1">
                  <p className="text-sm font-bold text-red-900 dark:text-red-300 mb-2">
                    QUALITY CHECK FAILED - REQUIRES HUMAN REVIEW
                  </p>
                  <p className="text-sm text-red-800 dark:text-red-400 mb-3">
                    Agent detected critical issues and refused to proceed. Manual intervention required.
                  </p>
                  {message.draft.quality_issues && message.draft.quality_issues.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-red-900 dark:text-red-300 mb-1">Issues Detected:</p>
                      <ul className="text-sm text-red-800 dark:text-red-300 list-disc list-inside space-y-1">
                        {message.draft.quality_issues.map((issue, i) => (
                          <li key={i}>{issue}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {message.draft.attempt && (
                    <p className="text-xs text-red-700 dark:text-red-400 mt-2">
                      Failed after {message.draft.attempt} attempt{message.draft.attempt > 1 ? 's' : ''}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Draft Content - Renders based on agent type */}
          {renderDraftContent()}
        </div>

        {/* Modal Footer */}
        <div className="border-t border-gray-200 dark:border-gray-800 px-6 py-4 bg-gray-50 dark:bg-gray-800/50 rounded-b-2xl">
          {message.draft && message.status !== 'approved' && message.status !== 'rejected' && (
            <div className="flex justify-end gap-3">
              {isEditing ? (
                <>
                  <button
                    onClick={handleSaveEdit}
                    className="px-6 py-2.5 bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-700 hover:to-emerald-600 text-white rounded-lg font-medium shadow-lg shadow-emerald-500/30 hover:shadow-xl hover:shadow-emerald-500/40 transition-all duration-200 hover:scale-[1.02]"
                  >
                    ✓ Save Changes
                  </button>
                  <button
                    onClick={() => {
                      setIsEditing(false);
                      setEditedSubject(message.draft.subject);
                      setEditedBody(message.draft.body);
                    }}
                    className="px-6 py-2.5 bg-gray-600 hover:bg-gray-700 text-white rounded-lg font-medium transition-all duration-200"
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={() => onDecision(message.id, 'approve')}
                    className="px-6 py-2.5 bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-700 hover:to-emerald-600 text-white rounded-lg font-medium shadow-lg shadow-emerald-500/30 hover:shadow-xl hover:shadow-emerald-500/40 transition-all duration-200 hover:scale-[1.02]"
                  >
                    ✓ Approve & Send
                  </button>
                  <button
                    onClick={() => setIsEditing(true)}
                    className="px-6 py-2.5 bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-700 hover:to-amber-600 text-white rounded-lg font-medium shadow-lg shadow-amber-500/30 hover:shadow-xl hover:shadow-amber-500/40 transition-all duration-200 hover:scale-[1.02]"
                  >
                    ✎ Edit Draft
                  </button>
                  <button
                    onClick={() => onDecision(message.id, 'reject')}
                    className="px-5 py-2.5 bg-gray-600 hover:bg-gray-700 text-white rounded-lg font-medium transition-all duration-200"
                  >
                    ✗ Reject
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;