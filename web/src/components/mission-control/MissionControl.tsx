import { useId, useMemo, useState } from 'react';
import { buildMission, taskKey, utcTime } from './model';
import { DependencyGraph } from './DependencyGraph';
import type { AgentEventStatus, MissionControlProps } from './types';
import './mission-control.css';

export type { AgentEvent, AgentEventStatus, AgentEventType, MissionControlProps } from './types';

const STATUS_LABEL: Record<AgentEventStatus, string> = {
  queued: 'Na fila', running: 'Em execução', completed: 'Encerrada', failed: 'Falhou', blocked: 'Bloqueada',
};
const EVENT_LABEL: Record<string, string> = {
  'task.created': 'Tarefa registrada', 'task.started': 'Execução iniciada',
  'tool.called': 'Ferramenta acionada', 'evidence.found': 'Evidência encontrada',
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
        <div><p className="mc-eyebrow">Rastro de execução</p><h2 id={headingId}>Central de agentes</h2>
          <p className="mc-description">Ações registradas, dependências e evidências do fechamento.</p></div>
        <div className="mc-sync" role="status" aria-live="polite">
          <span className={`mc-dot${loading ? ' mc-dot-loading' : ''}`} aria-hidden="true" />
          {loading ? 'Consultando eventos…' : `${mission.events.length} eventos recebidos`}
        </div>
      </header>

      <div className="mc-stats" aria-label="Estado das tarefas registradas">
        <div><strong>{mission.tasks.length}</strong><span>Tarefas observadas</span></div>
        <div><strong>{mission.counts.running}</strong><span>Em execução</span></div>
        <div><strong>{mission.counts.completed}</strong><span>Encerradas</span></div>
        <div><strong>{mission.counts.blocked + mission.counts.failed}</strong><span>Bloqueadas ou falhas</span></div>
      </div>

      {mission.rejected > 0 ? <p className="mc-notice" role="alert">{mission.rejected} evento(s) fora do contrato não exibido(s). Verifique a fonte; a visão pode estar incompleta.</p> : null}
      {mission.duplicates > 0 ? <p className="mc-caption">{mission.duplicates} repetição(ões) de ID consolidadas; exibida a última versão recebida de cada evento.</p> : null}

      {mission.events.length === 0 ? (
        <div className="mc-empty"><span className="mc-empty-symbol" aria-hidden="true">↳</span>
          <h3>{loading ? 'Aguardando o primeiro registro' : 'Nenhuma execução registrada'}</h3>
          <p>{loading ? 'Os eventos aparecerão quando a fonte responder.' : 'Execute um fechamento para acompanhar as ações. A ausência de eventos não confirma conclusão.'}</p>
        </div>
      ) : (
        <>
          <DependencyGraph tasks={mission.tasks} selectedKey={selected?.key} />
          <div className="mc-workspace">
            <div className="mc-tasks">
              <div className="mc-section-heading"><h3>Tarefas e dependências</h3><span>{mission.tasks.length}</span></div>
              <p className="mc-caption">Selecione uma tarefa para seguir seu rastro.</p>
              <ul className="mc-task-list">
                {mission.tasks.map((task) => (
                  <li key={task.key}>
                    <button type="button" className={`mc-task${selected?.key === task.key ? ' mc-task-selected' : ''}`} aria-pressed={selected?.key === task.key} onClick={() => chooseTask(selected?.key === task.key ? null : task.key)}>
                      <span className="mc-task-top"><span className="mc-task-id">{task.id}</span><span className={`mc-status mc-status-${task.lifecycleObserved ? task.status : 'unknown'}`}>
                        {task.lifecycleObserved ? STATUS_LABEL[task.status] : 'Sem estado de tarefa'}</span></span>
                      <span className="mc-task-actors">{task.actors.join(' · ')}</span>
                      <span className="mc-task-summary">{task.latest.summary}</span>
                      <span className="mc-task-foot"><span>{task.events.length} eventos · {task.evidenceRefs.length} referências</span>{task.reviewRequired ? <span className="mc-review">Revisão solicitada</span> : null}</span>
                      <span className="mc-run">Execução {task.runId}</span>
                    </button>
                    {task.parentIds.length > 0 ? <ul className="mc-dependencies" aria-label={`Dependências de ${task.id}`}>
                      {task.parentIds.map((id) => {
                        const parent = mission.taskMap.get(taskKey(task.runId, id));
                        return <li key={id}><span aria-hidden="true">↳</span> Origem: {parent ? <button type="button" onClick={() => chooseTask(parent.key)}>{id}</button> : <span>{id} <span className="mc-unavailable">(sem evento recebido)</span></span>}</li>;
                      })}
                    </ul> : null}
                  </li>
                ))}
              </ul>
              <p className="mc-caption">Relações declaradas por <code>parent_task_id</code>. Não indicam, por si só, um bloqueio ou uma aprovação.</p>
            </div>

            <div className="mc-trace">
              <div className="mc-section-heading"><h3>{selected ? `Rastro de ${selected.id}` : 'Linha do tempo'}</h3>{selected ? <button className="mc-clear" type="button" onClick={() => chooseTask(null)}>Ver todas</button> : null}</div>
              <p className="mc-caption">Mais recentes primeiro · horário UTC da fonte. Registros sem horário válido aparecem primeiro, na ordem inversa de recebimento.</p>
              <ol className="mc-timeline">
                {visibleEvents.map((event) => (
                  <li key={JSON.stringify([event.run_id, event.id])} className={`mc-event mc-event-${event.status}`}>
                    <span className="mc-event-marker" aria-hidden="true" />
                    <div className="mc-event-heading"><span>{EVENT_LABEL[event.type] ?? event.type}</span><time dateTime={Number.isFinite(Date.parse(event.timestamp)) ? event.timestamp : undefined}>{utcTime(event.timestamp)}</time></div>
                    <p>{event.summary}</p>
                    <div className="mc-event-meta"><span>{event.actor}</span><span>{event.task_id}</span><span>{event.id}</span></div>
                    {event.evidence_refs.length > 0 ? <details className="mc-event-evidence"><summary>{event.evidence_refs.length} referência(s) deste evento</summary><ul>{event.evidence_refs.map((ref, index) => <li key={`${index}-${ref}`}><code>{ref}</code></li>)}</ul></details> : null}
                  </li>
                ))}
              </ol>
              {scopedEvents.length > limit ? <button className="mc-more" type="button" onClick={() => setLimit((value) => value + PAGE_SIZE)}>Mostrar mais {Math.min(PAGE_SIZE, scopedEvents.length - limit)} eventos</button> : null}
              <section className="mc-evidence" aria-label="Referências de evidência">
                <div className="mc-section-heading"><h3>Evidências referenciadas</h3><span>{evidence.length}</span></div>
                {evidence.length > 0 ? <ul>{evidence.map((ref) => <li key={ref}><span aria-hidden="true">↗</span><code>{ref}</code></li>)}</ul> : <p className="mc-caption">Nenhuma referência registrada{selected ? ' nesta tarefa' : ''}. Conclusão sem referência exige conferência.</p>}
                <p className="mc-caption">Referências recebidas da execução. A presença de um identificador não comprova o conteúdo da fonte.</p>
              </section>
            </div>
          </div>
          <footer className="mc-footer"><span>Último registro: {latest ? utcTime(latest.timestamp) : 'não disponível'}</span><span>Execução encerrada não confirma resultado disponível nem aprovação de Helena.</span></footer>
        </>
      )}
    </section>
  );
}

export default MissionControl;
