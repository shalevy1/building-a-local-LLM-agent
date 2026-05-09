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
active_skill_content = ""  # This will sync skills to the background loop

if not os.path.exists(HISTORY_DIR):
    os.makedirs(HISTORY_DIR)

current_session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
current_file = os.path.join(HISTORY_DIR, f"{current_session_id}.json")

class SkillManager:
    def __init__(self, skills_dir="skills"):
        self.skills_dir = skills_dir
        if not os.path.exists(self.skills_dir): os.makedirs(self.skills_dir)

    def list_skills(self):
        files = [f for f in os.listdir(self.skills_dir) if f.endswith('.md')]
        return files if files else []

    def load_skill(self, skill_name):
        if not skill_name.endswith('.md'): skill_name += '.md'
        path = os.path.join(self.skills_dir, skill_name)
        try:
            with open(path, 'r', encoding='utf-8') as f: return f.read()
        except: return f"Error: Skill '{skill_name}' not found."

sm = SkillManager()

def get_current_datetime():
    return datetime.now().strftime("%A, %B %d, %Y - %H:%M:%S")

def save_history(messages):
    serializable_messages = []
    for m in messages:
        if hasattr(m, 'model_dump'): serializable_messages.append(m.model_dump())
        elif isinstance(m, dict): serializable_messages.append(m)
        else: serializable_messages.append(dict(m))
    with open(current_file, 'w', encoding='utf-8') as f:
        json.dump(serializable_messages, f, indent=4)

def list_histories():
    return sorted([f for f in os.listdir(HISTORY_DIR) if f.endswith('.json')], reverse=True)

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

def handle_tools(response_message, messages, is_background=False):
    global active_skill_content
    tool_calls = response_message.get('tool_calls', [])
    for tool in tool_calls:
        name = tool['function']['name']
        args = tool['function'].get('arguments', {})
        
        if name == 'manage_skills':
            if args.get('action') == 'list':
                res = str(sm.list_skills())
            else:
                content = sm.load_skill(args.get('skill_name', ''))
                active_skill_content = content # SYNC TO BACKGROUND
                res = f"SKILL LOADED: {content}\n\nInstruction: Acknowledge and use this persona."
        elif name == 'get_current_datetime':
            res = get_current_datetime()
        
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
        
        # Inject active skill into the loop's context
        loop_messages = []
        if active_skill_content:
            loop_messages.append({'role': 'system', 'content': f"Active Skill Context: {active_skill_content}"})
        
        loop_messages.append({'role': 'user', 'content': prompt})
        
        try:
            response = ollama.chat(model=model_name, messages=loop_messages, tools=tools)
            if response['message'].get('tool_calls'):
                loop_messages.append(response['message'])
                msg = handle_tools(response['message'], loop_messages, is_background=True)
            else:
                msg = response['message']
            print(f"Response: {msg['content']}\n\nYou: ", end='', flush=True)
        except Exception as e: print(f"Loop Error: {e}")

def chat():
    global current_file, active_skill_content
    print(f"--- Qwen Agent Terminal (Session: {current_session_id}) ---")
    messages = []

    while True:
        user_input = input("\nYou: ").strip()
        if not user_input: continue

        if user_input.startswith('/'):
            parts = user_input.split()
            cmd = parts[0].lower()
            
            if cmd == '/help':
                print("\n[HELP] Commands:")
                print(" /skills             - List available .md files")
                print(" /tools              - Show loaded tool definitions")
                print(" /loop <mins> <msg>  - Run a prompt in background")
                print(" /stop-loop          - Stop all background tasks")
                print(" /history-list       - Show saved chat sessions")
                print(" /history-load <id>  - Load a past session")
                print(" quit                - Exit the application")

            elif cmd == '/skills':
                # Actually print the results here!
                available = sm.list_skills()
                print(f"\n[SYSTEM] Available Skills in /skills folder:")
                if available:
                    for s in available: print(f" - {s}")
                else:
                    print(" - No .md files found.")

            elif cmd == '/tools':
                # Show the tools currently in the 'tools' list
                print(f"\n[SYSTEM] Active Tools for {model_name}:")
                for t in tools:
                    print(f" - {t['function']['name']}: {t['function']['description']}")

            elif cmd == '/history-list':
                hists = list_histories()
                print(f"\n[SYSTEM] Session History:")
                if not hists: print(" - No history files found.")
                for i, h in enumerate(hists): print(f" [{i}] {h}")

            elif cmd == '/history-load':
                try:
                    hists = list_histories()
                    idx = int(parts[1])
                    load_path = os.path.join(HISTORY_DIR, hists[idx])
                    with open(load_path, 'r', encoding='utf-8') as f:
                        messages = json.load(f)
                    print(f"[SYSTEM] Loaded {len(messages)} messages from {hists[idx]}")
                except Exception as e:
                    print(f"[ERROR] Usage: /history-load <number>. (e.g., /history-load 0)")

            elif cmd == '/loop':
                stop_event.clear()
                try:
                    mins = int(parts[1])
                    p_text = " ".join(parts[2:])
                    threading.Thread(target=background_loop, args=(p_text, mins), daemon=True).start()
                except:
                    print("[ERROR] Usage: /loop <minutes> <prompt>")

            elif cmd == '/stop-loop':
                stop_event.set()
                print("[SYSTEM] Stopping background loops...")
            
            continue # Go back to the top of the while loop

        if user_input.lower() in ['quit', 'exit', 'bye']: break
        messages.append({'role': 'user', 'content': user_input})

        try:
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