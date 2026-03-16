# S7.6 CommunityComms Agent — Explanation

## Why This Spec Exists

In Indian disaster scenarios, effective communication saves lives — but India's linguistic diversity (22 scheduled languages, 9 dominant in disaster-prone states) means a single English alert reaches only ~10% of affected populations. The CommunityComms agent bridges this gap by generating audience-adapted, multilingual alerts formatted for India's dominant communication channels (WhatsApp > SMS > social media).

This agent also addresses misinformation — a critical problem during Indian disasters where WhatsApp rumors spread faster than official advisories. Counter-messaging with official source citations is essential.

## What It Does

**CommunityComms** is a LangGraph state machine with 5 nodes:

1. **parse_alert** — Extracts disaster type, severity, affected areas, shelter info, and rumors from the task payload. Hardcodes NDRF (9711077372) and state (1070) helpline numbers.

2. **select_languages** — Uses a hardcoded `STATE_LANGUAGES` mapping (36 states/UTs → 9 languages) to determine which languages to generate alerts in. Hindi is always included as pan-India fallback.

3. **generate_messages** — Uses LLM (routine tier, Qwen Flash) to generate 3 audience-adapted messages:
   - **First responder**: Technical English with NDRF coordination details
   - **General public**: Simple language with shelter + helpline info
   - **Vulnerable**: Very simple directives
   Then translates the public message into target languages via a second LLM call.

4. **format_channels** — Pure Python formatting (no LLM) for 4 channels:
   - **WhatsApp**: Emoji-rich, bold headers, bullet points
   - **SMS**: 160-char truncation with `format_sms()` utility
   - **Social media**: Hashtag-driven, includes state name
   - **Media briefing**: Formal, structured for press

5. **counter_misinfo** — When rumors are present in the payload, uses LLM to generate counter-messages citing official sources (IMD, NDMA, CWC).

## How It Works

- **LLM Tier**: Routine (Qwen Flash, $0.04/M tokens) — alert text is high-volume but low-complexity
- **Translation Strategy**: LLM-based translation (not Bhashini API) to keep the agent self-contained and testable without external dependencies. Bhashini TTS is a stub for future integration.
- **State-to-Language Mapping**: Domain knowledge hardcoded as a dict. This is more reliable than LLM-based language detection and costs $0.
- **SMS Formatting**: `format_sms()` is a pure function that truncates to 160 chars with `...` — exported for direct testing.

## How It Connects

| Connection | Direction | Details |
|-----------|-----------|---------|
| **S7.1 BaseAgent** | Inherits | LangGraph state machine, LLM Router, A2A protocol, Langfuse tracing |
| **S7.2 Orchestrator** | Receives tasks from | Orchestrator delegates alert generation after SituationSense + PredictiveRisk |
| **S7.3 SituationSense** | Consumes output | Uses situation summaries and misinformation flags as input |
| **S7.5 ResourceAllocation** | Consumes output | Includes shelter assignments and evacuation routes in alerts |
| **S3.2 WebSocket** | Publishes to | Alert messages pushed to dashboard via WebSocket |

## Interview Q&A

**Q: Why use LLM for translation instead of a dedicated translation API like Bhashini?**
A: Three reasons: (1) Self-containment — the agent works without external API dependencies, which is critical for testing and offline fallback. (2) Context-aware translation — the LLM translates in the context of disaster alerts, not generic text, so it uses appropriate terminology. (3) Simplicity — one LLM call vs. managing Bhashini auth tokens, rate limits, and API errors. Trade-off: LLM translation quality may be lower for less-resourced languages (e.g., Odia), which is why Bhashini TTS is stubbed for future integration.

**Q: Why hardcode the state-to-language mapping instead of using an LLM?**
A: This is static domain knowledge that doesn't change. Using an LLM would add latency, cost, and potential for hallucination (imagine the LLM deciding Gujarat speaks Tamil). A dict lookup is O(1), free, and 100% reliable. The LLM is reserved for tasks that actually require reasoning.

**Q: Why is SMS limited to 160 characters?**
A: GSM-7 encoding (the standard for SMS) supports 160 characters per segment. Multi-segment SMS is unreliable on Indian telecom networks during disasters (when cell towers are overloaded). Keeping alerts to 1 segment maximizes delivery probability. The `format_sms()` function truncates with `...` to indicate there's more info available via other channels.

**Q: How does the misinformation counter-messaging work?**
A: When the Orchestrator or SituationSense agent detects rumors (via social media analysis), they're passed in the task payload. The CommunityComms agent uses the LLM to generate counter-messages that: (1) restate the rumor, (2) provide the corrected fact, (3) cite the official source (e.g., "IMD Cyclone Bulletin #47"). This follows NDMA's counter-messaging guidelines — acknowledge the rumor, then correct it with authority.
