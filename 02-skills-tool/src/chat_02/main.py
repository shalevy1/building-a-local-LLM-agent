import ollama
import os
import json

class SkillManager:
    def __init__(self, skills_dir="skills"):
        self.skills_dir = skills_dir
        if not os.path.exists(self.skills_dir):
            os.makedirs(self.skills_dir)

    def list_skills(self):
        """Returns a list of available .md files in the skills directory."""
        files = [f for f in os.listdir(self.skills_dir) if f.endswith('.md')]
        return files if files else "No skills available in the directory."

    def load_skill(self, skill_name):
        """Loads the content of a specific skill file."""
        # Ensure the filename has the correct extension
        if not skill_name.endswith('.md'):
            skill_name += '.md'
            
        path = os.path.join(self.skills_dir, skill_name)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return f"Error: Skill '{skill_name}' not found."

# Instantiate the manager
sm = SkillManager()

def chat():
    print("--- Qwen Skill-Aware Agent (Type 'quit' to exit) ---")
    model_name = 'qwen3.5:9b'
    messages = []

    # Define the tool schema
    tools = [
        {
            'type': 'function',
            'function': {
                'name': 'manage_skills',
                'description': 'Use this to list available skills or load a specific skill content. Use action="list" to see what is available, and action="load" with a skill_name to read it.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'action': {
                            'type': 'string',
                            'enum': ['list', 'load'],
                            'description': 'The action to perform'
                        },
                        'skill_name': {
                            'type': 'string',
                            'description': 'The name of the skill file to load (e.g., "SKILL.md")'
                        },
                    },
                    'required': ['action'],
                },
            },
        },
    ]

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ['quit', 'exit', 'bye']: break
        messages.append({'role': 'user', 'content': user_input})

        try:
            response = ollama.chat(model=model_name, messages=messages, tools=tools)

            if response['message'].get('tool_calls'):
                messages.append(response['message'])

                for tool in response['message']['tool_calls']:
                    args = tool['function'].get('arguments', {})
                    action = args.get('action')
                    
                    if tool['function']['name'] == 'manage_skills':
                        result=""
                        if action == 'list':
                            result = str(sm.list_skills())
                            print(f"  [System: Listing skills...]")
                        elif action == 'load':
                            s_name = args.get('skill_name')
                            result = sm.load_skill(s_name)
                            print(f"  [System: Loading skill: {s_name}...]")
                        
                        messages.append({'role': 'tool', 'content': result})

                final_response = ollama.chat(model=model_name, messages=messages)
                print(f"Qwen: {final_response['message']['content']}")
                messages.append(final_response['message'])
            else:
                print(f"Qwen: {response['message']['content']}")
                messages.append(response['message'])

        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    chat()