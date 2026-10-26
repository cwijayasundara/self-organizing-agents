# Coordination Patterns for Self-Organizing, Decentralized (Supervisor-Free) LLM Multi-Agent Systems

Research date: 2026-10-26. Verification legend: items marked **[verified]** were checked this session against the primary source page (abstract, HTML or docs). Items marked **[background, not re-verified]** come from well-known prior literature; the URL is given, but the content was not re-fetched this session, so the report writer should treat them as attributions to confirm.

---

## 1. Decentralized coordination mechanisms and how they work

### Takeaway
LLM systems use six main families of coordination: (a) a blackboard or shared workspace that agents read, write and volunteer from; (b) a shared task board with dependency gating and lock-based self-claiming; (c) peer-to-peer handoffs or messaging, where control passes between agents without a router; (d) debate, consensus or voting among peers; (e) contract-net, auction or market allocation; and (f) learned or dynamic topologies, where agents or graph edges are selected or pruned based on contribution. Most "decentralized" production systems are really hybrids that keep a thin control element, such as a lead that seeds tasks, a control unit, or a fixed number of termination rounds.

### Cited Findings

**Blackboard / shared workspace**
- Salemi et al. (arXiv 2510.01285, Sept 2025, rev. Jan 2026) build a blackboard system for data-science information discovery. A central agent posts requests to a shared blackboard, and subordinate agents **decide on their own whether to respond**, so there is no explicit assignment. The authors report up to **57% relative improvement in end-to-end task success** and a **9% relative gain in data-discovery accuracy (F1)** over baselines that include RAG and the master–slave paradigm. [verified, abstract via search] — [arXiv 2510.01285](https://arxiv.org/abs/2510.01285v2)
- Han & Zhang (arXiv 2507.01701, July 2025) build an LLM MAS from a **control unit + blackboard + role agents**. Each round, the control unit chooses which agents act based on the blackboard's current contents. The authors report results competitive with SOTA static and dynamic MAS, the **best average performance, and fewer tokens**. This design is more centralized, because a control unit does the selection. [verified, abstract via search] — [arXiv 2507.01701](https://arxiv.org/html/2507.01701v1)
- Classic origin: Hearsay-II-style blackboard systems use independent knowledge sources, a shared blackboard and a control component that schedules them opportunistically. [background, not re-verified] — [Nii, "Blackboard Systems", AI Magazine 1986](https://ojs.aaai.org/aimagazine/index.php/aimagazine/article/view/537)

**Shared task board with self-claiming and locking (production example)**
- Claude Code "agent teams" (experimental) has these parts: a team lead, teammates (separate Claude instances, each with its own context window), a **shared task list**, and a **mailbox** (one JSON inbox file per agent). Tasks have the states **pending / in progress / completed**. A pending task whose dependencies are unresolved **cannot be claimed**. After a teammate finishes a task, it "picks up the next unassigned, unblocked task on its own". **"Task claiming uses file locking to prevent race conditions"** when two teammates try to claim the same task. Completing a task automatically unblocks the tasks that depend on it. Teammates message each other directly by name, and there is no broadcast primitive ("send one message per recipient"). [verified] — [Claude Code docs: agent teams](https://code.claude.com/docs/en/agent-teams)
- Quality gates are enforced by hooks: `TaskCreated`, `TaskCompleted` (exit code 2 blocks completion and sends feedback) and `TeammateIdle` (keeps a teammate working). Shutdown is a request/approve protocol, and a teammate may reject a shutdown request with an explanation. [verified] — [Claude Code docs: agent teams](https://code.claude.com/docs/en/agent-teams)
- Note: the docs describe a lead that creates tasks, so this is a hybrid. Execution is decentralized (self-claim plus P2P messaging), and task seeding is centralized. [verified] — [Claude Code docs](https://code.claude.com/docs/en/agent-teams)

**Peer-to-peer handoffs ("swarm")**
- In LangChain's benchmark, in the swarm architecture "sub-agents can hand off to any other agent", and the **active agent replies directly to the user**. In the supervisor architecture, by contrast, sub-agents return control to a router. [verified] — [LangChain blog: Benchmarking multi-agent architectures](https://www.langchain.com/blog/benchmarking-multi-agent-architectures)
- In the OpenAI Agents SDK, handoffs are implemented as tools. The `handoff()` primitive supports an `on_handoff` callback and an `input_filter` that trims history before the receiving agent sees it. The SDK grew out of the experimental Swarm framework (Oct 2024). [secondary source, not verified against OpenAI docs] — [fast.io comparison](https://fast.io/resources/openai-agents-sdk-vs-langgraph/); [morphllm on Swarm](https://www.morphllm.com/openai-swarm)

**Debate / consensus / voting**
- "Towards a Science of Scaling Agent Systems" defines the **decentralized** architecture as **all-to-all communication with no orchestrator**: n agents run d sequential debate rounds, and a consensus policy (peer debate plus voting) aggregates the result. [verified] — [arXiv 2512.08296v2 HTML](https://arxiv.org/html/2512.08296v2)
- ReConcile runs a "round-table conference" among **different model families**, using confidence-weighted consensus. It reports gains of up to **11.4%** over prior single- and multi-agent baselines and **+8% on MATH**. Its ablations find that **diversity originating from different models is critical**. [verified, abstract via search] — [ReConcile arXiv 2309.13007](https://arxiv.org/html/2309.13007v3)
- Original multi-agent debate: multiple instances propose answers and then revise them over rounds after reading each other's answers. [background, not re-verified] — [Du et al., arXiv 2305.14325](https://arxiv.org/abs/2305.14325)

**Contract-net / auction / market**
- Classic Contract Net Protocol: a manager announces a task, contractors bid, and the manager awards the contract. [background, not re-verified] — [Smith, IEEE Trans. Computers 1980](https://doi.org/10.1109/TC.1980.1675516)
- COALESCE (arXiv 2506.01900) studies skill-based task outsourcing among teams of LLM agents. It notes that applying CNP directly to LLM agents is hard because **LLM skills are qualitative and probabilistic**, which complicates evaluating bids and verifying that contracts were fulfilled. It surveys single-good, multi-unit and combinatorial auctions. [verified, via search abstract] — [COALESCE arXiv 2506.01900](https://arxiv.org/pdf/2506.01900)
- "Agent Contracts" (arXiv 2601.08815) extends the contract metaphor from *who* does a task to *within what bounds* it may be done: **resource budgets, time limits and success criteria**. This is directly relevant to controlling runaway cost. [verified, via search abstract] — [arXiv 2601.08815](https://arxiv.org/html/2601.08815v2)

**Emergent / dynamic role and topology selection**
- **DyLAN** (arXiv 2310.02170) selects agent teams with an unsupervised **Agent Importance Score**. In a preliminary trial, each agent rates its predecessors, the ratings are propagated back from successors across time steps, and the top-scoring agents are kept. It reports **+13.3% on HumanEval** over a single GPT-3.5-turbo run. [verified, via search] — [DyLAN arXiv](https://arxiv.org/html/2310.02170v2); [code](https://github.com/SALT-NLP/DyLAN)
- **Self-Organized Agents (SoA)** (arXiv 2404.02183) is aimed at very large codebases. Agents **multiply according to task complexity**, so the codebase can grow while each agent's share of code stays roughly constant. It reports **+5% Pass@1 over Reflexion on HumanEval**. [verified, via search] — [SoA arXiv 2404.02183](https://arxiv.org/pdf/2404.02183)
- **MacNet** (ICLR 2025) organizes agents as a DAG and orchestrates reasoning in topological order. It scales to more than 1,000 agents, and **irregular topologies outperform regular ones**. The proposed "collaborative scaling law" is that performance follows a **logistic curve** as agents increase, with "collaborative emergence" appearing earlier than neural emergence. [verified, via search] — [MacNet arXiv 2406.07155](https://arxiv.org/abs/2406.07155v3); [ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/66a026c0d17040889b50f0dfa650e5e0-Abstract-Conference.html)
- **Evolving Orchestration / "Puppeteer"** (NeurIPS 2025, arXiv 2505.19591) uses an RL-trained central policy to choose which agent reasons next. It reports better performance at lower compute, attributed to the emergence of **more compact, cyclic reasoning structures**. A secondary summary says the reward penalizes redundant agents. It is centralized, but it is evidence that **learned pruning of interaction beats static full meshes**. [verified abstract; mechanism detail secondary] — [arXiv 2505.19591](https://arxiv.org/html/2505.19591v2); [NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/hash/f1320d2e2842169c6fc89dcbd80e94d0-Abstract-Conference.html); [Moonlight review](https://www.themoonlight.io/review/multi-agent-collaboration-via-evolving-orchestration)
- **AgentVerse** (ICLR 2024) runs dynamic expert recruitment and group collaboration. It reports emergent collaborative behaviors that raise group efficiency, along with **both positive and negative emergent social behaviors** in the Minecraft setting. [verified abstract via search] — [AgentVerse arXiv 2308.10848](https://arxiv.org/pdf/2308.10848)
- GPTSwarm treats agents as optimizable computational graphs, optimizing both nodes (prompts) and edges (connectivity). [background, not re-verified, since searches did not surface it] — [GPTSwarm arXiv 2402.16823](https://arxiv.org/abs/2402.16823)

### Inferences
- For a framework with up to ~10 agents, the most battle-tested supervisor-free primitive is **a shared task board with dependency DAG + atomic claim (lock/CAS) + P2P mailbox + completion hooks** (Claude Code agent teams pattern). A **blackboard with volunteer self-selection** (Salemi et al.) is the strongest research evidence for decentralized *task pickup*.
- A fully decentralized system still needs *some* deterministic control: a seeding or decomposition step, round limits, and termination rules. These can live in code, such as a scheduler, a board state machine or a budget contract, rather than in an LLM supervisor. That matches the "control unit" in Han & Zhang and the hooks in Claude Code.
- Contract-net and auctions are under-validated for LLMs. Bids such as self-reported confidence are unreliable, so self-claiming plus verification is probably safer than bidding.

### Gaps
- Stigmergy (environment-trace coordination) and gossip protocols specifically for LLM agents: I found no rigorous LLM-specific evaluations this session.
- No peer-reviewed head-to-head benchmark of LLM contract-net/auction allocation versus self-claiming. An Emergent Mind page claims "CNP reduced LLM calls per repair by ~15%", but I could not verify it ([Emergent Mind](https://www.emergentmind.com/topics/contract-net-protocols)).
- Not re-verified this session: details of the MetaGPT, ChatDev, CAMEL and AutoGen group chat mechanisms (shared message pool with publish-subscribe in MetaGPT; chat chain in ChatDev; role-playing inception prompting in CAMEL; speaker-selection GroupChatManager in AutoGen). See [MetaGPT](https://arxiv.org/abs/2308.00352), [ChatDev](https://arxiv.org/abs/2307.07924), [CAMEL](https://arxiv.org/abs/2303.17760), [AutoGen](https://arxiv.org/abs/2308.08155) [background].

---

## 2. Findings on centralized vs decentralized topologies and on scaling agent counts

### Takeaway
The strongest controlled study to date (Kim et al., Dec 2025; 180 configurations) finds **no universally best topology**. Centralized coordination wins on parallelizable analysis and contains error propagation best. Decentralized (peer debate) wins narrowly on dynamic web navigation, has similar overhead to centralized, and tolerates heterogeneous models better. **Every** multi-agent variant hurts on sequential planning. Coordination turns stop scaling well beyond roughly 3–4 agents under fixed budgets.

### Cited Findings
- Setup: five architectures (Single, Independent, Centralized, Decentralized, Hybrid) × three LLM families × four benchmarks (Finance-Agent, BrowseComp-Plus, PlanCraft, Workbench), giving 180 configurations with standardized tools and token budgets. [verified] — [arXiv 2512.08296](https://arxiv.org/abs/2512.08296v1)
- Task dependence: **Centralized +80.8–80.9% on parallelizable Finance-Agent**. **Decentralized +9.2% vs +0.2% on BrowseComp-Plus** (dynamic web navigation). On **sequential PlanCraft, every MAS variant degraded performance by 39–70%**. The recommended mapping is parallelizable → centralized, dynamic navigation → decentralized, planning → single agent. [verified] — [arXiv 2512.08296v2 HTML](https://arxiv.org/html/2512.08296v2)
- **Capability ceiling:** coordination yields diminishing or negative returns once the single-agent baseline exceeds about **45%** (β ≈ −0.404 to −0.408, p < 0.001). [verified] — [arXiv 2512.08296](https://arxiv.org/abs/2512.08296v1)
- **Overhead vs a single agent (SAS):** Independent 58% overhead and 11.4 turns; **Decentralized 263% and 26.1 turns (3.6×)**; Centralized 285% and 27.7 turns (3.8×); Hybrid 515% and 44.3 turns (6.2×). **Success per 1K tokens:** SAS 67.7, Independent 42.4, Decentralized 23.9, Centralized 21.5, Hybrid 13.6. [verified] — [arXiv 2512.08296v2 HTML](https://arxiv.org/html/2512.08296v2)
- **Agent-count scaling:** coordination turns follow a power law, **T = 2.72 × (n + 0.5)^1.724** (R² = 0.974). The authors say "per-agent reasoning capacity becomes prohibitively thin beyond 3–4 agents" under fixed budgets. Overhead above roughly 150% outweighs benefits when 16 tools are in play. [verified] — [arXiv 2512.08296v2 HTML](https://arxiv.org/html/2512.08296v2)
- Their predictive model picks the best architecture for **87% of held-out configurations** (cross-validated R² = 0.513). [verified] — [arXiv 2512.08296](https://arxiv.org/abs/2512.08296v1)
- **Embodied agents:** a system-level analysis reports that **centralized planners (MindAgent) lose task success sharply as agent count grows**, because a single planner struggles with complex joint plans. It compares them with decentralized CoELA and COMBO. [via search snippet] — [arXiv 2504.18945](https://arxiv.org/pdf/2504.18945)
- **Swarm vs supervisor (LangChain, τ-bench retail + 6 distractor domains, gpt-4o, 100 examples):** the single agent collapses once there are two or more distractor domains. **Swarm slightly outperforms supervisor throughout** and uses fewer tokens, because the supervisor makes "translation" (paraphrasing) errors relaying sub-agent output. Fixes to the supervisor (removing handoff messages from sub-agent state, plus a `forward_message` tool) raised performance by "nearly 50%". [verified] — [LangChain blog](https://www.langchain.com/blog/benchmarking-multi-agent-architectures)
- **Anthropic multi-agent research system (orchestrator-worker, centralized):** Opus 4 lead with Sonnet 4 subagents beat single-agent Opus 4 by **90.2%** on an internal research eval. **Token usage explained ~80% of BrowseComp variance**, and three factors together explained 95%. MAS uses about **15× the tokens of chat**. It is best for breadth-first, parallelizable queries and a poor fit for tightly coupled domains such as most coding. [verified] — [Anthropic Engineering](https://www.anthropic.com/engineering/multi-agent-research-system)
- MacNet: performance rises **logistically** with agent count (it saturates), and **irregular topologies beat regular ones**. [verified, via search] — [MacNet](https://arxiv.org/abs/2406.07155v3)

### Inferences
- "Decentralized" does not mean "cheaper". In Kim et al., decentralized peer debate costs about as much as centralized coordination (263% vs 285% overhead). Savings come from **sparser communication** (task board plus targeted messages instead of all-to-all), not from removing the supervisor.
- For 5–10 agents, all-to-all debate is likely to blow up turns (about 15 turns at n=3, rising as n^1.7). Use sparse topologies: a small debate or review cluster of 2–3 inside a larger, parallel board-driven team.
- Much of the multi-agent gain comes from spending more tokens across separate contexts (Anthropic). A fair evaluation must therefore compare against a single agent given the **same token budget**.

### Gaps
- Kim et al. do not report success rates by agent count (only turn and overhead laws). I found no controlled study of **5–10 agent** decentralized LLM teams on business tasks.
- Per-family numbers for the error-amplification tables vary slightly across paper versions (v1 vs v2). Section 4.4 of v2 also contains an internal inconsistency ("+4.6%" vs 17.2×) — [arXiv 2512.08296v2](https://arxiv.org/html/2512.08296v2).

---

## 3. How decentralized systems handle decomposition, duplicate work, conflicts, convergence/termination, QC, deadlock/livelock and cost

### Takeaway
The working mechanisms are mostly *structural* rather than prompt-level: explicit task boundaries, dependency-gated atomic claiming, ownership partitioning, external shared stores, multi-level verification gates, explicit termination conditions, fixed debate-round caps and budget contracts. MAST shows that prompt and role tweaks alone give only modest, inconsistent gains.

### Cited Findings
- **Decomposition and duplicate work:** Anthropic found that vague delegation caused **duplicated work and gaps**. Each worker needs a **clear objective, output format, tool guidance and task boundaries**. Early versions spawned too many subagents for simple queries, and agents "sent each other too many updates". [verified] — [Anthropic Engineering](https://www.anthropic.com/engineering/multi-agent-research-system)
- **Effort scaling rules:** simple fact-finding → 1 agent with a few tool calls; comparisons → a few agents; only complex research → 10+ agents. [verified] — [Anthropic Engineering](https://www.anthropic.com/engineering/multi-agent-research-system)
- **Atomic claiming and dependencies:** use file locking on claims, block tasks until their dependencies complete, and unblock dependents automatically. [verified] — [Claude Code docs](https://code.claude.com/docs/en/agent-teams)
- **Conflict avoidance through ownership:** "Two teammates editing the same file leads to overwrites. Break the work so each teammate owns a different set of files." [verified] — [Claude Code docs](https://code.claude.com/docs/en/agent-teams)
- **Task sizing:** tasks that are too small cost more in coordination than they gain, and tasks that are too large run long without check-ins. About **5–6 tasks per teammate** is recommended, and **3–5 teammates** is the suggested starting point ("three focused teammates often outperform five scattered ones"). [verified] — [Claude Code docs](https://code.claude.com/docs/en/agent-teams)
- **Shared artifacts instead of relaying:** subagents write outputs to a shared store and pass back lightweight references, which avoids losing information in relays. [verified] — [Anthropic Engineering](https://www.anthropic.com/engineering/multi-agent-research-system). Relatedly, a supervisor that paraphrases sub-agent output introduces "translation" errors, and a `forward_message` passthrough fixes them. [verified] — [LangChain](https://www.langchain.com/blog/benchmarking-multi-agent-architectures)
- **Termination:** MAST failure modes include **FM-1.5 "Unaware of termination conditions" (12.4%)**, **FM-3.1 "Premature termination" (6.2%)** and **FM-1.3 "Step repetition" (15.7%)**. The recommendation is explicit role, conversation-pattern and termination specifications. [verified] — [MAST arXiv 2503.13657v3](https://arxiv.org/html/2503.13657v3). In decentralized debate, Kim et al. use a **fixed number of rounds d** followed by a vote. [verified] — [arXiv 2512.08296v2](https://arxiv.org/html/2512.08296v2)
- **Early stopping in practice:** the "lead can stop early too, deciding the team is finished before all tasks are actually complete". Teammates also "sometimes fail to mark tasks as completed, which blocks dependent tasks". This is a stale-lock or deadlock analogue that needs manual nudging. [verified] — [Claude Code docs](https://code.claude.com/docs/en/agent-teams)
- **Quality control / verification:** in MAST, adding a **high-level objective verification step to ChatDev gave +15.6% task success** on ProgramDev, the largest single intervention gain. Improved role specs gave **+9.4%**. The authors recommend multi-level verification (high-level goal, external knowledge, test outputs) over superficial checks such as "it compiles". [verified] — [MAST](https://arxiv.org/html/2503.13657v3)
- **Error containment:** error amplification A_e = E_MAS/E_SAS is **Independent 17.2×, Decentralized 7.8×, Hybrid 5.1×, Centralized 4.4×**. The centralized review or validation step contains errors best. [verified] — [arXiv 2512.08296v2](https://arxiv.org/html/2512.08296v2)
- **Redundancy metric:** measured as mean cosine similarity of agent outputs, or as the fraction of subtasks done by multiple agents. High redundancy (R > 0.50) correlates negatively with success (r = −0.136). [verified] — [arXiv 2512.08296v2](https://arxiv.org/html/2512.08296v2)
- **Reliability engineering:** errors compound in stateful agents, so **resume from checkpoints**, add deterministic retries, summarize completed phases into external memory, and hand off to fresh agents when context runs low. Synchronous waiting creates bottlenecks, while asynchronous execution adds consistency challenges. [verified] — [Anthropic Engineering](https://www.anthropic.com/engineering/multi-agent-research-system)
- **Budgets:** contracts with explicit **resource budgets, time limits and success criteria** per task. [verified abstract] — [Agent Contracts arXiv 2601.08815](https://arxiv.org/html/2601.08815v2). In Claude Code, token cost scales linearly with the number of active teammates. [verified] — [Claude Code docs](https://code.claude.com/docs/en/agent-teams)

### Inferences
- A supervisor-free framework should encode the following in deterministic infrastructure: (1) a task schema with objective, output format, boundaries, owner and dependencies; (2) atomic claim with lease/TTL, so a stalled agent's claim expires and avoids the "stuck task status" deadlock; (3) a resource-ownership map for files and records; (4) a completion gate that runs verification before a task can move to *completed*; (5) a global budget and round ledger with hard stops; (6) an explicit, machine-checkable definition of done for the whole job.
- Loop and livelock detection can use MAST's FM-1.3 signal: detect near-duplicate consecutive actions or messages, for example by embedding similarity, which mirrors Kim et al.'s redundancy metric.

### Gaps
- I found no source that quantifies deadlock or livelock rates specifically in decentralized LLM systems. Mitigations here come from engineering practice rather than measured studies.
- Lease/TTL-based claim expiry for LLM task boards is my design inference. I did not find it documented in the sources.

---

## 4. Documented failure modes and mitigations

### Takeaway
MAST, built from 1,600+ annotated traces across 7 frameworks, is the reference taxonomy. The biggest buckets are step repetition, reasoning-action mismatch, unawareness of termination conditions, task-spec disobedience and weak verification. Debate-specific research adds **conformity/sycophancy** (agents flip from correct to incorrect answers under peer pressure) and finds that homogeneous debate gives no expected gain over voting.

### Cited Findings
- **MAST, all 14 modes with prevalence:** FC1 System design: FM-1.1 disobey task spec 11.8%, FM-1.2 disobey role spec 1.5%, FM-1.3 step repetition 15.7%, FM-1.4 loss of conversation history 2.8%, FM-1.5 unaware of termination conditions 12.4%. FC2 Inter-agent misalignment: FM-2.1 conversation reset 2.2%, FM-2.2 fail to ask for clarification 6.8%, FM-2.3 task derailment 7.4%, FM-2.4 information withholding 0.85%, FM-2.5 ignored other agent's input 1.9%, FM-2.6 reasoning-action mismatch 13.2%. FC3 Task verification: FM-3.1 premature termination 6.2%, FM-3.2 no or incomplete verification 8.2%, FM-3.3 incorrect verification 9.1%. [verified] — [MAST arXiv 2503.13657v3](https://arxiv.org/html/2503.13657v3)
- MAST frameworks studied: MetaGPT, ChatDev, HyperAgent, AppWorld, AG2 (MathChat), Magentic-One and OpenManus. Inter-annotator κ = 0.88. An LLM-as-judge annotator is provided, along with the MAST-Data release of 1,600+ traces. NeurIPS 2025. [verified] — [MAST](https://arxiv.org/html/2503.13657v3); [NeurIPS 2025](https://neurips.cc/virtual/2025/poster/121528)
- MAST caveat: tactical fixes (prompts, roles) gave **inconsistent** results and did not resolve all failures. The authors call for structural redesign covering organization, verification, memory and state, and standardized communication formats. [verified] — [MAST](https://arxiv.org/html/2503.13657v3)
- **Conformity in debate:** "Talk Isn't Always Cheap" (Wynn, Satija, Hadfield; arXiv 2509.05396) finds that debate can **harm** group accuracy, "particularly with heterogeneous LLM agents", and that models frequently move from correct to incorrect answers in response to peer reasoning, favoring agreement over challenge. [via search abstract] — [arXiv 2509.05396](https://arxiv.org/html/2509.05396v1)
- **Debate ≈ voting:** "Demystifying Multi-Agent Debate" (arXiv 2601.19921) argues that vanilla debate often underperforms majority vote, and that with homogeneous agents and uniform belief updates, debate preserves expected correctness (a martingale). It proposes diverse initial viewpoints plus calibrated confidence communication. [via search abstract] — [arXiv 2601.19921](https://www.arxiv.org/pdf/2601.19921)
- **"Cost of Consensus" (arXiv 2605.00914):** the title states that isolated self-correction beats unguided homogeneous multi-agent debate. [title only, details not verified] — [arXiv 2605.00914](https://arxiv.org/pdf/2605.00914)
- **Error/hallucination propagation:** independent (unchecked) multi-agent setups amplify errors 17.2× relative to a single agent, and decentralized setups 7.8×. [verified] — [arXiv 2512.08296v2](https://arxiv.org/html/2512.08296v2)
- **Operational failures:** endless searching for nonexistent sources, over-spawning agents, excessive inter-agent updates, and small prompt changes to one agent unpredictably altering others' behavior. [verified] — [Anthropic Engineering](https://www.anthropic.com/engineering/multi-agent-research-system)
- **Tool-description quality:** an agent that rewrote a flawed tool description cut task completion time by **40%**. [verified] — [Anthropic Engineering](https://www.anthropic.com/engineering/multi-agent-research-system)
- **Context pollution from irrelevant domains** makes single agents collapse. Routing messages stored in sub-agent state also clutter context, and removing them helps. [verified] — [LangChain](https://www.langchain.com/blog/benchmarking-multi-agent-architectures)
- **Inter-agent trust / injection:** Claude Code labels messages between agents as coming from another session, not the user. A teammate cannot grant permission or consent, and relayed approvals are treated as untrusted. [verified] — [Claude Code docs](https://code.claude.com/docs/en/agent-teams)

### Inferences
- Mitigation map: step repetition and livelock → repetition detectors plus round caps. Termination unawareness and premature termination → a machine-checkable definition of done plus a completion gate. Conformity → independent first drafts before exposure, confidence-weighted or anonymous voting, model diversity, and a designated devil's advocate. Hallucination propagation → a verifier at the board's commit point plus provenance and citations on blackboard entries. Coordination overhead → sparse messaging and shared-store references.
- Treat every peer message as untrusted data, not instructions, in any supervisor-free design, because there is no central authority filtering messages.

### Gaps
- The "Talk Isn't Always Cheap" quantitative results were not extracted, only the abstract-level claim.
- No quantified data on "information cascade" or hallucination propagation specifically on blackboards.

---

## 5. Evaluation methods (benchmarks and metrics)

### Takeaway
Evaluate on outcome success **and** on coordination efficiency: tokens, turns, overhead versus a single agent, success per 1K tokens, error amplification, redundancy and message density. Always include a budget-matched single-agent baseline, and use MAST-style failure attribution rather than aggregate success alone.

### Cited Findings
- Kim et al. metrics: overhead (% extra vs SAS), turns, **message density**, **success per 1K tokens**, **error amplification A_e = E_MAS/E_SAS**, **redundancy** (embedding cosine similarity, or the share of subtasks done by multiple agents) and efficiency. Benchmarks: Finance-Agent, BrowseComp-Plus, PlanCraft, Workbench. [verified] — [arXiv 2512.08296v2](https://arxiv.org/html/2512.08296v2)
- MAST: failure-mode attribution per trace using an LLM-as-judge (validated with human κ = 0.88). The authors recommend breaking results down by mode rather than reporting only aggregate success. Benchmarks in the traces include ProgramDev, MathChat tasks and AppWorld. [verified] — [MAST](https://arxiv.org/html/2503.13657v3)
- Anthropic: start with **about 20 realistic queries** (early effect sizes are large), and use **a single LLM-judge rubric** (factual accuracy, citation accuracy, completeness, source quality, tool efficiency). **Judge outcomes, not paths**, and keep human testing, which caught the agents' bias toward SEO content farms. [verified] — [Anthropic Engineering](https://www.anthropic.com/engineering/multi-agent-research-system)
- LangChain: τ-bench (retail) with injected **distractor domains** tests robustness to context growth, and tracks score plus tokens. [verified] — [LangChain](https://www.langchain.com/blog/benchmarking-multi-agent-architectures)
- Common benchmarks in the topology papers: HumanEval (DyLAN, SoA), MATH and GSM8K (ReConcile, Diversity of Thought), and BrowseComp (Anthropic). [verified, via the sources above] — [DyLAN](https://arxiv.org/html/2310.02170v2); [SoA](https://arxiv.org/pdf/2404.02183); [ReConcile](https://arxiv.org/html/2309.13007v3); [Diversity of Thought](https://arxiv.org/html/2410.12853v1)

### Inferences
- A suggested scorecard for a business-problem framework: task success (rubric-judged), cost in tokens and dollars, wall-clock time, turns and messages, overhead vs a budget-matched single agent, duplicate-work rate (tasks claimed or redone by more than one agent), verification pass/fail rate at the commit gate, MAST mode counts, and termination correctness (premature, late or never).

### Gaps
- No established benchmark exists for decentralized business-problem MAS, such as multi-step analyses, planning or reports. Most benchmarks are code, math, web or finance QA.

---

## 6. Practical design recommendations for 5–10 agents with heterogeneous LLMs (model diversity)

### Takeaway
Model diversity helps in **decentralized** consensus settings: diverse mid-tier models can beat a single frontier model in debate, and mixed teams match or beat homogeneous strong teams in Kim et al.'s decentralized runs. It is not a free win, though. Some studies find negative synergy and heightened conformity with heterogeneous teams. Start with 3–5 active agents, scale toward 10 only for genuinely parallel work, and add model diversity mainly to the review and verification roles.

### Cited Findings
- **Diversity helps debate:** after 4 rounds, a diverse trio of medium models (Gemini-Pro, Mixtral 8×7B, PaLM 2-M) reached **91% on GSM8K**, versus **82% for 3× Gemini-Pro**, and outperformed GPT-4. [verified, via search abstract] — [Diversity of Thought arXiv 2410.12853](https://arxiv.org/html/2410.12853v1)
- **ReConcile:** diversity from different model families is "critical" to its gains (up to +11.4%). [verified, via search] — [ReConcile](https://arxiv.org/html/2309.13007v3)
- **Kim et al., heterogeneous mixing:** in **decentralized** setups, mixed-capability teams were near or above homogeneous high-capability teams (OpenAI 0.53 vs 0.50; Anthropic 0.47 vs 0.37; Gemini 0.42 vs 0.43 on BrowseComp-Plus). In centralized setups, a low-capability orchestrator with high-capability sub-agents helped for Anthropic (0.42 vs 0.32) but hurt for OpenAI and Gemini. In every family, high-capability *workers* mattered more than a high-capability *orchestrator*. [verified] — [arXiv 2512.08296v2](https://arxiv.org/html/2512.08296v2)
- **Counter-evidence:** a 2026 preprint on small open models (Qwen2.5-7B + Llama-3.1-8B) found **negative synergy** in 6 of 8 condition–task pairs, where the heterogeneous team underperformed its best homogeneous member, with sycophancy comparable to homogeneous teams. [via search snippet; specific paper ID unclear, possibly arXiv 2604.26561 or 2605.00914] — [arXiv 2604.26561](https://arxiv.org/pdf/2604.26561). Wynn et al. also report that debate harms performance more often with heterogeneous agents. [via search] — [arXiv 2509.05396](https://arxiv.org/html/2509.05396v1)
- **Team size:** start with 3–5 teammates. Token costs scale linearly and coordination overhead rises. [verified] — [Claude Code docs](https://code.claude.com/docs/en/agent-teams). Per-agent capacity is "prohibitively thin beyond 3–4 agents" under fixed budgets. [verified] — [arXiv 2512.08296v2](https://arxiv.org/html/2512.08296v2)
- **When not to go multi-agent:** for sequential or tightly coupled tasks, same-file edits, or when the single-agent baseline is already above about 45%. [verified] — [Kim et al.](https://arxiv.org/abs/2512.08296v1); [Claude Code docs](https://code.claude.com/docs/en/agent-teams); [Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
- **Adversarial hypothesis teams:** having teammates actively try to disprove each other's hypotheses counters anchoring, and "the theory that survives is much more likely to be the actual root cause". [verified, vendor guidance not a measured result] — [Claude Code docs](https://code.claude.com/docs/en/agent-teams)
- **Parallelism payoff:** parallel subagent and tool calls cut research time by up to 90% on complex queries. [verified] — [Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)

### Inferences (design recommendations for the framework)
1. **Coordination substrate:** a typed blackboard or task board (event-sourced) with a task DAG, atomic claims with leases, per-resource ownership, and P2P mailboxes for targeted messages. Avoid all-to-all chat.
2. **Self-selection:** agents volunteer for tasks that match their declared capabilities (blackboard-volunteer pattern). A deterministic rule breaks ties, such as first atomic claim wins. Do not rely on LLM-generated bids.
3. **Decomposition without a supervisor:** a "planner" step can be a role that any agent claims, and its output is itself a board task subject to peer review. Alternatively, a deterministic seeder can decompose from templates.
4. **Quality:** a completion gate needs at least one independent reviewer, ideally a *different model family* (where diversity helps most), plus a check against the high-level objective (MAST's +15.6% intervention).
5. **Consensus:** for judgment calls, collect independent first answers, then do **at most 1–2 rounds** of exchange with confidence-weighted voting, and keep minority reports. Prefer heterogeneous models, and watch for conformity.
6. **Termination and cost:** hard global token and dollar budgets, per-task budget contracts, round caps, repetition detection, and an explicit machine-checkable definition of done. Record and stop.
7. **Sizing:** 3–5 active agents by default. Scale toward 10 only for breadth-first, parallel workloads with 5–6 tasks per agent.
8. **Evaluation:** use a budget-matched single-agent baseline, MAST failure tagging and the Kim et al. efficiency metrics.

### Gaps
- No study tested heterogeneous 5–10 agent teams on business tasks such as strategy analyses, forecasting or operations planning. The diversity evidence comes mainly from math and QA reasoning and from web browsing.
- The conflicting evidence on diversity seems to depend on model strength (small open models showed negative synergy, while frontier and mid-tier models showed gains). This remains unresolved.
- GPTSwarm's and AutoGen GroupChat's quantitative results were not retrieved this session.
