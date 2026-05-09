import ollama
import os

# 1. Define the actual Python function
def read_text_file(path):
    """Reads the content of a local text file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def chat():
    print("--- Qwen Tool-Enabled Chat (Type 'quit' to exit) ---")
    
    model_name = 'qwen3.5:9b'
    messages = []

    # 2. Define the tool metadata for the model
    tools = [
        {
            'type': 'function',
            'function': {
                'name': 'read_text_file',
                'description': 'Read the contents of a text file from the local disk',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'path': {
                            'type': 'string',
                            'description': 'The path to the file',
                        },
                    },
                    'required': ['path'],
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
                    func_name = tool['function']['name']
                    # Correct access pattern for the ollama library
                    args = tool['function'].get('arguments', {})
                    
                    if func_name == 'read_text_file':
                        path = args.get('path')
                        result = read_text_file(path)
                        messages.append({'role': 'tool', 'content': result})

                # Get final response after tool execution
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