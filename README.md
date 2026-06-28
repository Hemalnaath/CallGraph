# generate-call-graph skill

A **language-agnostic** Claude Code skill that builds the as-is, evidence-grounded call graph for one entry-point (operation) of one service.

---

## Quick start

```
/generate-call-graph <service> [<entry-point>]
```

Or describe what you want:
> "Build the call graph for the createAccount operation in account-service"

The skill asks **one question set** (P2 Elicitation gate) to confirm scope, then runs deterministically through P0–P6.

---

## What it produces

A **3-file bundle** under `<context-root>/<svc>/call-graph/operation-<op>/`:

| File | Contents |
|------|----------|
| `<op>.entities.jsonl` | Graph nodes — one JSON per line |
| `<op>.relationships.jsonl` | Graph edges — one per line, ids `<ABBREV>-R-NNN` |
| `<op>.callgraph.json` | Manifest: counts, coverage ledger, dynamic overlay |

Plus a timestamped `runs/<datetime>/` directory with a run report and evidence log.

---

## File structure

```
callgraph/
├── SKILL.md                       <- master specification (read this first)
├── adapters.md                    <- language, build, and observability adapter reference
├── edge-types.md                  <- full edge catalogue and weight scale
├── integration-edges.md           <- cross-service seam detection strategy and anatomy
├── runtime-overlay.md             <- topology-walk, fallback ladder, reconciliation rules
├── trace-provenance.md            <- per-record provenance and ID conventions
├── notation.md                    <- operation registry format and naming conventions
├── validate_call_graph.py         <- fail-closed validator (must exit 0)
└── <project>-adapter-config.yaml  <- stack-specific adapter config (one per project)
```

---

## Setting up for your project

1. Create a `<project>-adapter-config.yaml` for your project using the template in `adapters.md` as a guide.
2. Set `language` and `build_system` for your stack.
3. Configure `channel_patterns` for your remoting clients (REST, gRPC, MQ, etc.).
4. Set `output_config.context_root` to your preferred output directory.
5. Add your domains and operations to the operation registry in `notation.md`.
6. Run the validator after each graph: `python validate_call_graph.py <bundle-dir>`

---

## Hardening checklist

After your first run, verify and harden:

- [ ] `channel_patterns` catch all remoting client usages in your stack (REST, gRPC, MQ, WebSocket, etc.)
- [ ] Async publish/consume patterns emit correct `PUBLISHES_TO` / `CONSUMES_FROM` edges with a shared queue node
- [ ] DB migration paths point to the correct SQL or DDL directories for your project
- [ ] AST blind spots specific to your stack (generated code, AOP proxies, dynamic dispatch) are declared in the adapter config
- [ ] Observability adapter config matches your deployment platform
- [ ] Operation registry in `notation.md` has entries for your project's domains
- [ ] `validate_call_graph.py <bundle-dir>` exits 0 cleanly

---

## Design decisions (do not relitigate)

1. **No hardcoding** — internal prefixes auto-derived from build manifests; no org/repo literals in tool logic
2. **3-file bundle** — entities + relationships (JSONL) + manifest (JSON); one format, always
3. **One flat folder per operation** — no nested subfolders; exactly 3 files per operation
4. **Integration seams are first-class** — validator fails on zero `CALLS_VIA_*` unless explicitly declared with a reason
5. **Two-axis coverage model** — ingestion modes + dimensions; every gap is visible, not absent
6. **Provenance on every record** — `evidence_class` and `origin_report` on all nodes and edges; `depends_on_report` also on edges
7. **Runtime enrichment is an overlay, never fabricated** — topology-walk, not trace-id stitching; omit when unavailable
8. **Source AST is primary** — no dependency on external call-graph libraries
9. **Merge mode** — `merge=true` patches without overwriting manually-authored or runtime-injected edges
10. **Fail-closed** — reads and clones proceed freely; stop before any VCS write or remote mutation

---

## Acceptance test

After each P0–P6 run, verify:

- [ ] (a) ≥1 `CALLS_VIA_*` seam edge present, or `no_integration_expected: true` with stated reason
- [ ] (b) Every node has `evidence_class` and `origin_report`; every edge also has `depends_on_report`
- [ ] (c) `dynamic_overlay.status` is `present`, `partial`, or `omitted` — never missing or fabricated
- [ ] (d) `python validate_call_graph.py <bundle-dir>` exits 0
- [ ] (e) Exactly 3 files in `operation-<op>/`
- [ ] (f) Grep tool logic for any hardcoded org, repo, or package literal — zero hits
