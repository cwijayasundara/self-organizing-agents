# Decentralized / Supervisor-Free / Self-Organizing LLM Multi-Agent Coordination: Prior Art (excluding Microsoft Agensh)

Research date: 2026-10-26. Labels used: [EMPIRICAL] = measured result in paper/post; [OPINION] = practitioner argument or design guidance without controlled comparison; [UNVERIFIED] = recalled or seen only in search snippets, not fetched this session.

## 1. Mechanism catalogue: what supervisor-free coordination mechanisms exist, and what evidence backs each?

### Takeaway
The credible supervisor-free mechanisms are (a) a shared blackboard or shared verified context plus a claimable task queue (LbMAS 2025, DeLM June 2026), (b) agents routing work peer-to-peer from local capability estimates and memory (AgentNet, NeurIPS 2025; MorphAgent), and (c) bidding or market-style self-selection (MPT, Oct 2026; COALESCE; blockchain bid-and-assign). The strongest 2026 evidence for "no orchestrator" is DeLM, which uses a shared context of verified "gists" plus an async task queue. It beats a centralized orchestrator on SWE-bench at about half the cost, and beats single-agent baselines by roughly 4–6 points on multi-document QA (a knowledge-work task). Debate and voting are the weakest mechanism: they often fail to beat self-consistency, and naive debate can hurt accuracy.

### Cited Findings

