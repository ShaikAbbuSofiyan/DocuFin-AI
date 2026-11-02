export interface CitationItem {
  document_id: string;
  document_filename: string;
  document_title?: string;
  page_number: number;
  excerpt: string;
  relevance_score?: number;
}

export interface ChatQueryRequest {
  query: string;
  conversation_id?: string;
  document_ids?: string[];
  max_chunks?: number;
}

export interface ChatQueryResponse {
  answer: string;
  conversation_id: string;
  query: string;
  has_sufficient_evidence: boolean;
  is_numerical_aggregation: boolean;
  aggregation_type?: string;
  citations: CitationItem[];
  tokens_used?: number;
  processing_time_ms?: number;
}

export interface ChatMessageResponse {
  id: string;
  conversation_id: string;
  sender: 'user' | 'assistant';
  message: string;
  citations: CitationItem[];
  is_numerical_aggregation: boolean;
  tokens_used?: number;
  created_at: string;
}

export interface ConversationResponse {
  id: string;
  title: string;
  document_ids: string[];
  created_at: string;
  updated_at: string;
  messages?: ChatMessageResponse[];
}
