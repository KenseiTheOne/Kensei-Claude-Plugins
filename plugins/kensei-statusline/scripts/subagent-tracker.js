/**
 * Subagent tracker hook for Kensei Statusline.
 * Tracks active subagents via a state file read by statusline.py.
 *
 * Install as SubagentStart + SubagentStop hook in settings.json.
 * Reads hook input from stdin (JSON with session_id, subagent_id, etc.)
 */
const fs = require("fs");
const path = require("path");
const os = require("os");

const STATE_DIR = path.join(os.tmpdir(), "kensei-statusline");
const STATE_FILE = path.join(STATE_DIR, "subagents.json");
const LOCK_FILE = path.join(STATE_DIR, "subagents.lock");
const STALE_MS = 10 * 60 * 1000; // 10 min — auto-cleanup stale entries

function ensureDir() {
  if (!fs.existsSync(STATE_DIR)) {
    fs.mkdirSync(STATE_DIR, { recursive: true });
  }
}

function readState() {
  try {
    if (!fs.existsSync(STATE_FILE)) return {};
    return JSON.parse(fs.readFileSync(STATE_FILE, "utf-8"));
  } catch {
    return {};
  }
}

function writeState(state) {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), "utf-8");
}

function cleanStale(state) {
  const now = Date.now();
  const cleaned = {};
  for (const [id, entry] of Object.entries(state)) {
    if (now - entry.started_at < STALE_MS) {
      cleaned[id] = entry;
    }
  }
  return cleaned;
}

async function main() {
  let input = "";
  for await (const chunk of process.stdin) {
    input += chunk;
  }

  let data;
  try {
    data = JSON.parse(input);
  } catch {
    return;
  }

  const hookEvent = process.env.CLAUDE_HOOK_EVENT || "";
  const sessionId = data.session_id || "unknown";
  const subagentId = data.subagent_id || data.agent_id || `sa-${Date.now()}`;
  const model = data.model?.display_name || data.model?.id || "";
  const agentType = data.subagent_type || data.agent?.name || "";

  ensureDir();
  const state = cleanStale(readState());

  if (hookEvent === "SubagentStart") {
    state[subagentId] = {
      session_id: sessionId,
      model: model,
      type: agentType,
      started_at: Date.now(),
    };
  } else if (hookEvent === "SubagentStop") {
    delete state[subagentId];
  }

  writeState(state);
}

main().catch(() => {});
