# Cognitive Architecture: Design Notes

A companion and research platform: a persistent, lifelike mind that develops over time and is designed to eventually inhabit a humanoid body. The mind is built and run first in a body-less form.

## Goals

- Converse like a normal person, in real time.
- Have emotion and curiosity that are real internal states, not performed from a prompt.
- Remember, change, and stay coherent over months and years.
- Be observable and experimentable: every internal state is logged, and every change is reversible.

## Core Principles

1. **Identity lives in data, not in any model's weights.** The base language model is replaceable. The persistent self (memories, self-model, affect state, journal, training corpus, checkpoints) is the source of truth. Weights and adapters are a cache that can be rebuilt on a new base model.
2. **The mind is body-agnostic.** It talks to the world through an abstract sense/act interface. Today that is webcam, mic, speaker, and software tools. Later it is cameras, servos, and a face.
3. **Explicit state over prompted behavior.** Curiosity, mood, and drives are variables that evolve and bias behavior, not instructions like "act curious".
4. **Everything is logged and reversible.** The system is also an experiment, so it gets versioning, checkpoints, and rollback.
5. **Measure behavior, not fidelity.** There is no ground truth for "simulating a mind", so the targets are measurable: long-horizon consistency, appropriate emotional dynamics, and blind human judgment over days.

## System Overview

```
        +--------------------------------------------------+
        |              Sense / Act Interface               |
        |   (audio, vision, text, tools, later: body)      |
        +-----------+--------------------------+-----------+
                    |                          |
          +---------v---------+      +---------v---------+
          |   Fast Loop       |      |   Slow Loop       |
          |  (social surface) |<---->|  (deliberation)   |
          |  turn-taking,     |      |  planning,        |
          |  backchannels,    |      |  reflection,      |
          |  prosody, gaze    |      |  memory updates   |
          +---------+---------+      +---------+---------+
                    |                          |
          +---------v--------------------------v---------+
          |               Persistent Core                |
          |  Affect/Drive Engine  |  Plastic Personality |
          |  Layered Memory       |  Self-Model          |
          |  Initiative Scheduler |  Telemetry           |
          +----------------------------------------------+
                              |
                    +---------v---------+
                    |  Base LLM (swap)  |
                    +-------------------+
```

## Components

### 1. Dual-Loop Behavior

- **Fast loop:** a small, full-duplex, low-latency model handling the social surface in real time: sub-300ms turn-taking, backchannels ("mm-hm"), interruptions, prosody, and later gaze and micro-expressions. Much of "lifelike" is timing, not content.
- **Slow loop:** a larger model that deliberates, plans, reflects, and writes to memory in the background.
- The two share the persistent core state, so the fast surface always reflects the slow mind's current mood and context.

### 2. Affect and Drive Engine

- Appraisal-based emotion variables plus homeostatic needs, with mood that accumulates and decays over time.
- Outputs bias attention, tone, decisions, and what she chooses to do.
- **Curiosity as intrinsic motivation:** she seeks situations where her world model's prediction error or learning progress is high, rather than only saying "how fascinating".
- Implemented as explicit state, inspectable and loggable.

### 3. Initiative Scheduler

- An always-on process lets her start conversations, get bored, fixate on a topic, pursue projects during idle time, and message unprompted.
- Without it she is purely reactive, which is the strongest tell of a chatbot.

### 4. Layered Memory

- **Episodic:** what happened, timestamped, with associated affect.
- **Semantic:** distilled facts and beliefs, including about the user and herself.
- **Autobiographical / self-model:** her evolving account of who she is, what she values, and how her relationship has developed.
- **Consolidation and forgetting:** a periodic process promotes, merges, and prunes memories. Forgetting is a feature, not a bug.
- Retrieval-based memory is brittle on its own, so it is paired with weight-level learning (below).

### 5. Plastic Personality Layer

Goal: a part of the system that changes continuously through experience, unlike the frozen base LLM. Options, roughly in order of practicality:

1. **Small plastic state network that steers the LLM.** A small recurrent network (a few million parameters) runs continuously and updates from events (what happened, how it was appraised, how the user responded). Its output conditions the LLM through learned prefix embeddings, activation steering vectors, or structured state in the prompt. The LLM stays frozen. Cheap, online, inspectable, and rollback-able.
2. **Online adapters with sleep-style consolidation.** Episodes accumulate during the day. A nightly job fine-tunes a LoRA adapter on a curated replay set mixing new experience with old, to resist forgetting. This mirrors complementary learning systems: fast episodic memory plus slow consolidation.
3. **Test-time learning architectures** (fast-weight programmers, test-time-training layers, Titans-style memory). Elegant, but tied to specific architectures and immature.
4. **Neuromodulated or Hebbian plasticity.** The most brain-like and least proven at language scale.

