# Spec S5.4: OpenStreetMap Overpass MCP Server

**Phase**: 5 — MCP Data Servers
**Status**: pending
**Depends On**: S4.4 (MCP base framework)
**Location**: `src/protocols/mcp/osm_server.py`
**Tests**: `tests/unit/test_mcp_osm.py`

---

## Purpose

Wrap the OpenStreetMap Overpass API as an MCP server so that agents (especially SituationSense, ResourceAllocation, InfraStatus) can query Indian infrastructure data — hospitals, shelters, roads, bridges, helipads, fire stations, and police stations — within geographic bounding boxes or radii.

The Overpass API is free, requires no authentication, and has excellent India coverage for tagged infrastructure.

---

## MCP Tools

| Tool | Parameters | Returns |
|------|-----------|---------|
| `find_hospitals` | `lat`, `lon`, `radius_km` | Hospitals/clinics within radius |
| `find_shelters` | `lat`, `lon`, `radius_km` | Emergency shelters, community halls, schools (common shelter types in India) |
| `find_roads` | `bbox` (south,west,north,east) | Major roads (highway, trunk, primary, secondary) in bounding box |
| `find_bridges` | `bbox` | Bridges in bounding box (critical for flood assessment) |
| `find_helipads` | `lat`, `lon`, `radius_km` | Helipads/airstrips for aerial rescue |
| `find_fire_stations` | `lat`, `lon`, `radius_km` | Fire stations within radius |
| `find_police_stations` | `lat`, `lon`, `radius_km` | Police stations within radius |

---

## API Details

- **Endpoint**: `https://overpass-api.de/api/interpreter`
- **Method**: POST with `data=<Overpass QL query>`
- **Auth**: None (free, public)
- **Rate Limit**: Self-imposed 10 RPM to be a good citizen
- **Response**: JSON (`[out:json]` format)
- **Timeout**: 25s per query (Overpass default)

---

## Overpass QL Query Patterns

### Radius search (hospitals within 10km of lat/lon):
```
[out:json][timeout:25];
(
  node["amenity"="hospital"](around:10000,19.076,72.877);
  way["amenity"="hospital"](around:10000,19.076,72.877);
);
out center;
```

### Bounding box search (roads in bbox):
```
[out:json][timeout:25];
(
  way["highway"~"motorway|trunk|primary|secondary"](south,west,north,east);
);
out geom;
```

---

## Response Normalization

Each element from Overpass is normalized to:
```json
{
  "osm_id": 123456,
  "osm_type": "node|way|relation",
  "name": "AIIMS Hospital",
  "lat": 28.567,
  "lon": 77.210,
  "tags": {"amenity": "hospital", "beds": "2500", ...}
}
```

For ways with `out center`, use the center coordinates. For ways with `out geom`, include the geometry as a list of coordinate pairs.

---

## Design Decisions

1. **POST not GET**: Overpass QL queries can be long; POST avoids URL length limits.
2. **Self-imposed rate limit (10 RPM)**: Overpass is a shared community resource. Being polite prevents IP bans.
3. **`out center` for point queries**: Hospitals/shelters as ways get a center point — simpler for agents than full geometry.
4. **`out geom` for road/bridge queries**: Roads need full geometry for routing and flood intersection analysis.
5. **India-centric defaults**: All examples use Indian coordinates; shelter query includes schools and community halls (standard India disaster shelters per NDMA guidelines).

---

## Outcomes

1. `OSMOverpassServer` class extends `BaseMCPServer` with 7 MCP tools
2. All tools use Overpass QL via POST to `overpass-api.de`
3. Response normalization extracts `osm_id`, `name`, `lat`, `lon`, `tags`
4. Rate limited to 10 RPM (self-imposed, good citizen)
5. All external HTTP calls mocked in tests
6. `create_server()` factory function provided
7. Lint clean with ruff (line-length: 100)

---

## TDD Notes

### Red Phase — Tests to write FIRST:
1. **Init tests**: name, base URL, rate limit, no auth, all 7 tools registered
2. **`find_hospitals`**: returns normalized hospital data, passes lat/lon/radius
3. **`find_shelters`**: returns shelters (amenity=shelter + community centres + schools)
4. **`find_roads`**: returns roads with geometry, uses bbox
5. **`find_bridges`**: returns bridges in bbox
6. **`find_helipads`**: returns helipads/airstrips
7. **`find_fire_stations`**: returns fire stations
8. **`find_police_stations`**: returns police stations
9. **Response normalization**: node elements, way elements with center, way elements with geometry
10. **Error handling**: timeout, 429 rate limit, malformed response, empty results
11. **`create_server()` factory**: returns `OSMOverpassServer` instance
