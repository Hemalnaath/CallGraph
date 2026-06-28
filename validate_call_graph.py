#!/usr/bin/env python3
"""
validate_call_graph.py  —  fail-closed gate for generate-call-graph bundles.

Usage:
    python validate_call_graph.py <bundle-dir> [--stem <op>]

Arguments:
    <bundle-dir>   Path to the operation-<op>/ folder containing the 3 bundle files.
    --stem <op>    Operation slug (e.g. create-packet). If omitted, inferred from the
                   single *.callgraph.json file in bundle-dir.

Exit codes:
    0   PASS (warnings may be present — check output)
    1   FAIL (one or more errors)

Check classes:
    A. Schema conformance
    B. Call-graph invariants
"""

import json
import re
import sys
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_EVIDENCE_CLASSES = {"static", "runtime-confirmed", "runtime-only"}
EDGE_ID_PATTERN = re.compile(r'^[A-Z]{2,}-R-[0-9]+-?[A-Za-z0-9]*$')
DESCRIPTION_MIN_LEN = 20
MIN_WEIGHT = 0.0
MAX_WEIGHT = 1.0

REQUIRED_NODE_ATTRS = {"domain", "operation", "entry_point", "evidence_class", "origin_report"}
REQUIRED_EDGE_FIELDS = {"id", "src", "tgt", "type", "description", "keywords", "weight",
                        "evidence_class", "origin_report", "depends_on_report"}
REQUIRED_NODE_FIELDS = {"id", "name", "type", "description", "attributes"}

COVERAGE_DIMENSIONS = [
    "in-process-calls", "config-binds", "db-stored-proc", "integration-seams",
    "async-messaging", "vendor-egress", "triggers-cdc", "runtime", "bytecode",
    "auth", "error-compensation"
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class Result:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, msg):
        self.errors.append(f"  FAIL  {msg}")

    def warn(self, msg):
        self.warnings.append(f"  WARN  {msg}")

    def print_all(self):
        for w in self.warnings:
            print(w)
        for e in self.errors:
            print(e)

    def passed(self):
        return len(self.errors) == 0


def load_jsonl(path: Path):
    records = []
    with open(path) as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  FAIL  {path.name} line {i}: invalid JSON — {e}")
                sys.exit(1)
    return records


def load_json(path: Path):
    with open(path) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            print(f"  FAIL  {path.name}: invalid JSON — {e}")
            sys.exit(1)

# ---------------------------------------------------------------------------
# A. Schema conformance
# ---------------------------------------------------------------------------

