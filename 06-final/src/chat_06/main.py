# ============================================================
# PART 0: IMPORTS & GLOBAL CONFIGURATION
# ============================================================

import ollama
import os
from typing import Any
import time
import threading
import json
from datetime import datetime

model_name = 'qwen3.5:9b'
stop_event = threading.Event()
HISTORY_DIR = "history"
SKILLS_DIR = "skills"
CONTEXT_THRESHOLD = 4000

active_skill_content = ""

for d in [HISTORY_DIR, SKILLS_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

current_session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
current_file = os.path.join(HISTORY_DIR, f"{current_session_id}.json")


# ============================================================
# PART 1: CORE STREAMING WITH THINKING
# ============================================================

def stream_with_thinking(model, messages, tools=None):
    kwargs = {'model': model, 'messages': messages, 'stream': True}
    if tools:
        kwargs['tools'] = tools

    response_stream = ollama.chat(**kwargs)

    full_content = ""
    full_thinking = ""
    collected_tool_calls = []
    is_thinking = False
    answer_started = False

    print("\nQwen is thinking...")

    for chunk in response_stream:
        msg = chunk.message

        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            collected_tool_calls = msg.tool_calls

        if hasattr(msg, 'thinking') and msg.thinking:
            if not is_thinking:
                print("\n[THOUGHT PROCESS]:")
                is_thinking = True
            print(msg.thinking, end='', flush=True)
            full_thinking += msg.thinking
        elif msg.content:
            if is_thinking and not answer_started:
                print("\n\n[FINAL ANSWER]:")
                is_thinking = False
                answer_started = True
            print(msg.content, end='', flush=True)
            full_content += msg.content

    print()
    return full_content, collected_tool_calls


# ============================================================
# PART 2: TOOL USE
# ============================================================

# --- 2a: Simple File Tool ---

def read_text_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"


# --- 2b: Skills Tool ---

class SkillManager:
    def list_skills(self):
        return [f for f in os.listdir(SKILLS_DIR) if f.endswith('.md')]

    def load_skill(self, name):
        if not name.endswith('.md'):
            name += '.md'
        try:
            with open(os.path.join(SKILLS_DIR, name), 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return "Skill file not found."

sm = SkillManager()

tools = [
    {
        'type': 'function',
        'function': {
            'name': 'read_text_file',
            'description': 'Read the contents of a text file from the local disk.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string', 'description': 'The path to the file'},
                },
                'required': ['path'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'manage_skills',
            'description': 'List or load available .md skill files.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'action': {'type': 'string', 'enum': ['list', 'load']},
                    'skill_name': {'type': 'string'},
                },
                'required': ['action'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'get_current_datetime',
            'description': 'Get the current local date and time.',
            'parameters': {'type': 'object', 'properties': {}},
        },
    },
]

def handle_tools(tool_calls, messages):
    global active_skill_content
    for tool in tool_calls:
        name = tool.function.name
        args = tool.function.arguments or {}

        if name == 'read_text_file':
            res = read_text_file(args.get('path', ''))
        elif name == 'manage_skills':
            if args.get('action') == 'list':
                res = str(sm.list_skills())
            else:
                active_skill_content = sm.load_skill(args.get('skill_name', ''))
                res = f"SKILL LOADED: {active_skill_content}\n\nInstruction: Use this persona."
        elif name == 'get_current_datetime':
            res = datetime.now().strftime("%A, %B %d, %Y - %H:%M:%S")
        else:
            res = "Unknown tool."

        if len(res) > 4000:
            res = res[:1000] + "\n...[TRUNCATED]..." + res[-1000:]
        messages.append({'role': 'tool', 'content': res})

    final_content, _ = stream_with_thinking(model_name, messages)
    return {'role': 'assistant', 'content': final_content}


# ============================================================
# PART 3: BACKGROUND AUTOMATION
# ============================================================

def background_loop(prompt, interval_mins):
    print(f"\n[SYSTEM] Loop started: '{prompt}' every {interval_mins} min(s).")
    while not stop_event.is_set():
        for _ in range(interval_mins * 60):
            if stop_event.is_set():
                return
            time.sleep(1)

        print(f"\n\n[LOOP ALERT - {datetime.now().strftime('%H:%M')}]")
        loop_messages = []
        if active_skill_content:
            loop_messages.append({'role': 'system', 'content': f"Context: {active_skill_content}"})
        loop_messages.append({'role': 'user', 'content': prompt})

        try:
            content, tool_calls = stream_with_thinking(model_name, loop_messages, tools=tools)
            if tool_calls:
                loop_messages.append({'role': 'assistant', 'tool_calls': tool_calls})
                handle_tools(tool_calls, loop_messages)
            print(f"\nYou: ", end='', flush=True)
        except Exception as e:
            print(f"Loop Error: {e}")


# ============================================================
# PART 4: SESSION PERSISTENCE
# ============================================================

def save_history(messages):
    serializable = []
    for m in messages:
        if hasattr(m, 'model_dump'):
            serializable.append(m.model_dump())
        elif isinstance(m, dict):
            m_copy = dict(m)
            if 'tool_calls' in m_copy and m_copy['tool_calls']:
                m_copy['tool_calls'] = [
                    tc.model_dump() if hasattr(tc, 'model_dump') else tc
                    for tc in m_copy['tool_calls']
                ]
            serializable.append(m_copy)
        else:
            serializable.append(dict(m))
    with open(current_file, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, indent=4)


# ============================================================
# PART 5: CONTEXT MANAGEMENT
# ============================================================

def estimate_tokens(messages):
    text = "".join([str(m.get('content', '')) for m in messages])
    return len(text) // 4

def compact_history(messages):
    if len(messages) < 4:
        return messages
    print(f"\n[SYSTEM] Auto-compacting context ({estimate_tokens(messages)} tokens)...")
    split_idx = int(len(messages) * 0.7)
    to_summarize = messages[:split_idx]
    keep_fresh = messages[split_idx:]

    summary_prompt = "Summarize this conversation briefly, preserving key facts and active goals."
    try:
        # Non-streaming: compaction summary is internal, not user-visible
        resp = ollama.chat(
            model=model_name,
            messages=to_summarize + [{'role': 'user', 'content': summary_prompt}]
        )
        summary = resp['message']['content']
        new_history = [{'role': 'system', 'content': f"PREVIOUS SUMMARY: {summary}"}]
        if active_skill_content:
            new_history.insert(0, {'role': 'system', 'content': f"Active Skill: {active_skill_content}"})
        new_history.extend(keep_fresh)
        return new_history
    except Exception as e:
        print(f"[ERROR] Compaction failed: {e}")
        return messages


# ============================================================
# MAIN: THE CHAT LOOP
# ============================================================

def chat():
    global current_file, active_skill_content
    messages: list[dict[str, Any]] = []
    print(f"--- Qwen Agent Terminal (Context threshold: {CONTEXT_THRESHOLD} tokens) ---")
    print("Type /help to see available commands.")

    while True:
        user_input = input("\nYou: ").strip()
        if not user_input:
            continue

        if user_input.startswith('/'):
            parts = user_input.split()
            cmd = parts[0].lower()

            # Part 2 commands
            if cmd == '/skills':
                print(f"[SYSTEM] Skills: {sm.list_skills()}")
            elif cmd == '/tools':
                print(f"[SYSTEM] Tools: {[t['function']['name'] for t in tools]}")

            # Part 3 commands
            elif cmd == '/loop':
                stop_event.clear()
                try:
                    t = threading.Thread(
                        target=background_loop,
                        args=(" ".join(parts[2:]), int(parts[1])),
                        daemon=True,
                    )
                    t.start()
                except:
                    print("[ERROR] Usage: /loop <mins> <prompt>")
            elif cmd == '/stop-loop':
                stop_event.set()
                print("[SYSTEM] Loops stopped.")

            # Part 4 commands
            elif cmd == '/history-list':
                hists = sorted(os.listdir(HISTORY_DIR), reverse=True)
                for i, h in enumerate(hists):
                    print(f" [{i}] {h}")
            elif cmd == '/history-load':
                try:
                    hists = sorted(os.listdir(HISTORY_DIR), reverse=True)
                    with open(os.path.join(HISTORY_DIR, hists[int(parts[1])]), 'r', encoding='utf-8') as f:
                        messages = json.load(f)
                    print(f"[SYSTEM] Loaded {hists[int(parts[1])]}")
                except:
                    print("[ERROR] Usage: /history-load <number>")

            # Part 5 commands
            elif cmd == '/context':
                tokens = estimate_tokens(messages)
                print(f"[CONTEXT] {tokens}/{CONTEXT_THRESHOLD} tokens (Skill active: {'Yes' if active_skill_content else 'No'})")
            elif cmd == '/compact':
                messages = compact_history(messages)

            elif cmd == '/help':
                print(
                    "\n[COMMANDS]\n"
                    "  /skills              List available skill files\n"
                    "  /tools               List registered tools\n"
                    "  /loop <mins> <msg>   Start a background loop\n"
                    "  /stop-loop           Stop all background loops\n"
                    "  /history-list        List saved sessions\n"
                    "  /history-load <n>    Reload a saved session\n"
                    "  /context             Show current token usage\n"
                    "  /compact             Manually compact context\n"
                    "  quit                 Exit"
                )
            continue

        if user_input.lower() in ['quit', 'exit', 'bye']:
            break

        messages.append({'role': 'user', 'content': user_input})

        try:
            # Part 5: auto-compact before calling the model
            if estimate_tokens(messages) > CONTEXT_THRESHOLD:
                messages = compact_history(messages)

            # Part 1: stream response with thinking
            content, tool_calls = stream_with_thinking(model_name, messages, tools=tools)

            if tool_calls:
                # Part 2: resolve tool calls
                messages.append({'role': 'assistant', 'tool_calls': tool_calls})
                msg = handle_tools(tool_calls, messages)
                messages.append(msg)
            else:
                messages.append({'role': 'assistant', 'content': content})

            # Part 4: persist after every turn
            save_history(messages)

        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    chat()
