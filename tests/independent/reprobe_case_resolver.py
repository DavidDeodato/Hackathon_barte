"""R010 targeted source-resolution probes; real catalog/read tools, fixture adapters."""
import hashlib
import json
from datetime import datetime, timezone

from probe_case_review import ROOT, OUT, OFFICIAL, Investigator, Critic, review_case, build_case_packet


def run():
    context = {"project_root": str(ROOT), "output_dir": str(OFFICIAL), "run_id": "QA-R010-RESOLVER", "mode": "replay"}
    checks, observed = {}, {}
    source_hash = hashlib.sha256((ROOT / "src/tarvo/agents/case_review.py").read_bytes()).hexdigest()
    wanted = {
        "casa": ("contexto/RESPOSTAS_FINANCEIRO.md#CAN-07/CAN-17/REG-C02", {"CAN-07", "CAN-17", "REG-C02"}),
        "mundo": ("contexto/RESPOSTAS_FINANCEIRO.md#REG-R03/REG-R04/REG-R05", {"REG-R03", "REG-R04", "REG-R05"}),
        "atlas": ("contexto/RESPOSTAS_FINANCEIRO.md#CAN-04/CAN-19", {"CAN-04", "CAN-19"}),
    }
    for key, (ref, ids) in wanted.items():
        packet = build_case_packet(str(OFFICIAL), key)
        result = review_case(packet, dict(context, investigator_adapter=Investigator(lookup=ref), critic_adapter=Critic()))
        observed[key] = result
        rules = [row for row in result["evidence"] if row["kind"] == "rule"]
        checks[key + "_known_anchors_resolve"] = {row["data"]["id"] for row in rules} == ids
        checks[key + "_no_artificial_not_found"] = not any("not_found" in row["kind"] for row in result["evidence"])
        checks[key + "_actual_registered_source_and_text"] = all(row["data"].get("text") and row["data"]["reference_resolution"]["method"] == "registered_catalog_locator" for row in rules)
        checks[key + "_complete_packet_preserved"] = result["packet"] == packet and result["integration_allowed"]
    packet = build_case_packet(str(OFFICIAL), "casa")
    unknown = review_case(packet, dict(context, investigator_adapter=Investigator(lookup="contexto/RESPOSTAS_FINANCEIRO.md#CAN-999999"), critic_adapter=Critic()))
    observed["unknown_anchor"] = unknown
    checks["unknown_anchor_not_invented"] = any(row["kind"] == "catalog_reference_not_found" for row in unknown["evidence"])
    forbidden = review_case(packet, dict(context, investigator_adapter=Investigator(lookup="../QA-FORBIDDEN.txt#CAN-17"), critic_adapter=Critic()))
    observed["traversal"] = forbidden
    checks["path_traversal_rejected"] = forbidden["status"] == "failed" and not forbidden["integration_allowed"]
    unregistered = review_case(packet, dict(context, investigator_adapter=Investigator(lookup="docs/agent/branches/QA/artifacts/QA-NOT-REGISTERED.txt#L1"), critic_adapter=Critic()))
    observed["unregistered_file"] = unregistered
    checks["unregistered_file_rejected"] = unregistered["status"] == "failed" and not unregistered["integration_allowed"]
    business = review_case(packet, dict(context, investigator_adapter=Investigator(lookup="TX88410932"), critic_adapter=Critic()))
    observed["business_id"] = business
    checks["business_lookup_still_output_trace"] = any(row["kind"] == "output_trace" and row["data"]["reference"] == "TX88410932" for row in business["evidence"])
    checks["no_real_model_or_approval"] = all(not row["model_called"] and not row["approved"] and not row["applied_to_calculation"] for row in observed.values())
    checks["source_stable"] = source_hash == hashlib.sha256((ROOT / "src/tarvo/agents/case_review.py").read_bytes()).hexdigest()
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "kind": "targeted real-source resolver regression; no provider calls", "code_sha256": source_hash, "checks": checks, "observed": observed,
              "limits": ["Resolver normalization is deterministic tool behavior, not an independent model decision or semantic proof.", "Known financial cases are regressions; real corrected narrative still needs manual inspection of an authorized live run."]}
    (OUT / "resolver_003.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checks": checks}, ensure_ascii=False))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(run())
