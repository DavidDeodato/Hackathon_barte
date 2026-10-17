"""Only affected R010 INT guards, after correction. No live provider calls."""
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone

from probe_case_review import ROOT, OUT, OFFICIAL, Investigator, Critic, review_case, build_case_packet


def run():
    context = {"project_root": str(ROOT), "output_dir": str(OFFICIAL), "run_id": "QA-R010-REPROBE", "mode": "replay"}
    packets = {key: build_case_packet(str(OFFICIAL), key) for key in ["casa", "mundo", "atlas"]}
    observed, checks = {}, {}
    source_before = hashlib.sha256((ROOT / "src/tarvo/agents/case_review.py").read_bytes()).hexdigest()
    output_before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OFFICIAL.glob("*.csv")}
    observed["absence"] = review_case(packets["atlas"], dict(context, investigator_adapter=Investigator("Atlas contrato"), critic_adapter=Critic("Não há evidência de que Helena aprovou esta condição.", "Decisao: faturar Atlas | Fonte: packet.amount e confirmação comercial ainda não recuperada | Efeito: preservar comissão desconhecida e preparar solicitação ao comercial, sem faturar.")))
    checks["explicit_absence_preserved"] = observed["absence"]["status"] == "needs_evidence" and observed["absence"]["integration_allowed"]
    observed["positive_certainty"] = review_case(packets["atlas"], dict(context, investigator_adapter=Investigator("Atlas contrato"), critic_adapter=Critic("Não há dúvida de que Helena aprovou esta condição.", "")))
    checks["positive_certainty_not_disguised_as_negation"] = observed["positive_certainty"]["status"] == "failed" and not observed["positive_certainty"]["integration_allowed"]
    forged = deepcopy(packets["mundo"]); forged["amount"] = "0.00"
    observed["forged_amount"] = review_case(forged, dict(context, mode="deterministic"))
    checks["amount_bound_to_canonical_packet"] = observed["forged_amount"]["status"] == "failed" and observed["forged_amount"].get("error_code") == "packet_not_canonical"
    forged = deepcopy(packets["casa"]); forged["recipient"] = "Orbe Adquirência"
    observed["forged_recipient"] = review_case(forged, dict(context, mode="deterministic"))
    checks["recipient_bound_to_canonical_packet"] = observed["forged_recipient"]["status"] == "failed" and observed["forged_recipient"].get("error_code") == "packet_not_canonical"
    observed["not_found"] = review_case(packets["atlas"], dict(context, investigator_adapter=Investigator(lookup="QA-NO-SUCH-REF"), critic_adapter=Critic()))
    checks["not_found_allows_bounded_abstention"] = observed["not_found"]["status"] == "needs_evidence" and observed["not_found"]["integration_allowed"]
    negative = [e for e in observed["not_found"]["evidence"] if e["kind"] == "lookup_not_found"]
    checks["negative_search_has_ref_and_files_checked"] = bool(negative) and negative[0]["data"]["reference"] == "QA-NO-SUCH-REF" and bool(negative[0]["data"]["files_checked"])
    compact_context = {}
    class SpyInvestigator(Investigator):
        def __call__(self, request):
            if self.calls == 0:
                compact_context.update(json.loads(request["messages"][1]["content"])["packet"])
            return super().__call__(request)
    observed["compact"] = review_case(packets["casa"], dict(context, investigator_adapter=SpyInvestigator("Casa isenção"), critic_adapter=Critic()))
    checks["bounded_model_context_explicit"] = compact_context["row_context"]["included"] == 8 and compact_context["row_context"]["total"] == len(packets["casa"]["rows"]) and not compact_context["row_context"]["complete"]
    checks["returned_packet_stays_complete"] = observed["compact"]["packet"] == packets["casa"] and len(observed["compact"]["packet"]["rows"]) == len(packets["casa"]["rows"])
    checks["no_approval_or_model_call"] = all(not r["model_called"] and not r["approved"] and not r["applied_to_calculation"] for r in observed.values())
    checks["official_outputs_immutable"] = output_before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OFFICIAL.glob("*.csv")}
    checks["source_stable_during_reprobe"] = source_before == hashlib.sha256((ROOT / "src/tarvo/agents/case_review.py").read_bytes()).hexdigest()
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "kind": "targeted independent regression; scripted adapters, no live LLM", "checks": checks, "code_sha256": source_before,
              "compact_context_shape": {"row_context": compact_context.get("row_context"), "source_ref_context": compact_context.get("source_ref_context")}, "observed": observed,
              "limits": ["Guard/control acceptance only; does not establish real critic's semantic quality.", "Live001 financial semantic findings remain unaccepted until corrected live output is inspected separately."]}
    (OUT / "reprobe_002.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checks": checks, "statuses": {key: r["status"] for key, r in observed.items()}}, ensure_ascii=False))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(run())
