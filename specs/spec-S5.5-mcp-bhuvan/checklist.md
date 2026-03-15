# S5.5 Implementation Checklist

## Phase 1: Red (Write Failing Tests)
- [x] Test BhuvanServer initialization and tool registration
- [x] Test geocode_village with mock response
- [x] Test get_satellite_layers with mock response
- [x] Test get_lulc_data with mock response
- [x] Test get_flood_layers with mock response
- [x] Test get_admin_boundary with mock response
- [x] Test error handling (timeout, 404, 401 expired token, server error)
- [x] Test token injection into query params
- [x] Test create_server() factory

## Phase 2: Green (Implement)
- [x] Implement BhuvanServer class extending BaseMCPServer
- [x] Implement token injection in api_get override
- [x] Implement all 5 tool methods
- [x] Implement create_server() factory function
- [x] All 22 tests pass

## Phase 3: Refactor
- [x] Run ruff — lint clean
- [x] All tests still pass
- [x] No hardcoded secrets
