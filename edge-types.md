# Edge Types — Full Catalogue + Weights

This is the authoritative edge-type catalogue for the `generate-call-graph` skill.
Edge types are **free strings**; weights are advisory defaults. Override per-domain as needed.

## Weight scale
| Weight | Meaning |
|--------|---------|
| 1.0 | Verified (static AST + runtime confirmed) |
| 0.8 | Partial (static AST only, runtime not yet checked) |
| 0.6 | Cross-repo/gen-1 (one hop removed from direct evidence) |
| 0.4 | Inferred (pattern-matched, no direct source reference) |
| 0.2 | Deprecated (kept for history; do not rely on) |

---

## Static edge types

### In-process calls (direct invocation)
| Type | Description | Default weight |
|------|-------------|----------------|
| `CALLS` | Direct method/function call (same service, same process) | 0.8 |
| `CALLS_BYTECODE` | Edge discovered only via compiled-artifact analysis (AST-invisible: generics erasure, lambdas, anonymous classes) | 0.6 |
| `CALLS_SPROC` | Call to a stored procedure (detected via DB-source adapter) | 0.8 |
| `CALLS_DB` | Direct DB read/write (SQL, ORM, query builder) | 0.8 |
| `HAS_ENTRY_POINT` | Marks the root node as the operation entry point | 1.0 |

### Configuration bindings
| Type | Description | Default weight |
|------|-------------|----------------|
| `BINDS_CONFIG` | Component consumes an external config value (env var, config map, property file) | 0.8 |
| `DEP_ARTIFACT` | Build-manifest dependency on an internal artifact (not a direct call, but a compile/runtime classpath entry) | 0.6 |

### Cross-service integration seams (configurable via `references/integration-edges.md`)
| Type | Description | Default weight |
|------|-------------|----------------|
| `CALLS_VIA_HTTP_INVOKER` | Remoting via HTTP invoker proxy (Spring HttpInvokerProxyFactoryBean or equivalent) | 0.8 |
| `CALLS_VIA_HTTP_REST` | REST client call (RestTemplate, Feign, OpenFeign, Retrofit, fetch, axios, requests, etc.) | 0.8 |
| `CALLS_VIA_FEIGN` | Declarative HTTP client (Feign/OpenFeign annotation-driven) | 0.8 |
| `CALLS_VIA_JAXRPC` | JAX-RPC / JAX-WS SOAP proxy call | 0.8 |
| `CALLS_VIA_XMLRPC` | XML-RPC client call | 0.8 |
| `CALLS_VIA_MQ_VENDOR` | Proprietary MQ client (IBM MQ, ActiveMQ, RabbitMQ producer, etc.) | 0.8 |
| `CALLS_VIA_GRPC` | gRPC stub call | 0.8 |
| `CALLS_VIA_GRAPHQL` | GraphQL client call | 0.8 |
| `CALLS_VIA_THRIFT` | Apache Thrift RPC | 0.8 |
| `CALLS_VIA_SOCKET` | Raw TCP/UDP socket call | 0.6 |

### Async messaging
| Type | Description | Default weight |
|------|-------------|----------------|
| `PUBLISHES_TO` | Publishes a message/event to a topic/queue/channel (async, joined by a shared `queue:<dest>` node) | 0.8 |
| `CONSUMES_FROM` | Subscribes to / consumes from a topic/queue/channel | 0.8 |

### DB + stored-proc internals (from DB-source adapter)
| Type | Description | Default weight |
|------|-------------|----------------|
| `READS` | Stored proc / trigger reads from a table or view | 0.8 |
| `WRITES` | Stored proc / trigger writes to a table or view | 0.8 |
| `CALLS_PROC` | Stored proc calls another stored proc | 0.8 |
| `HAS_TRIGGER` | Table has an associated trigger (detected via DDL scan) | 0.8 |

---

## Runtime edge types (overlay — never fabricated)

These edges come **only** from the observability adapter. An `OBSERVED_*` edge whose target also exists as a static edge causes the static edge's `evidence_class` to be flipped to `runtime-confirmed`; otherwise it stays `runtime-only`.

| Type | Description | Default weight |
|------|-------------|----------------|
| `OBSERVED_SELECT` | Runtime SQL SELECT observed in spans | 1.0 |
| `OBSERVED_INSERT` | Runtime SQL INSERT observed in spans | 1.0 |
| `OBSERVED_UPDATE` | Runtime SQL UPDATE observed in spans | 1.0 |
| `OBSERVED_DELETE` | Runtime SQL DELETE observed in spans | 1.0 |
| `OBSERVED_EXEC` | Runtime stored-proc EXEC observed in spans | 1.0 |
| `OBSERVED_HTTP_CALL` | Outbound HTTP call observed in spans | 1.0 |
| `OBSERVED_RUNTIME_LINK` | Generic runtime link (messaging, socket, or other) observed in spans | 1.0 |
| `RUNTIME_CALLED` | Node was called at runtime (from local-coverage adapter, if available) | 0.8 |

---

## Edge-id convention
```
<ABBREV>-R-<NNN>
```
- `ABBREV`: uppercase abbreviation of the operation slug (e.g. `CA` for `create-account`)
- `R`: literal separator
- `NNN`: zero-padded integer, monotonically increasing within the bundle

Example: `CA-R-001`, `CA-R-002`, …

Runtime/CGRT edges use: `CGRT-R-<NNN>`
Observability-link edges use: `OBSLINK-R-<NNN>`

---

## Required edge attributes
Every edge must carry:

```json
{
  "id": "<ABBREV>-R-NNN",
  "src": "<node-id>",
  "tgt": "<node-id>",
  "type": "<EDGE_TYPE>",
  "description": "≥20 chars",
  "keywords": ["non-empty", "array"],
  "weight": 0.8,
  "evidence_class": "static | runtime-confirmed | runtime-only",
  "origin_report": "file:line or trace.id",
  "depends_on_report": "file:line or trace.id"
}
```

## Required node attributes
Every node must carry:

```json
{
  "id": "<svc>/<class>/<method>/<prop>/<sproc>/<dbquery>/<table_or_view>/<runtime>",
  "name": "human-readable",
  "type": "METHOD | FUNCTION | CLASS | SERVICE | QUEUE | TABLE | STORED_PROC | CONFIG | ...",
  "description": "≥20 chars",
  "attributes": {
    "domain": "string",
    "operation": "string",
    "entry_point": "string",
    "evidence_class": "static | runtime-confirmed | runtime-only",
    "origin_report": "file:line or trace.id",
    "mode": "api-sync | api-rest | batch | event | scheduled | portal | ...",
    "...": "all attribute values must be scalars (string/number/boolean)"
  }
}
```

> **Scalar-only rule:** all `attributes` values must be scalars. No nested objects or arrays inside `attributes`.
