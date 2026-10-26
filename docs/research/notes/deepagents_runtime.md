# LangChain Deep Agents (Python) as the runtime for a supervisor-less team of peer agents (state as of 26 Oct 2026)

Method note: I took the version facts from the PyPI JSON API. I read the API surface from the installed **deepagents 0.7.32 wheel source** (`deepagents/graph.py`, `backends/*.py`, `middleware/*.py`), downloaded from PyPI on 2026-10-26, and checked it against docs.langchain.com pages. GitHub REST and GraphQL access to the repo was blocked in this session. The cached GitHub releases page showed only September entries, so the changelog coverage is partial. Where the docs and the source disagree, I note it. Source-code citations point to the PyPI project page, because that is where the wheel came from.

## 1. Current `create_deep_agent` signature, version, and recent changes

### Takeaway
The latest release is `deepagents==0.7.32` (23 Oct 2026). Releases come out every few days. `create_deep_agent(model, tools, *, system_prompt, middleware, subagents, skills, memory, permissions, backend, interrupt_on, response_format, state_schema, context_schema, checkpointer, store, debug, name, cache)` returns a compiled LangGraph `CompiledStateGraph`. Each agent is therefore an ordinary LangGraph graph, so you can run many of them concurrently, each with its own model.

### Cited Findings
- The latest PyPI version is **0.7.32**, uploaded 2026-10-23T21:30. The 0.7.x line shipped about 25 patch releases between 20 Aug (0.7.8) and 23 Oct 2026 (0.7.32). It requires `langchain>=1.4.7,<2`, `langchain-core>=1.7.0`, `langchain-anthropic>=1.7.6`, `langchain-google-genai>=4.4.2`, `langsmith>=0.14.12`, with optional extras `aws`, `quickjs`, `video` — [PyPI deepagents](https://pypi.org/project/deepagents/)
- Related package versions on 26 Oct 2026: `langgraph 1.2.17` (24 Oct), `langchain 1.4.7` (21 Oct), `langchain-fireworks 1.7.1` (7 Oct), `langchain-mcp-adapters 0.3.2` (6 Aug), `langgraph-swarm 0.1.0` (4 Dec 2025, no 2026 release), `deepagents-cli 0.3.0` (24 Aug), `deepagents-code 0.2.1` (23 Oct) — PyPI JSON for [langgraph](https://pypi.org/project/langgraph/), [langchain-fireworks](https://pypi.org/project/langchain-fireworks/), [langchain-mcp-adapters](https://pypi.org/project/langchain-mcp-adapters/), [langgraph-swarm](https://pypi.org/project/langgraph-swarm/), [deepagents-code](https://pypi.org/project/deepagents-code/)
- Exact signature in the 0.7.32 source (`deepagents/graph.py`) — [PyPI deepagents 0.7.32](https://pypi.org/project/deepagents/0.7.32/):
```python
def create_deep_agent(
    model: str | BaseChatModel | None = None,
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
    *,
    system_prompt: str | SystemMessage | None = None,
    middleware: Sequence[AgentMiddleware[StateT_co, ContextT]] = (),
    subagents: Sequence[SubAgent | CompiledSubAgent | AsyncSubAgent] | None = None,
    skills: list[str] | None = None,
    memory: list[str] | None = None,
    permissions: list[FilesystemPermission] | None = None,
    backend: BackendProtocol | None = None,
    interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
    response_format: ResponseFormat[ResponseT] | type[ResponseT] | dict[str, Any] | None = None,
    state_schema: type[DeepAgentState] | None = None,
    context_schema: type[ContextT] | None = None,
    checkpointer: Checkpointer | None = None,
    store: BaseStore | None = None,
    debug: bool = False,
    name: str | None = None,
    cache: BaseCache | None = None,
) -> CompiledStateGraph[...]
```
- Docstring: passing `model=None` (default `claude-sonnet-4-6`) has been "deprecated since `0.5.3` and will be removed in `deepagents==1.0.0`". An `openai:` model uses the Responses API by default. Use `init_chat_model("openai:...", use_responses_api=False)` for Chat Completions — [PyPI deepagents 0.7.32 source](https://pypi.org/project/deepagents/0.7.32/)
- The default tools are `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`, `execute` (works only with a sandbox backend) and `task`. `delete` requires `deepagents>=0.7`. "Passing tools here is additive — it never removes a built-in". To hide a built-in tool, register a `HarnessProfile` with `excluded_tools` or pass your own `FilesystemMiddleware(tools=[...])` — [Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview); [source](https://pypi.org/project/deepagents/0.7.32/)
- Public exports in 0.7.32: `create_deep_agent, DeepAgentState, AsyncSubAgent, AsyncSubAgentMiddleware, FilesystemMiddleware, FilesystemPermission, FsToolName, GeneralPurposeSubagentProfile, HarnessProfile, HarnessProfileConfig, MemoryMiddleware, ProviderProfile, RubricMiddleware, SubAgent, CompiledSubAgent, SubAgentMiddleware, register_harness_profile, register_provider_profile` — [source `deepagents/__init__.py`](https://pypi.org/project/deepagents/0.7.32/)
- Version-specific changes from the docs:
  - Starting in v0.7, task planning (`TodoListMiddleware` / `write_todos`) is opt-in. Earlier versions included it by default.
  - `delete` and the `FilesystemMiddleware(tools=[...])` allowlist require 0.7.
  - Binary content offloading requires 0.7.21.
  - Fork-mode subagents require 0.7.13 (beta).
  - Async-subagent notifications, the `waiting` status and `parent_thread_id` thread tagging require 0.7.26 (beta).
  - Custom `state_schema` requires 0.6.6.
  - Backend factories have been deprecated since 0.5.0.
  — [overview](https://docs.langchain.com/oss/python/deepagents/overview), [backends](https://docs.langchain.com/oss/python/deepagents/backends.md), [async subagents](https://docs.langchain.com/oss/python/deepagents/async-subagents.md), [subagents](https://docs.langchain.com/oss/python/deepagents/subagents.md), [context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering.md)
- GitHub release notes I could see (September only): `deepagents==0.7.14` (14 Sep) "Updated `read_file` output formatting". `deepagents==0.7.15` (16 Sep) was bug fixes only. `deepagents-code==0.1.71` "Moved MCP support onto FastMCP and `langchain.mcp`" — [GitHub releases](https://github.com/langchain-ai/deepagents/releases)
- The minimal quickstart from the docs:
```python
from deepagents import create_deep_agent
agent = create_deep_agent(
    model="anthropic:claude-sonnet-5",
    tools=[get_weather],
    system_prompt="You are a helpful assistant",
)
agent.invoke({"messages": [{"role": "user", "content": "what is the weather in sf"}]})
```
— [overview](https://docs.langchain.com/oss/python/deepagents/overview)

### Inferences
- `create_deep_agent` returns a compiled LangGraph graph. Each peer is therefore an independent graph with its own model, its own thread (checkpointer) and a shared `store`. Nothing in the library forces a supervisor topology. Supervision comes only from how `subagents` / `task` are used.
- To get a pure peer (no `task` tool), set `general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)` on a harness profile and pass no sync subagents. The docstring says that with no synchronous subagents "the `task` tool is not exposed" — [source](https://pypi.org/project/deepagents/0.7.32/).
- Pin a version (e.g. `deepagents==0.7.32`), because the release cadence is high and several building blocks are beta.

### Gaps
- I could not read the full 2026 changelog (GitHub API blocked; the cached releases page covered September only). I found no deepagents 1.0 release.
- `deepagents-cli` (0.3.0, Aug) and `deepagents-code` (0.2.1, Oct) both exist. The docs now point to "Deep Agents Code", and `deepagents-cli` appears to be the older name. I did not confirm this.

## 2. Backends: can independent agents share a workspace, and what are the concurrency semantics?

### Takeaway
Yes. A `StoreBackend` (backed by a shared LangGraph `BaseStore`, such as Postgres) or a `FilesystemBackend` / sandbox pointed at the same root gives N independent agents one shared workspace. **None of the built-in backends provide locking or compare-and-swap for agents**, except `ContextHubBackend`, which uses optimistic commits. `write_file` and `edit_file` are plain read-modify-write with last-writer-wins, so an atomic task claim needs a custom tool.

### Cited Findings
- Backends available in 0.7.32: `StateBackend`, `FilesystemBackend`, `StoreBackend`, `CompositeBackend`, `LocalShellBackend`, `ContextHubBackend`, `LangSmithSandbox`, plus third-party sandboxes that implement `SandboxBackendProtocolV2` (these add `execute`) — [source `backends/__init__.py`](https://pypi.org/project/deepagents/0.7.32/); [overview](https://docs.langchain.com/oss/python/deepagents/overview)
- `StateBackend` (the default): "Files persist across turns on the same thread through checkpoints and are not shared across threads". The supervisor and its subagents share this backend — [backends](https://docs.langchain.com/oss/python/deepagents/backends.md)
- `StoreBackend` provides cross-thread durable storage, scoped by a namespace factory. Examples: per-user `(rt.server_info.user.identity,)`, per-assistant `(rt.server_info.assistant_id,)`, per-thread `(rt.execution_info.thread_id,)`, or combinations. Wildcards are rejected — [backends](https://docs.langchain.com/oss/python/deepagents/backends.md)
- Code from the docs:
```python
backend=StoreBackend(namespace=lambda rt: (rt.server_info.user.identity,))
backend=CompositeBackend(
    default=StateBackend(),
    routes={"/memories/": StoreBackend(namespace=lambda _rt: ("memories",))},
)
backend=FilesystemBackend(root_dir=".", virtual_mode=True)
backend=LocalShellBackend(root_dir=".", virtual_mode=True, env={"PATH": "/usr/bin:/bin"})
backend=ContextHubBackend("my-agent")
```
— [backends](https://docs.langchain.com/oss/python/deepagents/backends.md)
- In the source, `StoreBackend.__init__(*, namespace, store=None)` accepts an explicit `BaseStore`. Without one it falls back to `get_store()` from the graph context. The error-message example is `StoreBackend(store=my_store, namespace=lambda _rt: ('filesystem',))` — [source `backends/store.py`](https://pypi.org/project/deepagents/0.7.32/)
- **No locking.** `StoreBackend.awrite` does `existing = await store.aget(...)` and then `await store.aput(namespace, file_path, store_value)`. `aedit` reads the item, does a string replace in Python, then `aput`s the result. There is no version check or lock — [source `backends/store.py`](https://pypi.org/project/deepagents/0.7.32/)
- `FilesystemBackend.write` opens the file with `os.O_WRONLY | os.O_CREAT | os.O_TRUNC` (plus `O_NOFOLLOW`). There is no `O_EXCL` and no file lock, so concurrent writers overwrite each other — [source `backends/filesystem.py`](https://pypi.org/project/deepagents/0.7.32/)
- `ContextHubBackend` "uses optimistic parent-commit writes. If another writer advances the repo first, a stale write can fail". The source defines `_MAX_CONFLICT_RETRIES = 3` and handles `LangSmithConflictError` by reloading and rematerialising the edit — [backends](https://docs.langchain.com/oss/python/deepagents/backends.md); [source `backends/context_hub.py`](https://pypi.org/project/deepagents/0.7.32/)
- The backends page "does not describe concurrency controls for the other backends" — [backends](https://docs.langchain.com/oss/python/deepagents/backends.md)
- Shared scopes can enable prompt injection. LangChain advises restricting writes, for example through permissions or backend policy hooks — [going to production](https://docs.langchain.com/oss/python/deepagents/going-to-production)
- `FilesystemPermission(operations=[...], paths=[globs], mode="allow"|"deny"|"interrupt")` rules are evaluated first match wins, and a call that matches no rule is allowed. Permissions do not apply to sandbox backends — [overview](https://docs.langchain.com/oss/python/deepagents/overview); [source](https://pypi.org/project/deepagents/0.7.32/)
- Sandboxes can be thread-scoped (one per conversation) or assistant-scoped (shared across threads, which accumulates state). Files cross the sandbox boundary via `upload_files()` and `download_files()` — [going to production](https://docs.langchain.com/oss/python/deepagents/going-to-production)

### Inferences
- **Shared workspace:** build one `PostgresStore` (or `InMemoryStore` for a PoC) and give every peer `CompositeBackend(default=StateBackend(), routes={"/team/": StoreBackend(store=shared_store, namespace=lambda _rt: ("team", RUN_ID))})`. That keeps private scratch space per thread and puts `/team/...` in a shared space. For real code plus `execute`, point every peer at the same sandbox (assistant-scoped) or the same `FilesystemBackend(root_dir=...)`.
- **Atomic task claims cannot be built on `write_file`/`edit_file`.** Expose a custom `claim_task(task_id)` tool backed by something with real atomicity, then add it via `tools=`. Options: a Postgres `UPDATE ... WHERE status='open' RETURNING`, `INSERT ... ON CONFLICT DO NOTHING`, `os.open(path, O_CREAT|O_EXCL)` on a shared disk, or Redis `SETNX`. `ContextHubBackend`'s optimistic commit is the only built-in compare-and-swap-like behaviour. It works at repo-commit granularity and retries automatically, which hides conflicts rather than reporting a failed claim. That makes it unsuitable as a claim primitive without wrapping. (This is my inference. I did not check whether LangGraph `BaseStore` offers compare-and-swap; the deepagents code does not use any.)
- Use `FilesystemPermission` deny rules to stop peers from directly editing `/team/board/**`, so that claims go only through the atomic tool.

### Gaps
- No official doc covers several independent deep agents sharing one store. All the shared-scope examples are about multiple users or threads of a single assistant.

## 3. Middleware and injecting "team context" each turn

### Takeaway
The middleware stack is fixed and documented. Your own middleware is inserted between the base and tail stacks. To inject team context (board snapshot, inbox, peer status) on each turn, use a `wrap_model_call` / `@dynamic_prompt` that rewrites `request.system_message`, or a `before_model` hook that appends a message. `RubricMiddleware` (exported in 0.7.32) is a ready-made verify-and-iterate loop.

### Cited Findings
- Stack order (0.7.32 docstring):
  - Base: `FilesystemMiddleware` → `SubAgentMiddleware` (if sync subagents) → `SummarizationMiddleware` → `PatchToolCallsMiddleware` → `AsyncSubAgentMiddleware` (if async subagents).
  - **User middleware** goes here.
  - Tail: profile `extra_middleware` → `SkillsMiddleware` → `AnthropicPromptCachingMiddleware` (unconditional, does nothing for non-Anthropic models) → `BedrockPromptCachingMiddleware` (if `langchain-aws` is installed) → `FireworksPromptCachingMiddleware` (if `langchain-fireworks` is installed) → `MemoryMiddleware` → `HumanInTheLoopMiddleware` (if `interrupt_on` is set) → `UnsupportedContentMiddleware` → `_ToolExclusionMiddleware`.

  `FilesystemMiddleware` and `SubAgentMiddleware` are protected and cannot be excluded — [source `graph.py`](https://pypi.org/project/deepagents/0.7.32/)
- `TodoListMiddleware` comes from `langchain.agents.middleware`, adds `write_todos` with statuses `pending`/`in_progress`/`completed`, and has been opt-in since v0.7:
```python
from langchain.agents.middleware import TodoListMiddleware
agent = create_deep_agent(model="anthropic:claude-sonnet-5", middleware=[TodoListMiddleware()])
```
— [overview](https://docs.langchain.com/oss/python/deepagents/overview)
- Restricting filesystem tools (read-only peer):
```python
from deepagents.middleware import FilesystemMiddleware
agent = create_deep_agent(
    model="claude-sonnet-4-6",
    middleware=[FilesystemMiddleware(backend=backend, tools=["read_file", "ls", "glob", "grep"])],
)
```
— [overview](https://docs.langchain.com/oss/python/deepagents/overview)
- Custom middleware hooks:
  - Node-style hooks are `before_agent`, `before_model`, `after_model`, `after_agent`. Each takes `(state, runtime)` and returns a state-update dict or `None`.
  - Wrap-style hooks are `wrap_model_call` and `wrap_tool_call`. They take `(request, handler)` and can call the handler zero, one or many times (short-circuit or retry).
  - Change the system prompt with `request.override(system_message=...)`. For per-turn message injection, "use a node-style `before_model` hook that returns a `messages` update".
  - `@dynamic_prompt` is a convenience decorator. Class-based middleware subclasses `AgentMiddleware`, supports async variants (`abefore_model`) and attributes `state_schema` and `tools`.
  - `jump_to` takes `'end' | 'tools' | 'model'` together with `can_jump_to`.
  - Ordering: `before_*` hooks run first to last, `wrap_*` hooks nest with the first middleware outermost, and `after_*` hooks run in reverse.

  — [LangChain custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- The excerpt from the docs for modifying the system message: `return handler(request.override(system_message=new_system_message))` — [custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- `@dynamic_prompt` middleware "can read `request.runtime.context` and `request.runtime.store`". Runtime context is not added to the prompt automatically, and it "propagates to all subagents" — [context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering.md)
- `RubricMiddleware(*, model, system_prompt=None, tools=None, grader_middleware=None, ..., max_iterations=3, on_evaluation=None)`. Each time the agent would finish, it runs a separate grader sub-agent over the transcript. On `needs_revision` it injects the feedback as a `HumanMessage` and resumes. Verdicts are `satisfied | needs_revision | failed`, plus `max_iterations_reached | grader_error`. It is active only when the caller passes a `rubric` in the invocation state. The transcript sent to the grader is capped at 30 messages, with 4,000 characters per message. It is marked `@beta` — [source `middleware/rubric.py`](https://pypi.org/project/deepagents/0.7.32/)
- Human-in-the-loop: `interrupt_on={"edit_file": True}`. The permission mode `"interrupt"` installs `HumanInTheLoopMiddleware` automatically — [overview](https://docs.langchain.com/oss/python/deepagents/overview); [source](https://pypi.org/project/deepagents/0.7.32/)

### Inferences
- Team-context injector pattern:
  - Write a class `TeamContextMiddleware(AgentMiddleware)` whose `awrap_model_call` reads the shared store (`request.runtime.store`, or the store held in a closure) for the board snapshot, unread peer messages and the agent's own claims.
  - Render them into an extra text block appended to `request.system_message`.
  - Call `handler(request.override(system_message=...))`.

  This leaves the message history untouched (good for caching and summarisation). The block is rebuilt every model call, so peers see a live view. Alternatively, `before_model` can append a `HumanMessage` "inbox" update, which persists in history.
- Because user middleware runs before the tail stack, `AnthropicPromptCachingMiddleware` still applies after your injection. Put dynamic team context at the end of the system prompt so the static prefix stays cacheable.
- Verification/merge: use `RubricMiddleware` per peer as a self-check before an agent marks a task done. Add a separate "reviewer" peer that claims `review` tasks from the board, which gives verification without a supervisor.

### Gaps
- I did not read the verbatim `SummarizationMiddleware` constructor args. The docs only show `create_summarization_tool_middleware(model, backend)`.

## 4. Async/background subagents, remote agents, Agent Server, A2A, MCP, Store memory

### Takeaway
`AsyncSubAgent` lets an agent launch, monitor, update and cancel other deployed graphs (in-process ASGI or remote HTTP via the Agent Protocol), with completion notifications. It is the closest built-in thing to peer messaging, but it is still parent→child. Agent Server exposes every assistant at `/a2a/{assistant_id}` (A2A JSON-RPC v1.0), which can serve as a peer-to-peer transport. MCP tools plug in as ordinary tools.

### Cited Findings
- Docs example:
```python
from deepagents import AsyncSubAgent, create_deep_agent
async_subagents = [
    AsyncSubAgent(name="researcher", description="Research agent for information gathering and synthesis",
                  graph_id="researcher"),  # No url → ASGI transport (co-deployed)
    AsyncSubAgent(name="coder", description="Coding agent for code generation and review",
                  graph_id="coder"),  # url="https://coder-deployment.langsmith.dev" → HTTP
]
agent = create_deep_agent(model="google_genai:gemini-3.6-flash", subagents=async_subagents)
```
with `langgraph.json` `{"graphs": {"supervisor": "./src/supervisor.py:graph", "researcher": "./src/researcher.py:graph", "coder": "./src/coder.py:graph"}}` — [async subagents](https://docs.langchain.com/oss/python/deepagents/async-subagents.md)
- Tools: `start_async_task`, `check_async_task`, `update_async_task`, `cancel_async_task`, `list_async_tasks` — [async subagents](https://docs.langchain.com/oss/python/deepagents/async-subagents.md)
- Notifications arrive as a `HumanMessage` carrying `additional_kwargs["deepagents_notification"]` with `agent_name` and `status` (`success | error | timeout | waiting`). This requires `deepagents>=0.7.26` (beta) — [async subagents](https://docs.langchain.com/oss/python/deepagents/async-subagents.md)
- The 0.7.32 source has more `AsyncSubAgent` fields than the docs page shows:
  - `webhook`
  - `update_strategy: "interrupt" | "enqueue"` (default `interrupt`, beta)
  - `notify_parent: bool` (default True, beta)
  - `mode: "isolated" | "fork"`

  Each task's thread is created with `metadata={"subagent_name": ..., "parent_thread_id": ...}`, so you can find it via `threads.search`. When `url` is omitted, ASGI transport works only from `ainvoke`; the sync `invoke` path needs a `url`. The docs fetch said "no `notify_parent` / `update_strategy` parameter exists on the page", so this is a **docs-vs-source discrepancy**. The source is authoritative for 0.7.32 — [source `middleware/async_subagents.py`](https://pypi.org/project/deepagents/0.7.32/); [async subagents](https://docs.langchain.com/oss/python/deepagents/async-subagents.md)
- Limitations of async subagents:
  - A `waiting` task cannot be answered by the supervisor.
  - Fork mode is experimental and sends a snapshot only.
  - Locally, each active run takes a worker slot (`langgraph dev --n-jobs-per-worker 10`).

  — [async subagents](https://docs.langchain.com/oss/python/deepagents/async-subagents.md)
- A2A: Agent Server serves `/a2a/{assistant_id}` with an agent card at `/.well-known/agent-card.json?assistant_id=...`. It requires `langgraph-api>=0.4.21` (`returnImmediately`/`blocking` need 0.18.0). The graph state must have `messages`. The A2A `contextId` maps to the LangGraph `thread_id` and must be a UUID. Only JSON-RPC is supported. `SubscribeToTask` and push notifications return `-32601`. `historyLength` is capped at 10. Disable with `"http": {"disable_a2a": true}` — [Agent Server A2A](https://docs.langchain.com/langsmith/server-a2a.md)
- A2A client sketch from the docs:
```python
payload = {"jsonrpc": "2.0", "id": "1", "method": "SendMessage", "params": {"message": message}}
result = requests.post(URL, json=payload, headers={"Accept": "application/json"}).json()
```
— [Agent Server A2A](https://docs.langchain.com/langsmith/server-a2a.md)
- `CompiledSubAgent(name=..., description=..., runnable=custom_graph)` accepts any graph with a `messages` key — [subagents](https://docs.langchain.com/oss/python/deepagents/subagents.md)
- MCP: `tools=` accepts MCP tools. `langchain-mcp-adapters` is at 0.3.2 (Aug 2026), and `deepagents-code` 0.1.71 "Moved MCP support onto FastMCP and `langchain.mcp`" — [overview](https://docs.langchain.com/oss/python/deepagents/overview); [PyPI](https://pypi.org/project/langchain-mcp-adapters/); [GitHub releases](https://github.com/langchain-ai/deepagents/releases)
- Long-term memory:
  - `memory=["/project/AGENTS.md", ...]` files are always loaded into the system prompt.
  - For cross-thread persistence, route `/memories/` through `CompositeBackend` to a `StoreBackend`.
  - Skills (`skills=["/skills/"]`) load on demand.

  — [context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering.md)

### Inferences
- **Peer messaging options**, from simplest to heaviest:
  - (a) A mailbox in the shared store (`/team/inbox/<agent>/...`) plus a `send_message(to, body)` custom tool, read by the team-context middleware every turn.
  - (b) Each peer deployed as a graph on one Agent Server, with every peer listing the others as `AsyncSubAgent`s. This gives any-to-any `start_async_task` / `update_async_task` with notifications, but `update_strategy="interrupt"` restarts the peer's run.
  - (c) A2A `SendMessage` between assistants, which is cross-framework but limited (no push, no subscribe).

  Option (a) is the most controllable for a self-organising team. Options (b) and (c) suit distributed deployment.
- Using async subagents in an all-to-all mesh is not a documented pattern. They were designed as supervisor→worker.

### Gaps
- No official doc covers a peer mesh made of `AsyncSubAgent`s, or cycles where A launches B and B launches A.

## 5. Running N deep agents concurrently, each with its own model

### Takeaway
Build N graphs with `create_deep_agent(model=...)`, each with its own model, a shared `store`, and a shared or per-agent `checkpointer`. Run them with `asyncio.gather(agent_i.ainvoke(..., config={"configurable": {"thread_id": ...}}))`, or deploy them as separate graphs on one Agent Server. Inside a single agent, per-subagent `model` overrides are supported, and parallel `task` calls run concurrently.

### Cited Findings
- `model` accepts a `provider:model` string or a `BaseChatModel` instance — [source](https://pypi.org/project/deepagents/0.7.32/)
- Per-subagent model:
```python
subagents = [
    {"name": "contract-reviewer", "description": "Reviews legal documents and contracts",
     "system_prompt": "You are an expert legal reviewer...", "tools": [read_document, analyze_contract],
     "model": "google_genai:gemini-3.6-flash"},
    {"name": "financial-analyst", "description": "Analyzes financial data and market trends",
     "system_prompt": "You are an expert financial analyst...", "tools": [get_stock_price, analyze_fundamentals],
     "model": "openai:gpt-5.5"},
]
```
— [subagents](https://docs.langchain.com/oss/python/deepagents/subagents.md)
- The main agent "can issue several [task calls] in a single turn to run them in parallel" — [subagents](https://docs.langchain.com/oss/python/deepagents/subagents.md)
- Provider profiles set default init kwargs per provider or model string, e.g. `register_provider_profile("openai", ProviderProfile(init_kwargs={"temperature": 0}))`. They apply only to `provider:model` strings, not to pre-built instances — [models](https://docs.langchain.com/oss/python/deepagents/models)
- Runtime `context_schema` + `context=Context(...)` on `invoke` give per-run immutable inputs that tools read via `ToolRuntime`. Custom `state_schema` must subclass `DeepAgentState` — [context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering.md)

### Inferences
Sketch (assembled from documented APIs, not an official example):
```python
store = PostgresStore.from_conn_string(...)  # or InMemoryStore()
shared = StoreBackend(store=store, namespace=lambda _rt: ("team", RUN_ID))
def make_peer(name, model):
    return create_deep_agent(
        model=model, name=name, tools=[claim_task, send_message, complete_task],
        backend=CompositeBackend(default=StateBackend(), routes={"/team/": shared}),
        middleware=[TeamContextMiddleware(store, name)],
        context_schema=PeerCtx, store=store, checkpointer=checkpointer)
peers = [make_peer("planner", "anthropic:claude-sonnet-5"),
         make_peer("coder", "fireworks:accounts/fireworks/models/glm-5p2"), ...]
await asyncio.gather(*(p.ainvoke({"messages": [...]}, config={"configurable": {"thread_id": f"{RUN_ID}-{p.name}"}}, context=PeerCtx(agent_id=p.name)) for p in peers))
```
- Agents need a loop (re-invoke until the board is empty), because a single `ainvoke` ends when the model stops calling tools. Notifications from async subagents (0.7.26+) can wake an idle agent on Agent Server.
- LangGraph `Send` fan-out inside a parent graph is another option, but it reintroduces a parent graph. It is a coordinator, though not an LLM supervisor.

### Gaps
- No official deepagents example of N concurrent top-level peers.

## 6. Non-Anthropic/OpenAI models (Fireworks and other open models)

### Takeaway
Fireworks and other open models are first-class through `init_chat_model("fireworks:...")` strings. The docs list `fireworks:accounts/fireworks/models/glm-5p2` and others. `FireworksPromptCachingMiddleware` is added automatically when `langchain-fireworks` is installed. The only documented requirement is tool calling. I found no documented open-model issues.

### Cited Findings
- Model strings shown in the overview: `fireworks:accounts/fireworks/models/glm-5p2`, `openrouter:z-ai/glm-5.2`, `baseten:zai-org/GLM-5.2`, `ollama:north-mini-code-1.0`, `google_genai:gemini-3.6-flash`, `openai:gpt-5.5`, `anthropic:claude-sonnet-5` — [overview](https://docs.langchain.com/oss/python/deepagents/overview)
- The models page eval table includes `fireworks:accounts/fireworks/models/glm-5p1`, `fireworks:accounts/fireworks/models/minimax-m2p7`, `openrouter:deepseek/deepseek-v4-flash` and others. Recommended open-weight models are `GLM-5.2`, `Kimi-K2.7 Code`, `MiniMax-M3`. The only requirement stated is tool-calling support, and passing the evals is "necessary but not sufficient". Several open-weight entries show "—" in the Memory column, unexplained. `openai:gpt-5.4` scores 18% on tool use. No known-issues section — [models](https://docs.langchain.com/oss/python/deepagents/models)
- `init_chat_model` with extra kwargs:
```python
from langchain.chat_models import init_chat_model
model = init_chat_model(model="google_genai:gemini-3.6-flash", thinking_level="medium")
agent = create_deep_agent(model=model)
```
— [models](https://docs.langchain.com/oss/python/deepagents/models)
- The tail stack auto-adds `FireworksPromptCachingMiddleware` "when `langchain-fireworks` is installed (no-ops for non-Fireworks models)". Prompt caching is otherwise automatic only for Anthropic and Bedrock — [source `graph.py`](https://pypi.org/project/deepagents/0.7.32/); [overview](https://docs.langchain.com/oss/python/deepagents/overview)
- `langchain-fireworks` latest is 1.7.1 (7 Oct 2026) — [PyPI](https://pypi.org/project/langchain-fireworks/)
- Summarisation triggers at 85% of the model profile's `max_input_tokens`. If the model has no profile (common for less-known open models), it falls back to a 170,000-token trigger and keeps 6 messages — [context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering.md)

### Inferences
- For Fireworks, either pass `"fireworks:accounts/fireworks/models/<id>"` or build `ChatFireworks(model=..., ...)` and pass the instance. Note that provider profiles do not apply to instances.
- Check that the model's context window is known. Otherwise the 170k fallback may exceed a smaller window, although `ContextOverflowError` triggers summarise-and-retry.
- Structured output via `response_format` on open models is untested in the docs. Prefer tool-based claims over structured-output parsing for the board protocol.

### Gaps
- I found no GitHub issues or docs describing Fireworks-specific tool-calling bugs in deepagents. The search returned nothing relevant.

## 7. Observability: LangSmith and the CLI

### Takeaway
Tracing is LangSmith-native. Agent Server deployments trace automatically. Async-subagent launches carry the parent's trace headers so child runs nest (beta). A2A `contextId` maps to `thread_id`, which groups traces.

### Cited Findings
- Cloud deployments send traces automatically to a project named after the deployment. The docs recommend LangSmith Engine for monitoring — [going to production](https://docs.langchain.com/oss/python/deepagents/going-to-production)
- With tracing on, co-deployed async subagents receive the parent's LangSmith trace headers so the receiver can nest the run (beta, "may change") — [source `middleware/async_subagents.py`](https://pypi.org/project/deepagents/0.7.32/)
- Summarisation tokens are tagged `metadata["lc_source"] == "summarization"` in `stream_mode="messages"` — [context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering.md)
- A2A `contextId` → LangGraph `thread_id` groups traces in LangSmith — [Agent Server A2A](https://docs.langchain.com/langsmith/server-a2a.md)
- `deepagents` depends on `langsmith>=0.14.12`. The CLI packages are `deepagents-cli 0.3.0` and `deepagents-code 0.2.1` — [PyPI](https://pypi.org/project/deepagents/); [PyPI deepagents-code](https://pypi.org/project/deepagents-code/)

### Inferences
- For N independent peers run via `asyncio`, pass `config={"run_name": peer, "tags": [RUN_ID, peer], "metadata": {"team_run": RUN_ID}}` so all peer traces can be filtered together in LangSmith. These are standard LangChain `RunnableConfig` fields; this is not deepagents-specific guidance.

### Gaps
- I found no doc on multi-agent trace views or team-level dashboards.

## 8. Official multi-agent and swarm patterns, compared with a supervisor

### Takeaway
LangChain's documented multi-agent patterns are **Subagents** (a central agent calls the others as tools), **Handoffs** (agents transfer control to each other via tool calls), **Skills** and **Router**. Deep Agents itself implements the subagent/supervisor pattern. `langgraph-swarm` (handoffs) has not been released since 0.1.0 (Dec 2025). Neither pattern provides concurrent peers with a shared task board. That part has to be built.

### Cited Findings
- Multi-agent patterns from the docs:
  - Subagents: "A main agent coordinates subagents as tools".
  - Handoffs: "Agents transfer control to each other via tool calls".
  - Skills: one agent loads context on demand.
  - Router: classifies the input and dispatches.

  The page recommends Deep Agents for built-in multi-agent support and LangGraph for custom workflows — [LangChain multi-agent](https://docs.langchain.com/oss/python/langchain/multi-agent)
- `langgraph-swarm` latest is 0.1.0, released 2025-12-04 — [PyPI](https://pypi.org/project/langgraph-swarm/)
- Third-party coverage of swarm/handoff vs supervisor orchestration — [traeai orchestration patterns](https://learn.traeai.com/t/ai-engineering/phases/14-agent-engineering/28-orchestration-patterns.html); [lilys.ai notes on langgraph-swarm](https://lilys.ai/notes/ru/langgraph-swarm-20260202/build-agent-swarm-langgraph) (secondary sources)
- Deep Agents subagents are isolated by default. A fork (`mode: "fork"`, 0.7.13+, beta) inherits the parent history but cannot call `task` or define `skills` — [subagents](https://docs.langchain.com/oss/python/deepagents/subagents.md)

### Inferences
- Handoffs and swarm are **sequential**: one active agent at a time passes control. Supervisor/subagents is **hierarchical**. A self-organising peer team (all agents active, pulling from a shared board) matches neither. It is closer to a blackboard architecture: N concurrent `create_deep_agent` graphs, a shared `StoreBackend` workspace, custom atomic-claim and messaging tools, team-context middleware, and `RubricMiddleware` or reviewer peers for verification.
- For merge: when peers edit shared files, last-writer-wins will clobber work. Have each peer write to `/team/work/<task_id>/...` (or a git branch in a sandbox), and have a merge task claimed by a peer combine the outputs, with verification (tests via `execute`) before it is marked `done`.

### Gaps
- I found no official LangChain example (2025–2026) of a supervisor-less peer team or blackboard pattern on deepagents. Whether the swarm/handoff docs moved or were deprecated in 2026 is unconfirmed.
