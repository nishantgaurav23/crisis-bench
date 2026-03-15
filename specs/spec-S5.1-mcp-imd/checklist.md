# S5.1 Implementation Checklist

## Phase 1: Red (Write Failing Tests)
- [x] Test IMDServer initialization and tool registration
- [x] Test get_district_warnings with mock response
- [x] Test get_district_rainfall with mock response
- [x] Test get_cyclone_info with mock response
- [x] Test get_city_forecast with mock response
- [x] Test get_aws_data with mock response
- [x] Test error handling (timeout, 404, server error)
- [x] Test create_server() factory

## Phase 2: Green (Implement)
- [x] Implement IMDServer class extending BaseMCPServer
- [x] Implement all 5 tool methods
- [x] Implement create_server() factory function
- [x] All 19 tests pass

## Phase 3: Refactor
- [x] Run ruff — lint clean
- [x] All tests still pass
- [x] No hardcoded secrets
