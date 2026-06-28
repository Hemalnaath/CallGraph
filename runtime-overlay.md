# Runtime Overlay Reference
## MCP-first / Pasted-fragment / Omit Ladder + Topology-Walk

Runtime enrichment is an **overlay, reconciled — never fabricated.**

Runtime edges (`OBSERVED_*`) come only from the observability adapter. No spans → overlay omitted, not stubbed.

---

## The topology-walk approach (§2.8 — NOT trace-id stitching)

**Why not trace-id stitching:** On real tenants, filtering spans by a single `trace_id` returns zero rows — spans are stored as service-scoped aggregates, not join-able distributed traces.

**The correct method:** reconstruct E2E by **walking the static graph's downstream services** and running a per-service egress query on each, then unioning.

### Step-by-step topology-walk

```
For each service S in [entry-service] + static_downstream_services:
  1. find_entity_by_name(S)         → get observability entity ID
  2. run egress query for S         → get outbound span aggregates
  3. parse span fields              → candidate OBSERVED_* edges
  4. reconcile against static       → flip evidence_class if static edge exists
  5. inject new OBSERVED_* edges    → runtime-only if no static match
  6. record granularity             → always service-level; never claim per-operation
```

**Record runtime granularity honestly** (`granularity: "service"`); never claim per-operation runtime separation when multiple ops share one endpoint.

---

## Fallback ladder (P5 enrichment)

```
1. MCP query (preferred)
   └─ observability adapter: find_entity_by_name + per-service egress query
   └─ SUCCESS → inject OBSERVED_* edges, stamp dynamic_overlay

2. Pasted fragment (fallback if MCP unavailable or scope-blocked)
   └─ User pastes raw span export (JSON, CSV, or formatted text)
   └─ parse_runtime_fragment tool parses → OBSERVED_* edges
   └─ stamp dynamic_overlay with source: "pasted_fragment"

3. Omit (if neither MCP nor pasted fragment available)
   └─ Set dynamic_overlay.status = "omitted"
   └─ Set dynamic_overlay.reason = "<explain why>"
   └─ Do NOT fabricate any OBSERVED_* edges
   └─ Log clearly in run report
```

---

## Known blockers and mitigations

| Blocker | Symptom | Mitigation |
|---------|---------|-----------|
| API token lacks span-read scope | Query returns 403 or empty | Pasted-fragment fallback |
| `trace_id` equality returns nothing | Zero rows despite known traffic | Topology-walk (not stitch) |
| SQL text / URL+port is null (PCI/redaction) | DB spans have no query text | DB reconciliation is namespace/host-level; entry capture is path+host only |
| Operation not in span (shared endpoint) | Can't distinguish ops in spans | Overlay is service-granular; never claim per-op separation |
| Request/response bodies null | Can't infer payload shape | Expected; graph maps structure not payload |

---

## OBSERVED_* edge reconciliation rules

```
For each OBSERVED_* edge E:
  static_match = find static edge with same (src_service, tgt_service, type_family)
  
  IF static_match EXISTS:
    static_match.evidence_class = "runtime-confirmed"
    static_match.runtime_trace  = E.trace_ref
    # Do NOT emit a duplicate OBSERVED_* edge
    
  ELSE:
    emit E as a new edge with evidence_class = "runtime-only"
    flag as observed_but_not_static = true
    # This is a signal the static pass missed a path
```

### Discrepancy flags
| Flag | Meaning |
|------|---------|
| `observed_but_not_static` | Runtime saw a call that static analysis didn't; investigate |
| `*_discrepancy` | Static and runtime disagree on target, type, or weight |
| `static_not_confirmed` | Static edge has no runtime confirmation (may be dead code or test-only) |

---

## dynamic_overlay manifest block

The manifest `dynamic_overlay` block is always present (even when omitted):

```json
{
  "dynamic_overlay": {
    "status": "present | omitted | partial",
    "source": "mcp | pasted_fragment | none",
    "granularity": "service",
    "generated_at": "ISO timestamp",
    "services_walked": ["svc-a", "svc-b", "svc-c"],
    "services_missing": ["svc-d"],
    "observed_edge_count": 12,
    "runtime_confirmed_count": 8,
    "runtime_only_count": 4,
    "observed_but_not_static_count": 4,
    "omit_reason": null,
    "per_downstream_egress": {
      "svc-b": { "query_ran": true, "edge_count": 5 },
      "svc-c": { "query_ran": true, "edge_count": 3 },
      "svc-d": { "query_ran": false, "reason": "entity not found" }
    }
  }
}
```
