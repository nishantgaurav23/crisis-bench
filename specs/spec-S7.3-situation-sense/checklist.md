# Checklist S7.3 — SituationSense Agent

## Phase 1: Red (Write Failing Tests)
- [x] Write test_situation_sense.py with all test groups
- [x] Verify all tests fail (module doesn't exist yet)

## Phase 2: Green (Implement)
- [x] Create SituationState TypedDict
- [x] Create SituationSense class extending BaseAgent
- [x] Implement get_system_prompt()
- [x] Implement get_agent_card()
- [x] Implement build_graph() with all 5 nodes
- [x] Implement ingest_data node
- [x] Implement fuse_sources node
- [x] Implement score_urgency node
- [x] Implement detect_misinfo node
- [x] Implement produce_sitrep node
- [x] Implement urgency mapping helper
- [x] All 23 tests pass

## Phase 3: Refactor
- [x] Run ruff lint + fix
- [x] Verify all tests still pass
- [x] Update checklist status
