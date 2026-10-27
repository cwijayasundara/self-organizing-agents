CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author TEXT NOT NULL,
    type TEXT NOT NULL,
    text TEXT NOT NULL,
    task_id TEXT,
    detail TEXT,
    created_at REAL NOT NULL,
    invalidated INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    title_key TEXT NOT NULL,
    objective TEXT NOT NULL,
    output_format TEXT NOT NULL,
    acceptance TEXT NOT NULL,          -- JSON list
    required INTEGER NOT NULL DEFAULT 1,
    kind TEXT NOT NULL DEFAULT 'work',
    status TEXT NOT NULL DEFAULT 'open',
    owner TEXT,
    owner_family TEXT,
    lease_until REAL,
    review_of TEXT,
    author_family TEXT,
    artifact_id TEXT,
    version INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS task_deps (
    task_id TEXT NOT NULL,
    dep_id TEXT NOT NULL,
    PRIMARY KEY (task_id, dep_id)
);

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    author TEXT NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT NOT NULL,
    recipient TEXT,
    text TEXT NOT NULL,
    urgent INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS deliveries (
    message_id INTEGER NOT NULL,
    recipient TEXT NOT NULL,
    PRIMARY KEY (message_id, recipient)
);

CREATE TABLE IF NOT EXISTS cursors (
    agent_id TEXT PRIMARY KEY,
    last_note_id INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS spend (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    model_key TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    cached_input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    usd REAL NOT NULL,
    created_at REAL NOT NULL
);

-- Observability only: runner and tool activity for logs and the live view. Peers never read it.
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    kind TEXT NOT NULL,
    task_id TEXT,
    detail TEXT,
    created_at REAL NOT NULL
);
