import { DOCUMENT_ROLES } from './types';
import type { OriginalDocument } from './types';

export function selectionIssues(documents: OriginalDocument[]): string[] {
  if (!documents.length) return ['Selecione os arquivos que vão compor este fechamento.'];
  const issues: string[] = [];
  const unusable = documents.filter((doc) => !doc.role || doc.media_type === 'application/pdf');
  if (unusable.length) issues.push('Há documentos de apoio ou sem papel financeiro na seleção. Defina o papel ou retire-os do processamento.');
  for (const role of DOCUMENT_ROLES) {
    const count = documents.filter((doc) => doc.role === role.value).length;
    if (role.required && count === 0) issues.push(`Falta selecionar: ${role.label}.`);
    if (count > 1) issues.push(`Selecione uma única versão para: ${role.label}.`);
  }
  return issues;
}

export function formatBytes(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : bytes < 1024 * 1024 ? `${(bytes / 1024).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} KB` : `${(bytes / (1024 * 1024)).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} MB`;
}
