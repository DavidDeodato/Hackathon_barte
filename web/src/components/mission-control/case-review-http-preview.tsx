// Isolated QA entry, no fixtures. Only GET existing review + its own recorded events through the local proxy.
import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import CaseReviewTrace from './CaseReviewTrace';
import type { CaseReviewResult } from './case-review-types';
import type { AgentEvent } from './types';

function Preview() {
  const [result, setResult] = useState<CaseReviewResult | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const reviewId = new URLSearchParams(window.location.search).get('review_id') ?? '';
  useEffect(() => {
    const abort = new AbortController();
    if (!/^[a-zA-Z0-9-]{1,100}$/.test(reviewId)) { setError('Informe um review_id existente e válido. Nenhuma revisão é criada por esta página.'); setLoading(false); return; }
    const get = async (suffix: string) => {
      const response = await fetch(`/api/case-reviews/${encodeURIComponent(reviewId)}${suffix}`, { signal: abort.signal });
      if (!response.ok) throw new Error(`Consulta da revisão: HTTP ${response.status}. Nenhum resultado foi substituído por demonstração.`);
      return response.json();
    };
    void Promise.all([get(''), get('/events')]).then(([review, feed]) => {
      if (abort.signal.aborted) return;
      if (review.review_id !== reviewId || !Array.isArray(feed.events)) throw new Error('Envelope da revisão/eventos fora do contrato.');
      setResult(review.result ?? null); setEvents(feed.events);
    }).catch((reason: unknown) => { if (!abort.signal.aborted) setError(reason instanceof Error ? reason.message : 'Consulta indisponível.'); }).finally(() => { if (!abort.signal.aborted) setLoading(false); });
    return () => abort.abort();
  }, [reviewId]);
  return <main style={{ maxWidth: 1180, margin: '0 auto', padding: 24 }}><h1 style={{ fontSize: 21 }}>Verificação local · registro existente da API</h1><p>Somente leitura. Esta página não cria revisão, chama modelo ou aprova o caso.</p><p style={{ marginBlock: 16 }}><code>{reviewId || 'review_id ausente'}</code></p><CaseReviewTrace result={result} events={events} loading={loading} error={error} /></main>;
}
document.body.style.cssText = 'margin:0;font-family:Segoe UI,Arial,sans-serif;background:#f6f7f4;color:#132b2a';
createRoot(document.getElementById('root')!).render(<Preview />);
