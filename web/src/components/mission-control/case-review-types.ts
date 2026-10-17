import type { AgentEvent } from './types';

/** Read-only projection of review_case. No new HTTP fields or financial computation. */
export interface CaseReviewRole {
  role: string;
  executed?: boolean;
  status?: string;
  model_calls?: number;
  summary?: string;
  observations?: string[];
  objections?: string[];
  limitations?: string[];
  citations?: string[];
}

export interface CaseReviewEvidence {
  id: string;
  role?: string;
  kind?: string;
  source_refs?: string[];
  data?: unknown;
}

export interface CaseReviewResult {
  review_id?: string;
  case_id?: string | null;
  status?: string;
  mode?: string;
  model_called?: boolean;
  packet_unchanged?: boolean;
  integration_allowed?: boolean;
  approved?: boolean;
  applied_to_calculation?: boolean;
  packet?: { case_id?: string; source_refs?: string[] } | null;
  roles?: CaseReviewRole[];
  evidence?: CaseReviewEvidence[];
  limitations?: string[];
  events?: AgentEvent[];
}

export interface CaseReviewTraceProps {
  result: CaseReviewResult | null;
  /** Pass HTTP /case-reviews/{id}/events here; if omitted use result.events. Never both merged blindly. */
  events?: AgentEvent[];
  loading?: boolean;
  error?: string | null;
}
