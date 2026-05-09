import ollama
import os
import time
import threading
from datetime import datetime

# --- Global Configuration & State ---
model_name = 'qwen3.5:9b'
stop_event = threading.Event()

class SkillManager:
    def __init__(self, skills_dir="skills"):
        self.skills_dir = skills_dir
        if not os.path.exists(self.skills_dir):
            os.makedirs(self.skills_dir)

    def list_skills(self):
        files = [f for f in os.listdir(self.skills_dir) if f.endswith('.md')]
        return files if files else []

    def load_skill(self, skill_name):
        if not skill_name.endswith('.md'):
            skill_name += '.md'
        path = os.path.join(self.skills_dir, skill_name)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return f"Error: Skill '{skill_name}' not found."

sm = SkillManager()

def get_current_datetime():
    return datetime.now().strftime("%A, %B %d, %Y - %H:%M:%S")

# --- Tool Definitions (Global) ---
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

def handle_tools(response_message, messages):
    """Common logic for executing tools and returning results."""
    tool_calls = response_message.get('tool_calls', [])
    for tool in tool_calls:
        name = tool['function']['name']
        args = tool['function'].get('arguments', {})
        
        if name == 'manage_skills':
            res = str(sm.list_skills()) if args.get('action') == 'list' else sm.load_skill(args.get('skill_name', ''))
        elif name == 'get_current_datetime':
            res = get_current_datetime()
        else:
            res = "Tool not found."
            
        messages.append({'role': 'tool', 'content': res})
    
    # Get the final response from the LLM after tool usage
    final_res = ollama.chat(model=model_name, messages=messages)
    return final_res['message']

def background_loop(prompt, interval_mins):
    """Background loop that respects the stop_event and uses tools."""
    print(f"\n[SYSTEM] Loop started: '{prompt}' every {interval_mins} min(s).")
    
    while not stop_event.is_set():
        # Sleep in small increments so we can stop quickly
        for _ in range(interval_mins * 60):
            if stop_event.is_set(): return
            time.sleep(1)

        print(f"\n\n[LOOP ALERT - {datetime.now().strftime('%H:%M')}]")
        loop_messages = [{'role': 'user', 'content': prompt}]
        
        try:
            response = ollama.chat(model=model_name, messages=loop_messages, tools=tools)
            if response['message'].get('tool_calls'):
                loop_messages.append(response['message'])
                msg = handle_tools(response['message'], loop_messages)
            else:
                msg = response['message']
            
            print(f"Response: {msg['content']}\n\nYou: ", end='', flush=True)
        except Exception as e:
            print(f"Loop Error: {e}")

def chat():
    print("--- Qwen Agent Terminal (Type /help) ---")
    messages = []

    while True:
        user_input = input("\nYou: ").strip()
        if not user_input: continue

        # Slash Commands
        if user_input.startswith('/'):
            parts = user_input.split()
            cmd = parts[0].lower()
            
            if cmd == '/help':
                print("\n/skills, /tools, /loop <mins> <prompt>, /stop-loop, quit")
            elif cmd == '/skills':
                print(f"Skills: {sm.list_skills()}")
            elif cmd == '/tools':
                print(f"Tools: {[t['function']['name'] for t in tools]}")
            elif cmd == '/loop':
                stop_event.clear()
                mins = int(parts[1]); p_text = " ".join(parts[2:])
                threading.Thread(target=background_loop, args=(p_text, mins), daemon=True).start()
            elif cmd == '/stop-loop':
                stop_event.set()
                print("[SYSTEM] Stopping background loops...")
            continue

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
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    chat()