---
name: generate-call-graph
version: "1.0"
description: >
  Produce the as-is, evidence-grounded static call graph for one named entry-point
  (operation) of one service. Language-agnostic via pluggable adapters. Emits a
  3-file bundle (entities JSONL, relationships JSONL, manifest JSON) with full
  per-node/edge provenance, a two-axis coverage ledger, and an optional runtime
  overlay from an observability platform.
category: static-analysis
trigger: "build/generate/create the call graph for [operation or service]"
invocation: "/generate-call-graph <service> [<entry-point>]"
---

# Generate Call Graph — Skill Specification (v1.0)

---

## 1. Metadata

| Field | Value |
|-------|-------|
| **Name** | `generate-call-graph` |
| **Version** | 1.0 |
| **Category** | Static Analysis |
| **Scope** | One operation · One service · Any language (via adapters) |
| **Invocation** | `/generate-call-graph <service> [<entry-point>]` |
| **Trigger phrase** | "build / generate / create the call graph for [operation or service]" |

---

## 2. Purpose

Generate the **as-is static call graph** for a single named entry-point (operation) within a single service.

This skill answers one question:

> **What does this entry-point call — and through which channels — given the source code as it exists today?**

It captures in-process method calls, cross-service integration seams, database access, asynchronous messaging paths, and optionally runtime-observed topology — each record carrying full provenance. It does not answer questions about target-state design, code quality, or any operation other than the one requested.

---

## 3. Scope

### Responsible for

| Responsibility | Detail |
|---------------|--------|
| Operation resolution | Derive canonical operation slug and entry-point from the operation registry |
| Code acquisition | Clone the entry repository and internal transitive dependents via VCS MCP |
| Static graph construction | Run AST analysis to produce nodes and edges for in-process calls, integration seams, DB boundaries, and async messaging |
| Runtime overlay | Optionally enrich with observability topology; reconcile against static edges |
| Bundle emission | Write the 3-file bundle with full provenance on every node and edge |
| Validation | Run the fail-closed validator; block completion if it exits non-zero |
| Run recording | Write a timestamped run report and evidence log |

### Not responsible for

