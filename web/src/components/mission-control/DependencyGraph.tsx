import { useId } from 'react';
import { taskKey } from './model';
import type { MissionTask } from './types';

/** Overview only: the complete, keyboard-operable relation list stays in task cards. */
export function DependencyGraph({ tasks, selectedKey }: { tasks: MissionTask[]; selectedKey?: string }) {
  const markerId = useId().replace(/:/g, '');
  const nodes = tasks.slice(0, 12);
  const positions = new Map(nodes.map((task, index) => [task.key, { x: 12 + (index % 3) * 250, y: 18 + Math.floor(index / 3) * 90 }]));
  const edges = nodes.flatMap((task) => task.parentIds.flatMap((parentId) => {
    const parent = positions.get(taskKey(task.runId, parentId));
    const child = positions.get(task.key);
    return parent && child && parentId !== task.id ? [{ key: `${task.key}-${parentId}`, parent, child }] : [];
  }));
  if (edges.length === 0) return null;
  return <details className="mc-graph">
    <summary>Mapa de relações declaradas · {edges.length} conexões</summary>
    <p className="mc-caption">Seta da tarefa de origem para a tarefa derivada. A direção não representa aprovação.</p>
    <div className="mc-graph-scroll" tabIndex={0} role="region" aria-label="Mapa de dependências com rolagem horizontal">
      <svg viewBox={`0 0 750 ${Math.ceil(nodes.length / 3) * 90 + 12}`} role="img" aria-label="Relações entre as tarefas recebidas">
        <title>Relações declaradas pelos eventos</title>
        <desc>As mesmas relações estão descritas, com navegação por teclado, abaixo de cada card de tarefa. A posição dos nós não indica ordem de execução.</desc>
        <defs><marker id={markerId} markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L6,3 L0,6" fill="none" stroke="currentColor" /></marker></defs>
        {edges.map(({ key, parent, child }) => <path key={key} className="mc-graph-edge" d={`M${parent.x + 105},${parent.y + 48} C${parent.x + 105},${parent.y + 70} ${child.x + 105},${child.y - 12} ${child.x + 105},${child.y}`} fill="none" markerEnd={`url(#${markerId})`} />)}
        {nodes.map((task) => {
          const point = positions.get(task.key)!;
          return <g key={task.key} className={selectedKey === task.key ? 'mc-graph-node mc-graph-node-selected' : 'mc-graph-node'}>
            <title>{`${task.runId} / ${task.id}: ${task.actors.join(', ')}`}</title>
            <rect x={point.x} y={point.y} width="210" height="48" rx="5" />
            <text x={point.x + 10} y={point.y + 20}>{task.id.length > 25 ? `${task.id.slice(0, 24)}…` : task.id}</text>
            <text className="mc-graph-actor" x={point.x + 10} y={point.y + 36}>{task.actors.join(' · ').slice(0, 30)}</text>
          </g>;
        })}
      </svg>
    </div>
    {tasks.length > nodes.length ? <p className="mc-caption">Visão compacta das primeiras {nodes.length} tarefas; todas as relações permanecem na lista.</p> : null}
  </details>;
}