def check_schema(entities, relationships, result: Result):
    print("A. Schema conformance")

    # --- Entities ---
    node_ids = set()
    for i, node in enumerate(entities):
        prefix = f"entity[{i}] id={node.get('id','?')!r}"

        # Required top-level fields
        for f in REQUIRED_NODE_FIELDS:
            if f not in node:
                result.error(f"{prefix}: missing required field '{f}'")

        # id uniqueness
        nid = node.get("id")
        if nid:
            if nid in node_ids:
                result.error(f"{prefix}: duplicate node id")
            node_ids.add(nid)

        # description length
        desc = node.get("description", "")
        if len(desc) < DESCRIPTION_MIN_LEN:
            result.error(f"{prefix}: description too short ({len(desc)} chars, min {DESCRIPTION_MIN_LEN})")

        # attributes must be scalars
        attrs = node.get("attributes", {})
        if not isinstance(attrs, dict):
            result.error(f"{prefix}: 'attributes' must be a dict")
        else:
            for k, v in attrs.items():
                if isinstance(v, (dict, list)):
                    result.error(f"{prefix}: attribute '{k}' must be scalar, got {type(v).__name__}")

            # Required provenance attrs
            for req in REQUIRED_NODE_ATTRS:
                if req not in attrs:
                    result.error(f"{prefix}: missing required attribute '{req}' in attributes")

            # evidence_class valid
            ec = attrs.get("evidence_class")
            if ec and ec not in VALID_EVIDENCE_CLASSES:
                result.error(f"{prefix}: invalid evidence_class '{ec}'")

    # --- Relationships ---
    edge_ids = set()
    for i, edge in enumerate(relationships):
        prefix = f"edge[{i}] id={edge.get('id','?')!r}"

        # Required fields
        for f in REQUIRED_EDGE_FIELDS:
            if f not in edge:
                result.error(f"{prefix}: missing required field '{f}'")

        # id format
        eid = edge.get("id")
        if eid:
            if not EDGE_ID_PATTERN.match(eid):
                result.error(f"{prefix}: id format invalid (expected <ABBREV>-R-<NNN>)")
            if eid in edge_ids:
                result.error(f"{prefix}: duplicate edge id")
            edge_ids.add(eid)

        # description length
        desc = edge.get("description", "")
        if len(desc) < DESCRIPTION_MIN_LEN:
            result.error(f"{prefix}: description too short ({len(desc)} chars, min {DESCRIPTION_MIN_LEN})")

        # keywords non-empty
        kw = edge.get("keywords", [])
        if not isinstance(kw, list) or len(kw) == 0:
            result.error(f"{prefix}: 'keywords' must be a non-empty array")

        # weight in [0,1]
        w = edge.get("weight")
        if w is not None:
            if not isinstance(w, (int, float)) or not (MIN_WEIGHT <= w <= MAX_WEIGHT):
                result.error(f"{prefix}: weight {w!r} not in [0, 1]")

        # evidence_class valid
        ec = edge.get("evidence_class")
        if ec and ec not in VALID_EVIDENCE_CLASSES:
            result.error(f"{prefix}: invalid evidence_class '{ec}'")

        # src/tgt resolve to node ids
        src = edge.get("src")
        tgt = edge.get("tgt")
        if src and src not in node_ids:
            result.error(f"{prefix}: src '{src}' does not resolve to a node id in the bundle")
        if tgt and tgt not in node_ids:
            result.error(f"{prefix}: tgt '{tgt}' does not resolve to a node id in the bundle")

    return node_ids, edge_ids

# ---------------------------------------------------------------------------
# B. Call-graph invariants
# ---------------------------------------------------------------------------

