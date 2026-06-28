# Trace Provenance Reference
## Per-Record Provenance + ID Conventions

Every node and edge in the call graph must be traceable to its source. A reader must always be able to answer: "where did this start, what does it reach, how strong is the evidence?"

---

## Provenance fields (required on every record)

### On every node
| Field | Type | Description |
|-------|------|-------------|
| `domain` | string | The business domain this operation belongs to |
| `operation` | string | The operation slug (e.g. `create-order`) |
| `entry_point` | string | FQ method/function that is the graph root |
| `evidence_class` | enum | `static` \| `runtime-confirmed` \| `runtime-only` |
| `origin_report` | string | `file:line` (static) or `trace.id` (runtime) |

### On every edge (all of the above, plus)
| Field | Type | Description |
|-------|------|-------------|
| `depends_on_report` | string | Secondary evidence location; `file:line` or `trace.id` |

### Load-bearing claim rule
If a claim has no `file:line` or `trace.id` citation, it is **not load-bearing** and must be marked as such. Never emit uncited structural claims.

---

## Evidence class lifecycle

```
INITIAL EMIT (from static AST):
  evidence_class = "static"
  origin_report  = "path/to/file.ext:line_number"

AFTER RUNTIME OVERLAY (P5):
  IF runtime span confirms the static edge:
    evidence_class = "runtime-confirmed"
    [preserve origin_report; add runtime_trace field]

  IF runtime span has no static match:
    evidence_class = "runtime-only"
    origin_report  = "trace.id:<trace-id-or-aggregate-key>"

  IF static edge has no runtime confirmation:
    evidence_class stays "static"
    [add static_not_confirmed: true if runtime enrichment ran]
```

---

## Node ID conventions

Node IDs encode the **type and location** of the node. The vocabulary is:

```
<svc>/<class>/<method>       — method/function node
<svc>/<class>                — class/module node
<svc>                        — service node
queue:<topic-or-queue-name>  — messaging queue/topic node
db:<schema>/<table_or_view>  — database table/view node
sproc:<schema>/<proc_name>   — stored procedure node
config:<key>                 — configuration binding node
runtime:<svc>/<span_name>    — runtime-only node (no static match)
```

**Separator:** always `/` (forward slash). No backslashes. No spaces.

**Example node IDs:**
```
order-service/com.example.svc.OrderService/createOrder
queue:order.events.created
db:app_schema/orders
sproc:app_schema/sp_get_order_by_id
```

---

## Edge ID conventions

```
<ABBREV>-R-<NNN>
```

| Part | Rule |
|------|------|
| `ABBREV` | Uppercase abbreviation of the operation slug. E.g. `CO` for `create-order`, `AUTH` for `authenticate` |
| `R` | Literal separator — always the letter R |
| `NNN` | Zero-padded 3-digit integer, monotonically increasing within the bundle. Reset to `001` for each new bundle. |

**Special abbrevs:**
| Abbrev pattern | Usage |
|---------------|-------|
| `CGRT-R-NNN` | Runtime-overlay-injected edges (from topology-walk) |
| `OBSLINK-R-NNN` | Observability-link edges (non-CGRT runtime) |
| `MAN-R-NNN` | Manually added edges (human-authored; `manually_added: true`) |

**Examples:**
```
CO-R-001   (first edge in create-order bundle)
CO-R-042   (42nd edge)
CGRT-R-001 (first runtime-injected edge)
```

---

## Manifest ID conventions

The manifest (`<op>.callgraph.json`) carries:

```json
{
  "operation": "create-order",
  "domain": "orders",
  "entry_point": "com.example.svc.OrderService#createOrder",
  "generated_at": "2026-06-28T10:32:00Z",
  "bundle_version": "1",
  "counts": {
    "entities": 24,
    "relationships": 41
  },
  "dependency_chain": ["order-service", "inventory-service", "notification-service"],
  "analysisTypes": ["static-ast", "runtime-overlay"],
  "modes": {
    "api-rest": { "node_count": 12, "entry_modes": ["api-sync"] },
    "event": { "node_count": 4 }
  },
  "coverage": {
    "in-process-calls":     "covered",
    "config-binds":         "covered",
    "db-stored-proc":       "partial",
    "integration-seams":    "covered",
    "async-messaging":      "covered",
    "vendor-egress":        "gap(no vendor clients detected)",
    "triggers-cdc":         "gap(DDL not available)",
    "runtime":              "covered",
    "bytecode":             "partial",
    "auth":                 "covered",
    "error-compensation":   "partial"
  },
  "no_integration_expected": false,
  "dynamic_overlay": { "...": "see runtime-overlay.md" }
}
```

---

## Run directory layout

```
<context-root>/<svc>/call-graph/
  operation-<op>/
    <op>.entities.jsonl          <- bundle file 1
    <op>.relationships.jsonl     <- bundle file 2
    <op>.callgraph.json          <- bundle file 3 (manifest)
  runs/
    <YYYY-MM-DD-HHMMSS>/
      run-report.md              <- human-readable summary
      evidence.log               <- machine-readable evidence citations
      elicitation.json           <- recorded elicitation answers
      adapter-config.yaml        <- which adapters ran, with what config
```

**Exactly 3 files in the `operation-<op>/` folder.** No nesting, no legacy subfolders. Collisions resolved by filename suffix (e.g. `<op>-v2.entities.jsonl`), never by nesting.
