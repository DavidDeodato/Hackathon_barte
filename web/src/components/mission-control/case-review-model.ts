import type { CaseReviewResult, CaseReviewRole } from './case-review-types';

export const CASE_ROLES = ['investigator', 'critic'] as const;
export const CASE_ROLE_LABEL = { investigator: 'Investigador', critic: 'Crítico' } as const;
export const strings = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0) : [];

export function describeRole(role: CaseReviewRole | undefined, mode?: string) {
  if (mode === 'deterministic') return { label: 'Não executado · modo determinístico', tone: 'neutral', showContent: false };
  if (!role) return { label: 'Sem registro recebido', tone: 'neutral', showContent: false };
  if (role.executed !== true || role.status === 'not_executed') return { label: 'Não executado', tone: 'neutral', showContent: false };
  if (role.status === 'failed') return { label: 'Execução interrompida', tone: 'danger', showContent: true };
  if (role.status === 'needs_evidence') return { label: 'Evidência adicional necessária', tone: 'warning', showContent: true };
  if (role.status === 'review_required') return { label: 'Observações preparadas · revisão humana', tone: 'info', showContent: true };
  return { label: 'Estado do papel não reconhecido', tone: 'warning', showContent: false };
}

export function inspectCaseReview(result: CaseReviewResult | null) {
  const roles = Array.isArray(result?.roles) ? result.roles.filter((role) => role && typeof role.role === 'string') : [];
  const reasons: string[] = [];
  if (result && !['deterministic', 'llm', 'replay'].includes(result.mode ?? '')) reasons.push('Modo da revisão fora do contrato ou ausente. Conteúdo dos papéis ocultado.');
  if (result && !['review_required', 'needs_evidence', 'failed'].includes(result.status ?? '')) reasons.push('Estado do resultado fora do contrato. Conteúdo dos papéis ocultado.');
  if (result?.approved === true) reasons.push('O resultado declara aprovação fora do contrato. Não use este parecer para encerrar o caso.');
  if (result?.applied_to_calculation === true) reasons.push('O resultado declara alteração financeira fora do contrato. Confira a fonte antes de usar o parecer.');
  if (result && result.packet_unchanged !== true) reasons.push('A preservação do pacote não foi confirmada. Parecer sem vínculo confiável com a versão financeira.');
  if (result?.packet?.case_id && result.case_id && result.packet.case_id !== result.case_id) reasons.push('O caso do pacote diverge do caso da revisão. Conteúdo do parecer ocultado.');
  for (const key of CASE_ROLES) if (roles.filter((role) => role.role === key).length > 1) reasons.push(`Mais de um registro para o papel ${CASE_ROLE_LABEL[key]}; conteúdo ambíguo ocultado.`);
  return {
    roles,
    reasons,
    safeToShowContent: reasons.length === 0,
    unknownRoles: roles.filter((role) => !(CASE_ROLES as readonly string[]).includes(role.role)).length,
  };
}