def check_invariants(entities, relationships, manifest, node_ids, result: Result):
    print("B. Call-graph invariants")

    # Every node and edge has evidence_class in valid set
    for node in entities:
        attrs = node.get("attributes", {})
        ec = attrs.get("evidence_class")
        if not ec:
            result.error(f"node {node.get('id')!r}: missing evidence_class")
        elif ec not in VALID_EVIDENCE_CLASSES:
            result.error(f"node {node.get('id')!r}: invalid evidence_class '{ec}'")

    for edge in relationships:
        ec = edge.get("evidence_class")
        if not ec:
            result.error(f"edge {edge.get('id')!r}: missing evidence_class")

    # Every edge has origin_report and depends_on_report
    for edge in relationships:
        if not edge.get("origin_report"):
            result.error(f"edge {edge.get('id')!r}: missing origin_report")
        if not edge.get("depends_on_report"):
            result.error(f"edge {edge.get('id')!r}: missing depends_on_report")

    # ≥1 CALLS_VIA_* integration seam OR manifest no_integration_expected: true
    seam_edges = [e for e in relationships if e.get("type", "").startswith("CALLS_VIA_")]
    no_integration_expected = manifest.get("no_integration_expected", False)
    if len(seam_edges) == 0 and not no_integration_expected:
        result.error(
            "Zero CALLS_VIA_* integration seam edges found. "
            "If this operation genuinely has no cross-service calls, "
            "set no_integration_expected: true in the manifest with a reason."
        )
    elif len(seam_edges) == 0 and no_integration_expected:
        result.warn("no_integration_expected: true — confirm this is intentional")

    # HAS_ENTRY_POINT edge present
    entry_edges = [e for e in relationships if e.get("type") == "HAS_ENTRY_POINT"]
    if len(entry_edges) == 0:
        result.warn("No HAS_ENTRY_POINT edge found (warn; check entry-point node)")
    elif len(entry_edges) > 1:
        result.warn(f"Multiple HAS_ENTRY_POINT edges ({len(entry_edges)}) — expected 1")

    # Manifest present and has required fields
    required_manifest_fields = ["operation", "domain", "entry_point", "generated_at",
                                 "counts", "dependency_chain", "coverage"]
    for f in required_manifest_fields:
        if f not in manifest:
            result.error(f"manifest: missing required field '{f}'")

    # counts.entities / counts.relationships match actual
    counts = manifest.get("counts", {})
    actual_entities = len(entities)
    actual_relationships = len(relationships)
    if counts.get("entities") != actual_entities:
        result.error(
            f"manifest counts.entities={counts.get('entities')} "
            f"but actual entity count={actual_entities}"
        )
    if counts.get("relationships") != actual_relationships:
        result.error(
            f"manifest counts.relationships={counts.get('relationships')} "
            f"but actual relationship count={actual_relationships}"
        )

    # dynamic_overlay.status present and non-empty
    overlay = manifest.get("dynamic_overlay", {})
    if not overlay:
        result.error("manifest: missing dynamic_overlay block")
    else:
        status = overlay.get("status")
        if not status:
            result.error("manifest.dynamic_overlay: missing 'status' field")

    # coverage ledger present and non-empty for each dimension
    coverage = manifest.get("coverage", {})
    if not coverage:
        result.error("manifest: missing 'coverage' block")
    else:
        for dim in COVERAGE_DIMENSIONS:
            val = coverage.get(dim)
            if val is None:
                result.warn(f"manifest.coverage: dimension '{dim}' not present")
            elif not val:
                result.warn(f"manifest.coverage: dimension '{dim}' is empty")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Validate a generate-call-graph bundle.")
    parser.add_argument("bundle_dir", help="Path to the operation-<op>/ bundle directory")
    parser.add_argument("--stem", help="Operation slug (inferred if omitted)")
    args = parser.parse_args()

    bundle_dir = Path(args.bundle_dir)
    if not bundle_dir.is_dir():
        print(f"FAIL  {bundle_dir} is not a directory")
        sys.exit(1)

    # Infer stem
    stem = args.stem
    if not stem:
        manifests = list(bundle_dir.glob("*.callgraph.json"))
        if len(manifests) == 0:
            print(f"FAIL  No *.callgraph.json found in {bundle_dir}")
            sys.exit(1)
        if len(manifests) > 1:
            print(f"FAIL  Multiple *.callgraph.json found — use --stem to specify")
            sys.exit(1)
        stem = manifests[0].name.replace(".callgraph.json", "")

    entities_path      = bundle_dir / f"{stem}.entities.jsonl"
    relationships_path = bundle_dir / f"{stem}.relationships.jsonl"
    manifest_path      = bundle_dir / f"{stem}.callgraph.json"

    for p in [entities_path, relationships_path, manifest_path]:
        if not p.exists():
            print(f"FAIL  Required bundle file missing: {p}")
            sys.exit(1)

    print(f"\nValidating bundle: {bundle_dir} (stem={stem!r})\n")

    entities      = load_jsonl(entities_path)
    relationships = load_jsonl(relationships_path)
    manifest      = load_json(manifest_path)

    result = Result()

    node_ids, edge_ids = check_schema(entities, relationships, result)
    print()
    check_invariants(entities, relationships, manifest, node_ids, result)
    print()

    result.print_all()
    print()

    total_errors   = len(result.errors)
    total_warnings = len(result.warnings)

    if result.passed():
        print(f"RESULT: PASS  ({total_warnings} warning(s), 0 error(s))")
        sys.exit(0)
    else:
        print(f"RESULT: FAIL  ({total_errors} error(s), {total_warnings} warning(s))")
        sys.exit(1)


if __name__ == "__main__":
    main()
