import { useId } from 'react';
import type { BatchSelectorProps } from './types';

export function BatchSelector({ batches, value, onChange, disabled = false, loading = false }: BatchSelectorProps) {
  const id = useId();
  return <label className="dw-field" htmlFor={id}><span>Conjunto de documentos</span><select id={id} aria-label="Conjunto de documentos" value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled || loading || batches.length === 0}>
    <option value="">{loading ? 'Carregando conjuntos…' : batches.length ? 'Selecione um conjunto' : 'Nenhum conjunto recebido'}</option>
    {batches.map((batch) => <option key={batch.id} value={batch.id}>{batch.name}{batch.period ? ` · ${batch.period}` : ''}</option>)}
  </select></label>;
}

export default BatchSelector;
