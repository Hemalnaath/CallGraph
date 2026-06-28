# Integration Edges Reference
## Cross-Service Seam Patterns (configurable)

**Critical invariant:** A graph over ONE repo stops at the remoting boundary (it sees a local proxy bean / client stub, not the remote method). The cross-service hops only resolve when dependents are also pulled.

**The validator FAILS if there are zero `CALLS_VIA_*` edges** unless the manifest explicitly declares `no_integration_expected: true`.

---

## Why integration seams are first-class

The original graph's biggest hole was under-reported cross-service hops. Seams are not optional annotations — they are the primary evidence that a service boundary is crossed. Missing seams means the graph is misleading and decisions made on it are unsafe.

---

## Seam detection strategy (ordered)

For each service in the dependency chain:

1. **Import/require scan** — look for known remoting client imports (configurable via channel_patterns in `adapters.md`)
2. **Annotation scan** — look for remoting annotations (`@FeignClient`, `@WebServiceClient`, `@GrpcClient`, `@KafkaListener`, `@JmsListener`, etc.)
3. **Config scan** — look for URL/endpoint config bindings that point at other internal services
4. **AST call site** — confirm the proxy/client is actually invoked (not just imported)
5. **Runtime overlay (P5)** — observability egress spans confirm or extend

A seam edge is emitted at the **first positive signal**. If multiple signals agree, `evidence_class` is promoted to `runtime-confirmed`.

---

## Seam edge anatomy

```json
{
  "id": "CA-R-042",
  "src": "id-of-local-client-proxy-node",
  "tgt": "id-of-remote-service-entry-node",
  "type": "CALLS_VIA_HTTP_REST",
  "description": "REST call from account-service to notification-service via FeignClient",
  "keywords": ["integration-seam", "http-rest", "feign"],
  "weight": 0.8,
  "evidence_class": "static",
  "origin_report": "src/main/java/com/example/svc/AccountService.java:142",
  "depends_on_report": "src/main/java/com/example/client/NotificationClient.java:1",
  "seam_type": "sync-http",
  "remote_service": "notification-service",
  "channel": "CALLS_VIA_HTTP_REST"
}
```

---

## Seam classification

| Seam class | Edge types | Sync/Async | Notes |
|-----------|-----------|-----------|-------|
| Sync HTTP | `CALLS_VIA_HTTP_REST`, `CALLS_VIA_HTTP_INVOKER`, `CALLS_VIA_FEIGN` | Sync | Most common in microservice architectures |
| Sync RPC | `CALLS_VIA_JAXRPC`, `CALLS_VIA_GRPC`, `CALLS_VIA_THRIFT`, `CALLS_VIA_XMLRPC` | Sync | SOAP, gRPC, Thrift |
| Async messaging | `PUBLISHES_TO`, `CONSUMES_FROM` + shared `queue:<dest>` node | Async | Kafka, RabbitMQ, JMS, ActiveMQ, SNS/SQS |
| MQ vendor | `CALLS_VIA_MQ_VENDOR` | Async | Proprietary MQ clients |
| Socket | `CALLS_VIA_SOCKET` | Sync or async | Raw TCP/UDP |

### Async messaging — shared queue node
For async seams, emit a shared **queue node** as the intermediary:
```json
{
  "id": "queue:order.events.created",
  "name": "order.events.created",
  "type": "QUEUE",
  "description": "Kafka topic for order creation events published by the order service",
  "attributes": { "platform": "kafka", "evidence_class": "static" }
}
```
Then emit two edges: `PUBLISHES_TO` (producer → queue) and `CONSUMES_FROM` (queue → consumer).

---

## Manifest declaration for zero-seam operations

If an operation genuinely has no cross-service calls (rare for microservice architectures):

```json
{
  "no_integration_expected": true,
  "no_integration_reason": "This operation only reads from local cache and returns; no downstream service calls."
}
```

Without this declaration, the validator will fail.

---

## Example: Spring Boot + Kafka stack patterns

Common seam patterns for Spring Boot + Kafka microservice architectures:

| Pattern | Edge type | Evidence |
|---------|-----------|---------|
| `@FeignClient(name = "user-service")` | `CALLS_VIA_HTTP_REST` | Annotation on interface |
| `RestTemplate.exchange(url, ...)` | `CALLS_VIA_HTTP_REST` | Call site with URL config |
| `WebClient.post().uri(url)` | `CALLS_VIA_HTTP_REST` | Reactive HTTP client |
| `KafkaTemplate.send(topic, ...)` | `PUBLISHES_TO` | Kafka producer call site |
| `@KafkaListener(topics = "...")` | `CONSUMES_FROM` | Listener annotation |
| `JmsTemplate.send(destination, ...)` | `PUBLISHES_TO` | JMS producer |
| HTTP to auth-service (`/auth`, `/authorize`) | `CALLS_VIA_HTTP_REST` | URL pattern match |
| HTTP to id-generator-service | `CALLS_VIA_HTTP_REST` | URL pattern match |
| HTTP to data-processor-service | `CALLS_VIA_HTTP_REST` | URL pattern match |

> These are **starters for hardening** — verify against your project's actual source before finalising.
