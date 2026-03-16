"""Neo4j infrastructure graph setup — connectivity check and seed data.

Seeds infrastructure dependency graph for 10 major Indian states so that
the InfraStatus agent can query real infrastructure data during benchmarks.
Uses the InfraGraphManager from src/data/ingest/infra_graph.py for the 5
cities already defined there, and adds 5 additional states directly.

Never crashes — logs warnings and returns False if Neo4j is unavailable.
"""

from __future__ import annotations

import logging

import neo4j

from src.shared.config import get_settings

logger = logging.getLogger("crisis.neo4j_setup")

# =============================================================================
# Additional state seed data (supplements the 5 cities in infra_graph.py)
# infra_graph.py covers: Maharashtra, Tamil Nadu, West Bengal, Odisha, Assam
# We add: Kerala, Bihar, Gujarat, Delhi, Uttarakhand
# =============================================================================

ADDITIONAL_STATES: dict[str, dict] = {
    "Kerala": {
        "power_grids": [
            {"name": "KSEB Trivandrum Substation", "type": "distribution",
             "capacity_mw": 450, "backup_hours": 6},
            {"name": "Idukki Hydro Station", "type": "generation",
             "capacity_mw": 780, "backup_hours": 0},
            {"name": "KSEB Kochi Grid", "type": "distribution",
             "capacity_mw": 520, "backup_hours": 4},
        ],
        "telecom_towers": [
            {"name": "Jio Tower Ernakulam-001", "operator": "Jio",
             "backup_hours": 8, "coverage_radius_km": 5.0},
            {"name": "BSNL Exchange Trivandrum", "operator": "BSNL",
             "backup_hours": 4, "coverage_radius_km": 3.5},
            {"name": "Airtel Tower Kozhikode-001", "operator": "Airtel",
             "backup_hours": 6, "coverage_radius_km": 4.0},
        ],
        "hospitals": [
            {"name": "Trivandrum Medical College", "beds": 2500,
             "has_generator": True, "backup_hours": 48},
            {"name": "Amrita Hospital Kochi", "beds": 1200,
             "has_generator": True, "backup_hours": 24},
        ],
        "water_treatment": [
            {"name": "Aruvikkara WTP Trivandrum", "capacity_mld": 180,
             "backup_hours": 8},
            {"name": "Aluva WTP Kochi", "capacity_mld": 270,
             "backup_hours": 6},
        ],
        "roads": [
            {"name": "NH-66 Trivandrum-Kochi", "length_km": 220, "lanes": 4},
            {"name": "NH-544 Kochi-Salem", "length_km": 195, "lanes": 4},
            {"name": "MC Road Trivandrum-Angamaly", "length_km": 168, "lanes": 2},
        ],
        "bridges": [
            {"name": "Periyar Bridge Aluva", "load_capacity_tons": 60},
        ],
        "railways": [
            {"name": "Ernakulam Junction", "daily_trains": 120},
            {"name": "Trivandrum Central", "daily_trains": 95},
        ],
    },
    "Bihar": {
        "power_grids": [
            {"name": "BSPHCL Patna Grid", "type": "distribution",
             "capacity_mw": 600, "backup_hours": 4},
            {"name": "Barh Super Thermal", "type": "generation",
             "capacity_mw": 1320, "backup_hours": 0},
            {"name": "Kanti Thermal Station", "type": "generation",
             "capacity_mw": 610, "backup_hours": 0},
        ],
        "telecom_towers": [
            {"name": "Jio Tower Patna-001", "operator": "Jio",
             "backup_hours": 8, "coverage_radius_km": 5.0},
            {"name": "BSNL Exchange Muzaffarpur", "operator": "BSNL",
             "backup_hours": 4, "coverage_radius_km": 3.0},
        ],
        "hospitals": [
            {"name": "PMCH Patna", "beds": 2500,
             "has_generator": True, "backup_hours": 36},
            {"name": "SKMCH Muzaffarpur", "beds": 800,
             "has_generator": True, "backup_hours": 12},
            {"name": "IGIMS Patna", "beds": 600,
             "has_generator": True, "backup_hours": 24},
        ],
        "water_treatment": [
            {"name": "Saidpur WTP Patna", "capacity_mld": 250,
             "backup_hours": 6},
        ],
        "roads": [
            {"name": "NH-31 Patna-Purnia", "length_km": 320, "lanes": 4},
            {"name": "NH-19 Patna-Varanasi", "length_km": 250, "lanes": 4},
        ],
        "bridges": [
            {"name": "Mahatma Gandhi Setu Patna", "load_capacity_tons": 40},
            {"name": "Digha-Sonpur Rail-Road Bridge", "load_capacity_tons": 50},
        ],
        "railways": [
            {"name": "Patna Junction", "daily_trains": 180},
        ],
    },
    "Gujarat": {
        "power_grids": [
            {"name": "GETCO Ahmedabad Grid", "type": "distribution",
             "capacity_mw": 800, "backup_hours": 6},
            {"name": "Mundra Ultra Mega Power", "type": "generation",
             "capacity_mw": 4620, "backup_hours": 0},
            {"name": "PGVCL Rajkot Substation", "type": "distribution",
             "capacity_mw": 350, "backup_hours": 4},
            {"name": "Dhuvaran Gas Power Station", "type": "generation",
             "capacity_mw": 540, "backup_hours": 0},
        ],
        "telecom_towers": [
            {"name": "Jio Tower Ahmedabad-001", "operator": "Jio",
             "backup_hours": 10, "coverage_radius_km": 5.5},
            {"name": "Airtel Tower Surat-001", "operator": "Airtel",
             "backup_hours": 6, "coverage_radius_km": 4.0},
            {"name": "BSNL Exchange Bhuj", "operator": "BSNL",
             "backup_hours": 4, "coverage_radius_km": 3.0},
        ],
        "hospitals": [
            {"name": "Civil Hospital Ahmedabad", "beds": 3000,
             "has_generator": True, "backup_hours": 48},
            {"name": "Sir T Hospital Bhavnagar", "beds": 900,
             "has_generator": True, "backup_hours": 18},
            {"name": "New Civil Hospital Surat", "beds": 1600,
             "has_generator": True, "backup_hours": 36},
        ],
        "water_treatment": [
            {"name": "Jaspur WTP Ahmedabad", "capacity_mld": 450,
             "backup_hours": 8},
            {"name": "Narmada Canal WTP Rajkot", "capacity_mld": 200,
             "backup_hours": 6},
        ],
        "roads": [
            {"name": "NH-48 Ahmedabad-Mumbai", "length_km": 530, "lanes": 6},
            {"name": "NH-27 Ahmedabad-Rajkot", "length_km": 215, "lanes": 4},
            {"name": "SH-6 Bhuj-Gandhidham", "length_km": 57, "lanes": 2},
        ],
        "bridges": [
            {"name": "Sabarmati Riverfront Bridge", "load_capacity_tons": 55},
        ],
        "railways": [
            {"name": "Ahmedabad Junction", "daily_trains": 200},
            {"name": "Rajkot Junction", "daily_trains": 75},
        ],
    },
    "Delhi": {
        "power_grids": [
            {"name": "BSES Rajdhani Grid", "type": "distribution",
             "capacity_mw": 1200, "backup_hours": 6},
            {"name": "BSES Yamuna Grid", "type": "distribution",
             "capacity_mw": 900, "backup_hours": 6},
            {"name": "Tata Power Delhi Distribution", "type": "distribution",
             "capacity_mw": 1800, "backup_hours": 8},
            {"name": "Pragati Gas Power Station", "type": "generation",
             "capacity_mw": 750, "backup_hours": 0},
            {"name": "Badarpur Thermal (decommissioned)", "type": "generation",
             "capacity_mw": 0, "backup_hours": 0},
        ],
        "telecom_towers": [
            {"name": "Jio Tower Connaught Place-001", "operator": "Jio",
             "backup_hours": 10, "coverage_radius_km": 4.0},
            {"name": "Airtel Tower Dwarka-001", "operator": "Airtel",
             "backup_hours": 8, "coverage_radius_km": 4.5},
            {"name": "MTNL Exchange ITO", "operator": "MTNL",
             "backup_hours": 6, "coverage_radius_km": 3.0},
        ],
        "hospitals": [
            {"name": "AIIMS New Delhi", "beds": 2500,
             "has_generator": True, "backup_hours": 72},
            {"name": "Safdarjung Hospital", "beds": 1800,
             "has_generator": True, "backup_hours": 48},
            {"name": "GTB Hospital Dilshad Garden", "beds": 1500,
             "has_generator": True, "backup_hours": 36},
        ],
        "water_treatment": [
            {"name": "Wazirabad WTP", "capacity_mld": 480,
             "backup_hours": 10},
            {"name": "Chandrawal WTP", "capacity_mld": 360,
             "backup_hours": 8},
        ],
        "roads": [
            {"name": "NH-44 Delhi-Gurugram", "length_km": 32, "lanes": 8},
            {"name": "NH-9 Delhi-Meerut Expressway", "length_km": 96, "lanes": 6},
        ],
        "bridges": [
            {"name": "ITO Bridge Yamuna", "load_capacity_tons": 50},
            {"name": "Signature Bridge Wazirabad", "load_capacity_tons": 70},
        ],
        "railways": [
            {"name": "New Delhi Railway Station", "daily_trains": 350},
            {"name": "Hazrat Nizamuddin Station", "daily_trains": 150},
        ],
    },
    "Uttarakhand": {
        "power_grids": [
            {"name": "UPCL Dehradun Grid", "type": "distribution",
             "capacity_mw": 280, "backup_hours": 4},
            {"name": "Tehri Hydro Station", "type": "generation",
             "capacity_mw": 1000, "backup_hours": 0},
            {"name": "UPCL Haridwar Substation", "type": "distribution",
             "capacity_mw": 200, "backup_hours": 4},
        ],
        "telecom_towers": [
            {"name": "Jio Tower Dehradun-001", "operator": "Jio",
             "backup_hours": 6, "coverage_radius_km": 4.0},
            {"name": "BSNL Exchange Joshimath", "operator": "BSNL",
             "backup_hours": 4, "coverage_radius_km": 2.5},
        ],
        "hospitals": [
            {"name": "Doon Hospital Dehradun", "beds": 800,
             "has_generator": True, "backup_hours": 24},
            {"name": "AIIMS Rishikesh", "beds": 960,
             "has_generator": True, "backup_hours": 48},
        ],
        "water_treatment": [
            {"name": "Rispana WTP Dehradun", "capacity_mld": 80,
             "backup_hours": 6},
        ],
        "roads": [
            {"name": "NH-58 Dehradun-Badrinath", "length_km": 300, "lanes": 2},
            {"name": "NH-7 Haridwar-Rishikesh", "length_km": 25, "lanes": 4},
            {"name": "Char Dham Highway Rudraprayag", "length_km": 120, "lanes": 2},
        ],
        "bridges": [
            {"name": "Lakshman Jhula Rishikesh", "load_capacity_tons": 20},
            {"name": "Dobra Chanti Bridge Tehri", "load_capacity_tons": 45},
        ],
        "railways": [
            {"name": "Dehradun Railway Station", "daily_trains": 40},
        ],
    },
}


