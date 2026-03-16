# S7.6 CommunityComms Agent — Implementation Checklist

## Phase 1: Tests (Red)
- [x] Write test_community_comms.py with all 7 test groups
- [x] All tests fail (no implementation yet)

## Phase 2: Implementation (Green)
- [x] State-to-language mapping (STATE_LANGUAGES dict)
- [x] CommunityCommsState TypedDict
- [x] CommunityComms class extending BaseAgent
- [x] parse_alert node
- [x] select_languages node
- [x] generate_messages node
- [x] format_channels node (WhatsApp, SMS, social, media)
- [x] counter_misinfo node
- [x] build_graph() with 5 nodes wired
- [x] All tests pass

## Phase 3: Refactor
- [x] ruff lint clean
- [x] No hardcoded secrets
- [x] All async patterns correct
- [x] Code documented

## Phase 4: Verify
- [x] All 23 tests pass
- [x] Coverage >80%
- [x] roadmap.md updated
