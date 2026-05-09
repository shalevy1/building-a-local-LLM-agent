import ollama

def chat():
    print("--- Qwen 3.5 Reasoning Chat (Type 'quit' to exit) ---")
    messages = []

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ['quit', 'exit', 'bye']: break

        messages.append({'role': 'user', 'content': user_input})

        try:
            # We add 'think=True' to ensure the model uses its reasoning capabilities
            response_stream = ollama.chat(
                model='qwen3.5:9b', 
                messages=messages,
                stream=True,
            )

            print("\nQwen is thinking...")
            full_content = ""
            full_thinking = ""
            is_thinking = False

            for chunk in response_stream:
                # 1. Check for Thinking Trace
                if hasattr(chunk.message, 'thinking') and chunk.message.thinking:
                    if not is_thinking:
                        print("\n[THOUGHT PROCESS]:")
                        is_thinking = True
                    print(chunk.message.thinking, end='', flush=True)
                    full_thinking += chunk.message.thinking

                # 2. Check for Final Answer Content
                elif chunk.message.content:
                    if is_thinking:
                        print("\n\n[FINAL ANSWER]:")
                        is_thinking = False
                    print(chunk.message.content, end='', flush=True)
                    full_content += chunk.message.content
            
            print() # End of response

            # Important: Store the content back to history
            # You can decide whether to store the thinking trace or just the content
            messages.append({'role': 'assistant', 'content': full_content})

        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    chat()