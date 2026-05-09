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

def stream_with_thinking(model, messages, tools=None):
    """Stream a response, displaying thinking traces and final answer separately."""
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
            content, tool_calls = stream_with_thinking(model_name, messages, tools=tools)

            if tool_calls:
                messages.append({'role': 'assistant', 'tool_calls': tool_calls})

                for tool in tool_calls:
                    func_name = tool.function.name
                    args = tool.function.arguments or {}

                    if func_name == 'read_text_file':
                        path = args.get('path')
                        result = read_text_file(path)
                        messages.append({'role': 'tool', 'content': result})

                # Get final response after tool execution
                final_content, _ = stream_with_thinking(model_name, messages)
                messages.append({'role': 'assistant', 'content': final_content})
            else:
                messages.append({'role': 'assistant', 'content': content})

        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    chat()
