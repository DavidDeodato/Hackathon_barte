export type AgentEventStatus = 'queued' | 'running' | 'completed' | 'failed' | 'blocked';

export type AgentEventType =
  | 'task.created'
  | 'task.started'
  | 'tool.called'
  | 'evidence.found'
  | 'handoff.requested'
  | 'task.completed'
  | 'task.failed'
  | 'decision.proposed'
  | 'review.required';

/** Public operational events only. Never include hidden reasoning or credentials. */
export interface AgentEvent {
  id: string;
  run_id: string;
  task_id: string;
  timestamp: string;
  actor: string;
  type: AgentEventType;
  status: AgentEventStatus;
  summary: string;
  evidence_refs: string[];
  parent_task_id?: string | null;
}

export interface MissionControlProps {
  events: AgentEvent[];
  loading?: boolean;
  context?: MissionContext;
  onNavigate?: (target: MissionNavigationTarget) => void;
}

export interface MissionContext {
  runId: string;
  period?: string;
  status?: string;
  batchId?: string;
  kind?: 'close' | 'investigation' | 'case_review' | 'comparison';
  mode?: 'live' | 'history' | 'replay';
}

export interface MissionNavigationTarget {
  kind: 'documents' | 'results' | 'case' | 'investigation' | 'evidence';
  runId: string;
  batchId?: string;
  taskId?: string;
  evidenceRef?: string;
  output?: string;
}

export interface MissionTask {
  key: string;
  id: string;
  runId: string;
  actors: string[];
  status: AgentEventStatus;
  lifecycleObserved: boolean;
  reviewRequired: boolean;
  latest: AgentEvent;
  events: AgentEvent[];
  evidenceRefs: string[];
  parentIds: string[];
}
