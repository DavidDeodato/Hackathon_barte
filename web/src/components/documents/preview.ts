import Papa from 'papaparse';

export type DocumentPreview =
  | { kind: 'pdf'; url: string }
  | { kind: 'csv'; columns: string[]; rows: string[][]; encoding: string; delimiter: string; warningCount: number; limited: boolean }
  | { kind: 'unsupported' };

/** Reads the original without changing its bytes or converting IDs/money to numbers. */
export async function previewOriginal(blob: Blob, name: string, mediaType: string): Promise<DocumentPreview> {
  if (mediaType.split(';')[0] === 'application/pdf') return { kind: 'pdf', url: URL.createObjectURL(blob) };
  if (!/\.csv$/i.test(name) && !['text/csv', 'application/csv'].includes(mediaType.split(';')[0])) return { kind: 'unsupported' };
  const bytes = await blob.slice(0, 2 * 1024 * 1024).arrayBuffer();
  let text: string; let encoding = 'UTF-8';
  const signature = new Uint8Array(bytes, 0, Math.min(2, bytes.byteLength));
  try { if (signature[0] === 255 && signature[1] === 254) { text = new TextDecoder('utf-16le').decode(bytes); encoding = 'UTF-16 LE'; } else if (signature[0] === 254 && signature[1] === 255) { text = new TextDecoder('utf-16be').decode(bytes); encoding = 'UTF-16 BE'; } else text = new TextDecoder('utf-8', { fatal: true }).decode(bytes); }
  catch { text = new TextDecoder('windows-1252').decode(bytes); encoding = 'Windows-1252'; }
  const result = Papa.parse<string[]>(text, { skipEmptyLines: 'greedy', preview: 52, dynamicTyping: false });
  const data = result.data.filter(Array.isArray);
  const columns = (data.shift() ?? []).map(String);
  return { kind: 'csv', columns, rows: data.slice(0, 50).map((row) => row.map(String)), encoding, delimiter: result.meta.delimiter, warningCount: result.errors.length, limited: data.length > 50 || result.meta.truncated || blob.size > bytes.byteLength };
}

export function releasePreview(preview: DocumentPreview | null): void {
  if (preview?.kind === 'pdf') URL.revokeObjectURL(preview.url);
}
