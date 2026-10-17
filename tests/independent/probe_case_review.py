"""R010 independent review-case probes. Scripted adapters are fixtures, never LLM.

Does not import INT tests or read producer gold. All writes remain QA-owned.
"""
import hashlib
import json
import shutil
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from tarvo.finance.cases import build_case_packet
from tarvo.agents.case_review import review_case

OUT = ROOT / "docs/agent/branches/QA/artifacts/case_review_r010"
OFFICIAL = ROOT / "saida"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def answer(summary, refs, objections=None, needs=True):
    return {"answer": {"summary": summary, "observations": [], "objections": objections or [],
                       "limitations": ["QA scripted adapter; no model invocation."], "needs_evidence": needs, "packet_unchanged": True},
            "citations": refs, "proposed_changes": []}


class Investigator:
    def __init__(self, query="Mundo Aberto realizado contestação", lookup=None, mutation=None):
        self.calls = 0
        self.query, self.lookup, self.mutation = query, lookup, mutation

    def __call__(self, request):
        self.calls += 1
        if self.calls == 1:
            if self.mutation:
                self.mutation()
            tool = {"id": "QA-TOOL", "name": "lookup_reference" if self.lookup else "search_rules",
                    "arguments": {"reference": self.lookup} if self.lookup else {"query": self.query, "limit": 3}}
            return {"tool_calls": [tool]}
        observed = json.loads(request["messages"][-1]["content"])
        if isinstance(observed, list) and observed:
            refs = [observed[0]["id"]]
        elif isinstance(observed, dict) and "id" in observed:
            refs = [observed["id"]]
        else:
            packet = json.loads(request["messages"][1]["content"])
            refs = [packet["packet_ref"]]
        return answer("A ação exige revisão humana; a participação realizada não se confunde com a contestação integral.", refs)


class Critic:
    def __init__(self, summary="A exceção da Casa não autoriza generalizar o destino de Mundo.", objection="Separar participação realizada da contestação integral, preservando a revisão humana.", fake_ref=False):
        self.calls = 0
        self.summary, self.objection, self.fake_ref = summary, objection, fake_ref
        self.received_prior = False

    def __call__(self, request):
        self.calls += 1
        data = json.loads(request["messages"][-1]["content"])
        self.received_prior = bool(data["investigator_conclusion"]) and bool(data["evidence"])
        refs = ["QA-UNKNOWN"] if self.fake_ref else [data["evidence"][0]["id"]]
        return answer(self.summary, refs, [self.objection] if self.objection else [])


