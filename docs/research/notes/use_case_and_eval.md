# Showcase Use Cases and Evaluation Design for a Self-Organizing (No-Supervisor) Team of up to 10 LLM Agents

## Which enterprise problems decompose into parallel, loosely-coupled, verifiable sub-tasks, and where does multi-agent plausibly beat single-agent or supervisor-led?

### Takeaway
The best evidence (Google/MIT's 180-configuration scaling study, Anthropic's research system) says multi-agent setups pay off on breadth-first, parallelisable work whose information exceeds one context window. Financial research is one such task (+81% on Finance-Agent). On sequential, tightly-coupled tasks multi-agent setups hurt badly (-39% to -70% on PlanCraft). So the showcase must be chosen for decomposability first and industry appeal second. Of the eight candidates, due diligence / financial research, underwriting submission triage, regulatory obligation mapping, and payments/fee reconciliation analytics have public data with objective, test-like scoring. RFP assembly and claims fraud do not.

### Cited Findings
**General evidence on when multi-agent helps**
- Google Research/MIT ran a controlled study of 180 agent configurations. It covered 5 architectures (single-agent, independent, centralized, decentralized, hybrid), 4 benchmarks (Finance-Agent, BrowseComp-Plus, PlanCraft, Workbench) and 3 model families (GPT, Gemini, Claude) — [Google Research blog](https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/); [arXiv 2512.08296](https://arxiv.org/html/2512.08296v1)
- In that study, multi-agent coordination improved Finance-Agent (parallelisable financial reasoning) by about 81% over single-agent, with centralized coordination at +80.9%. Every multi-agent variant degraded PlanCraft (sequential) by 39–70% — [Google Research blog](https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/)
- In the same study, errors were amplified up to 17.2x in independent multi-agent systems versus 4.4x in centralized ones, where the orchestrator acts as a validation checkpoint. Coordination overhead grows disproportionately with tool count (16+ tools). A predictive model built on task decomposability and tool density picks the optimal architecture for 87% of unseen configurations (R² = 0.513) — [Google Research blog](https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/)
- Anthropic's multi-agent research system (Opus 4 lead with Sonnet 4 subagents) beat single-agent Opus 4 by 90.2% on an internal research eval. Multi-agent systems use about 15x the tokens of chat, and token usage alone explained 80% of BrowseComp performance variance. Anthropic says the approach suits "breadth-first" queries, heavy parallelisation and information beyond a single context window. It fits poorly where agents must share the same context or have many dependencies, which includes most coding — [Anthropic Engineering](https://www.anthropic.com/engineering/multi-agent-research-system)
- The MAST study of 7 MAS frameworks across 200+ tasks identified 14 failure modes in 3 categories: specification issues, inter-agent misalignment and task verification (Cohen's kappa 0.88). It found MAS gains over single-agent frameworks "often remain minimal" on popular benchmarks — [arXiv 2503.13657](https://arxiv.org/abs/2503.13657v2)

**Evidence specific to self-organization (no supervisor)**
- Dochkina (Mar 2026), "Drop the Hierarchy and Roles", ran about 25,000 tasks with 8 models, 4–256 agents and 8 coordination protocols. A hybrid "Sequential" protocol with minimal structure (fixed ordering, no pre-assigned roles) beat centralized coordination by 14% (p<0.001). Quality varied 44% across protocols (d=1.86). Agents spontaneously specialised (8 agents produced 5,006 unique roles), declined tasks outside their competence and formed shallow hierarchies. Self-organization works only above a model-capability threshold, and weaker models still benefit from rigid structure — [arXiv 2603.28990](https://arxiv.org/abs/2603.28990) (single-author preprint, not yet peer-reviewed)
- MultiAgentBench/MARBLE (ACL 2025) tested star and tree (centralized) against graph and chain (decentralized). In the research scenario, the decentralized graph-mesh protocol was best on task score, planning efficiency and tokens, and tree was worst. Going from 1 to 3 agents improved coordination, but overall KPI fell as agents rose to 5 and 7, and group-discussion planning scored worst — [arXiv 2503.01935](https://arxiv.org/html/2503.01935v1)
- Related decentralized frameworks: AgentNet (decentralized evolutionary coordination) — [arXiv 2504.00587](https://arxiv.org/html/2504.00587v1); MorphAgent (self-evolving profiles, decentralized collaboration) — [arXiv 2410.15048](https://arxiv.org/pdf/2410.15048)

**Candidate assessments (sub-tasks, data, objective metric)**

1. **M&A / vendor / investment due diligence (financial research dossier)**
   - Finance Agent Benchmark (Vals AI) has 537 expert-authored questions from bank, hedge-fund and PE analysts. It is split into a 50-question public validation set, a 150-question private validation set and a 337-question private test set. Its 9 categories are Quantitative Retrieval, Qualitative Retrieval, Numerical Reasoning, Complex Retrieval, Adjustments, Beat-or-Miss, Trends, Financial Modeling and Market Analysis. Tools are web search, EDGAR search, HTML parse and retrieve — [arXiv 2508.00828](https://arxiv.org/pdf/2508.00828)
   - Grading uses an LLM judge against per-question rubric items extracted from expert answers. Each item is checked separately, with a contradiction check. The best model (o3) scored 46.8% class-balanced, about $3.79 and 3.1 minutes per query, and no model exceeded 50% — [arXiv 2508.00828](https://arxiv.org/pdf/2508.00828)
   - This is the same "Finance-Agent" task family on which multi-agent gained about 81% — [Google Research blog](https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/)
   - Legal-side data: CUAD (expert-annotated contract review) — [arXiv 2103.06268](https://arxiv.org/pdf/2103.06268); MAUD (expert-annotated merger-agreement understanding) — [arXiv 2301.00876](https://arxiv.org/pdf/2301.00876)

2. **Commercial insurance underwriting submission triage**
   - The Snorkel multi-turn underwriting benchmark has 6 task types: appetite check, product recommendation, small-business qualification, NAICS classification, policy limits and deductibles. Data is a multi-table DB (NAICS and SBA tables via SQL) plus free-text underwriting guidelines. Agents must ask the (simulated) underwriter follow-up questions. The dataset is public at huggingface.co/datasets/snorkelai/Multi-Turn-Insurance-Underwriting — [Snorkel blog](https://snorkel.ai/blog/evaluating-ai-agents-for-insurance-underwriting/); [leaderboard](https://snorkel.ai/leaderboard/snorkel-underwrite/)
   - Scoring is against reference answers built from expert input and programmatic methods. Results by task: deductibles 0.784, NAICS classification 0.772, limits 0.762, appetite 0.615, product recommendation 0.377. 36% of conversations had at least one tool-call error, and models hallucinated non-existent products in 15–45% of product-recommendation cases — [Snorkel blog](https://snorkel.ai/blog/evaluating-ai-agents-for-insurance-underwriting/)

3. **Regulatory change impact analysis (obligation to control mapping)**
   - ObliQA has 27,869 questions over 40 ADGM regulatory documents (about 640k words). The RePASs metric is (Entailment − Contradiction + Obligation Coverage + 1)/3, where obligation coverage is the share of source obligations entailed by the answer (p > 0.7). Dataset and metric are on GitHub (RegNLP/ObliQADataset, RegNLP/RePASs) — [arXiv 2409.05677](https://arxiv.org/html/2409.05677v2)

4. **Financial close / payments reconciliation and fee analytics**
   - DABstep (Adyen and Hugging Face) has 450+ tasks (72 easy, 378 hard) over 138k payment transactions, 1,000+ fee rules and a payments manual. Answers are factoids scored by quasi-exact match. The best result on hard tasks was 14.55% (o4-mini), against 76.39% on easy tasks. The dataset is CC BY 4.0 on Hugging Face, with a hidden test set and a public leaderboard — [arXiv 2506.23719](https://arxiv.org/html/2506.23719v1)

5. **CRM / sales / service ops (RFP-adjacent: CPQ, policy compliance)**
   - CRMArena-Pro has 19 expert-validated tasks across 4 skills (DB querying, info retrieval, workflow execution, policy compliance), covering B2B and B2C. The best single-turn score is about 58% (gemini-2.5-pro), falling to about 35% multi-turn. Models show "near-zero inherent confidentiality awareness" — [arXiv 2505.18878](https://arxiv.org/html/2505.18878v1)

6. **Expert-graded knowledge-work deliverables (RFP response, market-entry memo, finance or healthcare manager deliverables)**
   - GDPval has 1,320 tasks across 44 occupations in 9 sectors, with a 220-task gold subset open-sourced. Tasks average about 7 hours of expert work (appendix: 9.49 h gold, 8.63 h full). Grading is blinded pairwise comparison against human expert deliverables by industry experts, scored as win-or-tie rate. The experimental automated grader agrees with experts 66% of the time, against 71% human inter-rater agreement. The best model on the gold subset, Claude Opus 4.1, scored 47.6% wins or ties — [arXiv 2510.04374](https://arxiv.org/html/2510.04374v1)
   - Relevant GDPval occupations: Financial Managers, Financial & Investment Analysts, Personal Financial Advisors and Securities Sales Agents (Finance & Insurance); Medical & Health Services Managers and Medical Secretaries (Health Care); Producers & Directors, Editors and Film/Video Editors (Information/media) — [arXiv 2510.04374](https://arxiv.org/html/2510.04374v1)
   - TheAgentCompany is a simulated software company. Its best agent completes 30% of tasks autonomously (v3, Sept 2025) — [arXiv 2412.14161](https://arxiv.org/abs/2412.14161)

### Inferences
- **Fit ranking for a no-supervisor team (decomposability × verifiability × public data × client relevance):**
  1. **Due-diligence dossier (Finance Agent Benchmark ± FinanceBench / CUAD / MAUD).** This has the strongest prior evidence of multi-agent gain. The sub-tasks are heterogeneous (revenue and segments, guidance beat/miss, adjustments, debt and covenants, risk factors, comps, contract clauses), so specialised roles can actually emerge. Rubric items act as unit tests.
  2. **Underwriting submission-batch triage (Snorkel).** It has high relevance to insurance clients and exact reference answers. Its weakness is that each submission is small and conversational, so a 10-agent team mostly shards the batch (embarrassingly parallel), which weakly demonstrates self-organization. Mixing submission types and a shared guideline-interpretation burden could help.
  3. **Regulatory obligation mapping (ObliQA + RePASs).** Obligation coverage is a natural "coverage" metric, and work splits naturally by document or chapter. DORA and EU AI Act versions would need a home-built gold mapping.
  4. **Payments reconciliation analytics (DABstep).** It has the most objective scoring (exact match), but the hard tasks are deep sequential chains. The Google results suggest multi-agent could hurt here, which makes it a good negative-control benchmark.
  5. **GDPval-style RFP or market-entry deliverables.** These are most compelling to executives but have the weakest verifiability. Use them as a secondary expert-graded showcase.
  6. **Claims fraud investigation.** It decomposes well into document, provider-network, billing-anomaly and narrative-consistency checks, but there is no public agentic benchmark with verifiable outputs (see Gaps).
- Plausible emergent roles in the dossier task: filings retriever(s) per document type, quantitative modeler, qualitative/risk-factor analyst, contract/legal reader, cross-checker/verifier (critical, given 17.2x error amplification without checks) and synthesiser/editor.
- Self-organization is more credible in 2026 than in 2024–25 because capable models now self-specialise (Dochkina). The Google and MAST findings, however, imply that a decentralized team needs an explicit peer-verification mechanism (for example a claim-then-verify protocol on a shared blackboard) to avoid error cascades.

### Gaps
- I did not obtain the Google study's numbers for the decentralized architecture specifically on Finance-Agent, only the overall (~81%) and centralized (80.9%) figures. Check the paper's tables before claiming decentralized beats centralized on that task.
- I did not verify current (Oct 2026) leaderboard tops for Finance Agent, DABstep, Snorkel Underwrite, GDPval or TheAgentCompany. The figures above are from the original papers (2025).
- I did not verify details of FinanceBench, tau2-bench, OfficeBench, WorkArena or BrowseComp-Plus beyond BrowseComp-Plus being used in the Google study. CUAD and MAUD sizes (contracts and clause counts) were not verified.
- I found no public, reproducible agentic benchmark for claims fraud investigation, RFP response assembly, supply-chain disruption response, or DORA/EU AI Act control mapping. These would need synthetic or home-built gold sets.
- The Snorkel underwriting dataset size (number of conversations or companies) is not stated in the blog.

## How should the team be evaluated (baselines, team sizes, metrics, judges)?

### Takeaway
The experiment should be a factorial: {single agent, supervisor-led team, self-organized team} × team size {1, 3, 5, 10}, run on held-out tasks with a rubric-item "test-pass rate" as the primary metric. Because token spend alone explains about 80% of performance variance in research-agent evals, the comparison must control for total token budget, or report quality per dollar. Otherwise "the team won" just means "the team spent more."

### Cited Findings
- Token usage explained 80% of BrowseComp variance, and multi-agent systems burn about 15x the tokens of chat — [Anthropic Engineering](https://www.anthropic.com/engineering/multi-agent-research-system)
- Anthropic's judge design: a single LLM call returning a 0–1 score plus pass/fail against a rubric (factual accuracy, citation accuracy, completeness, source quality, tool efficiency) was the most consistent and best aligned with humans. About 20 real queries were enough when early effect sizes were large — [Anthropic Engineering](https://www.anthropic.com/engineering/multi-agent-research-system)
- Finance Agent Benchmark grading checks each rubric item separately with an LLM judge plus a contradiction check, which gives a natural item-level pass rate — [arXiv 2508.00828](https://arxiv.org/pdf/2508.00828)
- GDPval-style expert grading uses blinded pairwise comparison against a human expert deliverable, scored as win-or-tie rate. Automated grader to expert agreement was 66%, against 71% human to human — [arXiv 2510.04374](https://arxiv.org/html/2510.04374v1)
- MultiAgentBench measures milestone-based KPIs: per-agent KPI is milestones contributed ÷ total milestones, and overall KPI is Σ milestones ÷ (N×M). It also scores communication and planning on a 1–5 LLM-rated scale, averaged into a Coordination Score — [arXiv 2503.01935](https://arxiv.org/html/2503.01935v1)
- Error amplification (how much one agent's error propagates to the final output) was used as a key architecture metric: 17.2x for independent and 4.4x for centralized — [Google Research blog](https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/)
- MAST provides a 14-mode failure taxonomy with high inter-annotator reliability (kappa 0.88), usable to label team traces — [arXiv 2503.13657](https://arxiv.org/abs/2503.13657v2)
- The RePASs obligation-coverage metric offers a reference-free coverage measure for regulatory outputs — [arXiv 2409.05677](https://arxiv.org/html/2409.05677v2)
- DABstep's quasi-exact-match scorer gives fully objective pass/fail for factoid answers — [arXiv 2506.23719](https://arxiv.org/html/2506.23719v1)
- The self-organization study reports quality, emergent role counts and scaling with agent count (4–256) under significance testing — [arXiv 2603.28990](https://arxiv.org/abs/2603.28990)

### Inferences
**Proposed evaluation protocol**
- **Arms:**
  - (A) a single agent with the same tools;
  - (B) a supervisor/orchestrator with N−1 workers;
  - (C) a self-organized peer team of N agents with a shared blackboard or task board, claim/lock semantics and peer verification, and no supervisor;
  - optionally, (D) an independent ensemble (N agents in parallel, majority vote) to isolate "more compute" from "coordination."
  - Run N ∈ {1, 3, 5, 10} with the same base model, plus one weaker model to test the capability-threshold claim.
- **Budget control:** run every arm at (i) a fixed total token budget per task and (ii) an unconstrained budget. Report Pareto curves of quality against cost.
- **Primary metric ("test-pass rate"):** the share of rubric items or exact-match answers passed per task. Use Finance Agent rubric items, Snorkel reference answers or DABstep exact-match answers, as applicable.
- **Secondary metrics:**
  - Coverage: the share of required sub-questions or obligations addressed (RePASs-style).
  - Time-to-quality: wall-clock time to reach X% of the arm's final pass rate, the analogue of time to green tests.
  - Cost per passed item ($ and tokens).
  - Duplicate-work rate: overlapping tool calls or document reads across agents divided by total, plus claim collisions on the task board.
  - Message volume and messages per passed item.
  - Error amplification: inject a known error into one agent and measure propagation to the final output.
  - Idle/blocked time.
  - Emergent role specialisation: entropy of each agent's action/tool distribution.
  - MAST failure-mode incidence per run.
- **Judging:**
  - Use rubric-item LLM judges, with a contradiction check, from a different model family than the agents.
  - Calibrate judges against roughly 50 expert-labelled items, targeting agreement near the human-to-human level, and report kappa.
  - For deliverable-style tasks, run GDPval-style blinded pairwise expert comparison (arm vs arm, and arm vs human).
- **Statistics:** use ≥3 seeds per cell, paired bootstrap confidence intervals across tasks, and pre-registered hypotheses. One hypothesis is H1: C ≥ B on pass rate at equal budget for N=5 and 10. Another is H2: C < A on sequential control tasks (DABstep-hard or PlanCraft) to show the architecture is task-sensitive.

**Recommended single best showcase: "Autonomous due-diligence dossier"**
- **What it is:** for a target company, a 10-agent peer team answers a bundle of 15–30 diligence questions. Questions come from Finance Agent Benchmark categories (public 50-question set, regrouped by company), optionally adding FinanceBench questions and CUAD/MAUD contract-clause checks. The team then assembles an investment-committee or vendor-risk memo.
- **Why this one:**
  - It has the strongest published evidence that multi-agent coordination helps (+81% on Finance-Agent).
  - The work is breadth-first and exceeds one context window (multiple 10-Ks, 10-Qs, transcripts and contracts).
  - Sub-tasks are heterogeneous, so role emergence can actually be observed.
  - Per-item expert rubrics give a credible "unit test pass rate."
  - Headroom is large (best single model below 50%).
  - It maps directly to Virtusa's financial-services, insurance and PE clients, including the existing PE data-migration and M&A context.
- **Secondary showcase for insurance clients:** underwriting submission triage on the Snorkel dataset, as a batch of mixed submissions per run, scored by reference-answer accuracy per task type.
- **Negative control:** DABstep hard tasks.
- **Risks to disclose:**
  - Finance Agent's private sets are not public, so reproducible runs must use the 50-question public set or a self-built extension, which limits statistical power.
  - The Google study shows centralized coordination limits errors better than independent agents, so the self-organized design must include peer verification to be competitive.