# =============================================================================
# Seeding Logic
# =============================================================================


async def _count_nodes(session: neo4j.AsyncSession) -> int:
    """Return total node count in the graph."""
    result = await session.run("MATCH (n) RETURN count(n) AS cnt")
    record = await result.single()
    return record["cnt"] if record else 0


async def _create_indexes(session: neo4j.AsyncSession) -> None:
    """Create indexes for query performance. Idempotent."""
    index_specs = [
        ("PowerGrid", "name"), ("Hospital", "name"), ("State", "name"),
        ("TelecomTower", "name"), ("WaterTreatment", "name"),
        ("Road", "name"), ("Bridge", "name"), ("Railway", "name"),
    ]
    for label, prop in index_specs:
        await session.run(
            f"CREATE INDEX idx_{label.lower()}_{prop} "
            f"IF NOT EXISTS FOR (n:{label}) ON (n.{prop})"
        )
    # State index for all infra types
    for label in ["PowerGrid", "Hospital", "TelecomTower", "WaterTreatment",
                   "Road", "Bridge", "Railway"]:
        await session.run(
            f"CREATE INDEX idx_{label.lower()}_state "
            f"IF NOT EXISTS FOR (n:{label}) ON (n.state)"
        )


async def _seed_state(session: neo4j.AsyncSession, state: str, data: dict) -> int:
    """Seed infrastructure for one state. Returns node count created."""
    count = 0

    # PowerGrid nodes
    for pg in data.get("power_grids", []):
        await session.run(
            "MERGE (n:PowerGrid {name: $name, state: $state}) "
            "SET n.type = $type, n.capacity_mw = $cap, n.backup_hours = $bh, "
            "n.status = 'operational'",
            name=pg["name"], state=state, type=pg["type"],
            cap=pg["capacity_mw"], bh=pg.get("backup_hours", 0),
        )
        count += 1

    # TelecomTower nodes
    for tt in data.get("telecom_towers", []):
        await session.run(
            "MERGE (n:TelecomTower {name: $name, state: $state}) "
            "SET n.operator = $op, n.backup_hours = $bh, "
            "n.coverage_radius_km = $cr, n.status = 'operational'",
            name=tt["name"], state=state, op=tt["operator"],
            bh=tt["backup_hours"], cr=tt.get("coverage_radius_km", 0.0),
        )
        count += 1

    # Hospital nodes
    for h in data.get("hospitals", []):
        await session.run(
            "MERGE (n:Hospital {name: $name, state: $state}) "
            "SET n.beds = $beds, n.has_generator = $gen, "
            "n.backup_hours = $bh, n.status = 'operational'",
            name=h["name"], state=state, beds=h["beds"],
            gen=h.get("has_generator", False), bh=h.get("backup_hours", 0),
        )
        count += 1

    # WaterTreatment nodes
    for wt in data.get("water_treatment", []):
        await session.run(
            "MERGE (n:WaterTreatment {name: $name, state: $state}) "
            "SET n.capacity_mld = $cap, n.backup_hours = $bh, "
            "n.status = 'operational'",
            name=wt["name"], state=state, cap=wt["capacity_mld"],
            bh=wt.get("backup_hours", 0),
        )
        count += 1

    # Road nodes
    for r in data.get("roads", []):
        await session.run(
            "MERGE (n:Road {name: $name, state: $state}) "
            "SET n.length_km = $lkm, n.lanes = $lanes, "
            "n.status = 'operational'",
            name=r["name"], state=state,
            lkm=r.get("length_km", 0), lanes=r.get("lanes", 2),
        )
        count += 1

    # Bridge nodes
    for b in data.get("bridges", []):
        await session.run(
            "MERGE (n:Bridge {name: $name, state: $state}) "
            "SET n.load_capacity_tons = $lct, n.status = 'operational'",
            name=b["name"], state=state, lct=b["load_capacity_tons"],
        )
        count += 1

    # Railway nodes
    for rw in data.get("railways", []):
        await session.run(
            "MERGE (n:Railway {name: $name, state: $state}) "
            "SET n.daily_trains = $dt, n.status = 'operational'",
            name=rw["name"], state=state, dt=rw["daily_trains"],
        )
        count += 1

    # ---- DEPENDS_ON relationships (cascading failure chains) ----

    power_grids = data.get("power_grids", [])
    if not power_grids:
        return count

    primary_pg = power_grids[0]["name"]

    # Hospital -> PowerGrid
    for h in data.get("hospitals", []):
        await session.run(
            "MATCH (h:Hospital {name: $h_name, state: $state}) "
            "MATCH (pg:PowerGrid {name: $pg_name, state: $state}) "
            "MERGE (h)-[:DEPENDS_ON {priority: 'critical'}]->(pg)",
            h_name=h["name"], state=state, pg_name=primary_pg,
        )

    # TelecomTower -> PowerGrid
    for tt in data.get("telecom_towers", []):
        await session.run(
            "MATCH (tt:TelecomTower {name: $tt_name, state: $state}) "
            "MATCH (pg:PowerGrid {name: $pg_name, state: $state}) "
            "MERGE (tt)-[:DEPENDS_ON {priority: 'critical'}]->(pg)",
            tt_name=tt["name"], state=state, pg_name=primary_pg,
        )

    # WaterTreatment -> PowerGrid
    for wt in data.get("water_treatment", []):
        await session.run(
            "MATCH (wt:WaterTreatment {name: $wt_name, state: $state}) "
            "MATCH (pg:PowerGrid {name: $pg_name, state: $state}) "
            "MERGE (wt)-[:DEPENDS_ON {priority: 'critical'}]->(pg)",
            wt_name=wt["name"], state=state, pg_name=primary_pg,
        )

    # Hospital -> WaterTreatment (first WTP)
    water_plants = data.get("water_treatment", [])
    if water_plants:
        primary_wt = water_plants[0]["name"]
        for h in data.get("hospitals", []):
            await session.run(
                "MATCH (h:Hospital {name: $h_name, state: $state}) "
                "MATCH (wt:WaterTreatment {name: $wt_name, state: $state}) "
                "MERGE (h)-[:DEPENDS_ON {priority: 'high'}]->(wt)",
                h_name=h["name"], state=state, wt_name=primary_wt,
            )

    # TelecomTower -> Road (first road, for maintenance access)
    roads = data.get("roads", [])
    if roads:
        primary_road = roads[0]["name"]
        for tt in data.get("telecom_towers", []):
            await session.run(
                "MATCH (tt:TelecomTower {name: $tt_name, state: $state}) "
                "MATCH (r:Road {name: $r_name, state: $state}) "
                "MERGE (tt)-[:DEPENDS_ON {priority: 'moderate'}]->(r)",
                tt_name=tt["name"], state=state, r_name=primary_road,
            )

    return count


