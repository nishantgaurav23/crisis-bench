Generate a comprehensive explanation of a completed spec.

## Input
- Spec ID: $ARGUMENTS (e.g., "S1.4")

## Instructions

This command creates `explanation.md` in the spec folder. It documents the "why", "what", and "how" of the spec — serving as a knowledge artifact for understanding the system architecture.

1. **Read the spec files**:
   - `specs/spec-{ID}-*/spec.md` — requirements and outcomes
   - `specs/spec-{ID}-*/checklist.md` — implementation tracker
   - The actual source code files listed in spec.md "Target Location"
   - The test files

2. **Read context files**:
   - `roadmap.md` — understand where this spec sits in the project
   - `design.md` — understand the architectural context
   - `requirements.md` — understand which FRs this spec satisfies

3. **Create `specs/spec-{ID}-{slug}/explanation.md`** with this structure:

```markdown
# Spec {ID}: {Feature Name} — Explanation

## Why This Spec Exists

### The Problem
[What problem does this functionality solve? Why can't the project work without it?]

### The Need
[Why was this specific approach chosen? What alternatives were considered?]

### Requirements Addressed
[List the FR-xxx and NFR-xxx requirements from requirements.md that this spec satisfies]

## What It Does

### In One Sentence
[Single sentence: "{Spec name} provides {capability} so that {benefit}"]

### Key Capabilities
1. **{Capability 1}**: [What it does and what calls it]
2. **{Capability 2}**: [What it does and what calls it]

### Important Functions / Classes
| Function/Class | Purpose | Called By |
|---------------|---------|----------|
| `function_name()` | What it does | Which modules call it |
| `ClassName` | What it represents | Where it's used |

### Data Flow
[How data enters, is processed, and exits this module. Include Redis streams, DB tables, or API endpoints involved.]

## How It Works

### Architecture
[Brief description of the internal design — patterns used, key decisions]

### Implementation Details
[Notable implementation choices: why async, why this data structure, why this algorithm]

### Error Handling & Degradation
[How failures are handled. For LLM calls: what's the fallback chain? For DB calls: what happens on connection loss?]

## How It Connects to the Project

### Upstream Dependencies
[What this spec depends on — and why each dependency is needed]
| Dependency | Why Needed |
|-----------|-----------|
| S{x}.{y} | Provides X that this spec uses for Y |

### Downstream Dependents
[What specs depend on this one — found by searching roadmap.md "Depends On" column]
| Dependent | How It Uses This Spec |
|----------|---------------------|
| S{x}.{y} | Uses X to do Y |

### Redis Streams / DB Tables / APIs
[Which shared resources this spec reads from or writes to]

### Agent Interactions
[If this spec is used by agents: which agents use it and how]

## Testing Summary
- Total tests: X
- Key test scenarios: [list the most important 3-5 tests and what they verify]
- Mocks used: [what external services are mocked]
```

4. **Verify the explanation** — ensure all sections are filled with specific, accurate information from the actual code (not generic placeholders).

## Purpose

This explanation serves multiple goals:
- **Onboarding**: A new developer can read this to understand the module without reading all the code
- **Architecture documentation**: Shows how the module fits into the larger system
- **Decision record**: Captures why specific approaches were chosen
- **Spec-to-code traceability**: Links requirements to implementation
