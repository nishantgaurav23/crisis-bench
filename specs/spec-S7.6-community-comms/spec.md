# Spec S7.6 — CommunityComms Agent

**Status**: done

**Phase**: 7 (Agent System)
**Depends On**: S7.1 (BaseAgent)
**Location**: `src/agents/community_comms.py`
**Test File**: `tests/unit/test_community_comms.py`

---

## Overview

The CommunityComms agent generates **multilingual emergency alerts** for Indian disaster scenarios. It translates messages into 9 Indian languages, formats them for different channels (WhatsApp, SMS, media briefing), adapts tone for different audiences (first responders vs. general public vs. vulnerable populations), and generates misinformation counter-messaging.

**LLM Tier**: Routine (Qwen Flash, $0.04/M tokens) — alert generation is high-volume, low-complexity text.

---

## Requirements (from FR-005)

| ID | Requirement |
|----|-------------|
| FR-005.1 | Generate alerts in 9 Indian languages: Hindi, Bengali, Tamil, Telugu, Odia, Marathi, Gujarati, Kannada, Malayalam |
| FR-005.2 | Adapt messaging for audiences: first responders (technical/English), general public (simple/local language), vulnerable populations (simple directives) |
| FR-005.3 | Generate misinformation counter-messaging with source citations |
| FR-005.4 | Format for Indian channels: WhatsApp broadcast, SMS, social media, media briefing |
| FR-005.5 | Follow NDMA communication guidelines and state SDMA protocols |
| FR-005.6 | Include actionable instructions: nearest shelter, helpline numbers (NDRF: 9711077372, state: 1070), evacuation routes |
| FR-005.7 | Support text-to-speech via Bhashini TTS API (stub — actual integration is external) |

---

## LangGraph State Machine

```
parse_alert -> select_languages -> generate_messages -> format_channels -> counter_misinfo -> END
```

### Nodes

1. **parse_alert**: Extract disaster type, severity, affected areas, actionable info from task payload
2. **select_languages**: Determine appropriate languages based on affected state(s)
3. **generate_messages**: Use LLM to generate audience-adapted messages in English, then translate
4. **format_channels**: Format messages for WhatsApp, SMS, social media, media briefing
5. **counter_misinfo**: Generate misinformation counter-messaging if rumors present

---

## State Schema (CommunityCommsState)

```python
class CommunityCommsState(AgentState, total=False):
    alert_info: dict          # Parsed alert: disaster_type, severity, areas, instructions
    target_languages: list    # Languages to generate alerts in
    audience_messages: dict   # Messages keyed by audience type
    channel_formats: dict     # Messages formatted per channel
    counter_messages: list    # Misinformation counter-messages
```

---

## Key Design Decisions

1. **Translation via LLM**: Use the LLM (Qwen Flash) for translation instead of Bhashini API in the core path. Bhashini TTS is exposed as a helper method stub for future integration. This keeps the agent self-contained and testable without external API dependencies.

2. **State-to-Language Mapping**: Hardcoded mapping of Indian states to primary languages. This is domain knowledge, not LLM-dependent.

3. **Channel Formatting**: Pure Python string formatting — no LLM needed. WhatsApp has emoji + bullet formatting, SMS is 160-char limited, etc.

4. **NDMA Helpline Numbers**: Hardcoded constants (NDRF: 9711077372, state helpline: 1070). These are stable public numbers.

---

## Outcomes

- [ ] CommunityComms agent extends BaseAgent with ROUTINE tier
- [ ] 5-node LangGraph state machine compiles and runs
- [ ] State-to-language mapping covers all 36 states/UTs → 9 languages
- [ ] 3 audience adaptations: first_responder, general_public, vulnerable
- [ ] 4 channel formats: whatsapp, sms, social_media, media_briefing
- [ ] SMS format respects 160-char limit
- [ ] Misinformation counter-messaging generated when rumors present
- [ ] Helpline numbers (NDRF, state) included in public-facing messages
- [ ] All external services mocked in tests
- [ ] >80% code coverage

---

## TDD Notes

### Test Groups

1. **Initialization**: Correct AgentType, LLM tier, system prompt, agent card
2. **State Machine**: All 5 nodes present, graph compiles, end-to-end run
3. **Language Selection**: State-to-language mapping (Maharashtra → Marathi+Hindi, Tamil Nadu → Tamil+Hindi, etc.)
4. **Message Generation**: Audience adaptation (3 types), LLM called with correct prompts
5. **Channel Formatting**: WhatsApp/SMS/social/media format structure, SMS char limit
6. **Misinformation Countering**: Counter-messages generated when rumors present, empty when no rumors
7. **Edge Cases**: Empty payload, unknown state, missing fields, no languages matched
