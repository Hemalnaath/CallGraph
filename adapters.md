# Adapters Reference

The `generate-call-graph` engine is **fully de-hardcoded**. Every stack-specific concern is expressed as a named adapter interface. You plug in the right adapter for your language/build system/observability platform; the engine logic is identical regardless.

---

## 1. Language adapter (required)

**Interface:** given source files in the cloned repo, yield:
- **functions / methods** (with receiver type resolution for OO languages)
- **call edges** (caller → callee, with file:line provenance)
- **annotations / decorators** (e.g. `@Transactional`, `@Bean`, `@RestController` or equivalents)
- **config bindings** (inline SQL, property references, env-var reads)

**One adapter per language. The engine is language-agnostic over the adapter's output.**

### Adapter implementations by language

| Language | Recommended tool | Notes |
|----------|-----------------|-------|
| **Java** | tree-sitter Java AST | Primary; `jdeps` on `target/classes` supplements at class level for generics erasure, lambdas, anonymous classes |
| **Python** | tree-sitter Python AST | `ast` module also viable |
| **JavaScript / TypeScript** | tree-sitter JS/TS AST | Resolve module aliases via `tsconfig.json` / `webpack.config` |
| **Go** | `go/ast` (stdlib) | Module graph from `go.mod` |
| **Rust** | `syn` crate AST | Cargo workspace for deps |
| **C# / .NET** | Roslyn API | Project file for deps |
| **Ruby** | tree-sitter Ruby AST | Bundler for deps |
| **PHP** | tree-sitter PHP AST | Composer for deps |
| **C / C++** | tree-sitter C/C++ AST | `compile_commands.json` for include paths |
| **Kotlin** | tree-sitter Kotlin or kotlinc PSI | Gradle for deps |
| **Scala** | tree-sitter Scala or Scalameta | SBT/Maven for deps |

### AST blind spots (document, do not silently drop)
The following patterns are commonly invisible to static AST and must be flagged in the manifest:
- Reflection-based invocation (e.g. `Class.forName`, `getMethod`, `invoke`)
- Dynamic dispatch through interfaces with many implementations
- Generics erasure (use compiled-artifact supplement if available)
- Lambda / anonymous class targets (use compiled-artifact supplement if available)
- Config-driven routing (e.g. strategy patterns, plugin registries)
- Generated code (Lombok, annotation processors, protobuf-generated stubs)

---

## 2. Build-manifest resolver adapter (required)

**Interface:** given the entry repo's build manifest, yield:
- **internal artifacts** (artifact IDs that belong to the same org/namespace)
- **repo-name candidates** (mapping artifact → repo to clone)
- **clone order** (dependency order for transitive resolution)

**Implementations by build system:**

| Build system | Source | Notes |
|-------------|--------|-------|
| **Maven** | `pom.xml` → `dependency:tree` + `dependency:sources` | Internal prefix derived from `groupId` patterns in the manifest itself — never hardcoded |
| **Gradle** | `build.gradle[.kts]` → dependency report | Kotlin DSL or Groovy; check `settings.gradle` for included builds |
| **npm / yarn** | `package.json` → dependency tree | Workspaces supported; internal packages identified by org scope (e.g. `@myorg/`) |
| **Cargo** | `Cargo.toml` → workspace members + `cargo tree` | Path deps are always internal |
| **Go modules** | `go.mod` → `go list -m all` | Module path prefix identifies internal modules |
| **pip / Poetry** | `pyproject.toml` or `requirements.txt` | Internal packages identified by org-specific index or namespace |
| **NuGet** | `.csproj` + `packages.config` | Internal feed vs. nuget.org |
| **SBT** | `build.sbt` | Aggregated projects are always internal |

**Key rule:** internal-prefix detection is **auto-derived** from the build manifest itself (look at what groupIds/scopes/module-paths are already in the repo). Never hardcode org names or prefixes in tool logic.

---

## 3. Compiled-artifact supplement adapter (optional)

**Interface:** given compiled output (`.class` files, `.so`, etc.), yield additional call edges at class/symbol level that the AST missed.

**Skip cleanly if absent** — do not fail.

| Language | Tool | What it adds |
|----------|------|-------------|
| Java | `jdeps` on `target/classes` | Class-level deps for generics erasure, lambdas, anonymous/compiled-only |
| .NET | IL disassembler (ILSpy, ildasm) | IL-level call edges |
| C/C++ | Symbol table (`nm`, `objdump`) | Linker-visible symbols |

**Decline third-party call-graph libs** — the source AST already gives method depth, not worth a new dependency in a regulated codebase.

---

## 4. Local-coverage adapter (optional)

**Interface:** given a local-coverage report, emit `RUNTIME_CALLED` edges for nodes that were actually executed in tests.

**Skip cleanly if absent.**

| Language | Tool |
|----------|------|
| Java | JaCoCo |
| Python | coverage.py |
| JavaScript | Istanbul / nyc |
| Go | `go test -coverprofile` |
| Rust | `cargo-tarpaulin` |
| .NET | coverlet |

---

## 5. Channel-patterns table (integration-seam adapter, configurable)

**Interface:** a configurable table mapping `{pattern → CALLS_VIA_<KIND>}`, supplied per stack. **Never hardcode org class names.**

The engine matches import statements, type references, and annotation patterns against this table to emit cross-service seam edges.

