# Build Your Own OpenClaw — Progressive Examples

A step-by-step series of CLI chat applications built on top of [Ollama](https://ollama.com/) and the Qwen model. Each subdirectory is a standalone example that builds on the previous one.

## Prerequisites

- [Ollama](https://ollama.com/) installed and running locally
- The `qwen3.5:9b` model pulled:
  ```
  ollama pull qwen3.5:9b
  ```
- Python 3.9+

## Setup

Clone the repo and create the shared virtual environment from the project root:

```
python -m venv .venv
```

Activate it:

```
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

Install all examples and their dependencies:

```
pip install -e .
```

This registers all `chat-qwen-*` scripts into the virtual environment.

---

## Examples

### 00 — Basic Loop
**Directory:** `00-basic-loop/`

A minimal interactive chat loop. Maintains message history within the session.

```
chat-qwen-00
```

---

### 00-th — Basic Loop with Thinking
**Directory:** `00-basic-loop-thinking/`

Same as above, but displays the model's internal reasoning process separately from its final answer.

```
chat-qwen-00-th
```

---

### 01 — Tools
**Directory:** `01-tools/`

Introduces tool use. The model can call a `read_text_file` function to read local files and use their content in its answers.

```
chat-qwen-01
```

---

### 02 — Skills Tool
**Directory:** `02-skills-tool/`

Adds a `manage_skills` tool that lets the model list and load `.md` persona files from a `skills/` directory. Loading a skill changes the model's behaviour for the rest of the session.

Run from inside the subdirectory so the `skills/` folder is found:

```
cd 02-skills-tool
chat-qwen-02
```

Available slash commands: none (skills are loaded via the model's tool call).

---

### 03 — Skills Tool + Slash Commands
**Directory:** `03-skills-tool-slash/`

Extends example 02 with user-facing slash commands that execute without sending a message to the model.

```
cd 03-skills-tool-slash
chat-qwen-03
```

| Command | Description |
|---|---|
| `/help` | List available commands |
| `/skills` | List available skill files |
| `/tools` | Show active tool definitions |
| `/loop <mins> <prompt>` | Run a prompt in the background on a timer |
| `/stop-loop` | Stop all background loops |

---

### 04 — History
**Directory:** `04-history/`

Persists each session to a JSON file in a `history/` directory. Past sessions can be listed and reloaded.

```
cd 04-history
chat-qwen-04
```

Additional commands on top of example 03:

| Command | Description |
|---|---|
| `/history-list` | Show saved sessions |
| `/history-load <n>` | Load session number `n` from the list |

---

### 05 — Compaction
**Directory:** `05-compaction/`

Adds automatic context management. When the conversation exceeds a token threshold, older messages are summarised and replaced with a compact summary — keeping the context window manageable over long sessions.

```
cd 05-compaction
chat-qwen-05
```

Additional commands on top of example 04:

| Command | Description |
|---|---|
| `/context` | Show current estimated token usage |
| `/compact` | Manually trigger context compaction |

---

## Project Structure

```
jfj-alternative/
├── pyproject.toml              # shared dependencies and script entry points
├── .venv/                      # shared virtual environment
├── 00-basic-loop/
│   └── src/chat_00/main.py
├── 00-basic-loop-thinking/
│   └── src/chat_00_thinking/main.py
├── 01-tools/
│   └── src/chat_01/main.py
├── 02-skills-tool/
│   ├── skills/                 # persona .md files
│   └── src/chat_02/main.py
├── 03-skills-tool-slash/
│   ├── skills/
│   └── src/chat_03/main.py
├── 04-history/
│   ├── skills/
│   ├── history/                # saved session JSON files
│   └── src/chat_04/main.py
└── 05-compaction/
    ├── skills/
    ├── history/
    └── src/chat_05/main.py
```

> **Note:** Examples 02–05 use paths relative to your working directory for `skills/` and `history/`. Always run those scripts from inside their subdirectory.
