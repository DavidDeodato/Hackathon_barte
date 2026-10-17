"""Public conversation export with explicit omission markers; raw sessions stay local."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ('# AGENTS.md instructions', '<INSTRUCTIONS>', '<environment_context>', '<heartbeat>',
           '<codex_delegation>', 'MEMORY_SUMMARY BEGINS', '<system_instructions>', '<developer_instructions>')
PATTERNS = (
    (r'(?i)(token\s*["\x27]?\s*[:=]\s*["\x27]?\s*)[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', r'\1[CREDENCIAL_REMOVIDA]'),
    (r"\bsk-[A-Za-z0-9_-]{16,}", "[CREDENCIAL_REMOVIDA]"),
    (r"\b(?:ghp|github_pat|gho|ghu|ghs)_[A-Za-z0-9_]{16,}", "[CREDENCIAL_REMOVIDA]"),
    (r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b", "[CREDENCIAL_REMOVIDA]"),
    (r"(?i)Bearer\s+[A-Za-z0-9._-]{20,}", "Bearer [CREDENCIAL_REMOVIDA]"),
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[EMAIL_REMOVIDO]"),
    (r'(?i)C:[/\\]Users[/\\][^/\\\s"<>]+', 'C:/Users/[USUARIO]'),
    (r'(?is)<oai-mem-citation>.*?</oai-mem-citation>', '[MEMORIA_PRIVADA_OMITIDA]'),
    (r"(?i)(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s<>]+", "[CONEXAO_PRIVADA_REMOVIDA]"),
    (r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b", "[CREDENCIAL_REMOVIDA]"),
)

def local_secrets(root):
    values = set()
    for path in [root/'.env', *sorted((root/'.secrets/env-catalog').glob('*.env'))]:
        if not path.is_file(): continue
        for line in path.read_text(encoding='utf-8-sig', errors='replace').splitlines():
            name, sep, value = line.partition('=')
            if sep and re.search('TOKEN|SECRET|PASSWORD|API_KEY|ACCESS_KEY|PRIVATE_KEY', name, re.I):
                value = value.strip().strip(chr(34)+chr(39))
                if len(value)>=8 and not value.startswith(('$','your_','<')): values.add(value)
    path = root/'.secrets/lastro-api-token.txt'
    if path.is_file() and path.read_text().strip(): values.add(path.read_text().strip())
    return values

def clean_text(text, secrets=()):
    for secret in sorted(secrets, key=len, reverse=True): text = text.replace(secret, '[CREDENCIAL_REMOVIDA]')
    for pattern, replacement in PATTERNS: text = re.sub(pattern, replacement, text)
    return text

def classify(record, position, secrets=()):
    if record.get('type')!='response_item': return None
    p = record.get('payload', {}); role = p.get('role'); kind = p.get('type')
    row = dict(source_record=position, timestamp=record.get('timestamp'))
    reason = ('private_reasoning' if kind in ('reasoning','compaction') else
              'system_or_developer' if role in ('system','developer') else
              'tool_or_internal_record' if kind!='message' or role not in ('user','assistant') else
              'private_or_unknown_phase' if role=='assistant' and p.get('phase') not in ('commentary','final_answer') else None)
    if reason: return dict(row, record_kind='omission', reason=reason, content=['[REGISTRO_OMITIDO: '+reason+']'])
    parts, omissions, redacted = [], [], False
    for part in p.get('content', []):
        text = part.get('text','')
        reason = ('non_text_attachment' if part.get('type') not in ('input_text','output_text','text') else
                  'runtime_instructions_or_internal_message' if any(x in text for x in RUNTIME) else
                  'private_key' if '-----BEGIN ' in text and 'PRIVATE KEY-----' in text else None)
        if reason: omissions.append(reason); parts.append('[PARTE_OMITIDA: '+reason+']')
        else:
            cleaned = clean_text(text,secrets); redacted |= cleaned!=text; parts.append(cleaned)
    return dict(row, record_kind='message', role=role, phase=p.get('phase'), content=parts, omitted_parts=omissions, redacted=redacted)

def export(session_dir, destination, root=ROOT):
    destination.mkdir(parents=True,exist_ok=True); secrets=local_secrets(root); sessions=[]; omissions=[]
    for path in sorted(session_dir.glob('*.jsonl')):
        snapshot=path.read_bytes()
        try: metadata=json.loads(snapshot.splitlines()[0])
        except (ValueError,IndexError): continue
        if Path(metadata.get('payload',{}).get('cwd','')).resolve()!=root.resolve(): continue
        rows=[]; counts=Counter()
        for position,line in enumerate(snapshot.splitlines(),1):
            try: record=json.loads(line)
            except ValueError: counts['invalid_or_partial_lines']+=1; continue
            row=classify(record,position,secrets)
            if row is None: counts['non_response_metadata_excluded']+=1; continue
            rows.append(row); counts[row['record_kind']]+=1
            if row['record_kind']=='message':
                counts['visible_messages' if any(part.strip() and not part.startswith('[PARTE_OMITIDA:') for part in row['content']) else 'fully_omitted_messages']+=1
            if row.get('redacted'): counts['redacted_messages']+=1
            for reason in ([row['reason']] if row['record_kind']=='omission' else row['omitted_parts']):
                counts['omission:'+reason]+=1; omissions.append(dict(session=path.name,source_record=position,reason=reason))
        data=''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows).encode()
        (destination/path.name).write_bytes(data)
        sessions.append(dict(file=path.name,sha256=hashlib.sha256(data).hexdigest(),source_snapshot_sha256=hashlib.sha256(snapshot).hexdigest(),counts=dict(counts)))
    data=''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in omissions).encode()
    (destination/'omissions.jsonl').write_bytes(data)
    manifest=dict(schema_version=2,generated_at=datetime.now(timezone.utc).isoformat(),scope='Textos públicos reais com omissões explícitas; não é exportação integral.',
                  omissions_index=dict(file='omissions.jsonl',records=len(omissions),sha256=hashlib.sha256(data).hexdigest()),sessions=sessions)
    (destination/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-dir',type=Path,required=True)
    parser.add_argument('--destination',type=Path,default=ROOT/'PROMPTS/conversas_publicas')
    args=parser.parse_args(); manifest=export(args.session_dir,args.destination)
    print(json.dumps(dict(sessions=len(manifest['sessions']),visible_messages=sum(s['counts'].get('visible_messages',0) for s in manifest['sessions']),omissions=manifest['omissions_index']['records'])))
