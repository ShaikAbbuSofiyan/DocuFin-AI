import React, { useState, useEffect, useRef } from 'react';
import {
  Bot,
  Send,
  Sparkles,
  Calculator,
  AlertTriangle,
  FileText,
  BookOpen,
  PlusCircle,
  Trash2,
  CheckCircle2,
  Layers,
  Search,
  Check,
  ChevronDown,
  RefreshCw,
} from 'lucide-react';
import { apiClient } from '../services/api';
import { DocumentItem } from '../types/document';
import {
  ChatQueryResponse,
  CitationItem,
  ConversationResponse,
  ChatMessageResponse,
} from '../types/chat';

interface MessageUI {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  citations?: CitationItem[];
  hasSufficientEvidence?: boolean;
  isNumericalAggregation?: boolean;
  aggregationType?: string;
  tokensUsed?: number;
  processingTimeMs?: number;
  createdAt: string;
}

export const AiAssistantPage: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageUI[]>([]);
  const [inputQuery, setInputQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [indexingDocId, setIndexingDocId] = useState<string | null>(null);
  const [indexSuccessMsg, setIndexSuccessMsg] = useState<string | null>(null);
  const [docSearchTerm, setDocSearchTerm] = useState('');
  const [isDocDropdownOpen, setIsDocDropdownOpen] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Quick prompt suggestions
  const suggestedQuestions = [
    { label: 'Invoice Totals', query: 'What is the total amount across these invoices?' },
    { label: 'Overdue Invoices', query: 'Which invoices are overdue?' },
    { label: 'Closing Balance', query: 'What is the closing balance?' },
    { label: 'High-Value (>₹50k)', query: 'Which transactions exceed ₹50,000?' },
    { label: 'Manual Verification', query: 'Which fields need manual verification?' },
  ];

  // Fetch documents and conversations on load
  useEffect(() => {
    loadDocuments();
    loadConversations();
  }, []);

  // Auto-scroll on new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const loadDocuments = async () => {
    try {
      const res = await apiClient.getDocuments({ page_size: 50 });
      setDocuments(res.items || []);
    } catch (err) {
      console.error('Failed to load documents for RAG assistant:', err);
    }
  };

  const loadConversations = async () => {
    try {
      const convList = await apiClient.getChatConversations();
      setConversations(convList);
    } catch (err) {
      console.error('Failed to load chat conversations:', err);
    }
  };

  const handleSelectConversation = async (convId: string) => {
    setActiveConversationId(convId);
    try {
      const conv = await apiClient.getChatConversation(convId);
      if (conv.document_ids) {
        setSelectedDocIds(conv.document_ids);
      }
      if (conv.messages) {
        setMessages(
          conv.messages.map((m: ChatMessageResponse) => ({
            id: m.id,
            sender: m.sender,
            text: m.message,
            citations: m.citations,
            isNumericalAggregation: m.is_numerical_aggregation,
            hasSufficientEvidence: true,
            tokensUsed: m.tokens_used,
            createdAt: m.created_at,
          }))
        );
      }
    } catch (err) {
      console.error('Failed to fetch conversation history:', err);
    }
  };

  const handleNewConversation = () => {
    setActiveConversationId(null);
    setMessages([]);
  };

  const handleDeleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await apiClient.deleteChatConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConversationId === convId) {
        handleNewConversation();
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  const handleIndexDocument = async (docId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setIndexingDocId(docId);
    setIndexSuccessMsg(null);
    try {
      const res = await apiClient.indexDocumentForRag(docId);
      setIndexSuccessMsg(`Indexed ${res.chunks_indexed} chunks`);
      setTimeout(() => setIndexSuccessMsg(null), 3000);
    } catch (err) {
      console.error('Error indexing document:', err);
    } finally {
      setIndexingDocId(null);
    }
  };

  const toggleDocSelection = (docId: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  const handleSendMessage = async (queryToSend?: string) => {
    const q = (queryToSend || inputQuery).trim();
    if (!q || isLoading) return;

    const userMsg: MessageUI = {
      id: `usr-${Date.now()}`,
      sender: 'user',
      text: q,
      createdAt: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuery('');
    setIsLoading(true);

    try {
      const resp: ChatQueryResponse = await apiClient.queryChatAssistant({
        query: q,
        conversation_id: activeConversationId || undefined,
        document_ids: selectedDocIds.length > 0 ? selectedDocIds : undefined,
      });

      if (!activeConversationId && resp.conversation_id) {
        setActiveConversationId(resp.conversation_id);
        loadConversations();
      }

      const botMsg: MessageUI = {
        id: `bot-${Date.now()}`,
        sender: 'assistant',
        text: resp.answer,
        citations: resp.citations || [],
        hasSufficientEvidence: resp.has_sufficient_evidence,
        isNumericalAggregation: resp.is_numerical_aggregation,
        aggregationType: resp.aggregation_type,
        tokensUsed: resp.tokens_used,
        processingTimeMs: resp.processing_time_ms,
        createdAt: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err: any) {
      const errMsg: MessageUI = {
        id: `err-${Date.now()}`,
        sender: 'assistant',
        text: err?.message || 'An error occurred while answering your question. Please try again.',
        hasSufficientEvidence: false,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredDocuments = documents.filter((d) =>
    (d.title || d.filename || '').toLowerCase().includes(docSearchTerm.toLowerCase())
  );

  return (
    <div className="flex h-[calc(100vh-5rem)] bg-slate-950 text-slate-100 overflow-hidden rounded-xl border border-slate-800 shadow-2xl">
      {/* LEFT SIDEBAR: Conversations & Document Scoping */}
      <div className="w-80 border-r border-slate-800 bg-slate-900/60 flex flex-col backdrop-blur-md">
        {/* Sidebar Header */}
        <div className="p-4 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Bot className="w-5 h-5 text-indigo-400" />
            <span className="font-semibold text-sm tracking-wide text-slate-200">
              Financial RAG AI
            </span>
          </div>
          <button
            onClick={handleNewConversation}
            className="flex items-center space-x-1 px-2.5 py-1 text-xs font-medium bg-indigo-600/30 text-indigo-300 hover:bg-indigo-600/50 hover:text-white rounded-md border border-indigo-500/30 transition-all"
            title="Start new conversation"
          >
            <PlusCircle className="w-3.5 h-3.5" />
            <span>New Chat</span>
          </button>
        </div>

        {/* Document Scope Filter Selector */}
        <div className="p-3 border-b border-slate-800/80 bg-slate-900/40">
          <label className="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-indigo-400" />
              Document Scope
            </span>
            <span className="text-[10px] text-indigo-400">
              {selectedDocIds.length > 0 ? `${selectedDocIds.length} Selected` : 'All Documents'}
            </span>
          </label>

          <div className="relative">
            <button
              onClick={() => setIsDocDropdownOpen(!isDocDropdownOpen)}
              className="w-full text-left px-3 py-2 text-xs bg-slate-800/90 border border-slate-700 rounded-lg hover:border-indigo-500/60 transition-colors flex items-center justify-between"
            >
              <span className="truncate text-slate-300">
                {selectedDocIds.length === 0
                  ? 'All Organization Documents'
                  : `${selectedDocIds.length} document(s) targeted`}
              </span>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 ml-1 shrink-0" />
            </button>

            {isDocDropdownOpen && (
              <div className="absolute z-20 mt-1 w-full bg-slate-900 border border-slate-700 rounded-lg shadow-xl p-2 max-h-60 overflow-y-auto">
                <div className="relative mb-2">
                  <Search className="w-3 h-3 absolute left-2.5 top-2.5 text-slate-500" />
                  <input
                    type="text"
                    value={docSearchTerm}
                    onChange={(e) => setDocSearchTerm(e.target.value)}
                    placeholder="Search documents..."
                    className="w-full pl-7 pr-2 py-1 text-xs bg-slate-800 border border-slate-700 rounded text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                {selectedDocIds.length > 0 && (
                  <button
                    onClick={() => setSelectedDocIds([])}
                    className="w-full text-left px-2 py-1 mb-1 text-[11px] text-amber-400 hover:bg-slate-800 rounded transition-colors"
                  >
                    Clear selection (query all)
                  </button>
                )}

                <div className="space-y-1">
                  {filteredDocuments.map((doc) => {
                    const isSelected = selectedDocIds.includes(doc.id);
                    const isIndexing = indexingDocId === doc.id;
                    return (
                      <div
                        key={doc.id}
                        onClick={() => toggleDocSelection(doc.id)}
                        className={`flex items-center justify-between px-2 py-1.5 rounded cursor-pointer text-xs transition-colors ${
                          isSelected
                            ? 'bg-indigo-950/60 border border-indigo-500/40 text-indigo-200'
                            : 'hover:bg-slate-800 text-slate-300'
                        }`}
                      >
                        <div className="flex items-center space-x-2 truncate mr-2">
                          <div
                            className={`w-3.5 h-3.5 rounded flex items-center justify-center border ${
                              isSelected
                                ? 'bg-indigo-600 border-indigo-400'
                                : 'border-slate-600'
                            }`}
                          >
                            {isSelected && <Check className="w-2.5 h-2.5 text-white" />}
                          </div>
                          <span className="truncate">{doc.title || doc.filename}</span>
                        </div>
                        <button
                          onClick={(e) => handleIndexDocument(doc.id, e)}
                          title="Generate/Refresh Embeddings for this document"
                          disabled={isIndexing}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 hover:bg-indigo-900/60 text-slate-400 hover:text-indigo-300 border border-slate-700 shrink-0 flex items-center gap-1"
                        >
                          <RefreshCw className={`w-2.5 h-2.5 ${isIndexing ? 'animate-spin' : ''}`} />
                          <span>Index</span>
                        </button>
                      </div>
                    );
                  })}
                  {filteredDocuments.length === 0 && (
                    <div className="text-center py-3 text-xs text-slate-500">
                      No documents found.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
          {indexSuccessMsg && (
            <div className="mt-1.5 text-[11px] text-emerald-400 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" />
              <span>{indexSuccessMsg}</span>
            </div>
          )}
        </div>

        {/* Conversation History List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wider px-2 py-1 mb-1">
            Recent Threads
          </div>
          {conversations.length === 0 ? (
            <div className="text-center py-8 text-xs text-slate-500">
              No conversations yet. Ask a question to start.
            </div>
          ) : (
            conversations.map((conv) => {
              const isActive = conv.id === activeConversationId;
              return (
                <div
                  key={conv.id}
                  onClick={() => handleSelectConversation(conv.id)}
                  className={`group flex items-center justify-between px-3 py-2.5 rounded-lg text-xs cursor-pointer transition-all ${
                    isActive
                      ? 'bg-indigo-600/20 border border-indigo-500/40 text-indigo-100 font-medium'
                      : 'hover:bg-slate-800/60 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <div className="flex items-center space-x-2 truncate mr-2">
                    <BookOpen className="w-3.5 h-3.5 shrink-0 opacity-70" />
                    <span className="truncate">{conv.title || 'Conversation'}</span>
                  </div>
                  <button
                    onClick={(e) => handleDeleteConversation(conv.id, e)}
                    className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-rose-400 p-1 transition-opacity"
                    title="Delete conversation"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* RIGHT MAIN PANEL: Active Chat Stream */}
      <div className="flex-1 flex flex-col bg-slate-950">
        {/* Chat Header */}
        <div className="h-14 border-b border-slate-800 px-6 flex items-center justify-between bg-slate-900/30">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-indigo-950 border border-indigo-500/30 text-indigo-400">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-sm font-semibold text-slate-200">Financial Document QA Assistant</h1>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-medium">
                  pgvector + Hybrid Search
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Grounded source citations & deterministic mathematical calculations
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2 text-xs text-slate-400">
            <span className="px-2 py-1 rounded bg-slate-800/80 border border-slate-700/60">
              Defends against prompt injection
            </span>
          </div>
        </div>

        {/* Message Feed */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="max-w-2xl mx-auto py-12 text-center space-y-4">
              <div className="w-12 h-12 rounded-2xl bg-indigo-900/30 border border-indigo-500/30 flex items-center justify-center mx-auto text-indigo-400">
                <Bot className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-slate-200">
                  Ask Any Question About Your Financial Documents
                </h2>
                <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
                  DocuFin combines semantic chunk embeddings with deterministic financial rule aggregation. Factual claims include source citations and page numbers.
                </p>
              </div>

              {/* Suggestion Chips */}
              <div className="pt-4">
                <p className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold mb-2">
                  Sample Financial Questions
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {suggestedQuestions.map((item, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSendMessage(item.query)}
                      className="px-3 py-1.5 text-xs bg-slate-900 hover:bg-indigo-950/70 text-slate-300 hover:text-indigo-200 border border-slate-800 hover:border-indigo-500/50 rounded-full transition-all flex items-center space-x-1.5 shadow-sm"
                    >
                      <Sparkles className="w-3 h-3 text-indigo-400" />
                      <span>{item.query}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col ${
                  msg.sender === 'user' ? 'items-end' : 'items-start'
                }`}
              >
                {/* Message Bubble */}
                <div
                  className={`max-w-2xl rounded-2xl px-5 py-3.5 shadow-md ${
                    msg.sender === 'user'
                      ? 'bg-indigo-600 text-white rounded-br-sm'
                      : 'bg-slate-900/90 border border-slate-800 text-slate-200 rounded-bl-sm'
                  }`}
                >
                  {/* Assistant Badges: Deterministic vs Insufficient Info */}
                  {msg.sender === 'assistant' && (
                    <div className="flex flex-wrap items-center gap-2 mb-2 pb-2 border-b border-slate-800/80">
                      {msg.isNumericalAggregation && (
                        <div className="flex items-center space-x-1.5 text-[11px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-medium">
                          <Calculator className="w-3 h-3" />
                          <span>Deterministic Calculation (DB-Validated)</span>
                        </div>
                      )}

                      {msg.hasSufficientEvidence === false && (
                        <div className="flex items-center space-x-1.5 text-[11px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 font-medium">
                          <AlertTriangle className="w-3 h-3" />
                          <span>Insufficient Evidence</span>
                        </div>
                      )}

                      {msg.tokensUsed !== undefined && (
                        <span className="text-[10px] text-slate-500 ml-auto">
                          Tokens: {msg.tokensUsed}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Message Text */}
                  <div className="text-sm whitespace-pre-wrap leading-relaxed">
                    {msg.text}
                  </div>

                  {/* Citation Cards */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-4 pt-3 border-t border-slate-800/90 space-y-2">
                      <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 flex items-center space-x-1">
                        <FileText className="w-3 h-3 text-indigo-400" />
                        <span>Source Citations ({msg.citations.length})</span>
                      </div>
                      <div className="grid grid-cols-1 gap-2">
                        {msg.citations.map((citation, cIdx) => (
                          <div
                            key={cIdx}
                            className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 hover:border-indigo-500/40 transition-colors"
                          >
                            <div className="flex items-center justify-between text-xs mb-1">
                              <span className="font-medium text-indigo-300 truncate max-w-xs">
                                {citation.document_title || citation.document_filename}
                              </span>
                              <span className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] font-mono text-slate-300 border border-slate-700">
                                Page {citation.page_number}
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-400 italic line-clamp-3 bg-slate-900/40 p-1.5 rounded border border-slate-800/40">
                              "{citation.excerpt}"
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Timestamp */}
                <span className="text-[10px] text-slate-500 mt-1 px-1">
                  {new Date(msg.createdAt).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </div>
            ))
          )}

          {isLoading && (
            <div className="flex items-start space-x-3">
              <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 flex items-center space-x-3 text-slate-300 text-sm">
                <RefreshCw className="w-4 h-4 animate-spin text-indigo-400" />
                <span>Searching document chunks and verifying citations...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Bottom Input Area */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/50">
          {/* Suggestion Chips when in active chat */}
          {messages.length > 0 && (
            <div className="flex items-center space-x-1.5 overflow-x-auto pb-2 mb-2 scrollbar-none">
              <span className="text-[10px] uppercase font-bold text-slate-500 shrink-0">
                Quick:
              </span>
              {suggestedQuestions.map((item, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendMessage(item.query)}
                  className="px-2.5 py-1 text-[11px] bg-slate-800/70 hover:bg-slate-700 text-slate-300 rounded-full whitespace-nowrap transition-colors shrink-0"
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-center space-x-2"
          >
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder={
                selectedDocIds.length > 0
                  ? `Ask question scoped to ${selectedDocIds.length} document(s)...`
                  : 'Ask a question across all documents (e.g. invoice total, overdue, closing balance)...'
              }
              className="flex-1 bg-slate-900 border border-slate-700/80 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors shadow-inner"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={!inputQuery.trim() || isLoading}
              className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-600 text-white rounded-xl text-sm font-medium transition-colors flex items-center space-x-1.5 shadow-md shadow-indigo-900/20"
            >
              <span>Ask</span>
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