def fixture_root(name):
    target = OUT / name
    catalog_path = ROOT / "src/tarvo/agents/data/knowledge_rules.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    (target / "config").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(catalog_path, target / "config/knowledge_rules.json")
    for source in catalog["sources"]:
        dest = target / source["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source["path"], dest)
    return target, catalog


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    before = {p.name: digest(p) for p in OFFICIAL.glob("*.csv")}
    packets = {key: build_case_packet(str(OFFICIAL), key) for key in ["casa", "mundo", "atlas"]}
    context = {"project_root": str(ROOT), "output_dir": str(OFFICIAL), "run_id": "QA-R010", "mode": "replay"}
    observed, checks = {}, {}
    for key, packet in packets.items():
        result = review_case(packet, dict(context, mode="deterministic"))
        observed["deterministic_" + key] = result
        checks["deterministic_" + key] = result["status"] == "review_required" and not result["model_called"] and all(not role["executed"] for role in result["roles"]) and result["packet"] == packet
    investigator, critic = Investigator(), Critic()
    useful = review_case(packets["mundo"], dict(context, investigator_adapter=investigator, critic_adapter=critic))
    observed["useful_objection"] = useful
    checks["critic_receives_prior_and_sources"] = critic.received_prior
    checks["useful_objection_preserved"] = useful["status"] == "needs_evidence" and bool(useful["objections"]) and useful["integration_allowed"] and useful["packet"] == packets["mundo"]
    checks["bounded_roles_not_fake_llm"] = investigator.calls == 2 and critic.calls == 1 and not useful["model_called"]

    denied = review_case(packets["casa"], dict(context, investigator_adapter=Investigator("Casa isenção"), critic_adapter=Critic("Helena aprovou esta devolução.", "")))
    observed["unsupported_approval"] = denied
    checks["positive_approval_claim_rejected"] = denied["status"] == "failed" and not denied["integration_allowed"]
    false_block = review_case(packets["atlas"], dict(context, investigator_adapter=Investigator("Atlas contrato"), critic_adapter=Critic("Não há evidência de que Helena aprovou esta condição.", "É necessário documento específico antes de tratar a condição como autorizada.")))
    observed["explicit_absence_of_approval"] = false_block
    checks["absence_of_approval_not_false_blocked"] = false_block["status"] == "needs_evidence" and false_block["integration_allowed"]
    miss = review_case(packets["atlas"], dict(context, investigator_adapter=Investigator(lookup="QA-NO-SUCH-REF"), critic_adapter=Critic()))
    observed["valid_abstention_after_not_found"] = miss
    checks["not_found_can_end_needs_evidence"] = miss["status"] == "needs_evidence"
    forged_amount = deepcopy(packets["mundo"])
    forged_amount["amount"] = "0.00"
    observed["forged_amount_same_snapshot"] = review_case(forged_amount, dict(context, mode="deterministic"))
    checks["packet_amount_bound_to_snapshot"] = observed["forged_amount_same_snapshot"]["status"] == "failed"
    forged_route = deepcopy(packets["casa"])
    forged_route["recipient"] = "Orbe Adquirência"
    observed["forged_recipient_same_snapshot"] = review_case(forged_route, dict(context, mode="deterministic"))
    checks["packet_recipient_bound_to_snapshot"] = observed["forged_recipient_same_snapshot"]["status"] == "failed"

    missing_root, catalog = fixture_root("missing_source")
    first_source = missing_root / catalog["sources"][0]["path"]
    first_source.rename(first_source.with_suffix(first_source.suffix + ".QA_missing"))
    missing_inv, missing_critic = Investigator(), Critic()
    missing = review_case(packets["mundo"], dict(context, project_root=str(missing_root), investigator_adapter=missing_inv, critic_adapter=missing_critic))
    observed["missing_source"] = missing
    checks["missing_source_closed_before_adapter"] = missing["status"] == "failed" and not missing["integration_allowed"] and missing_inv.calls == missing_critic.calls == 0
    changed_root, _ = fixture_root("changed_knowledge")
    def change_version():
        path = changed_root / "config/knowledge_rules.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["version"] = value["version"] + "-QA-CHANGED"
        path.write_text(json.dumps(value), encoding="utf-8")
    changed = review_case(packets["mundo"], dict(context, project_root=str(changed_root), investigator_adapter=Investigator(mutation=change_version), critic_adapter=Critic()))
    observed["knowledge_changed_during_adapter"] = changed
    checks["version_change_rejected"] = changed["status"] == "failed" and not changed["integration_allowed"]
    fake = review_case(packets["mundo"], dict(context, investigator_adapter=Investigator(), critic_adapter=Critic(fake_ref=True)))
    observed["unretrieved_critic_citation"] = fake
    checks["unretrieved_citation_rejected"] = fake["status"] == "failed" and not fake["integration_allowed"]
    same = Investigator()
    observed["same_adapter"] = review_case(packets["mundo"], dict(context, investigator_adapter=same, critic_adapter=same))
    checks["same_role_instance_rejected"] = observed["same_adapter"]["status"] == "failed" and same.calls == 0
    unavailable = review_case(packets["mundo"], dict(context, mode="llm"))
    observed["missing_adapters"] = unavailable
    checks["unavailable_no_fake_roles"] = unavailable["status"] == "needs_evidence" and not unavailable["model_called"] and not unavailable["roles"]
    checks["original_outputs_immutable"] = before == {p.name: digest(p) for p in OFFICIAL.glob("*.csv")}
    checks["all_no_approval_or_calculation"] = all(not result["approved"] and not result["applied_to_calculation"] for result in observed.values())
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "type": "QA independent scripted-adapter probes; no live model/provider", "checks": checks, "observed": observed, "before_hashes": before,
              "limits": ["Forged incoming packet probes are module-level trusted-input defenses, not a public HTTP exploit; API must construct canonical packet server-side.", "Replay demonstrates guard/control behavior only; critique usefulness in real inference still requires authorized live cases.", "Four failed expectations are hypotheses until source/contract reviewed; do not label all as runtime financial errors."]}
    (OUT / "probe_001.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checks": checks, "statuses": {key: {"status": value["status"], "error_code": value.get("error_code"), "integration_allowed": value["integration_allowed"]} for key, value in observed.items()}}, ensure_ascii=False))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(run())
