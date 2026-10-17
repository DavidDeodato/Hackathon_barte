"""Prepare evidence packets from real existing outputs; no financial mutation."""
import json
from pathlib import Path

from test_cases import ROOT,digest
from tarvo.finance.cases import build_case_packet


def main():
    output=ROOT/'saida'
    before=digest(output)
    evidence=ROOT/'docs/agent/branches/DOM/artifacts/case_packets'
    evidence.mkdir(parents=True,exist_ok=True)
    summary=[]
    for key in ('casa','rota','mundo','atlas'):
        packet=build_case_packet(str(output),key)
        (evidence/f'{key}.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2),encoding='utf-8')
        summary.append({k:packet[k] for k in ('case_key','case_id','snapshot_id','period','amount','amount_nature','recipient','owner','status')})
        summary[-1]['source_row_count']=len(packet['rows'])
    assert before==digest(output)
    (evidence/'proof.json').write_text(json.dumps(dict(packets=summary,originals_preserved=True,snapshot=before),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(packets=summary,originals_preserved=True),ensure_ascii=False))


if __name__=='__main__':
    main()
