import type { AgentEvent, AgentEventStatus, MissionTask } from './types';

const STATUSES = new Set(['queued', 'running', 'completed', 'failed', 'blocked']);
const TYPES = new Set(['task.created', 'task.started', 'tool.called', 'evidence.found', 'handoff.requested', 'task.completed', 'task.failed', 'decision.proposed', 'review.required']);
const LIFECYCLE: Record<string, AgentEventStatus> = {
  'task.created': 'queued',
  'task.started': 'running',
  'task.completed': 'completed',
  'task.failed': 'failed',
};

export function taskKey(runId: string, taskId: string): string {
  return JSON.stringify([runId, taskId]);
}

/** Labels only explicit role actors; never infers an agent from a task name or summary. */
export function observedCaseRole(actors: readonly string[]): string | undefined {
  const roles = [actors.includes('INT:investigator') ? 'Investigador' : '', actors.includes('INT:critic') ? 'Crítico' : ''].filter(Boolean);
  return roles.length ? roles.join(' + ') : undefined;
}

function isEvent(value: unknown): value is AgentEvent {
  if (!value || typeof value !== 'object') return false;
  const event = value as Record<string, unknown>;
  return ['id', 'run_id', 'task_id', 'timestamp', 'actor', 'type', 'status', 'summary'].every(
    (key) => typeof event[key] === 'string' && (key === 'summary' || event[key] !== ''),
  ) && STATUSES.has(String(event.status)) && TYPES.has(String(event.type)) && Array.isArray(event.evidence_refs)
    && event.evidence_refs.every((ref: unknown) => typeof ref === 'string')
    && (event.parent_task_id == null || typeof event.parent_task_id === 'string');
}

/** No progress is inferred from elapsed time, actor names, tool calls or evidence counts. */
export function buildMission(events: readonly AgentEvent[]) {
  const unique = new Map<string, { event: AgentEvent; order: number }>();
  let rejected = 0;
  let duplicates = 0;
  for (const [order, event] of events.entries()) {
    if (!isEvent(event)) { rejected += 1; continue; }
    const key = JSON.stringify([event.run_id, event.id]);
    if (unique.has(key)) duplicates += 1;
    unique.set(key, { event, order });
  }
  // Unknown timestamps preserve reception order after dated events; never invent a time.
  const ordered = [...unique.values()].sort((a, b) => {
    const aTime = Date.parse(a.event.timestamp);
    const bTime = Date.parse(b.event.timestamp);
    if (Number.isFinite(aTime) && Number.isFinite(bTime)) return aTime - bTime || a.order - b.order;
    if (Number.isFinite(aTime)) return -1;
    if (Number.isFinite(bTime)) return 1;
    return a.order - b.order;
  }).map(({ event }) => event);
  const taskMap = new Map<string, MissionTask>();
  for (const event of ordered) {
    const key = taskKey(event.run_id, event.task_id);
    let task = taskMap.get(key);
    if (!task) {
      task = { key, id: event.task_id, runId: event.run_id, actors: [], status: 'queued',
        lifecycleObserved: false, reviewRequired: false, latest: event, events: [], evidenceRefs: [], parentIds: [] };
      taskMap.set(key, task);
    }
    task.events.push(event);
    task.latest = event;
    if (!task.actors.includes(event.actor)) task.actors.push(event.actor);
    for (const ref of event.evidence_refs) {
      if (ref && !task.evidenceRefs.includes(ref)) task.evidenceRefs.push(ref);
    }
    if (event.parent_task_id && !task.parentIds.includes(event.parent_task_id)) task.parentIds.push(event.parent_task_id);
    if (LIFECYCLE[event.type]) {
      task.status = event.status;
      task.lifecycleObserved = true;
    }
    if (event.type === 'review.required') {
      task.reviewRequired = true;
      // A review gate stops an active task. An already ended technical task stays ended.
      if (event.status === 'blocked' && (!task.lifecycleObserved || task.status !== 'completed')) {
        task.status = 'blocked';
        task.lifecycleObserved = true;
      }
    }
  }
  const tasks = [...taskMap.values()];
  const counts: Record<AgentEventStatus, number> = { queued: 0, running: 0, completed: 0, failed: 0, blocked: 0 };
  for (const task of tasks) if (task.lifecycleObserved) counts[task.status] += 1;
  return { events: ordered, tasks, taskMap, counts, rejected, duplicates };
}

export function utcTime(value: string): string {
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp)
    ? new Date(timestamp).toISOString().replace('T', ' ').replace(/\.\d{3}Z$/, ' UTC')
    : 'Horário inválido na fonte';
}
