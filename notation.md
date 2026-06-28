# Notation Reference
## Operation Registry Format + Naming Conventions

---

## Operation registry

The operation registry maps operation slugs to their canonical metadata. It is the source of truth for operation IDs, domain membership, and entry-point fully-qualified names.

**Format:**

| ID | Slug | Domain | Service | Entry Point (FQ) | Status |
|----|------|--------|---------|-----------------|--------|
| D1-OP01 | create-packet | registration | registration-service | com.example.registration.PacketService#createPacket | active |
| D2-OP01 | authenticate | auth | auth-service | com.example.auth.AuthService#authenticate | active |

**Key format:** `D<n>-OP<nn>` — `D` + domain number + `-OP` + operation number within domain.

**If an operation is not in the registry:**
- Do NOT coin a new ID
- Mark the run `PROVISIONAL`
- Surface for human confirmation before promoting the bundle

---

## PROVISIONAL status

When an operation is not yet in the registry, the run is marked `PROVISIONAL`:

```json
{
  "operation": "new-operation",
  "status": "PROVISIONAL",
  "provisional_reason": "Operation not found in registry at notation.md",
  "action_required": "Register operation and assign canonical ID before promoting bundle"
}
```

The bundle is still emitted but must not be treated as authoritative until promoted.

---

## Naming conventions

### Operation slugs
- Lowercase kebab-case: `create-packet`, `sync-packet`, `authenticate`
- Verb-noun: what the operation *does*
- Domain-scoped: unique within domain (not necessarily globally)

### Service and repository names
- Lowercase kebab-case: `registration-service`, `packet-manager`
- Match the VCS repository name exactly

### Bundle folder name
```
operation-<slug>/
```
Example: `operation-create-packet/`

### Bundle file names
```
<slug>.entities.jsonl
<slug>.relationships.jsonl
<slug>.callgraph.json
```
Example: `create-packet.entities.jsonl`

### Run directory name
```
runs/<YYYY-MM-DD-HHMMSS>/
```
Timestamp is in UTC ISO format, compacted (no colons in the filename).

---

## Domain mapping

Domain mapping is **project-specific** and belongs in the project adapter config file (e.g. `<project>-adapter-config.yaml`), not in this core notation spec.

The registry key format `D<n>-OP<nn>` is fixed; the domain numbers and names are defined per project. Add a `domain_mapping` section to your project adapter config:

```yaml
domain_mapping:
  - number: 1
    name: registration
    key_services:
      - registration-service
  - number: 2
    name: authentication
    key_services:
      - auth-service
```

Verify domain assignments against the actual repository structure before finalising.