| Out of scope | Canonical skill for that task |
|-------------|-------------------------------|
| Sequence diagram generation | Sequence-diagram skill (consumes this skill's output) |
| Whole-service inventory | Outside this skill's one-operation-per-run contract |
| Target-state or future architecture | Architecture-design skill |
| Code quality review or linting | Code-review skill |
| Dependency vulnerability analysis | Dependency-audit skill |
| Documentation generation beyond the bundle | Report-generator skill |

---

## 4. Activation Criteria

### Invoke when

- The user says "build", "generate", or "create the call graph for [operation or service]"
- The user runs `/generate-call-graph <service> [<entry-point>]`
- The user asks to map what a specific entry-point calls, statically or at runtime

### Do not invoke when

- The user requests a **sequence diagram** — the sequence-diagram skill consumes a call graph; it does not produce one
- The user requests a **whole-service inventory** — one operation per run only
- The user requests a **future or target-state design** — this skill produces as-is graphs only
- The user asks to **review code quality** — different skill

---

## 5. Inputs

### Required

| Input | Type | Description |
|-------|------|-------------|
| `service` | string | Repository name or service slug |
| `entry_point` | string | Fully-qualified method or function — e.g. `com.example.svc.AccountService#createAccount` |
| `operation` | string | Operation slug in kebab-case — e.g. `create-account`; derived from registry if not supplied |
| `domain` | string | Domain the operation belongs to; derived from registry if not supplied |

If `entry_point`, `operation`, or `domain` are not supplied, P2 elicitation resolves them interactively.

### Optional (with defaults)

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `depth` | enum | `transitive` | `entry-only` · `direct` · `transitive` — how far to follow dependencies |
| `environment` | enum | `prod` | `prod` · `qa` — target environment for runtime enrichment |
| `runtime_enrichment` | enum | `on` | `on` · `off` — whether to attempt observability overlay in P5 |
| `merge` | boolean | `false` | Patch an existing bundle without overwriting it |

### Adapter configuration (from config file)

All stack-specific behavior is supplied through a project adapter config file. Never hardcode these values in tool logic.

| Config key | Description |
|-----------|-------------|
| `language` | Target language — determines AST adapter |
| `build_system` | Build system — determines build-manifest resolver adapter |
| `channel_patterns` | Integration-seam detection rules (see `adapters.md`) |
| `db_source_adapter` | Migration path globs and proc-detection triggers |
| `org_config` | VCS org and operation-registry path (always auto-derived; never hardcoded) |
| `output_config` | Output root directory and path template |
| `observability_adapter` | Platform, MCP endpoint, egress-query field names |

---

## 6. Outputs

### 3-File Bundle

Written to `<context-root>/<svc>/call-graph/operation-<op>/` — one flat folder per operation, no nested subfolders.

| File | Format | Contents |
|------|--------|----------|
| `<op>.entities.jsonl` | JSONL | Graph nodes — one JSON object per line |
| `<op>.relationships.jsonl` | JSONL | Graph edges — one JSON object per line |
| `<op>.callgraph.json` | JSON | Manifest: metadata, counts, dependency chain, coverage ledger, dynamic overlay |

### Run Directory

`runs/<YYYY-MM-DD-HHMMSS>/` under the output root.

| File | Contents |
|------|----------|
| `run-report.md` | Phase outcome table, acceptance test checklist |
| `evidence.log` | Machine-readable per-node/edge source citations |
| `elicitation.json` | Recorded P2 answers |
| `adapter-config.yaml` | Snapshot of which adapters ran and with what configuration |

### Node Schema

Every entity in `<op>.entities.jsonl` must conform to:

```json
{
  "id": "<unique-node-id>",
  "name": "human-readable label",
  "type": "METHOD | FUNCTION | CLASS | SERVICE | QUEUE | TABLE | STORED_PROC | CONFIG",
  "description": "<at least 20 characters>",
  "attributes": {
    "domain": "string",
    "operation": "string",
    "entry_point": "string",
    "evidence_class": "static | runtime-confirmed | runtime-only",
    "origin_report": "path/to/file.ext:line or trace.id",
    "mode": "api-sync | api-rest | batch | event | scheduled | portal"
  }
}
```

All values inside `attributes` must be **scalars** (string, number, or boolean). No nested objects or arrays.

Node ID vocabulary:

| Pattern | Node type |
|---------|-----------|
| `<svc>/<class>/<method>` | Method or function |
| `<svc>/<class>` | Class or module |
| `<svc>` | Service |
| `queue:<topic-name>` | Messaging queue or topic |
| `db:<schema>/<table>` | Database table or view |
| `sproc:<schema>/<proc>` | Stored procedure |
| `config:<key>` | Configuration binding |
| `runtime:<svc>/<span>` | Runtime-only node (no static match) |

### Edge Schema

Every relationship in `<op>.relationships.jsonl` must conform to:

```json
{
  "id": "<ABBREV>-R-<NNN>",
  "src": "<node-id>",
  "tgt": "<node-id>",
  "type": "<EDGE_TYPE>",
  "description": "<at least 20 characters>",
  "keywords": ["non-empty", "array"],
  "weight": 0.8,
  "evidence_class": "static | runtime-confirmed | runtime-only",
  "origin_report": "path/to/file.ext:line or trace.id",
  "depends_on_report": "path/to/file.ext:line or trace.id"
}
```

Edge ID convention: `<ABBREV>-R-<NNN>` — uppercase abbreviation of the operation slug, literal `R`, zero-padded 3-digit monotonically increasing integer. Runtime-injected edges use `CGRT-R-<NNN>`; manually authored edges use `MAN-R-<NNN>`. See `edge-types.md` for the full edge-type catalogue and weight scale.

### Coverage Ledger

Reported in the manifest; every dimension is `covered`, `partial(<reason>)`, or `gap(<reason>)`.

| Dimension | What it covers |
|-----------|---------------|
| `in-process-calls` | Direct method or function calls within the service boundary |
| `config-binds` | External configuration values consumed (env vars, property files, config maps) |
| `db-stored-proc` | Stored procedures and DB query boundaries |
| `integration-seams` | Cross-service calls via REST, gRPC, MQ, or other remoting channels |
| `async-messaging` | Publish and consume edges on queues and topics |
| `vendor-egress` | External third-party or vendor API calls |
| `triggers-cdc` | Database triggers and change-data-capture patterns |
| `runtime` | Runtime-observed topology from the observability platform |
| `bytecode` | Compiled-artifact supplement edges (generics erasure, lambdas, anonymous classes) |
| `auth` | Authentication and authorization call paths |
| `error-compensation` | Exception handler paths and compensation flows |

---

## 7. Dependencies

### Required

| Dependency | Role |
|-----------|------|
| Language adapter (see `adapters.md`) | Source AST analysis — yields nodes and call edges |
| Build-manifest resolver adapter | Resolves internal dependencies to clone from VCS |
| Operation registry (`notation.md`) | Maps entry-point to canonical operation slug and domain |
| `validate_call_graph.py` | Fail-closed validator — must exit 0 before the run is declared complete |
| VCS MCP | Clones the entry repository and internal transitive dependents |

### Optional

| Dependency | Role | Behavior when absent |
|-----------|------|---------------------|
| Observability MCP | Runtime span data for P5 enrichment | Omit overlay; set `dynamic_overlay.status = "omitted"`; do not fabricate |
| Compiled-artifact supplement (e.g. `jdeps`) | Adds edges invisible to AST: generics erasure, lambdas, anonymous classes | Skip cleanly; flag `gap` in `coverage.bytecode` |
| Local-coverage adapter (e.g. JaCoCo, Istanbul) | Emits `RUNTIME_CALLED` edges for test-executed nodes | Skip cleanly |
| DB-source adapter | Parses DDL/migration files for stored-proc internals | Skip cleanly; flag gap in `coverage.db-stored-proc` if proc usage is detected |

---

## 8. Assumptions

Before execution, the following must hold. If an assumption fails, stop and report which one was violated before proceeding.

| # | Assumption | Consequence if false |
|---|-----------|---------------------|
| 1 | Entry repository is accessible via the configured VCS MCP | Stop; cannot clone source |
| 2 | Target language has a registered language adapter | Stop; unsupported language |
| 3 | Repository filesystem is readable (no write access needed for source) | Stop; cannot analyze source |
| 4 | Operation registry file exists at the configured path | P1 marks PROVISIONAL; run continues |
| 5 | `validate_call_graph.py` is present and executable | Stop; cannot run P6 gate |
| 6 | Output root directory is writable | Stop; cannot emit bundle |
| 7 | No protected-branch policy blocks reading source files | Stop; ask user for access |

---

## 9. Execution Workflow

Each phase follows: **pre-condition → action → post-condition → fail-closed behavior**.

### P0 — Bootstrap

**Pre:** Working branch is accessible.

**Action:** Verify the branch is not write-protected; create `runs/<YYYY-MM-DD-HHMMSS>/`; capture the ISO timestamp and pass it as `--generated-at` to the engine. The engine accepts no internal clock — timestamps are injected, ensuring reproducible runs.

**Post:** Run directory exists; timestamp recorded.

**Fail-closed:** Protected branch with no graphs present → stop and ask the user before proceeding.

---

### P1 — Resolve Operation

**Pre:** Service or repository name is known or inferable.

**Action:** Look up the entry-point in the operation registry (`notation.md`) to derive the canonical operation slug and domain. Record the fully-qualified entry method or function.

**Post:** `operation`, `domain`, and `entry_point` are set.

**Fail-closed:** Entry-point not in registry → do NOT coin a new operation ID; mark the run `PROVISIONAL`; surface for human confirmation. Continue generating the bundle.

---

### P2 — Elicitation Gate

**Pre:** P1 complete.

**Action:** Ask exactly **one question set** — do not split across multiple turns:
1. Confirm operation and entry-point repository (if not already resolved from P1)
2. Depth: `entry-only` · `direct` · **`transitive`** (default)
3. Environment: **`prod`** (default) · `qa`
4. Runtime enrichment: **`on`** (default) · `off`

**Post:** All four parameters confirmed and logged.

**Fail-closed:** Non-interactive mode → apply all defaults; log that elicitation was skipped.

---

### P3 — Acquire Code

**Pre:** P2 complete; VCS MCP connected.

**Action:**
- Clone the entry repository.
- Run the build-manifest resolver adapter: auto-derive the internal artifact prefix from the repo's own build manifest (groupId, module path, org scope); never hardcode.
- Confirm each internal dependent against the live VCS org; clone confirmed dependents (direct first, then transitive if `depth=transitive`).
- Record the full dependency chain in the manifest.

**Post:** All resolvable repositories cloned; dependency chain logged.

**Fail-closed:** Un-cloneable dependent → log as `resolved: false`; its seam edge still emits with downstream marked unresolved — never silently dropped.

---

### P4 — Build Static Graph

**Pre:** P3 complete.

**Action:**
- Run the language-adapter engine over the union (entry repo + all cloned dependents).
- Emit the full edge set including `CALLS_VIA_*` seam edges, DB edges, and async messaging edges.
- Optionally run the DB-source adapter to scan DDL/migration files for stored-proc internals.
- Flag every AST blind spot in `manifest.ast_blind_spots`.
- If `merge=true`: patch the existing bundle, preserving `manually_added` and runtime-injected edges; append only non-colliding new ones.
- Write `<op>.entities.jsonl` and `<op>.relationships.jsonl` to the operation folder.

**Post:** Both JSONL files written.

**Fail-closed:**
- Missing language parser → stop; print the install command for the missing tool.
- Zero `CALLS_VIA_*` edges when `depth != entry-only` and `no_integration_expected` is not set → surface for review before P6.

---

### P5 — Runtime Enrichment *(conditional on `runtime_enrichment=on`)*

**Pre:** P4 complete; observability MCP connected or pasted fragment available.

**Action (topology-walk — not trace-id stitching):**

For the entry service and every downstream service the static graph reaches:
1. `find_entity_by_name(<svc>)` — locate the service entity in the observability platform
2. Run the per-service egress query: `summarize by span.kind, span.name, server.address, db.namespace, messaging.system, messaging.destination.name`
3. Parse results into candidate `OBSERVED_*` edges
4. Reconcile: if a static edge matches, flip its `evidence_class` to `runtime-confirmed`; otherwise inject as `runtime-only`
5. Stamp the `dynamic_overlay` block in the manifest

**Post:** Runtime overlay present in manifest; `OBSERVED_*` edges injected into relationships JSONL.

**Fail-closed (fallback ladder in priority order):**
1. MCP query — preferred path
2. User-pasted span fragment — parse via `parse_runtime_fragment` tool
3. Neither available — **omit**; set `dynamic_overlay.status = "omitted"` with reason

Never fabricate a runtime edge. See `runtime-overlay.md` for reconciliation rules and known blockers.

---

### P6 — Validate and Record

**Pre:** P4 complete (and P5 if enrichment was chosen).

**Action:** Run `validate_call_graph.py <bundle-dir>` — must exit 0. Write run-report and evidence log to the run directory.

**Post:** Validator exits 0; all 3 bundle files present; run directory contains report, evidence log, elicitation record, and adapter config snapshot.

**Fail-closed:** Non-zero validator exit → do not mark the run complete; surface all errors to the user; require human action before promoting the bundle.

---

## 10. Decision Rules

| Scenario | Rule |
|----------|------|
| Language selection | Read `language` from the adapter config; do not infer from file extensions alone |
| Parser selection | Map language to adapter per `adapters.md`; fail explicitly if no adapter matches |
| Internal prefix detection | Auto-derive from the build manifest (groupId, module path, org scope); never hardcode org names or prefixes in tool logic |
| Dependency scope | Clone only artifacts whose prefix matches the auto-derived internal prefix; skip external library archives |
| Un-cloneable dependent | Emit the seam edge with `downstream.resolved = false`; continue; log it |
| Operation not in registry | Mark run `PROVISIONAL`; emit bundle with `status: PROVISIONAL`; do not coin a new operation ID |
| Zero `CALLS_VIA_*` edges | Error unless `no_integration_expected: true` is set in the manifest with a stated reason |
| Merge mode (`merge=true`) | Append edges with new IDs; never overwrite `manually_added: true` or `evidence_class: runtime-only` edges; skip colliding IDs and log them |
| Runtime overlay unavailable | Set `dynamic_overlay.status = "omitted"`; record the reason; never emit a fabricated value |
| AST blind spot detected | Record in `manifest.ast_blind_spots` with name, description, and recommended action; do not emit an edge for the invisible call; do not silently drop it |
| Duplicate node ID | Merge attributes; keep one canonical node; log the merge |
| Generated code (annotation processors, mappers, stubs) | Flag as blind spot in coverage; do not trace into generated artifacts unless a compiled-artifact supplement is available |
| Async seam | Emit a shared `queue:<dest>` node; connect publisher with `PUBLISHES_TO`; connect consumer with `CONSUMES_FROM` |

---

## 11. Constraints

| Constraint | Rule |
|-----------|------|
| Static analysis only | Do not execute any code, script, or binary from the target repository |
| Read-only source access | All filesystem operations on the source repository are read-only |
| No hardcoding | No operation slug, repo name, package prefix, org name, or artifact ID may appear in tool logic; derive all values from the build manifest or adapter config |
| No fabrication | Never emit a runtime edge without observed evidence; never stub a `CALLS_VIA_*` edge without source citation |
| One operation per run | Each run targets exactly one entry-point; do not fan out across operations |
| No third-party call-graph libraries | Source AST analysis only; the engine has no dependency on external call-graph tooling |
| Binaries excluded from primary analysis | Do not analyze compiled artifacts as source; the compiled-artifact supplement is additive only |
| Generated code excluded | Generated files are flagged as blind spots, not traced as authoritative source |
| ASCII-only output | All authored files must be ASCII-only |
| No PII or secrets in output | Credentials or personally identifiable information found in source are recorded as findings and excluded from all node and edge fields |
| VCS write gate | Reads and clones proceed freely; stop and ask before any push, PR creation, branch mutation, or other remote write |
| Observability write gate | Read-only span queries only; never write back to the observability platform |

---

## 12. Validation

The run is declared successful only when all of the following pass.

### Check A — Schema Conformance

| Rule | Pass criterion |
|------|---------------|
| Node required fields | Every node has `id`, `name`, `type`, `description` (≥20 chars), `attributes` |
| Node required attributes | `attributes` contains `domain`, `operation`, `entry_point`, `evidence_class`, `origin_report` |
| Attributes scalar-only | No nested objects or arrays inside `attributes` |
| Node ID uniqueness | No two nodes share the same `id` |
| Edge required fields | Every edge has `id`, `src`, `tgt`, `type`, `description` (≥20 chars), `keywords` (non-empty array), `weight` in [0, 1], `evidence_class`, `origin_report`, `depends_on_report` |
| Edge ID format | Every edge ID matches `^[A-Z]{2,}-R-[0-9]+-?[A-Za-z0-9]*$` |
| Edge ID uniqueness | No two edges share the same `id` |
| src/tgt resolution | Both `src` and `tgt` resolve to node IDs present in the bundle |
| evidence_class | Value is one of: `static`, `runtime-confirmed`, `runtime-only` |

### Check B — Call-Graph Invariants

| Rule | Pass criterion |
|------|---------------|
| Integration seam | ≥1 `CALLS_VIA_*` edge present, or `no_integration_expected: true` with a stated reason |
| Entry-point edge | Exactly 1 `HAS_ENTRY_POINT` edge present |
| Manifest required fields | `operation`, `domain`, `entry_point`, `generated_at`, `counts`, `dependency_chain`, `coverage` all present |
| Count accuracy | `counts.entities` equals actual JSONL line count; `counts.relationships` equals actual JSONL line count |
| Overlay status | `dynamic_overlay.status` is present and non-empty |
| Coverage dimensions | All 11 coverage dimensions present in the manifest |

### Validator Gate

`validate_call_graph.py <bundle-dir>` must exit 0. A non-zero exit blocks the run from being recorded as complete.

---

## 13. Error Handling

| Error | Cause | Behavior |
|-------|-------|----------|
| Unsupported language | No adapter registered for the detected language | Stop; print supported languages list; ask user to register an adapter |
| Parser not installed | AST tool binary not found on PATH | Stop; print the install command for the missing tool |
| VCS MCP unavailable | Connection to VCS platform fails | Stop; report which repos could not be reached |
| Un-cloneable dependent | Individual repo is inaccessible | Mark `resolved: false`; emit seam edge with unresolved downstream; continue |
| Operation not in registry | Slug has no entry in operation registry | Mark `PROVISIONAL`; continue; do not block the run |
| Zero seam edges | No `CALLS_VIA_*` edge and `no_integration_expected` not set | Surface as validator error; do not mark the run passed |
| Validator exits non-zero | Schema or invariant failure | Print all errors; do not write run-report as PASS; require human action |
| Malformed JSONL | A line is not valid JSON | Abort; print the line number and content; do not emit a partial bundle |
| Missing manifest field | Required field absent | Fail Check B; surface with field name |
| Observability MCP unavailable | Platform unreachable or token lacks read scope | Apply fallback ladder; if exhausted, set `dynamic_overlay.status = "omitted"` |
| Merge collision | `merge=true` but an existing edge ID would be overwritten | Skip the conflicting edge; log the skipped ID; never silently overwrite |
| PII or secret in source | Credential or identifier found in repository | Record as a finding; exclude from output; warn in run report |

---

## 14. Logging

Log the following at each phase. Do not log raw source code, PII, or credentials.

| Phase | Required log entries |
|-------|---------------------|
| **P0** | Run directory path; ISO timestamp |
| **P1** | Resolved operation slug; domain; entry-point FQ name; PROVISIONAL flag if set |
| **P2** | All 4 elicited parameters or defaults applied; whether elicitation was interactive or skipped |
| **P3** | Repositories cloned (name, source); repositories skipped (name, reason); dependency chain summary; unresolved dependents (name, reason) |
| **P4** | Source files scanned (count); files skipped (count, reason); language adapter selected; edge counts by type; AST blind spots flagged (names only); total node count; total edge count |
| **P5** | Observability platform queried; services walked (count); `OBSERVED_*` edges injected (count); `runtime-confirmed` upgrades (count); fallback path taken if any; overlay status |
| **P6** | Validator result (PASS / FAIL); error count; warning count; bundle file paths |

---

## 15. Security

| Requirement | Rule |
|-------------|------|
| No code execution | Never execute any file, script, test, or binary from the target repository during analysis |
| Read-only source access | No write, delete, or rename operation against source repository files |
| No secrets in output | Credentials, API keys, and personally identifiable information found in source are recorded as findings and excluded from all node and edge fields |
| Path sanitization | Validate all filesystem paths derived from user input or build manifests; reject paths that traverse outside the working directory |
| VCS write gate | Reads and clones proceed without confirmation; stop and ask before any push, PR creation, branch mutation, or other remote write via the VCS MCP |
| Observability read-only | Observability MCP is used for read-only span queries only; no write-back |
| Minimal MCP scope | Request only the permissions required: VCS read, observability read; never request write or admin scopes |

---

## 16. Related Skills

| Skill | Relationship |
|-------|-------------|
| `sequence-diagram` | **Downstream** — consumes this skill's output bundle to render a sequence diagram |
| `language-detection` | **Upstream** — identifies repository language and selects the correct adapter; may run as a pre-step |
| `dependency-resolver` | **Complementary** — resolves the full transitive build dependency graph; supplements P3 |
| `runtime-overlay` | **Complementary** — applies observability enrichment to an existing bundle without re-running P0–P4 |
| `graph-validator` | **Operational** — standalone wrapper around `validate_call_graph.py` for CI or scheduled use |
| `report-generator` | **Downstream** — produces human-readable reports from the call graph bundle |

---

## Appendix A — MCP Connections

| MCP | Purpose | Guardrails |
|-----|---------|-----------|
| **VCS MCP** (e.g. GitHub MCP) | Clone entry repo; confirm and clone transitive dependents; read build manifests | Reads and clones proceed freely; stop and ask before push, PR creation, branch mutation, or any remote write; confirm artifact-to-repo mapping against the live VCS org — no static lookup map |
| **Observability MCP** (e.g. Dynatrace, Datadog, Jaeger) | Entity lookup and per-service egress query execution in P5 | Read-only; pasted-fragment fallback if token lacks span-read scope; topology-walk approach, not trace-id stitching; overlay is omitted, not fabricated, if platform is unavailable |

---

## Appendix B — Acceptance Test

After every P0–P6 run, verify:

- [ ] (a) ≥1 `CALLS_VIA_*` seam edge present, or `no_integration_expected: true` with stated reason
- [ ] (b) Every node carries `evidence_class` and `origin_report`; every edge also carries `depends_on_report`
- [ ] (c) `dynamic_overlay.status` is `present`, `partial`, or `omitted` — never missing or fabricated
- [ ] (d) `validate_call_graph.py <bundle-dir>` exits 0
- [ ] (e) Exactly 3 files exist in `operation-<op>/`
- [ ] (f) No hardcoded org, repo, package prefix, or artifact ID in tool logic — all auto-derived from build manifest