async def _seed_all(driver: neo4j.AsyncDriver) -> int:
    """Seed the 5 additional states and also trigger InfraGraphManager for the original 5."""
    total = 0

    # Seed additional states via direct Cypher
    async with driver.session() as session:
        await _create_indexes(session)
        for state_name, state_data in ADDITIONAL_STATES.items():
            n = await _seed_state(session, state_name, state_data)
            total += n
            logger.info("neo4j_state_seeded", extra={"state": state_name, "nodes": n})

    # Seed original 5 cities via InfraGraphManager (reuses existing logic)
    try:
        from src.data.ingest.infra_graph import InfraGraphManager

        mgr = InfraGraphManager()
        mgr._driver = driver  # reuse the already-connected driver
        await mgr.init_schema()
        await mgr.seed_all()
        # Don't close — we passed our driver in, caller manages lifetime
        mgr._driver = None
        logger.info("neo4j_infra_graph_seeded", extra={"cities": 5})
        total += 50  # approximate count for the 5 existing cities
    except Exception as exc:
        logger.warning(
            "neo4j_infra_graph_seed_partial",
            extra={"error": str(exc)},
        )

    return total


# =============================================================================
# Public API
# =============================================================================


async def ensure_neo4j_ready() -> bool:
    """Check Neo4j connectivity and seed infrastructure graph if empty.

    Returns True if Neo4j is available and seeded, False otherwise.
    Never raises — all errors are caught and logged.
    """
    settings = get_settings()
    driver: neo4j.AsyncDriver | None = None

    try:
        driver = neo4j.AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
        await driver.verify_connectivity()
        logger.info("neo4j_connected", extra={"uri": settings.NEO4J_URI})

        # Check if data already exists
        async with driver.session() as session:
            node_count = await _count_nodes(session)

        if node_count > 10:
            logger.info(
                "neo4j_already_seeded",
                extra={"node_count": node_count},
            )
            return True

        # Seed infrastructure graph
        logger.info("neo4j_seeding_start")
        total = await _seed_all(driver)
        logger.info("neo4j_seeding_complete", extra={"total_nodes": total})
        return True

    except Exception as exc:
        logger.warning(
            "neo4j_setup_failed",
            extra={"error": str(exc), "uri": settings.NEO4J_URI},
        )
        return False

    finally:
        if driver is not None:
            try:
                await driver.close()
            except Exception:
                pass
