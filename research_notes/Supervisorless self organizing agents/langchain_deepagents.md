# LangChain Deep Agents (Python) as a substrate for peer-to-peer, supervisor-free multi-agent systems

Research date: 2026-10-26. Primary evidence: the `deepagents==0.7.32` wheel source from PyPI (released 2026-10-23, read directly), the official docs at docs.langchain.com, the 0.7.0 release notes, and PyPI metadata. Source-code citations point to the PyPI project page, since the code was read from the published wheel for that version. Anything marked **[INFERRED]** is my own design reasoning and is not documented behavior.

## 1. What deepagents is, and what `create_deep_agent` accepts

### Takeaway
`deepagents` is an "agent harness": `create_deep_agent(...)` puts a fixed middleware stack (filesystem tools, `task` subagents, summarization, prompt caching, HITL, etc.) around LangChain v1 `create_agent` and returns a LangGraph `CompiledStateGraph`. That means everything LangGraph offers (checkpointers, stores, streaming, subgraph composition) is available. As of v0.7, planning (`write_todos`) is opt-in rather than on by default.

### Cited Findings
**Package and versions**
- Latest version is `deepagents 0.7.32` (uploaded 2026-10-23). It requires Python `>=3.11,<4.0` and depends on `langchain>=1.4.7,<2`, `langchain-core>=1.7.0,<2`, `langchain-anthropic>=1.7.6,<2`, `langchain-google-genai>=4.4.2,<5` and `langsmith>=0.14.12`. Extras: `aws` (langchain-aws), `quickjs` (langchain-quickjs), `video` (av, pillow) — [PyPI deepagents](https://pypi.org/project/deepagents/)
- Release cadence is very fast. 0.2.0 shipped 2025-10-28, 0.3.0 2025-12-08, 0.4.0 2026-02-10, 0.5.0 2026-04-07, 0.6.0 2026-05-12 and 0.7.0 2026-07-29, followed by 0.7.1 through 0.7.32 between Aug and Oct 2026 (about 2–3 patch releases per week) — [PyPI release history](https://pypi.org/project/deepagents/#history)
- Related package versions as of Oct 2026: `langgraph 1.2.17` (2026-10-24), `langchain 1.4.7` (2026-10-21), `langgraph-checkpoint 4.3.0`, `langgraph-checkpoint-postgres 3.2.0`, `langchain-fireworks 1.7.1` (2026-10-07), `langchain-anthropic 1.7.6`, `langgraph-swarm 0.1.0` (2025-12-04, no newer release) and `langgraph-supervisor 0.0.31` (2025-11-19) — [PyPI](https://pypi.org/project/langgraph/), [PyPI langgraph-swarm](https://pypi.org/project/langgraph-swarm/)
- The docs describe it as "an agent harness for building LLM-powered agents that handle complex, multi-step tasks," built on LangChain and using the LangGraph runtime — [Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview)
- Public top-level exports in `deepagents/__init__.py` (0.7.32): `create_deep_agent`, `DeepAgentState`, `SubAgent`, `CompiledSubAgent`, `SubAgentMiddleware`, `AsyncSubAgent`, `AsyncSubAgentMiddleware`, `FilesystemMiddleware`, `FilesystemPermission`, `FsToolName`, `MemoryMiddleware`, `RubricMiddleware`, `HarnessProfile`, `HarnessProfileConfig`, `GeneralPurposeSubagentProfile`, `register_harness_profile`, `ProviderProfile`, `register_provider_profile`, `__version__`. `deepagents.backends` exports `StateBackend`, `StoreBackend`, `NamespaceFactory`, `FilesystemBackend`, `LocalShellBackend`, `CompositeBackend`, `ContextHubBackend`, `LangSmithSandbox`, `BackendProtocol` and `DEFAULT_EXECUTE_TIMEOUT`. `deepagents.middleware` additionally exports `SkillsMiddleware`, `SummarizationMiddleware`, `SummarizationToolMiddleware`, `create_summarization_tool_middleware`, `UnsupportedContentMiddleware`, `TaskEvent` and the Rubric types — [deepagents 0.7.32 source (PyPI wheel)](https://pypi.org/project/deepagents/0.7.32/)

**Exact signature (0.7.32, `deepagents/graph.py`)** — [source](https://pypi.org/project/deepagents/0.7.32/)
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
- **The parameter is `system_prompt`, not `instructions`.** The older `instructions` name doesn't exist in 0.7.x. The final prompt is built as `USER -> BASE -> SUFFIX`, where BASE and SUFFIX come from the active HarnessProfile and are empty by default. If you pass `system_prompt=None` and no profile is active, the model receives an empty authored system prompt. Passing a `SystemMessage` keeps its `cache_control` blocks — [source docstring](https://pypi.org/project/deepagents/0.7.32/)
- `model=None` (falling back to `claude-sonnet-4-6`) has been deprecated since 0.5.3 and will be removed in 1.0.0. String models resolve through `init_chat_model(model, **apply_provider_profile(model))`, and `BaseChatModel` instances are passed through unchanged. For `openai:` strings the Responses API is the default — [source `_models.py`/graph.py](https://pypi.org/project/deepagents/0.7.32/)
- `tools` is additive and never removes a built-in tool. To hide a built-in, use a `HarnessProfile(excluded_tools=...)`. To remove one entirely, pass your own `FilesystemMiddleware(tools=[...])` — [source docstring](https://pypi.org/project/deepagents/0.7.32/)
- `checkpointer`, `store`, `context_schema`, `debug`, `name`, `cache` and `response_format` are passed straight through to `langchain.agents.create_agent`. `store` is required if the backend uses `StoreBackend` (unless the platform provides one) — [source](https://pypi.org/project/deepagents/0.7.32/)
- `state_schema` must be a TypedDict subclass of `DeepAgentState`, so the `DeltaChannel` reducer on `messages` is preserved. It is forwarded to declarative subagents, which can write the fields back to the parent. "If parallel `task` calls may change the same field, give it a reducer; otherwise the step fails with `InvalidUpdateError`" — [source docstring](https://pypi.org/project/deepagents/0.7.32/)
- The return value is `create_agent(...).with_config({"recursion_limit": 9_999, "metadata": {"ls_integration": "deepagents", "lc_versions": {...}, "lc_agent_name": name}})` — [source](https://pypi.org/project/deepagents/0.7.32/)

**Middleware stack order (main agent), from the source docstring and code**
1. `FilesystemMiddleware(backend, permissions)`
2. `SubAgentMiddleware` (when any synchronous subagents exist, including the auto-added `general-purpose` one)
3. `_ParentNotifierMiddleware` (private), then `SummarizationMiddleware` (the deepagents variant via `create_summarization_middleware(model, backend)`), then `PatchToolCallsMiddleware`
4. `AsyncSubAgentMiddleware` (when there are async subagents)
5. **User `middleware=` is inserted here**
6. Tail: harness-profile `extra_middleware`, `SkillsMiddleware` (when `skills`), `AnthropicPromptCachingMiddleware` (unconditional; it no-ops for non-Anthropic models), `BedrockPromptCachingMiddleware` (when langchain-aws is installed), `FireworksPromptCachingMiddleware` (when langchain-fireworks is installed), `MemoryMiddleware` (when `memory`), `HumanInTheLoopMiddleware` (when `interrupt_on` or there are interrupt-mode permissions), `UnsupportedContentMiddleware`, and `_ToolExclusionMiddleware` (when the profile excludes tools)
- User middleware whose `.name` matches a default middleware replaces it in place (added in 0.7.0, #4251) — [source](https://pypi.org/project/deepagents/0.7.32/), [0.7.0 release notes](https://newreleases.io/project/github/langchain-ai/deepagents/release/deepagents==0.7.0)

**Subagent specs (`deepagents/middleware/subagents.py`)**
- `SubAgent(TypedDict)` fields are `name`, `description`, `system_prompt?`, `tools?`, `model?` (str | BaseChatModel), `middleware?`, `interrupt_on?`, `skills?`, `permissions?`, `response_format?` and `mode?: Literal["isolated", "fork"]`. Fork mode is experimental/beta: it continues the parent's conversation and cannot define its own skills — [source](https://pypi.org/project/deepagents/0.7.32/)
- `CompiledSubAgent` takes a pre-built `runnable` (any LangGraph graph). It does not inherit top-level `interrupt_on` or `state_schema` — [source docstring](https://pypi.org/project/deepagents/0.7.32/)
- A `general-purpose` subagent is added automatically unless you supply one with that name or disable it with `HarnessProfile(general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False))`. When there are no synchronous subagents, the `task` tool is not exposed at all — [source](https://pypi.org/project/deepagents/0.7.32/)
- Subagents inherit the parent's `tools` unless they declare `tools`. They also share the **same backend instance** as the parent — [source graph.py](https://pypi.org/project/deepagents/0.7.32/)
- State keys excluded when passing state to and from subagents: `messages` (only the final message comes back), `todos`, `structured_response`, `skills_metadata`, `pinned_skills`, plus private keys. The subagent prompt says: "The calling agent only sees your final assistant message" — [source](https://pypi.org/project/deepagents/0.7.32/)

**CLI status**
- `deepagents-cli` 0.3.0 (2026-08-24) is marked "DEPRECATED … final release". It has been superseded by `managed-deepagents` (`uv tool install managed-deepagents`; `mda init my-agent`, `mda deploy`) — [PyPI deepagents-cli](https://pypi.org/project/deepagents-cli/)
- The overview page links "Deep Agents Code" as a separate product and also lists ACP (Agent Client Protocol) support for code editors — [overview](https://docs.langchain.com/oss/python/deepagents/overview)

### Inferences
- Because the return type is a plain `CompiledStateGraph`, a deep agent can be a node in a parent `StateGraph`, a `CompiledSubAgent` runnable, a `langgraph-swarm` member, or a graph registered in `langgraph.json` for async/remote invocation. **[INFERRED from return type]**
- Pin an exact `deepagents` version. The project ships breaking changes inside 0.x minors (0.5 and 0.7 both did), and it releases several times a week.

### Gaps
- I could not fetch the quickstart, customization and CLI pages verbatim. The overview's quickstart snippet was summarized by the fetch tool as `create_deep_agent(model="anthropic:claude-sonnet-5", tools=[get_weather], system_prompt=...)`. Check the exact model strings on the live page.

## 2. Built-in capabilities and backends; can a shared backend/Store act as a blackboard?

### Takeaway
Built-in tools in 0.7.x are `ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob` and `grep`, plus `execute` (sandbox backends only), `task` (sync subagents), and the async-task tools. `write_todos` is opt-in. A `StoreBackend` pointed at a shared `BaseStore` with a fixed namespace is a workable shared blackboard across independent agents and threads. **It has no locking or compare-and-swap**: `write` overwrites and `edit` is an unguarded read-modify-write, so atomic task claiming has to be built separately.

### Cited Findings
**Tools and planning**
- Tool names: `FsToolName = Literal["ls", "read_file", "write_file", "edit_file", "delete", "glob", "grep", "execute"]`. `FilesystemMiddleware.__init__(*, backend=None, system_prompt=None, custom_tool_descriptions=None, tool_token_limit_before_evict=20000, human_message_token_limit_before_evict=50000, max_execute_timeout=3600, grep_max_count=1000, tools=None | list[FsToolName] | "all", offload_binary_content=False, permissions=None)` — [source](https://pypi.org/project/deepagents/0.7.32/)
- Breaking change in v0.7.0 (#4929): "`create_deep_agent` no longer includes `TodoListMiddleware` by default." To restore it, pass `middleware=[TodoListMiddleware()]` (from `langchain.agents.middleware`), and add it to each SubAgent too. The OpenAI Codex harness profile still opts in automatically — [0.7.0 release notes](https://newreleases.io/project/github/langchain-ai/deepagents/release/deepagents==0.7.0), [overview](https://docs.langchain.com/oss/python/deepagents/overview)
- Other 0.7.0 changes: the base prompt is now empty (`BASE_AGENT_PROMPT` is deprecated and will be removed in 0.9.0); `FilesystemBackend` and `LocalShellBackend` default to `virtual_mode=True`; a new recursive `delete` tool; `write_file` now creates or **replaces entirely** with no create-only mode (#4109); `StoreBackend` requires an explicit `namespace`; the legacy `ls_info`/`glob_info`/`grep_raw` methods and `files_update` were removed; and empty `ls`/`glob` output now reads "No files found" — [0.7.0 release notes](https://newreleases.io/project/github/langchain-ai/deepagents/release/deepagents==0.7.0)
- Secondary sources say v0.7 cut base input tokens by about 65% (roughly 6k down to 2k). This is unconfirmed in the official notes — [explainx](https://explainx.ai/blog/langchain-deep-agents-0-7-leaner-harness-july-2026)
- Other capabilities: Skills (`SKILL.md`, progressive loading), Memory (`AGENTS.md` loaded into the system prompt), summarization and offloading of large tool results (`/large_tool_results/`, `/conversation_history/`), a QuickJS `eval` interpreter, and automatic prompt caching for Anthropic and Bedrock — [overview](https://docs.langchain.com/oss/python/deepagents/overview), [backends](https://docs.langchain.com/oss/python/deepagents/backends)
- The deepagents summarization factory picks fraction-based trigger/keep thresholds from the model profile's `max_input_tokens` (LangChain's own default is `trigger=None, keep=("messages", 20)`). It offloads evicted history to the backend and clips older `write_file`/`edit_file` arguments — [source summarization.py](https://pypi.org/project/deepagents/0.7.32/)

**Backends**
- `StateBackend()` takes no arguments. Files live in graph state for one thread; they are "not shared across threads" but are shared between the main agent and its subagents — [backends docs](https://docs.langchain.com/oss/python/deepagents/backends)
- `StoreBackend(*, namespace: NamespaceFactory, store: BaseStore | None = None)`, where `NamespaceFactory = Callable[[Runtime], tuple[str, ...]]`. If `store` is None, it calls `get_store()` from the graph context; if you pass a store explicitly, that one is used. Each namespace component must match `^[A-Za-z0-9\-_.@+:~]+$` (no wildcards). Example factories: per-user `lambda rt: (rt.server_info.user.identity,)`, per-assistant `rt.server_info.assistant_id`, per-thread `rt.execution_info.thread_id` — [source store.py](https://pypi.org/project/deepagents/0.7.32/), [backends docs](https://docs.langchain.com/oss/python/deepagents/backends)
- `StoreBackend.write()` does `store.get` and then `store.put`, overwriting any existing file. `edit()` does `store.get`, string replacement, then `store.put`. Neither has a version check or lock. Async variants (`awrite`, `aedit`) use `aget`/`aput` — [source store.py](https://pypi.org/project/deepagents/0.7.32/)
- LangGraph `BaseStore` API (langgraph-checkpoint 4.3.0): `get(namespace, key, *, refresh_ttl=None)`, `search(namespace_prefix, /, *, query=None, filter=..., limit=..., offset=...)`, `put(namespace, key, value: Mapping, index=None, *, ttl=NOT_PROVIDED)`, `delete`, `list_namespaces`, `batch`, plus the `a*` async versions. `get` raises `InvalidNamespaceError` if a namespace label "contains a period (`.`)" — [langgraph-checkpoint source (PyPI)](https://pypi.org/project/langgraph-checkpoint/)
- `FilesystemBackend(root_dir=None, virtual_mode=True, max_file_size_mb=10)` and `LocalShellBackend(root_dir=None, *, virtual_mode=True, timeout=DEFAULT_EXECUTE_TIMEOUT, max_output_bytes=100_000, env=None, inherit_env=False)`. LocalShell runs `subprocess.run(shell=True)` with no sandboxing — [source](https://pypi.org/project/deepagents/0.7.32/), [backends docs](https://docs.langchain.com/oss/python/deepagents/backends). **Conflict:** the backends docs page still says "The default (`virtual_mode=False`) provides no security", while the 0.7.32 source and the 0.7.0 release notes both say the default is `True`.
- `CompositeBackend(default, routes: dict[str, BackendProtocol], *, artifacts_root="/")` routes by longest matching path prefix and keeps prefixes in `ls`/`glob`/`grep` results. Internal offload data goes to the default backend — [source](https://pypi.org/project/deepagents/0.7.32/), [backends docs](https://docs.langchain.com/oss/python/deepagents/backends)
- `ContextHubBackend("owner/name")` stores files in a LangSmith Context Hub repo. Writes use optimistic `parent_commit` checks, so "a stale write can fail" and you must re-pull and retry. **This is the only backend with documented concurrency semantics** — [backends docs](https://docs.langchain.com/oss/python/deepagents/backends)
- Sandboxes (`SandboxBackendProtocol` adds `id` and `execute`): `LangSmithSandbox(sandbox)` ships built in; AgentCore and Daytona are integrations — [source](https://pypi.org/project/deepagents/0.7.32/), [backends docs](https://docs.langchain.com/oss/python/deepagents/backends)
- Custom backends subclass `BackendProtocol` and implement `ls`, `read`, `write`, `edit`, `glob` and `grep` (`delete`, `upload_files` and `download_files` are optional). They should return results with an `error` field instead of raising. Backend factories (`lambda rt: StateBackend(rt)`) have been deprecated since 0.5.0 — [backends docs](https://docs.langchain.com/oss/python/deepagents/backends)
- `FilesystemPermission(operations=["read"|"write"], paths=[globs], mode="allow"|"deny"|"interrupt")` is evaluated first-match-wins at the tool level, not the backend level, so direct backend calls bypass it — [source docstring](https://pypi.org/project/deepagents/0.7.32/)

### Inferences
- **Blackboard pattern [INFERRED]:** give every peer `backend=CompositeBackend(default=StateBackend(), routes={"/board/": StoreBackend(store=shared_store, namespace=lambda _rt: ("swarm", "board"))})` and pass `store=shared_store`. All peers then see the same `/board/*` files through `ls/read_file/grep`, while scratch files and offloaded tool results stay private per thread. With `PostgresStore` the board persists and works across processes.
- **Race hazard [INFERRED from source]:** two peers editing the same board file can lose updates (last `put` wins), because `edit` is a read-modify-write with no lock. Mitigations: one file per item (`/board/tasks/<id>.md`); append-only per-agent files (`/board/log/<agent>-<ts>.md`); and a custom `claim_task` tool that does atomic claiming outside the backend (Postgres `INSERT … ON CONFLICT DO NOTHING`, `SELECT … FOR UPDATE SKIP LOCKED`, Redis `SETNX`). `ContextHubBackend`'s optimistic commits are the only built-in conflict detection.
- **Gotcha [INFERRED by comparing two sources]:** the deepagents namespace regex allows `.`, but LangGraph `BaseStore` rejects labels containing `.`. Avoid dots in namespace components such as model names or emails.
- Use `permissions=[FilesystemPermission(operations=["write"], paths=["/board/archive/**"], mode="deny")]` to make parts of the board read-only for some peers. Since 0.7, `write` permissions also cover the recursive `delete` tool.

### Gaps
- There's no official guidance on concurrent writers for State, Store or Filesystem backends; the docs table says "Not discussed".
- Whether `StoreBackend` `grep`/`glob` over a large shared namespace pages through `search` efficiently was not verified.

## 3. Building supervisor-free (peer) topologies on Deep Agents

### Takeaway
Deep Agents ships only hierarchical delegation (sync `task` subagents, and async subagents that a supervisor launches and polls). There is no first-class peer or swarm primitive. Peer topologies have to be assembled from: (a) several independent top-level `create_deep_agent` graphs run concurrently, each on its own `thread_id`, sharing a `BaseStore`/backend as a blackboard; (b) custom tools using `ToolRuntime.store` for messaging and claiming; (c) middleware hooks that inject board state each turn; and (d) LangGraph composition or `langgraph-swarm` handoffs when a single-active-agent topology is enough.

### Cited Findings
- Sync subagents block until they finish and return a single report. Async subagents "run in parallel with launch, check, update, and cancel tools" — [overview](https://docs.langchain.com/oss/python/deepagents/overview)
- Async subagents: `AsyncSubAgent(name, description, graph_id, url?, headers?, mode?)` runs on an Agent Protocol server (LangSmith Deployment or self-hosted). If `url` is omitted, in-process ASGI transport is used, which requires an async entrypoint (`ainvoke`). The supervisor gets the tools `start_async_task`, `check_async_task`, `update_async_task`, `cancel_async_task` and `list_async_tasks`. Task metadata lives in an `async_tasks` state channel that survives summarization. Each run takes a worker slot (`langgraph dev --n-jobs-per-worker 10`). Completion and waiting notifications are beta and need `>=0.7.26`. Each task thread carries `metadata={"subagent_name", "parent_thread_id"}` — [async subagents docs](https://docs.langchain.com/oss/python/deepagents/async-subagents), [source](https://pypi.org/project/deepagents/0.7.32/)
- Async limitations: a waiting subagent must be answered on its own thread, since "the supervisor cannot answer on the user's behalf." The supervisor may poll right after launch or truncate task IDs. A subagent that needs information must ask in its result — [async subagents docs](https://docs.langchain.com/oss/python/deepagents/async-subagents)
- LangChain v1 middleware hooks: node-style `before_agent`, `before_model`, `after_model`, `after_agent` (these return state-update dicts and can `jump_to` `"end"|"tools"|"model"` when declared via `can_jump_to`); wrap-style `wrap_model_call(request, handler)` and `wrap_tool_call(request: ToolCallRequest, handler)`. Decorators `@before_model`, `@wrap_model_call` etc. come from `langchain.agents.middleware`; the class form subclasses `AgentMiddleware` with an optional `state_schema` and async `abefore_model` etc. `request.override(model=..., tools=..., system_message=...)`; `ExtendedModelResponse(model_response=..., command=Command(update=...))` updates state from a wrap hook — [custom middleware docs](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- Tools reach shared resources through `runtime: ToolRuntime` (`from langchain.tools import tool, ToolRuntime`), which exposes `runtime.state`, `.context`, `.store`, `.stream_writer`, `.tool_call_id`, `.config`, execution info and server info. Tools can return `Command(update=..., ToolMessage(tool_call_id=runtime.tool_call_id))`, and parallel tool calls updating the same field need reducers — [tools docs](https://docs.langchain.com/oss/python/langchain/tools)
- `langgraph-swarm`: `create_swarm([agents], default_active_agent="Alice")` returns a StateGraph that you `.compile(checkpointer=...)`. `create_handoff_tool(agent_name=..., description=...)`; `add_active_agent_router(builder, route_to=[...], default_active_agent=...)`; `SwarmState`. The README example uses `langchain.agents.create_agent`. You need a checkpointer, or the swarm loses track of the active agent. The latest PyPI release is still 0.1.0 (2025-12-04) — [langgraph-swarm-py](https://github.com/langchain-ai/langgraph-swarm-py), [PyPI](https://pypi.org/project/langgraph-swarm/)
- `CompiledSubAgent` accepts any pre-built runnable, so another deep agent or a swarm graph can be exposed as a `task` target — [source docstring](https://pypi.org/project/deepagents/0.7.32/)

### Inferences — reference design sketch [INFERRED; not from docs; APIs as cited above]
```python
import asyncio, uuid
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langchain.agents.middleware import AgentMiddleware, ModelRequest
from langchain.tools import tool, ToolRuntime
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore   # use PostgresStore for multi-process

shared_store = InMemoryStore()
BOARD_NS = ("swarm", "board")

@tool
def post_message(to: str, body: str, runtime: ToolRuntime) -> str:
    """Post a message to a peer's inbox (or 'all')."""
    msg_id = str(uuid.uuid4())
    runtime.store.put(("swarm", "inbox", to), msg_id,
                      {"from": runtime.context["agent_id"], "body": body})
    return f"posted {msg_id}"

@tool
def claim_task(task_id: str, runtime: ToolRuntime) -> str:
    """Claim an open task. NOT atomic on InMemoryStore/BaseStore -- replace with DB-level CAS."""
    item = runtime.store.get(("swarm", "tasks"), task_id)
    if item is None or item.value.get("owner"):
        return "already claimed"
    runtime.store.put(("swarm", "tasks"), task_id, {**item.value, "owner": runtime.context["agent_id"]})
    return "claimed"

class BoardInjector(AgentMiddleware):
    """Inject open tasks + inbox into the system prompt before every model call."""
    def wrap_model_call(self, request: ModelRequest, handler):
        store, me = request.runtime.store, request.runtime.context["agent_id"]
        open_tasks = [i.value for i in store.search(("swarm", "tasks"), limit=20) if not i.value.get("owner")]
        inbox = [i.value for i in store.search(("swarm", "inbox", me), limit=10)]
        extra = f"\n\n## Shared board\nOpen tasks: {open_tasks}\nInbox: {inbox}"
        return handler(request.override(system_message=...))  # append `extra` to request.system_message

def make_peer(agent_id: str, model):
    return create_deep_agent(
        model=model,
        tools=[post_message, claim_task],
        system_prompt=f"You are peer {agent_id}. No one supervises you; coordinate via the board.",
        middleware=[BoardInjector()],
        backend=CompositeBackend(default=StateBackend(),
                                 routes={"/board/": StoreBackend(store=shared_store, namespace=lambda _rt: BOARD_NS)}),
        store=shared_store,
        checkpointer=InMemorySaver(),
        context_schema=dict,   # or a TypedDict with agent_id
        name=agent_id,
    )

async def run_peers(models: dict[str, object], goal: str):
    peers = {aid: make_peer(aid, m) for aid, m in models.items()}
    await asyncio.gather(*[
        p.ainvoke({"messages": [{"role": "user", "content": goal}]},
                  config={"configurable": {"thread_id": f"{aid}-{uuid.uuid4()}"}, "recursion_limit": 200},
                  context={"agent_id": aid})
        for aid, p in peers.items()])
```
- An "outer loop" ([INFERRED]) is usually needed: each peer runs a bounded episode, the runner re-invokes peers on the same `thread_id` while the board has open work, and termination is decided by a board-level condition (all tasks done, quorum, budget exhausted) rather than by a supervisor.
- Alternative composition ([INFERRED]): put N deep agents as parallel nodes in one LangGraph `StateGraph` (fan-out via `Send`, with a reducer on a shared `board` state key) to get a single checkpoint and trace. Or use `langgraph-swarm` for decentralized handoff with one active agent at a time. Swarm is peer-to-peer but not concurrent.
- The async-subagent machinery (Agent Protocol threads, `runs.cancel`, `threads.search` by metadata) can serve as a remote peer-messaging transport if every peer has the async tools pointing at every other peer's `graph_id` (a mesh rather than a tree). This is not documented as a pattern, and the "waiting" semantics assume a parent.

### Gaps
- I found no official LangChain documentation or blog post on peer, blackboard or supervisor-free topologies built from Deep Agents.
- Whether `langgraph-swarm` 0.1.0 works cleanly with `create_deep_agent` graphs (whose `messages` channel uses a custom `DeltaChannel` reducer) is unverified. A schema/reducer mismatch with `SwarmState` is plausible.
- The exact `ModelRequest.system_message` append helper wasn't verified. deepagents uses an internal `append_to_system_message` in `deepagents.middleware._utils`, which is private.

## 4. Non-OpenAI/Anthropic models (e.g., Fireworks)

### Takeaway
Any LangChain chat model that supports tool calling works. Pass a `provider:model` string (resolved via `init_chat_model`) or a configured instance such as `ChatFireworks(...)`. If `langchain-fireworks` is installed, deepagents automatically adds `FireworksPromptCachingMiddleware` (session affinity).

### Cited Findings
- "Deep Agents work with any LangChain chat model that supports tool calling." Strings use `provider:model`, and namespaced IDs keep their path, e.g. `baseten:zai-org/GLM-5.2`. The eval table lists `fireworks:accounts/fireworks/models/glm-5p1` and `fireworks:accounts/fireworks/models/minimax-m2p7`. Suggested open-weight models: GLM-5.2, Kimi-K2.7 Code, MiniMax-M3 — [models docs](https://docs.langchain.com/oss/python/deepagents/models)
- `ProviderProfile` (`register_provider_profile("openai", ProviderProfile(init_kwargs={"temperature": 0}))`) applies **only to string specs**, not to preconfigured instances. Runtime model switching is done with a `@wrap_model_call` that calls `request.override(model=init_chat_model(name))` — [models docs](https://docs.langchain.com/oss/python/deepagents/models)
- Built-in harness profiles exist for Anthropic Haiku 4.5, Opus 4.7, Sonnet 4.6, NVIDIA Nemotron 3 Ultra and OpenAI Codex. Built-in provider profiles cover OpenAI (Responses API), OpenRouter and NVIDIA — [source profiles/](https://pypi.org/project/deepagents/0.7.32/)
- Fireworks: `pip install -qU langchain-fireworks`, set `FIREWORKS_API_KEY`, then `from langchain_fireworks import ChatFireworks`; `ChatFireworks(model="accounts/fireworks/models/kimi-k2-instruct-0905", temperature=0, max_tokens=None, timeout=None, max_retries=2)`. Tool calling and structured output are supported. `reasoning_effort` requires `langchain-fireworks>=1.5.2` — [Fireworks integration](https://docs.langchain.com/oss/python/integrations/chat/fireworks)
- Fireworks prompt caching (session affinity) is enabled automatically when a compatible `langchain-fireworks` is installed (0.7.0, #4598) — [0.7.0 release notes](https://newreleases.io/project/github/langchain-ai/deepagents/release/deepagents==0.7.0), [source _prompt_caching.py](https://pypi.org/project/deepagents/0.7.32/)

### Inferences
- Example **[INFERRED, consistent with the docs]**: `create_deep_agent(model=ChatFireworks(model="accounts/fireworks/models/glm-5p1", temperature=0), tools=[...], system_prompt=...)`, or `model="fireworks:accounts/fireworks/models/glm-5p1"`.
- Open-weight models vary in parallel tool-call reliability. The harness includes `PatchToolCallsMiddleware`, which repairs dangling tool calls. Running heterogeneous peers (a different provider per peer) is simple because each `create_deep_agent` resolves its own model and harness profile.
- The summarization thresholds depend on the model profile's `max_input_tokens`. For a custom or unprofiled model, check that a profile exists, or pass your own `SummarizationMiddleware` by name to override the default. **[INFERRED]**

### Gaps
- The docs page has no Fireworks-specific deepagents code, and the minimum `langchain-fireworks` version for the caching middleware wasn't found.

## 5. Observability, checkpointing, streaming, cost control, recursion limits; gotchas

### Takeaway
Tracing goes through LangSmith automatically (runs carry `ls_integration: deepagents` metadata). Persistence is the standard LangGraph checkpointer plus `thread_id`. Streaming uses LangGraph stream modes with `subgraphs=True` namespaces, or the v0.6+ typed event-streaming API. **The harness sets `recursion_limit=9_999`**, so cost control is effectively your responsibility.

### Cited Findings
- `create_deep_agent` returns `.with_config({"recursion_limit": 9_999, "metadata": {"ls_integration": "deepagents", "lc_versions": {...}, "lc_agent_name": name}})` — [source graph.py](https://pypi.org/project/deepagents/0.7.32/)
- Streaming: `agent.stream(input, stream_mode="updates"|"messages"|"custom"|[...], subgraphs=True, version="v2")`. The namespace `()` is the main agent and `("tools:<id>",)` is a subagent spawned by that `task` call. Interrupts appear as `__interrupt__` and resume with `{"decisions": [...]}` on the same `thread_id`. For new apps the docs recommend the v0.6+ typed event-streaming API — [streaming docs](https://docs.langchain.com/oss/python/deepagents/streaming)
- HITL: `interrupt_on={"edit_file": True}` or an `InterruptOnConfig`. Declarative subagents inherit it, but `CompiledSubAgent` and `AsyncSubAgent` do not. HITL needs a checkpointer — [source docstring](https://pypi.org/project/deepagents/0.7.32/)
- Async subagents propagate LangSmith trace headers so child runs nest under the parent trace (beta) — [source async_subagents.py](https://pypi.org/project/deepagents/0.7.32/)
- `RubricMiddleware` (exported) is a grader loop that accepts any positive `max_iterations` as of 0.7.0 — [0.7.0 release notes](https://newreleases.io/project/github/langchain-ai/deepagents/release/deepagents==0.7.0)
- Offloading: tool results over `tool_token_limit_before_evict=20000` tokens and human messages over 50000 are evicted to the backend. `offload_binary_content=True` (>=0.7.21) stores blobs at `/blobs/<sha256>` — [source](https://pypi.org/project/deepagents/0.7.32/), [backends docs](https://docs.langchain.com/oss/python/deepagents/backends)

**Gotchas and version changes (summary)**
- 0.5.0: backend factories were deprecated. 0.5.3: `model=None` was deprecated. 0.7.0: no default todos, empty base prompt, `virtual_mode=True` default, recursive `delete`, overwrite-only `write_file`, required `StoreBackend(namespace=...)`, legacy backend methods removed, and the "No files found" output change — [0.7.0 notes](https://newreleases.io/project/github/langchain-ai/deepagents/release/deepagents==0.7.0), [backends docs](https://docs.langchain.com/oss/python/deepagents/backends)
- `StateBackend` files don't cross threads, so peers on different threads can't share them. Use `StoreBackend` or `FilesystemBackend` — [backends docs](https://docs.langchain.com/oss/python/deepagents/backends)
- `FilesystemBackend` without `CompositeBackend` writes the internal `/large_tool_results/` and `/conversation_history/` to real disk — [backends docs](https://docs.langchain.com/oss/python/deepagents/backends)
- Permissions apply only to the built-in tools. Custom tools that touch the backend or store bypass them — [source docstring](https://pypi.org/project/deepagents/0.7.32/)
- `LocalShellBackend` is not sandboxed. `virtual_mode` gives no protection once shell is enabled — [backends docs](https://docs.langchain.com/oss/python/deepagents/backends)

### Inferences
- **Cost control [INFERRED]:** override the recursion limit per call (`config={"recursion_limit": N}`). Add LangChain's built-in limiting middleware via `middleware=[...]`; I believe `ModelCallLimitMiddleware` and `ToolCallLimitMiddleware` exist in `langchain.agents.middleware` in v1 but did not re-verify them for 1.4.7. Alternatively, count tokens in an `after_model` hook and `jump_to="end"` once a shared per-swarm budget kept in the Store is exhausted. That gives you a budget for the whole swarm with no supervisor.
- For peer swarms, give each peer a distinct `name=` and `thread_id` so LangSmith traces are attributable. Optionally run all peers under one parent run (e.g., a wrapping `@traceable`) to see the whole swarm in one trace.

### Gaps
- I didn't fetch the "going to production" and LangSmith pages, so details on deployment-specific store/checkpointer provisioning beyond "omit `store` on LangSmith Deployment" are not covered.
- I didn't verify the exact API of the v0.6 typed event-streaming feature.