**Format (YAML or JSON config):**
```yaml
channel_patterns:
  - pattern: "HttpInvokerProxyFactoryBean"
    edge_type: CALLS_VIA_HTTP_INVOKER
    language: java
  - pattern: "JaxRpcPortProxyFactoryBean"
    edge_type: CALLS_VIA_JAXRPC
    language: java
  - pattern: "JmsTemplate"
    edge_type: CALLS_VIA_MQ_VENDOR
    language: java
  - pattern: "RestTemplate|FeignClient|OpenFeign"
    edge_type: CALLS_VIA_HTTP_REST
    language: java
  - pattern: "XmlRpcClient"
    edge_type: CALLS_VIA_XMLRPC
    language: java
  # --- Python examples ---
  - pattern: "requests.get|requests.post|httpx"
    edge_type: CALLS_VIA_HTTP_REST
    language: python
  - pattern: "pika|aio_pika"
    edge_type: CALLS_VIA_MQ_VENDOR
    language: python
  - pattern: "grpc.channel|grpc.stub"
    edge_type: CALLS_VIA_GRPC
    language: python
  # --- JavaScript / TypeScript examples ---
  - pattern: "axios|fetch|node-fetch"
    edge_type: CALLS_VIA_HTTP_REST
    language: javascript
  - pattern: "amqplib|@nestjs/microservices"
    edge_type: CALLS_VIA_MQ_VENDOR
    language: javascript
  # Add patterns for your stack here
```

**Example: Java Spring Boot stack starter patterns:**
```yaml
channel_patterns:
  - pattern: "RestTemplate|FeignClient|WebClient"
    edge_type: CALLS_VIA_HTTP_REST
    language: java
  - pattern: "HttpInvokerProxyFactoryBean"
    edge_type: CALLS_VIA_HTTP_INVOKER
    language: java
  - pattern: "KafkaTemplate|@KafkaListener"
    edge_type: CALLS_VIA_MQ_VENDOR
    language: java
  - pattern: "JmsTemplate|@JmsListener"
    edge_type: CALLS_VIA_MQ_VENDOR
    language: java
  - pattern: "ActiveMQConnectionFactory|RabbitTemplate"
    edge_type: CALLS_VIA_MQ_VENDOR
    language: java
```

---

## 6. DB-source adapter (optional)

**Interface:** scan DDL/migration files for `CREATE PROC / FUNCTION / TRIGGER`; parse bodies into `READS / WRITES / CALLS_PROC / HAS_TRIGGER` edges.

**The proc-detection trigger pattern is per-DAO-style, configurable:**

```yaml
db_source_adapter:
  migration_paths:
    - "db/migration/**/*.sql"
    - "src/main/resources/db/**/*.sql"
    - "flyway/**/*.sql"
    - "liquibase/**/*.xml"
  proc_detection_triggers:
    # Patterns that indicate a DAO/repo class calls stored procs
    - annotation: "@StoredProcedure"
    - extends: "StoredProcedure"
    - annotation: "@NamedStoredProcedureQuery"
    - method_call: "SimpleJdbcCall|StoredProcedureQuery"
```

---

## 7. Org + repo-naming convention config (required)

**Interface:** a domain set + an operation-registry path + the key format string. Registry lookup is pluggable; unknown op → `PROVISIONAL`.

```yaml
org_config:
  vcs_org: "auto-derived"           # NEVER hardcode; resolved from build manifest at runtime
  internal_prefix: "auto-derived"   # NEVER hardcode; auto-derived from groupId/module patterns
  repo_naming_suffixes:             # Suffixes that identify internal artifact repos
    - "_API"
    - "_SVC"
    - "_LIB"
    - "-service"
    - "-api"
    - "-lib"
  operation_registry_path: "references/notation.md"
  operation_key_format: "D<n>-OP<nn>"   # Override per project
```

---

## 8. Output-root config (required)

```yaml
output_config:
  context_root: "service-context"           # Root folder for all call graphs
  path_template: "<svc>/call-graph/operation-<op>/"
  one_folder_per_op: true                   # NEVER nest legacy/ subfolders
  flat_layout: true                         # All bundle files flat in the op folder
```

---

## 9. Observability adapter (required for P5)

**Interface:**
- `find_entity_by_name(name)` — locate service entity in the observability platform
- `query(per-service egress query)` — execute the egress span query for one service

**Map provider fields → `OBSERVED_*` edges. Keep the topology-walk + fallback ladder** (see `references/runtime-overlay.md`).

| Platform | MCP / SDK | Query language |
|----------|-----------|----------------|
| Dynatrace | Dynatrace MCP (`execute_dql`) | DQL |
| Datadog | Datadog MCP | Log/APM query |
| Jaeger | Jaeger API | Jaeger query |
| Zipkin | Zipkin API | Zipkin query |
| OpenTelemetry Collector | OTLP export | — |
| AWS X-Ray | X-Ray API | X-Ray filter expressions |
| New Relic | New Relic MCP / NRQL | NRQL |

**Generic per-service egress query structure** (adapt field names to your platform):
```
summarize by span.kind, span.name, server.address, db.namespace,
             messaging.system, messaging.destination.name
WHERE service.name = "<svc>"
  AND timestamp >= <start>
  AND timestamp <= <end>
```