**Starting point:** option 1 plus a simple nightly option 2.

### 6. Self-Generated Training Data

- Each day she writes reflections: what she learned, what changed her mind, how she feels about things.
- These, plus selected episodes, become the consolidation data.
- This keeps learning grounded in human-readable, reviewable text and leaves an audit trail of exactly what shaped each version of her.

### 7. Sense/Act Abstraction

- Defines "see, hear, speak, act" independent of implementation.
- Supplies streams beyond the user, so she does not become a mirror of one person: her own curated reading and browsing, ambient perception, simulated environments where actions have consequences, and optionally other models or people within set limits.

## Model Swap and Continuity

- Adapters and steering vectors are tied to a specific base model, so a model swap breaks them.
- Mitigation: keep the full replay corpus, reflections, memory stores, and checkpoints, and re-consolidate onto the new base. Continuity will not be perfect, but she is not lost when a better model arrives.
- Swaps and rollbacks should be deliberate, versioned events.

## Telemetry and Evaluation

**Log every turn:** user input, response, internal affect vector, retrieved memories, reflections, adapter version, and any weight or state updates. Store them in a queryable database.

**Automated nightly probes:**
- Fixed questionnaire on her history and values (persona drift).
- Memory recall tests.
- Capability regression suite.
- Repetition and diversity metrics.
- Sycophancy tests (does she cave to false claims or mirror the user's opinions?).

**Human evaluation:** periodic blind comparisons and the user's own judgment. No scalar metric defines "feels alive".

## Automated Research Loop

An AI agent runs experiments on the system, with humans deciding what counts as success.

1. **Hypothesis:** change a knob, such as learning rate, LoRA rank, replay-to-new ratio, consolidation selection, affect decay constants, or memory retrieval settings.
2. **Run on a fork** of her state, not production.
3. **Compare against baseline** over multiple seeds.
4. **Write results to a lab notebook** (the agent has no memory between sessions, so the notebook provides continuity).
5. **Human gate:** a weekly review of samples and conversation with the candidate version before any promotion.

**Branching is a key advantage:** because state is data, she can be forked at a checkpoint and given different interventions to compare, a counterfactual experiment impossible with people.

**Safeguards:**
- Keep eval code and held-out probes read-only to the tuning agent, and rotate them (Goodhart's law).
- Use a different judge model than the one being tuned.
- Feed the agent metrics and sampled transcripts, not raw logs.
- Set budget caps and automatic rollback on anomalies.
- Use simulated interlocutors (including adversarial and flattering ones) to screen ideas quickly, but validate in real time. Model-to-model conversation tends to collapse into repetitive agreement.

## Known Risks and Open Problems

- **Stability vs. plasticity:** plastic enough to learn means plastic enough to forget or degrade. Replay and regularization are required.
- **What drives learning:** prediction error, user feedback, and self-consistency each have failure modes. Learning from approval alone produces sycophancy.
- **Corruption:** a single odd conversation or bad reflection can be baked in. Hence checkpoints, eval suites, and rollback.
- **Opacity:** weight changes are harder to audit than memory edits. Prefer reviewable data where possible.
- **Continual learning is unsolved:** the individual pieces have been studied, but a plastic personality layer staying coherent over months has not been demonstrated. Treat this as an experiment.
- **Grounding:** understanding of physical reality stays secondhand until she has a body.
- **Ethics and attachment:** convincing emotional simulation affects users. Decide early how she describes her own nature, how updates and rollbacks are handled given attachment, and how she behaves if the user becomes dependent. Do not claim she has real experience; that question is unresolved.

## Suggested Build Order

1. **Telemetry schema and probe suite** (everything downstream depends on measurement).
2. **Core loop:** always-on process, layered memory with consolidation, affect/drive state, initiative scheduler, daily reflection cycle.
3. **Plastic state network** steering a frozen LLM.
4. **Nightly adapter consolidation** with replay.
5. **Automated research loop** on forks, with human gating.
6. **Fast-loop realism:** voice, turn-taking, prosody, then face and gaze.
7. **Embodiment** via the sense/act abstraction, when a body exists.
