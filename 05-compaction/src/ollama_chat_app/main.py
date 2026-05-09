import ollama
import os
import time
import threading
import json
from datetime import datetime

# --- Global Configuration & State ---
model_name = 'qwen3.5:9b'
stop_event = threading.Event()
HISTORY_DIR = "history"
SKILLS_DIR = "skills"
active_skill_content = ""
CONTEXT_THRESHOLD = 4000 

for d in [HISTORY_DIR, SKILLS_DIR]:
    if not os.path.exists(d): os.makedirs(d)

current_session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
current_file = os.path.join(HISTORY_DIR, f"{current_session_id}.json")

# --- Utility Functions ---

def estimate_tokens(messages):
    text = "".join([str(m.get('content', '')) for m in messages])
    return len(text) // 4

def save_history(messages):
    serializable = []
    for m in messages:
        if hasattr(m, 'model_dump'): serializable.append(m.model_dump())
        elif isinstance(m, dict): serializable.append(m)
        else: serializable.append(dict(m))
    with open(current_file, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, indent=4)

class SkillManager:
    def list_skills(self): return [f for f in os.listdir(SKILLS_DIR) if f.endswith('.md')]
    def load_skill(self, name):
        if not name.endswith('.md'): name += '.md'
        try:
            with open(os.path.join(SKILLS_DIR, name), 'r', encoding='utf-8') as f: return f.read()
        except: return "Skill file not found."

sm = SkillManager()

# --- Tool Definitions ---

tools = [
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

# --- Logic Core ---

def compact_history(messages):
    if len(messages) < 4: return messages
    print(f"\n[SYSTEM] Auto-compacting context ({estimate_tokens(messages)} tokens)...")
    split_idx = int(len(messages) * 0.7)
    to_summarize = messages[:split_idx]
    keep_fresh = messages[split_idx:]
    
    summary_prompt = "Summarize this conversation briefly, preserving key facts and active goals."
    try:
        resp = ollama.chat(model=model_name, messages=to_summarize + [{'role': 'user', 'content': summary_prompt}])
        summary = resp['message']['content']
        new_history = [{'role': 'system', 'content': f"PREVIOUS SUMMARY: {summary}"}]
        if active_skill_content:
            new_history.insert(0, {'role': 'system', 'content': f"Active Skill: {active_skill_content}"})
        new_history.extend(keep_fresh)
        return new_history
    except Exception as e:
        print(f"[ERROR] Compaction failed: {e}")
        return messages

def handle_tools(response_message, messages):
    global active_skill_content
    tool_calls = response_message.get('tool_calls', [])
    for tool in tool_calls:
        name = tool['function']['name']
        args = tool['function'].get('arguments', {})
        
        if name == 'manage_skills':
            if args.get('action') == 'list':
                res = str(sm.list_skills())
            else:
                active_skill_content = sm.load_skill(args.get('skill_name', ''))
                res = f"SKILL LOADED: {active_skill_content}\n\nInstruction: Use this persona."
        elif name == 'get_current_datetime':
            res = datetime.now().strftime("%A, %B %d, %Y - %H:%M:%S")
        
        # Tier 1 Truncation
        if len(res) > 4000: res = res[:1000] + "\n...[TRUNCATED]..." + res[-1000:]
        messages.append({'role': 'tool', 'content': res})
    
    final_res = ollama.chat(model=model_name, messages=messages)
    return final_res['message']

def background_loop(prompt, interval_mins):
    print(f"\n[SYSTEM] Loop started: '{prompt}' every {interval_mins} min(s).")
    while not stop_event.is_set():
        for _ in range(interval_mins * 60):
            if stop_event.is_set(): return
            time.sleep(1)
        
        print(f"\n\n[LOOP ALERT - {datetime.now().strftime('%H:%M')}]")
        loop_messages = []
        if active_skill_content:
            loop_messages.append({'role': 'system', 'content': f"Context: {active_skill_content}"})
        loop_messages.append({'role': 'user', 'content': prompt})
        
        try:
            response = ollama.chat(model=model_name, messages=loop_messages, tools=tools)
            if response['message'].get('tool_calls'):
                loop_messages.append(response['message'])
                msg = handle_tools(response['message'], loop_messages)
            else:
                msg = response['message']
            print(f"Response: {msg['content']}\n\nYou: ", end='', flush=True)
        except Exception as e: print(f"Loop Error: {e}")

# --- Main Interface ---

def chat():
    global current_file, active_skill_content
    messages = []
    print(f"--- Qwen Agent Terminal (Threshold: {CONTEXT_THRESHOLD} tokens) ---")

    while True:
        user_input = input("\nYou: ").strip()
        if not user_input: continue

        if user_input.startswith('/'):
            parts = user_input.split()
            cmd = parts[0].lower()
            
            if cmd == '/help':
                print("\n[COMMANDS]\n /skills, /tools, /context, /compact, /history-list, /history-load <id>\n /loop <mins> <msg>, /stop-loop, quit")
            elif cmd == '/skills':
                print(f"[SYSTEM] Skills: {sm.list_skills()}")
            elif cmd == '/tools':
                print(f"[SYSTEM] Tools: {[t['function']['name'] for t in tools]}")
            elif cmd == '/context':
                tokens = estimate_tokens(messages)
                print(f"[CONTEXT] {tokens}/{CONTEXT_THRESHOLD} tokens (Skill Active: {'Yes' if active_skill_content else 'No'})")
            elif cmd == '/compact':
                messages = compact_history(messages)
            elif cmd == '/history-list':
                hists = sorted([f for f in os.listdir(HISTORY_DIR)], reverse=True)
                for i, h in enumerate(hists): print(f" [{i}] {h}")
            elif cmd == '/history-load':
                try:
                    hists = sorted([f for f in os.listdir(HISTORY_DIR)], reverse=True)
                    with open(os.path.join(HISTORY_DIR, hists[int(parts[1])]), 'r', encoding='utf-8') as f:
                        messages = json.load(f)
                    print(f"[SYSTEM] Loaded {hists[int(parts[1])]}")
                except: print("[ERROR] Usage: /history-load <number>")
            elif cmd == '/loop':
                stop_event.clear()
                try:
                    t = threading.Thread(target=background_loop, args=(" ".join(parts[2:]), int(parts[1])), daemon=True)
                    t.start()
                except: print("[ERROR] Usage: /loop <mins> <prompt>")
            elif cmd == '/stop-loop':
                stop_event.set()
                print("[SYSTEM] Loops stopped.")
            continue

        if user_input.lower() in ['quit', 'exit']: break
        messages.append({'role': 'user', 'content': user_input})

        try:
            if estimate_tokens(messages) > CONTEXT_THRESHOLD:
                messages = compact_history(messages)

            response = ollama.chat(model=model_name, messages=messages, tools=tools)
            if response['message'].get('tool_calls'):
                messages.append(response['message'])
                msg = handle_tools(response['message'], messages)
                print(f"Qwen: {msg['content']}")
                messages.append(msg)
            else:
                print(f"Qwen: {response['message']['content']}")
                messages.append(response['message'])
            
            save_history(messages)
        except Exception as e: print(f"Error: {e}")

if __name__ == "__main__":
    chat()