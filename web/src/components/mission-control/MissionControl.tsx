import { useId, useMemo, useState } from 'react';
import { buildMission, observedCaseRole, taskKey, utcTime } from './model';
import { DependencyGraph } from './DependencyGraph';
import type { AgentEventStatus, MissionControlProps } from './types';
import './mission-control.css';

export type { AgentEvent, AgentEventStatus, AgentEventType, MissionControlProps } from './types';

const STATUS_LABEL: Record<AgentEventStatus, string> = {
  queued: 'Na fila', running: 'Em andamento', completed: 'Encerrada', failed: 'Falhou', blocked: 'Bloqueada',
};
const EVENT_LABEL: Record<string, string> = {
  'task.created': 'Tarefa registrada', 'task.started': 'Execução iniciada',
  'tool.called': 'Consulta iniciada', 'evidence.found': 'Evidência encontrada',
  'handoff.requested': 'Transferência solicitada', 'task.completed': 'Tarefa encerrada',
  'task.failed': 'Falha registrada', 'decision.proposed': 'Decisão proposta', 'review.required': 'Revisão solicitada',
};
const PAGE_SIZE = 30;

export function MissionControl({ events, loading = false }: MissionControlProps) {
  const headingId = useId();
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [limit, setLimit] = useState(PAGE_SIZE);
  const mission = useMemo(() => buildMission(events), [events]);
  const selected = selectedKey ? mission.taskMap.get(selectedKey) : undefined;
  const scopedEvents = selected ? selected.events : mission.events;
  const visibleEvents = scopedEvents.slice(-limit).reverse();
  const evidence = selected ? selected.evidenceRefs : [...new Set(mission.events.flatMap((event) => event.evidence_refs).filter(Boolean))];
  const latest = mission.events.at(-1);
  const chooseTask = (key: string | null) => { setSelectedKey(key); setLimit(PAGE_SIZE); };

  return (
    <section className="mc" aria-labelledby={headingId}>
      <header className="mc-header">
        <div><p className="mc-eyebrow">Histórico do fechamento</p><h2 id={headingId}>Atividade do fechamento</h2>
          <p className="mc-description">Acompanhe as etapas e consulte os documentos de cada análise.</p></div>
        <div className="mc-sync" role="status" aria-live="polite">
          <span className={`mc-dot${loading ? ' mc-dot-loading' : ''}`} aria-hidden="true" />
          {loading ? 'Atualizando histórico…' : `${mission.events.length} registros`}
        </div>
      </header>

      <div className="mc-stats" aria-label="Estado das tarefas registradas">
        <div><strong>{mission.tasks.length}</strong><span>Etapas registradas</span></div>
        <div><strong>{mission.counts.running}</strong><span>Em andamento</span></div>
        <div><strong>{mission.counts.completed}</strong><span>Encerradas</span></div>
        <div><strong>{mission.counts.blocked + mission.counts.failed}</strong><span>Precisam de atenção</span></div>
      </div>

      {mission.rejected > 0 ? <p className="mc-notice" role="alert">{mission.rejected} registro(s) não puderam ser exibidos. O histórico pode estar incompleto.</p> : null}
      {mission.duplicates > 0 ? <details className="mc-caption"><summary>Registros atualizados</summary>{mission.duplicates} repetição(ões) consolidadas na versão mais recente.</details> : null}

      {mission.events.length === 0 ? (
        <div className="mc-empty"><span className="mc-empty-symbol" aria-hidden="true">↳</span>
          <h3>{loading ? 'Aguardando o primeiro registro' : 'Nenhuma atividade registrada'}</h3>
          <p>{loading ? 'As etapas aparecerão conforme o fechamento avançar.' : 'Inicie um fechamento para acompanhar as etapas e suas evidências.'}</p>
        </div>
      ) : (
        <>
          <DependencyGraph tasks={mission.tasks} selectedKey={selected?.key} />
          <div className="mc-workspace">
            <div className="mc-tasks">
              <div className="mc-section-heading"><h3>Etapas do fechamento</h3><span>{mission.tasks.length}</span></div>
              <p className="mc-caption">Selecione uma etapa para consultar seu histórico.</p>
              <ul className="mc-task-list">
                {mission.tasks.map((task, index) => (
                  <li key={task.key}>
                    <button type="button" className={`mc-task${selected?.key === task.key ? ' mc-task-selected' : ''}`} aria-pressed={selected?.key === task.key} onClick={() => chooseTask(selected?.key === task.key ? null : task.key)}>
                      <span className="mc-task-top"><span className="mc-task-identity"><strong>{observedCaseRole(task.actors) || `Etapa ${index + 1}`}</strong></span><span className={`mc-status mc-status-${task.lifecycleObserved ? task.status : 'unknown'}`}>
                        {task.lifecycleObserved ? STATUS_LABEL[task.status] : 'Estado não informado'}</span></span>
                      <span className="mc-task-summary">{task.latest.summary}</span>
                      <span className="mc-task-foot"><span>{task.events.length} registros · {task.evidenceRefs.length} referências</span>{task.reviewRequired ? <span className="mc-review">Revisão solicitada</span> : null}</span>
                    </button>
                    <details className="mc-event-evidence"><summary>Identificação da etapa</summary><div className="mc-task-id">{task.id}</div><div className="mc-task-actors">{task.actors.join(' · ')}</div><div className="mc-run">{task.runId}</div></details>
                    {task.parentIds.length > 0 ? <ul className="mc-dependencies" aria-label={`Etapas relacionadas à etapa ${index + 1}`}>
                      {task.parentIds.map((id) => {
                        const parent = mission.taskMap.get(taskKey(task.runId, id));
                        return <li key={id}><span aria-hidden="true">↳</span> Origem: {parent ? <button type="button" onClick={() => chooseTask(parent.key)}>{observedCaseRole(parent.actors) || `Etapa ${mission.tasks.findIndex(item => item.key === parent.key) + 1}`}</button> : <span className="mc-unavailable">Etapa anterior sem registro disponível</span>}</li>;
                      })}
                    </ul> : null}
                  </li>
                ))}
              </ul>
            </div>

            <div className="mc-trace">
              <div className="mc-section-heading"><h3>{selected ? `Histórico · ${observedCaseRole(selected.actors) || 'etapa selecionada'}` : 'Linha do tempo'}</h3>{selected ? <button className="mc-clear" type="button" onClick={() => chooseTask(null)}>Ver todas</button> : null}</div>
              <p className="mc-caption">Mais recentes primeiro · horários em UTC. Registros sem horário aparecem no início.</p>
              <ol className="mc-timeline">
                {visibleEvents.map((event) => (
                  <li key={JSON.stringify([event.run_id, event.id])} className={`mc-event mc-event-${event.status}`}>
                    <span className="mc-event-marker" aria-hidden="true" />
                    <div className="mc-event-heading"><span>{EVENT_LABEL[event.type] ?? event.type}</span><time dateTime={Number.isFinite(Date.parse(event.timestamp)) ? event.timestamp : undefined}>{utcTime(event.timestamp)}</time></div>
                    <p>{event.summary}</p>
                    <details className="mc-event-meta"><summary>Detalhes do registro</summary><span>{event.actor}</span><span>{event.task_id}</span><span>{event.id}</span></details>
                    {event.evidence_refs.length > 0 ? <details className="mc-event-evidence"><summary>{event.evidence_refs.length} fonte(s) deste registro</summary><ul>{event.evidence_refs.map((ref, index) => <li key={`${index}-${ref}`}><code>{ref}</code></li>)}</ul></details> : null}
                  </li>
                ))}
              </ol>
              {scopedEvents.length > limit ? <button className="mc-more" type="button" onClick={() => setLimit((value) => value + PAGE_SIZE)}>Mostrar mais {Math.min(PAGE_SIZE, scopedEvents.length - limit)} registros</button> : null}
              <section className="mc-evidence" aria-label="Referências de evidência">
                <div className="mc-section-heading"><h3>Documentos e evidências</h3><span>{evidence.length}</span></div>
                {evidence.length > 0 ? <ul>{evidence.map((ref) => <li key={ref}><span aria-hidden="true">↗</span><code>{ref}</code></li>)}</ul> : <p className="mc-caption">Nenhuma referência registrada{selected ? ' nesta etapa' : ''}.</p>}
              </section>
            </div>
          </div>
          <footer className="mc-footer"><span>Último registro: {latest ? utcTime(latest.timestamp) : 'não disponível'}</span><span>A aprovação do fechamento cabe a Helena.</span></footer>
        </>
      )}
    </section>
  );
}

export default MissionControl;