**Blackboard / shared-artifact (stigmergy-like) coordination**
- [EMPIRICAL] LbMAS (Han & Zhang, CAS; arXiv 2507.01701, 2 Jul 2025): agents "communicate solely through the blackboard." The blackboard has a public space plus private spaces used for debate and verification, and it replaces per-agent memory. — [arXiv 2507.01701](https://arxiv.org/html/2507.01701v1)
- [EMPIRICAL] LbMAS roles: query-generated domain experts plus fixed roles (planner, decider, critic, conflict-resolver, cleaner). The cleaner removes redundant messages, and the conflict-resolver detects contradictions and names the agents who should discuss them. An LLM "control unit" picks which agents act each round. Note that this is a soft central scheduler, not a full supervisor. — [arXiv 2507.01701](https://arxiv.org/html/2507.01701v1)
- [EMPIRICAL] LbMAS termination: it stops when the decider emits a solution, or after a maximum of 4 rounds. A majority-vote variant picks the answer with the highest cumulative similarity to the other answers. — [arXiv 2507.01701](https://arxiv.org/html/2507.01701v1)
- [EMPIRICAL] LbMAS results: best average across MMLU, ARC-C, GPQA-Diamond, BBH, MATH-500 and GSM8K (81.68 vs ChatEval 80.56 vs CoT-Qwen 80.09). Reported gains are +4.33% over CoT and +5.02% over static MAS. It is not uniformly better: Llama-only LbMAS trails CoT on MATH (58.4 vs 62.2). — [arXiv 2507.01701](https://arxiv.org/html/2507.01701v1)
- [EMPIRICAL] LbMAS token cost on MATH is about 4.72M tokens, against about 16.7M for AFlow and about 13.0M for MaAS (both need a search phase). Removing the control unit raised cost to about 13.9M with little change in accuracy. In other words, a lightweight selector *saves* tokens compared with letting every agent act. — [arXiv 2507.01701](https://arxiv.org/html/2507.01701v1)
- [UNVERIFIED] A second 2025 blackboard paper (arXiv 2510.01285) applies a blackboard MAS to data discovery in data lakes. I did not fetch it, so its numbers are not reported here. — [arXiv 2510.01285](https://arxiv.org/abs/2510.01285v2)

**Shared verified context + claimable task queue (DeLM)**
- [EMPIRICAL] DeLM, "Decentralized Multi-Agent Systems with Shared Context" (Mao & Mirhoseini, Stanford; arXiv 2606.10662, 9 Jun 2026), replaces the orchestrator with two shared structures: (1) a shared context of compact, verified "gists" and (2) a dependency-aware task queue. Agents asynchronously claim ready subtasks, read admitted progress, reason locally, and write back verified updates. — [arXiv 2606.10662](https://arxiv.org/html/2606.10662v1)
- [EMPIRICAL] DeLM on SWE-bench Verified with Gemini 3 Flash (Avg@1 / Pass@4 / cost per task):
  - DeLM: 65.7% / 77.4% / $0.12
  - Centralized AOrchestra: 55.2% / 73.2% / $0.24
  - Single-agent mini-SWE-agent: 54.7% / 75.1% / $0.26
  - Claude Code: 49.3% Avg@1

  — [arXiv 2606.10662](https://arxiv.org/html/2606.10662v1)
- [EMPIRICAL] With a stronger model (Claude Opus 4.6) the gain shrinks to near parity: DeLM 78.0% Avg@1 at $0.63 vs 76.9% at $0.61 for the best baseline. This is consistent with Google's capability-saturation finding (Section 5). — [arXiv 2606.10662](https://arxiv.org/html/2606.10662v1)
- [EMPIRICAL] Knowledge work: on LongBench-v2 Multi-Doc QA (125 samples across finance, government, legal, academic and multi-news), DeLM beats the best baseline by +5.7 (GPT-5.4), +5.3 (Sonnet 4.6), +4.4 (Gemini 3 Flash) and +3.6 (DeepSeek-V4-Pro) points. The centralized baseline was not run on this benchmark. — [arXiv 2606.10662](https://arxiv.org/html/2606.10662v1)

**Peer routing / self-organizing networks**
- [EMPIRICAL-mechanism] AgentNet (Yang et al., NeurIPS 2025; arXiv 2504.00587):
  - Each agent has its own router and executor, and "routing decisions are made independently by each agent, without relying on a central authority."
  - For each task, an agent forwards it to the most capability-similar peer, splits it into subtasks, or executes it directly. A visited set prevents loops, and the network is a DAG.
  - Each agent keeps a RAG memory of successful trajectories, which drives specialization.
  - Edge weights and capability vectors evolve over time, and edges below a threshold are pruned.

  — [arXiv 2504.00587](https://arxiv.org/html/2504.00587v1); [NeurIPS 2025 poster](https://neurips.cc/virtual/2025/poster/115584)
- AgentNet's intro *claims* better efficiency, adaptability and scalability than centralized MAS. The quantitative tables were not in the section I retrieved (see Gaps). — [arXiv 2504.00587](https://arxiv.org/html/2504.00587v1)
- [EMPIRICAL] MorphAgent (arXiv 2410.15048, v2 3 Sep 2025; listed at ICML 2025):
  - Each agent runs an Observe-Think-Act loop and chooses EXECUTE or SKIP with no central controller.
  - Profiles self-evolve, guided by Role Clarity, Role Differentiation and Task-Role Alignment scores.

  — [arXiv 2410.15048](https://arxiv.org/pdf/2410.15048); [ICML 2025](https://icml.cc/virtual/2025/49363)
- [EMPIRICAL] MorphAgent robustness: at 0.8 node-failure probability it retains 40.1–54.0% accuracy, against 1.43–19.52% for the baselines (GPTSwarm, AgentVerse, AFlow). Under domain shift from BigCodeBench to MATH it reaches 63.33%, against 11.33% for GPTSwarm and 58.00% for Naive. — [arXiv 2410.15048](https://arxiv.org/pdf/2410.15048)
- [EMPIRICAL] MorphAgent's own metric ablation gives modest gains: 52.00% vs a 50.67% no-metric baseline on BigCodeBench with GPT-4o-mini, and single metrics generally don't beat the baseline. — [arXiv 2410.15048](https://arxiv.org/pdf/2410.15048)

**Market / auction / bidding self-selection**
- [EMPIRICAL, abstract-level] MPT, "Learning Self-Orchestration in Decentralized Agent Swarms" (Xu, Qi, Kiruga, Lakkaraju, Du; arXiv 2610.22322, 15 Oct 2026):
  - Agents place *bids* expressing how much they want to participate, and the bids decide who acts, with no central coordinator. Credit comes from the collective outcome.
  - Market-based post-training jointly learns each agent's action policy and its bidding behavior.
  - Reported results: it beats monolithic post-training on embodied crafting, navigation and **deep research**; learned self-orchestration beats alternative coordination strategies; and it degrades less when agents drop out.
  - No agent counts or token costs appear in the abstract.

  — [arXiv 2610.22322](https://arxiv.org/abs/2610.22322v1); code at github.com/Embodied-Minds-Lab/MPT
- [EMPIRICAL, simulated] A blockchain-based LLM-MAS (Qi et al., arXiv 2509.16736, 2025) uses bid-and-assign. A matching score combines capability, reputation and workload; a softmax turns scores into assignment probabilities; tasks above a complexity threshold are split; and reputation is tracked as an EMA. Setup: 20 GPT-4 agents over 50 rounds. Success rose from 80.15% to 94.49%. Caveats: there is no centralized baseline, outcomes come from a simulator rather than real execution, and only gas costs are reported (about 148k gas per transaction), not LLM tokens. — [arXiv 2509.16736](https://arxiv.org/html/2509.16736v1)
- [UNVERIFIED] COALESCE (arXiv 2506.01900) studies skill-based task outsourcing among LLM agents, covering economic and security dynamics. Not fetched. — [arXiv 2506.01900](https://arxiv.org/pdf/2506.01900)

**Debate / voting / consensus**
- [EMPIRICAL] "If Multi-Agent Debate is the Answer, What is the Question?" (Zhang et al., arXiv 2502.08788, Feb 2025) tested 5 MAD methods on 9 benchmarks with 4 models. MAD "fail[s] to reliably outperform" CoT and Self-Consistency even with more compute. Model *heterogeneity* (Heter-MAD) helps. — [arXiv 2502.08788](https://arxiv.org/html/2502.08788v2)
- [EMPIRICAL] "Talk Isn't Always Cheap" (Wynn, Satija, Hadfield; arXiv 2509.05396, Sep/Oct 2025):
  - Debate can *lower* accuracy compared with majority voting over initial answers, and more answers flip correct→incorrect than incorrect→correct.
  - On CommonSenseQA with 3 agents and 2 rounds: Mistral-7B 44.4→39.4, Llama-3.1-8B 63.0→58.6, GPT-4o-mini 75.6→74.8.
  - Weaker agents can drag down stronger majorities.

  — [arXiv 2509.05396](https://arxiv.org/html/2509.05396v2)
- [EMPIRICAL, older] "Should we be going MAD?" (ICML 2024) also found debate strategies don't reliably beat other prompting strategies and are hyperparameter-sensitive. — [PMLR v235](https://proceedings.mlr.press/v235/smit24a.html)

**Other named systems (not re-verified this session)**
- [UNVERIFIED] DyLAN (dynamic agent networks with an agent-importance score and early-stopping consensus), GPTSwarm (agents as optimizable computational graphs), Self-Organized Agents / SoA (code agents that self-multiply to keep each agent's context bounded), and Agent Q (MCTS plus self-critique for web agents; single-agent rather than a coordination method). I could not fetch these within budget, so treat any numbers from memory as unconfirmed.
- [UNVERIFIED] OrgAgent, "Organize Your Multi-Agent System like a Company" (arXiv 2604.01020, 2026), is relevant to the "MAS are org charts" framing but was not fetched. I found no primary source for a paper or post titled "Multi-agent systems are just org charts." — [arXiv 2604.01020](https://arxiv.org/pdf/2604.01020)
- [UNVERIFIED] "Matrix: Peer-to-Peer Multi-Agent Synthetic Data Generation Framework" (arXiv 2511.21686) is a P2P agent runtime, seen in search only. — [arXiv 2511.21686](https://arxiv.org/html/2511.21686v2)

### Inferences
- The pattern most transferable to a small business/knowledge-work framework is DeLM-style: a shared verified artifact store, a dependency-aware claimable queue, verification at admission, and "last finisher decides." It is the only 2026 result showing a supervisor-free design beating a supervisor on both quality and cost, and it also showed gains on document-heavy QA.
- "Decentralized" systems almost always keep some lightweight shared selector or arbiter: the LbMAS control unit, the DeLM last-finisher, MorphAgent all-SKIP consensus. The real design choice is *where state and verification live*, not whether any coordination role exists.
- Use voting or self-consistency, not free-form debate, as the default consensus primitive. Use heterogeneous models where debate is used.

### Gaps
- AgentNet's quantitative results vs centralized baselines, and how it scales with agent count, were not in the retrieved section.
- DyLAN, GPTSwarm, SoA and Agent Q numbers were not re-verified.
- I found no controlled LLM study of classic Contract-Net or stigmergy with real task execution and a centralized baseline. The bid-based work is either RL-trained (MPT) or simulated (2509.16736).

## 2. Failure modes of multi-agent LLM systems and decentralized mitigations

### Takeaway
MAST (NeurIPS 2025) measured 14 failure modes over 1,642 traces. The most frequent are step repetition (15.7%), reasoning-action mismatch (13.2%), unawareness of stopping conditions (12.4%) and task-spec violation (11.8%). Verification failures, whether missing or incorrect, make up about 17%. The practical answer in decentralized designs is to verify at the point where content enters shared state, use explicit termination predicates, and use idempotent claiming. Leases and quorum are not specifically evaluated in the LLM literature I found.

### Cited Findings
- [EMPIRICAL] MAST (Cemri et al., arXiv 2503.13657; NeurIPS 2025) annotated 1,642 traces from 7 MAS frameworks. Human inter-annotator agreement was κ=0.88, and the LLM annotator reached κ=0.77 against humans. — [arXiv 2503.13657v3](https://arxiv.org/html/2503.13657v3); [NeurIPS 2025](https://mlanthology.org/neurips/2025/cemri2025neurips-multiagent)
- [EMPIRICAL] MAST failure-mode frequencies:
  - **FC1 System design:** disobey task spec 11.8%, disobey role spec 1.5%, step repetition 15.7%, loss of history 2.8%, unaware of stopping conditions 12.4%.
  - **FC2 Inter-agent misalignment:** conversation reset 2.2%, fail to ask clarification 6.8%, task derailment 7.4%, information withholding 0.85%, ignoring others' input 1.9%, reasoning-action mismatch 13.2%.
  - **FC3 Verification:** premature termination 6.2%, no/incomplete verification 8.2%, incorrect verification 9.1%.

  — [arXiv 2503.13657v3](https://arxiv.org/html/2503.13657v3)
- [EMPIRICAL] MAST interventions on ChatDev: better role specs plus giving the CEO final say gave +9.4% task success, and adding a high-level objective verification step gave +15.6%. Many existing verifiers are superficial (e.g. "does it compile"), so the authors argue for multi-level verification. They also note that AppWorld's star topology may contribute to premature termination. — [arXiv 2503.13657v3](https://arxiv.org/html/2503.13657v3)
- [EMPIRICAL] Anthropic's research system observed these failures: spawning 50 subagents for simple queries, endless searching for nonexistent sources, distracting status updates between agents, and duplicated work (two subagents redoing the same 2025 supply-chain research). — [Anthropic, Jun 13 2025](https://www.anthropic.com/engineering/multi-agent-research-system)
- [OPINION + anecdote] Cognition's failure is *implicit decision conflict*. In their Flappy Bird example, parallel subagents built a Mario-style background and a mismatched bird because neither could see the other's work. Their principles are "Share context, and share full agent traces," and "Actions carry implicit decisions." — [Cognition, Jun 12 2025](https://cognition.com/blog/dont-build-multi-agents)
- [EMPIRICAL] Google measured error amplification of 17.2× for independent (no-check) MAS against 4.4× for centralized MAS. The containment is attributed to the orchestrator validating sub-agent outputs before aggregation. — [arXiv 2512.08296](https://arxiv.org/html/2512.08296v1)
- [EMPIRICAL] DeLM's decentralized mitigations:
  - Admission-time verification of each gist against its evidence; failing gists are rejected or regenerated. This addresses unverified claims spreading through shared state.
  - Hierarchical raw→summary→gist storage with selective unfolding, which addresses details lost in summarization.
  - Constraints persisted as shared state that later agents must respect, which addresses constraint dilution by a controller.

  — [arXiv 2606.10662](https://arxiv.org/html/2606.10662v1)
- [EMPIRICAL] DeLM notes that coupling parallel workers through a main agent (AOrchestra-Parallel) improves Avg@1 but *reduces* Pass@k diversity. A supervisor homogenizes exploration. — [arXiv 2606.10662](https://arxiv.org/html/2606.10662v1)
- [EMPIRICAL] Other mitigations seen in the papers above:
  - LbMAS's "cleaner" removes redundant blackboard messages and its "conflict-resolver" targets contradictions. — [arXiv 2507.01701](https://arxiv.org/html/2507.01701v1)
  - AgentNet's visited-set plus DAG prevents routing loops. — [arXiv 2504.00587](https://arxiv.org/html/2504.00587v1)
  - Reputation EMA plus workload terms in bid scoring spread load. — [arXiv 2509.16736](https://arxiv.org/html/2509.16736v1)
- [EMPIRICAL] Debate-specific failure: conformity or sycophancy flips correct answers to incorrect ones. — [arXiv 2509.05396](https://arxiv.org/html/2509.05396v2)

### Inferences
- Mapping MAST to decentralized controls:
  - Step repetition and duplicate work: atomic, idempotent claims on a task queue with a dependency DAG (DeLM-style).
  - Stopping-condition unawareness and premature termination: an explicit, checkable termination predicate on shared state.
  - Verification gaps: verifier-at-admission plus an objective-level final check (MAST +15.6%).
  - Implicit decision conflict (Cognition): decisions and constraints written as first-class shared records.
- Leases with TTL (to reclaim tasks from stalled agents) and quorum acceptance are standard distributed-systems answers. I found **no LLM-MAS paper that evaluates them**, so they are design inferences, not evidence.
- Independent parallel agents without verification are the worst case (17.2× error amplification). A decentralized design must replace the orchestrator's checking role, for example with admission verification, or it will look like "independent" rather than "centralized" in Google's taxonomy.

### Gaps
- No quantitative study found on deadlock frequency in LLM-MAS, or on lease/heartbeat mechanisms.
- MAST's traces are mostly coding/math/general tasks with supervisor or pipeline topologies. I found no MAST-style failure distribution specifically for decentralized systems.

## 3. Termination and convergence without a supervisor

### Takeaway
Published supervisor-free systems use one of these predicates:
- the queue is empty and a "last finisher" decides to finalize or enqueue more (DeLM);
- all agents vote SKIP (MorphAgent);
- a designated decider role emits an answer, with a round cap (LbMAS, 4 rounds);
- majority or similarity-based consensus over candidate answers;
- for debate, a fixed small number of rounds, because extra rounds can lower accuracy.

### Cited Findings
- [EMPIRICAL] DeLM: agents run until the task queue is empty. The last agent to finish then checks subtask states and shared context, and either enqueues new subtasks or finalizes from verified context. — [arXiv 2606.10662](https://arxiv.org/html/2606.10662v1)
- [EMPIRICAL] MorphAgent: execution ends when all agents choose SKIP (consensus) or the required rounds are done. Profile updates run up to 5 rounds and stop early when all three metrics improve by more than 0.1. At N=3/5/10 agents, average rounds were 1.54/1.61/2.06. — [arXiv 2410.15048](https://arxiv.org/pdf/2410.15048)
- [EMPIRICAL] LbMAS: it terminates on the decider's output or after 4 rounds. The voting variant picks the answer with the highest cumulative similarity. — [arXiv 2507.01701](https://arxiv.org/html/2507.01701v1)
- [EMPIRICAL] Debate accuracy can decline over rounds (MMLU, CommonSenseQA), which argues for early stopping or capping rounds. — [arXiv 2509.05396](https://arxiv.org/html/2509.05396v2)
- [EMPIRICAL] Termination failures are common: unaware of stopping conditions 12.4%, premature termination 6.2%. — [arXiv 2503.13657v3](https://arxiv.org/html/2503.13657v3)
- [EMPIRICAL] Anthropic embedded explicit effort-scaling rules in prompts (1 agent with 3–10 calls for simple tasks; 2–4 subagents for comparisons; 10+ for complex tasks) after seeing runaway spawning and searching. — [Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)

### Inferences
- A reusable framework should combine:
  - a structural predicate (queue empty, all DAG nodes done);
  - a semantic check (an objective-level verifier, or the last finisher, confirms the goal is met);
  - hard budgets (rounds, tokens, wall-clock) as backstops;
  - quiescence detection (no new admitted writes in K cycles) to catch livelock.

  Only the first three are directly evidenced. Quiescence detection is an inference.

### Gaps
- No paper found that compares termination policies head-to-head in decentralized LLM teams.

## 4. Protocol standards (A2A, MCP, ACP) for peer messaging

### Takeaway
A2A (Google, April 2025; Linux Foundation, June 2025; v1.0 early 2026) is the agent-to-agent layer. IBM's ACP merged into it in 2025. MCP is client-server agent-to-tool. A2A's task lifecycle and SSE streaming can carry peer delegation and claims, but neither protocol defines blackboard, claim or consensus semantics. Those would sit on top, for example as a shared-state service exposed over MCP plus A2A tasks between peers.

### Cited Findings
- A2A details (secondary source, May 2026):
  - Origin: Google, April 2025. Governance: Linux Foundation, June 2025. Version: v1.0 in early 2026. Adoption: 150+ organisations as of April 2026.
  - Agent Card at `/.well-known/agent.json` listing skills, I/O modes, auth and streaming support.
  - Task states: submitted, working, input_required, completed, failed, canceled.
  - Methods: `tasks/send`, `tasks/get`, `tasks/cancel`, and `tasks/sendSubscribe` (SSE). Transport is JSON-RPC 2.0 over HTTPS.

  — [Vaughan, May 2026](https://codex.danielvaughan.com/2026/05/29/agent-to-agent-communication-protocols-a2a-vs-acp-vs-mcp-compared/)
- ACP (IBM Research, REST) merged into A2A in 2025. The source conflicts on the date: its table says August 2025 and its body says IBM announced it in September 2025. ACP no longer exists standalone. — [Vaughan, May 2026](https://codex.danielvaughan.com/2026/05/29/agent-to-agent-communication-protocols-a2a-vs-acp-vs-mcp-compared/)
- MCP:
  - Origin: Anthropic, November 2024. Spec version 2025-11-25. Governance moved to the Linux Foundation in December 2025 (per the same source).
  - Client-server model: servers expose tools, resources and prompts; clients expose sampling, roots and elicitation.
  - In the recommended layering, each agent is both an MCP client and an A2A client/server.

  — [Vaughan, May 2026](https://codex.danielvaughan.com/2026/05/29/agent-to-agent-communication-protocols-a2a-vs-acp-vs-mcp-compared/)

### Inferences
- For a decentralized framework:
  - Expose the blackboard or task queue as an MCP server: claim, admit, read-gists and finalize tools, with atomic operations.
  - Use A2A for direct peer delegation or "ask a peer," mapping `input_required` to a clarification request. This targets MAST's 6.8% "failure to ask for clarification."
  - Use Agent Cards as the capability vectors for AgentNet-style routing.

  This is a design inference, not something any cited source evaluated.

### Gaps
- The source is a secondary blog post. Exact dates (ACP merger, MCP foundation governance) should be checked against Linux Foundation and A2A spec primary sources.
- I found no benchmark of protocol overhead for peer messaging.

## 5. Quantitative scaling evidence: agent count, cost, and when multi-agent helps or hurts

### Takeaway
Google's December 2025 controlled study (180 configurations, 3 model families, 4 benchmarks) found:
- multi-agent helps on parallelizable tasks (centralized +80.9% on finance) and decentralized helps on exploratory web navigation (+9.2%);
- every MAS variant *hurts* on sequential planning (−39% to −70%);
- returns turn negative once the single agent exceeds about 45% accuracy;
- tool-heavy tasks suffer under fixed budgets.

Anthropic found multi-agent research uses about 15× chat tokens, and that token spend explains 80% of BrowseComp variance. For small teams, more agents rarely helps by itself: MorphAgent accuracy is flat to slightly down from 3 to 10 agents while rounds rise.

### Cited Findings
- [EMPIRICAL] Google's study: "Towards a Science of Scaling Agent Systems" (Kim et al., Google Research / Google DeepMind / MIT; arXiv 2512.08296, 9 Dec 2025).
  - **Design:** SAS vs Independent, Centralized, Decentralized and Hybrid MAS; 180 configurations; OpenAI, Google and Anthropic models; benchmarks Finance-Agent, BrowseComp-Plus, PlanCraft and Workbench. — [arXiv 2512.08296](https://arxiv.org/html/2512.08296v1); [Google Research blog](https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/)
  - **Task-type results:** centralized +80.9% on finance (parallelizable); decentralized +9.2% on web browsing (dynamic, high-entropy exploration); all MAS −39% to −70% on PlanCraft (sequential constraint satisfaction). — [arXiv 2512.08296](https://arxiv.org/html/2512.08296v1)
  - **Coefficients:**
    - capability saturation β=−0.408 (p<0.001): coordination yields diminishing or negative returns once SAS exceeds about 45%;
    - tool-coordination trade-off β=−0.330 (p<0.001), with a 16-tool setting hurt disproportionately;
    - redundancy × agent count β=0.041 (p=0.04).

    — [arXiv 2512.08296](https://arxiv.org/html/2512.08296v1)
  - **Predictive model:** cross-validated R²=0.513; leave-one-domain-out R²=0.89; it picks the optimal architecture for 87% of held-out configurations. — [arXiv 2512.08296](https://arxiv.org/html/2512.08296v1)
  - **Overhead shape:** turn count follows a power law and message density saturates logarithmically. Centralized and hybrid show better scaling efficiency. Exact token numbers were not in the retrieved text. — [arXiv 2512.08296](https://arxiv.org/html/2512.08296v1)
- [EMPIRICAL] Anthropic (13 Jun 2025):
  - Opus 4 lead plus Sonnet 4 subagents beat single-agent Opus 4 by 90.2% on an internal research eval.
  - Agents use about 4× chat tokens and multi-agent about 15×.
  - Token usage explains 80% of BrowseComp variance; with tool calls and model choice, 95%.
  - Parallel tool calls cut time by up to 90%.
  - Multi-agent is a poor fit for tasks needing shared context or many dependencies, including most coding.

  — [Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
- [EMPIRICAL] Supervisor-free can be *cheaper*: DeLM costs $0.12/task vs $0.24 for centralized AOrchestra and $0.26 for single-agent on SWE-bench with Gemini 3 Flash. The savings are attributed to sharing compact gists instead of raw traces; one example dropped from $0.399 to $0.125. — [arXiv 2606.10662](https://arxiv.org/html/2606.10662v1)
- [EMPIRICAL] Selector vs all-agents: removing LbMAS's control unit nearly tripled MATH tokens (4.72M→13.9M). — [arXiv 2507.01701](https://arxiv.org/html/2507.01701v1)
- [EMPIRICAL] Small-team scaling: MorphAgent on MATH went from 66.67% at 3 agents to 66.19% at 5 and 65.71% at 10, with average rounds rising from 1.54 to 2.06. — [arXiv 2410.15048](https://arxiv.org/pdf/2410.15048)
- [EMPIRICAL] Coordination is a separate capability from individual skill. On the alem benchmark (Tessera et al., arXiv 2606.08340, Jun 2026; 13 LLMs in zero-shot homogeneous teams), LLMs average about 6% normalized return. GPT-5.4-High scores high on base-task reward but low on coordination, while Gemini-3.1-Pro-High approaches MARL agents trained for 1B steps on the hardest setting. Communication is the biggest contributor to coordination in ablations. — [arXiv 2606.08340](https://arxiv.org/abs/2606.08340)
- [OPINION] Cognition recommends defaulting to a single-threaded linear agent with context compression, and avoiding parallel multi-agents unless they share full context. — [Cognition](https://cognition.com/blog/dont-build-multi-agents)

### Inferences
- **When to go decentralized** for 2–10 agent business/knowledge-work teams:
  - the task decomposes into parallel, partially independent subtasks (research, multi-document analysis, exploration);
  - the single-agent baseline is below about 45%;
  - the tool set per agent is small;
  - a shared verified state replaces the supervisor's validation role.
- **When to stay single-agent:** strictly sequential, constraint-heavy planning.
- Opinion and evidence partly reconcile. Cognition's "share context" worry is exactly what DeLM's shared verified context addresses, and DeLM's gains shrink with stronger models, consistent with saturation.

### Gaps
- No found study sweeps agent count from 2 to 10 on *business* tasks with token cost per task under centralized vs decentralized designs.
- Google's exact agent counts and token-cost tables were not in the retrieved excerpt.
- Anthropic's 90.2% figure comes from an internal eval and has not been independently replicated.

## 6. Evaluation methodology for single-agent vs supervisor vs self-organized teams

### Takeaway
Best practice from the sources:
- hold the model, tools and token budget fixed across single-agent (SAS), independent, centralized, decentralized and hybrid conditions (Google);
- report accuracy plus cost per task and Pass@k diversity (DeLM);
- measure robustness to agent dropout and domain shift (MorphAgent, MPT);
- annotate failures with MAST via an LLM judge (κ≈0.77–0.79);
- use small real-query sets with a rubric-based LLM-as-judge plus human review (Anthropic).

### Cited Findings
- Google controlled for architecture across 180 configurations and 3 model families, fit a mixed-effects/regression model of coordination features, and validated with leave-one-domain-out. It also measures error amplification (17.2× vs 4.4×). — [arXiv 2512.08296](https://arxiv.org/html/2512.08296v1)
- DeLM reports Avg@1, Pass@2 and Pass@4 plus $/task against single-agent, centralized and centralized-parallel baselines, on both a coding and a knowledge-work benchmark. — [arXiv 2606.10662](https://arxiv.org/html/2606.10662v1)
- The MAST LLM annotator reaches κ=0.77 against human experts (94% accuracy) and κ=0.79 on unseen systems, so it is usable as an automated failure-attribution step. — [arXiv 2503.13657v3](https://arxiv.org/html/2503.13657v3)
- Anthropic started with about 20 real queries because early effect sizes were large. They used a single-prompt LLM judge (0.0–1.0 plus pass/fail) with rubric items for factual accuracy, citation accuracy, completeness, source quality and tool efficiency, plus human testing. Humans caught a bias toward SEO content farms that automation missed. — [Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
- Robustness protocols:
  - MorphAgent: node-failure probability sweeps and domain-shift transfer. — [arXiv 2410.15048](https://arxiv.org/pdf/2410.15048)
  - MPT: agent dropout and larger inference-time populations. — [arXiv 2610.22322](https://arxiv.org/abs/2610.22322v1)
- Separate coordination reward from base-task reward (alem). — [arXiv 2606.08340](https://arxiv.org/abs/2606.08340)
- Debate evaluations must include Self-Consistency and majority-vote baselines at matched compute. — [arXiv 2502.08788](https://arxiv.org/html/2502.08788v2); [arXiv 2509.05396](https://arxiv.org/html/2509.05396v2)

### Inferences
- A framework eval harness should run each task under at least SAS, SAS+self-consistency (compute-matched), supervisor, and self-organized conditions, using the same models, tools and token caps. It should log:
  - quality via a rubric LLM-judge plus a human spot-check;
  - $/task and tokens;
  - wall-clock;
  - Pass@k;
  - MAST failure labels;
  - duplicate-work rate (overlapping claims or outputs);
  - robustness under agent dropout.

### Gaps
- I found no public benchmark specifically for small-team decentralized coordination on enterprise/business workflows. Closest: LongBench-v2 Multi-Doc QA (DeLM), Finance-Agent and Workbench (Google), BrowseComp (Anthropic).
