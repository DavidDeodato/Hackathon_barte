import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import MissionControl from './MissionControl';
import { DEMO_EVENTS } from './demo-events';
import type { AgentEvent } from './types';

function Preview() {
  const [mode, setMode] = useState<'demo' | 'empty' | 'loading' | 'long' | 'invalid'>('demo');
  const events = mode === 'invalid' ? [...DEMO_EVENTS, { ...DEMO_EVENTS[0], id: 'bad-payload', type: 'invented.success' } as unknown as AgentEvent] : mode === 'demo' ? DEMO_EVENTS : mode === 'long' ? Array.from({ length: 70 }, (_, index) => ({ ...DEMO_EVENTS[4], id: `volume-${index}`, timestamp: new Date(Date.UTC(2026, 9, 17, 16, 0, index)).toISOString() })) : [];
  return <main style={{ maxWidth: 1140, margin: '0 auto', padding: 20 }}>
    <h1 style={{ fontSize: 22 }}>MOTION · demonstração isolada</h1>
    <p>Fixture inventada para validar a interface. Nenhum fechamento ou agente está sendo executado.</p>
    <nav aria-label="Cenários da demonstração" style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBlock: 18 }}>
      {([['demo', 'Eventos demonstrativos'], ['empty', 'Sem eventos'], ['loading', 'Carregando'], ['long', '70 eventos'], ['invalid', 'Payload inválido']] as const).map(([value, label]) => <button key={value} onClick={() => setMode(value)} aria-pressed={mode === value}>{label}</button>)}
    </nav>
    <MissionControl events={events} loading={mode === 'loading'} />
  </main>;
}

document.body.style.cssText = 'margin:0;background:#f6f7f4;color:#132b2a;font-family:Segoe UI,Arial,sans-serif';
createRoot(document.getElementById('root')!).render(<Preview />);
