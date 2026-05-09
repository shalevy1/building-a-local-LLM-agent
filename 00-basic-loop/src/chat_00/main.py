import ollama

def chat():
    print("--- Qwen 3.5 Chatroom (Type 'quit' to exit) ---")
    
    # Initialize message history to give the model context
    messages = []

    while True:
        user_input = input("\nYou: ")
        
        if user_input.lower() in ['quit', 'exit', 'bye']:
            print("Goodbye!")
            break

        # Add user message to history
        messages.append({'role': 'user', 'content': user_input})

        try:
            # Stream the response for a "typing" effect
            response = ollama.chat(
                model='qwen3.5:9b',
                messages=messages,
                stream=True,
            )

            print("Qwen: ", end='', flush=True)
            full_response = ""
            
            for chunk in response:
                content = chunk['message']['content']
                print(content, end='', flush=True)
                full_response += content
            
            print() # New line after response finishes

            # Add assistant response to history
            messages.append({'role': 'assistant', 'content': full_response})

        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    chat()