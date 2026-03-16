# Explanation: S6.3 — Neo4j Infrastructure Dependency Graph

## Why This Spec Exists

Disaster response requires understanding **cascading infrastructure failures**. When a cyclone knocks out a power grid, you need to instantly know: which hospitals lose power, which telecom towers exhaust backup batteries, which water treatment plants stop, and which districts lose services. Relational databases handle this poorly — multi-hop dependency traversal requires recursive self-joins that scale as O(n × joins). Neo4j's graph model makes this O(path_length) with a single Cypher query.

This module is the foundation for the **InfraStatus agent** (S7.7), which will query this graph in real-time during disaster scenarios to predict cascading failures and recommend restoration priorities.

## What It Does

### Infrastructure Dependency Graph
Models Indian infrastructure as a directed graph with 8 node types and 5 relationship types:

**Nodes**: PowerGrid, TelecomTower, MobileNetwork, WaterTreatment, Hospital, Road, District, Shelter

**Edges**:
- `POWERS` — PowerGrid → TelecomTower, WaterTreatment, Hospital, Shelter
- `DEPENDS_ON` — Hospital → PowerGrid, WaterTreatment; WaterTreatment → PowerGrid
- `ENABLES` — TelecomTower → MobileNetwork
- `SERVES` — WaterTreatment → District; Hospital → District
- `ACCESSIBLE_VIA` — Hospital → Road; Shelter → Road

### Pre-seeded Data
5 Indian cities with realistic infrastructure:
- **Mumbai** (Maharashtra) — BEST, Tata Power, Adani grids; KEM, Sion, JJ hospitals; Bhandup WTP
- **Chennai** (Tamil Nadu) — TANGEDCO grids; Rajiv Gandhi GGH, Stanley Medical
- **Kolkata** (West Bengal) — CESC, WBSEDCL grids; SSKM, NRS hospitals
- **Bhubaneswar** (Odisha) — TPCODL, OPTCL grids; cyclone shelters (critical for Fani-like events)
- **Guwahati** (Assam) — APDCL, AEGCL grids; GMCH; flood shelters

~100 nodes, ~200 edges — well within NFR-010 limits (5,000 nodes / 20,000 edges).

### Cascading Failure Analysis
- `get_downstream_impacts()` — traverses dependency chains to find all affected nodes when one fails
- `get_upstream_dependencies()` — finds what a node depends on
- `simulate_failure()` — marks a node as damaged and returns the full cascade

### Query Utilities
- Infrastructure by district/state
- Status summary (operational/damaged/destroyed counts)
- Status updates

## How It Works

1. **Connection**: Uses `neo4j.AsyncGraphDatabase.driver` with config from `CrisisSettings` (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
2. **Schema**: Creates uniqueness constraints on `(name, state)` for each label, plus indexes on `status`, `state`, and `district`
3. **Seeding**: `MERGE` queries ensure idempotent data loading — safe to run multiple times
4. **Cascading Analysis**: Cypher variable-length path queries: `MATCH (affected)-[:DEPENDS_ON|POWERS*]->(source)` finds all transitively dependent nodes

Key design decisions:
- **MERGE over CREATE** — idempotent, handles re-runs gracefully
- **Composite uniqueness on (name, state)** — allows same-named infrastructure in different states
- **Status field on every node** — enables real-time status tracking during disaster simulation
- **Edge metadata (priority, backup_available)** — supports prioritized restoration ordering

## How It Connects

| Connection | Direction | Description |
|-----------|-----------|-------------|
| S1.3 (Config) | ← depends on | Reads NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD from CrisisSettings |
| S2.4 (Errors) | ← uses | Raises `GraphDBError` when Neo4j is unreachable |
| S7.7 (InfraStatus Agent) | → consumed by | Agent queries this graph for cascading failure analysis |
| S8.3 (Scenario Runner) | → consumed by | Runner updates node statuses to simulate infrastructure damage |

## Interview Talking Points

**Q: Why Neo4j instead of storing dependencies in PostgreSQL?**
A: Multi-hop traversal. "Find all infrastructure affected when this power grid fails" is a single Cypher query with variable-length paths: `MATCH (n)-[:DEPENDS_ON*]->(failed)`. In PostgreSQL, this requires recursive CTEs or application-level BFS — slower and harder to maintain. Neo4j also provides visual graph exploration through its browser UI, making debugging dependency chains intuitive.

**Q: How does the cascading failure analysis work?**
A: We use Cypher's variable-length path matching. `MATCH (affected)-[:DEPENDS_ON|POWERS*]->(source)` traverses all paths of any length following DEPENDS_ON or POWERS edges backward from the failed source node. Each `affected` node in the result set is a downstream casualty. The path itself is returned for visualization — "KEM Hospital lost power because Mumbai BEST grid failed."

**Q: Why MERGE instead of CREATE for seeding?**
A: Idempotency. `MERGE` is a conditional `CREATE` — it only creates the node/relationship if it doesn't already exist. This means you can run `seed_all()` multiple times without duplicating data. Critical for development workflows where you might restart the system frequently.
