"""Produce explicit synthetic comparison evidence; never writes canonical saida/."""
import json
from pathlib import Path

from test_compare import ROOT, hashes, write_snapshot
from tarvo.finance.compare import compare_runs


def main():
    root=ROOT/'docs/agent/branches/DOM/artifacts/compare_synthetic'
    before,after=root/'before',root/'after'
    write_snapshot(before)
    write_snapshot(after,amount='12.25',run_id='synthetic-after',input_hash='b'*64,extra_commission=True,unknown=True)
    originals=(hashes(before),hashes(after))
    replay=compare_runs(str(before),str(before))
    delta=compare_runs(str(before),str(after))
    assert originals==(hashes(before),hashes(after))
    report=dict(dataset_kind='synthetic_test',not_client_adjustments=True,
                replay_identical=replay,known_delta=delta,originals_preserved=True,
                baseline_untouched='Canonical saida/ was only read by tests; never written by this proof.')
    (root/'proof.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(status='passed',synthetic=True,proof=str(root/'proof.json'),
                         changed={x['name']:len(x['changed']) for x in delta['outputs']},originals_preserved=True)))


if __name__=='__main__':
    main()
