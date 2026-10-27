export type DocumentType = 'INVOICE' | 'BANK_STATEMENT' | 'EXPENSE_REPORT' | 'UNKNOWN';

export type ExtractionMethod = 'LLM' | 'DETERMINISTIC_FALLBACK' | 'HYBRID' | 'MANUAL';

export type ExtractionStatus = 'EXTRACTED' | 'REVIEW_REQUIRED' | 'APPROVED' | 'REJECTED';

export interface FieldMetadata {
  value: any;
  raw_value?: string | null;
  source_page?: number | null;
  extraction_method: string;
  confidence: number;
}

export interface InvoiceLineItem {
  description?: string | null;
  quantity?: number | null;
  unit_price?: number | null;
  total_price?: number | null;
}

export interface InvoiceData {
  schema_version?: string;
  invoice_number?: string | null;
  vendor?: string | null;
  invoice_date?: string | null;
  due_date?: string | null;
  currency?: string | null;
  subtotal?: number | null;
  tax?: number | null;
  total?: number | null;
  line_items?: InvoiceLineItem[];
}

export interface BankTransaction {
  transaction_date?: string | null;
  description?: string | null;
  debit?: number | null;
  credit?: number | null;
  running_balance?: number | null;
}

export interface StatementPeriod {
  start_date?: string | null;
  end_date?: string | null;
  raw_period?: string | null;
}

export interface BankStatementData {
  schema_version?: string;
  statement_period?: StatementPeriod | string | null;
  opening_balance?: number | null;
  closing_balance?: number | null;
  transactions?: BankTransaction[];
  transaction_dates?: string[];
  descriptions?: string[];
  debits?: number[];
  credits?: number[];
  running_balances?: number[];
}

export interface ExpenseItem {
  expense_date?: string | null;
  merchant?: string | null;
  category?: string | null;
  amount?: number | null;
  currency?: string | null;
  description?: string | null;
}

export interface ExpenseReportData {
  schema_version?: string;
  expense_date?: string | null;
  merchant?: string | null;
  category?: string | null;
  amount?: number | null;
  currency?: string | null;
  description?: string | null;
  expenses?: ExpenseItem[];
}

export interface DocumentExtractionResponse {
  id: string;
  document_id: string;
  organization_id: string;
  document_type: DocumentType;
  classification_confidence: number;
  schema_version: string;
  extracted_data: Record<string, any>;
  field_metadata: Record<string, FieldMetadata>;
  extraction_method: string;
  llm_provider?: string | null;
  llm_model?: string | null;
  token_usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    estimated_cost_usd: number;
  } | null;
  confidence_score: number;
  needs_review: boolean;
  review_reasons: string[];
  is_valid: boolean;
  validation_errors: (string | ValidationRuleResult)[];
  status: ExtractionStatus;
  created_at: string;
  updated_at: string;
}

export interface DocumentExtractionUpdate {
  extracted_data: Record<string, any>;
  status?: string | null;
  analyst_notes?: string | null;
}

export interface ReviewQueueItem {
  extraction_id: string;
  document_id: string;
  document_title: string;
  document_type: string;
  filename: string;
  status: string;
  confidence_score: number;
  review_reasons: string[];
  created_at: string;
  total_amount?: number | null;
  currency?: string | null;
}

export type ValidationSeverity = 'ERROR' | 'WARNING' | 'INFO';

export interface ValidationRuleResult {
  rule_id: string;
  rule_name: string;
  severity: ValidationSeverity;
  is_passed: boolean;
  explanation: string;
  affected_fields: string[];
}

export interface ValidationSummary {
  is_valid: boolean;
  has_warnings: boolean;
  error_count: number;
  warning_count: number;
  info_count: number;
  results: ValidationRuleResult[];
}

export interface ValidationRunResponse {
  id: string;
  document_id: string;
  extraction_id?: string | null;
  organization_id: string;
  triggered_by: string;
  is_valid: boolean;
  error_count: number;
  warning_count: number;
  info_count: number;
  results: ValidationRuleResult[];
  created_at: string;
}
