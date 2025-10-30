import requests
from inference_auth_token import get_access_token
from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent, AgentType
import json, time, os
from datetime import datetime
from dotenv import load_dotenv

from tools import TOOLS
from react_prompt import add_react_context

load_dotenv()

SOPHIA_TOKEN = get_access_token()
SOPHIA_BASE_URL = "https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = "https://api.openai.com/v1"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1/"

def build_model(model_name: str, provider: str = "anl"):
    if provider == "openai":
        token = OPENAI_API_KEY
        print(token[:5])
        base_url = OPENAI_BASE_URL
    elif provider == "anl":
        token = SOPHIA_TOKEN
        base_url = SOPHIA_BASE_URL
    elif provider == "anthropic":
        token = ANTHROPIC_API_KEY
        base_url = ANTHROPIC_BASE_URL

    return ChatOpenAI(
        model=model_name,
        temperature=1.0,
        #max_tokens=7000,
        timeout=15,
        api_key=token,
        base_url=base_url,
    )

def get_response(
    model: ChatOpenAI,
    prompt: str
):
    try:
        response = model.invoke(prompt)
        response_text = response.content
        if response_text == "":
            print("[WARNING] Empty response from model.")
            print("="* 20)
            print(f"[DEBUG] Full prompt was:\n{prompt}")
            print("="* 20)
            print("[DEBUG] Full response object:")
            print(json.dumps(response.model_dump(), indent=2))
            print("="* 20)
        return response_text
    except Exception as e:
        print(f"Error evaluating sample: {e}")
        return None

def parse_response(response_text: str) -> tuple:
    # Expect response to start with ```json and end with ```
    text = response_text
    if text.startswith('```'):
        text = text[3:]
    if text.startswith('json'):
        text = text[4:]
    if text.startswith('\n'):
        text = text[1:]
    if text.endswith('```'):
        text = text[:-3]
    if text.endswith('\n'):
        text = text[:-1]
    if text.startswith('{') and text.endswith('}'):
        try:
            return True, json.loads(text)
        except (json.JSONDecodeError, AttributeError) as e:
            return False, {"type": "error", "message": f"Error parsing response JSON: {e}"}
    else:
        return False, {"type": "error", "message": "Invalid response format, isn't a json codeblock. Expected something like:\n```json\n{{...}}\n```"}

def save_conversation_history(scratchpad_content: str, filename = None):
    """Save conversation history to a file."""
    if not os.path.exists("conversations"):
        os.makedirs("conversations")
    
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conversations/conversation_{timestamp}.txt"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(scratchpad_content)
        print(f"[INFO] Conversation history saved to: {filename}")
        return filename
    except Exception as e:
        print(f"[ERROR] Failed to save conversation history: {e}")
        return None

def load_conversation_history(filename: str) -> str:
    """Load conversation history from a file."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"[INFO] Conversation history loaded from: {filename}")
        return content
    except FileNotFoundError:
        print(f"[ERROR] History file not found: {filename}")
        return ""
    except Exception as e:
        print(f"[ERROR] Failed to load conversation history: {e}")
        return ""

def list_conversation_files() -> list:
    """List available conversation history files."""
    if not os.path.exists("conversations"):
        return []
    
    files = []
    for filename in os.listdir("conversations"):
        if filename.endswith('.txt'):
            filepath = os.path.join("conversations", filename)
            mtime = os.path.getmtime(filepath)
            files.append((filename, datetime.fromtimestamp(mtime)))
    
    # Sort by modification time, newest first
    files.sort(key=lambda x: x[1], reverse=True)
    return files

def invoke_tool(response_data: dict, tools: list) -> dict:
    if "action_input" not in response_data:
        return {
            "type": "observation",
            "observation": f"Got action '{response_data['action']}' but failed to find 'action_input' field."
        }
    action_name = response_data["action"]
    action_input = response_data["action_input"]
    # Find the tool corresponding to the action name
    for tool in tools:
        if tool.name == action_name:
            try:
                obs = tool.invoke(action_input)
                return {
                    "type": "observation",
                    "observation": obs
                }
            except Exception as e:
                return {
                    "type": "observation",
                    "observation": f"Error invoking tool {action_name} with input {action_input}: {e}"
                }
    return {
        "type": "observation",
        "observation": f"Unknown action, no tool with name '{action_name}'."
    }

def run_agent_step(
    model: ChatOpenAI,
    user_query: str,
    agent_scratchpad_json: str,
    tools: list,
    is_first_step: bool = False
) -> tuple:
    # Add user input to scratchpad if first step
    if is_first_step:
        new_scratchpad_json = f'\n```json\n{{"type": "user_input", "message": "{user_query}"}}\n```'
    else:
        new_scratchpad_json = ""
    prompt = add_react_context(agent_scratchpad_json + new_scratchpad_json, tools)
    response_text = get_response(model, prompt)
    while response_text is None:
        retry = input("No response from model. Retry? (y/n): ")
        if retry.lower() == "y":
            response_text = get_response(model, prompt)
        else:
            raise RuntimeError("No response from model.")
    new_scratchpad_json += f'\n{response_text}'
    
    success, parse_result = parse_response(response_text)
    if not success:
        # JSON parsing failed, reply with error
        new_scratchpad_json += f'\n```json\n{json.dumps(parse_result)}\n```'
        return None, new_scratchpad_json
    if "reply" in parse_result: 
        # Reply to user
        new_scratchpad_json += f'\n```json\n{json.dumps(parse_result)}\n```'
        return parse_result["reply"], new_scratchpad_json
    if "action" in parse_result:
        # Invoke tool
        tool_result = invoke_tool(parse_result, tools)
        new_scratchpad_json += f'\n```json\n{json.dumps(tool_result)}\n```'
        return None, new_scratchpad_json
    # Invalid response, no reply or action
    error_dict = {
        "type": "error",
        "message": "Invalid response format. Either 'reply' or 'action' should be present."
    }
    new_scratchpad_json += f'\n```json\n{json.dumps(error_dict)}\n```'
    return None, new_scratchpad_json

def main():
    #model = build_model("openai/gpt-oss-120b")
    #model  = build_model("meta-llama/Meta-Llama-3.1-70B-Instruct")
    #model = build_model("gpt-5-nano", use_openai=True)
    model = build_model("claude-sonnet-4-5", provider="anthropic")
    print("Model loaded!")
    
    # Initialize conversation history
    agent_scratchpad_json = ""
    
    # Check for existing conversation history
    loaded = False
    history_files = list_conversation_files()
    if history_files:
        print("\n[INFO] Found existing conversation history files:")
        for i, (filename, mtime) in enumerate(history_files[:5]):
            print(f"  {i+1}. {filename} (modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')})")
        
        load_choice = input("\n[INFO] Load previous conversation? Enter number (1-5), 'n' for new conversation: ").strip()
        if load_choice.isdigit() and 1 <= int(load_choice) <= min(5, len(history_files)):
            selected_file = history_files[int(load_choice)-1][0]
            agent_scratchpad_json = load_conversation_history(os.path.join("conversations", selected_file))
            loaded = True
    #user_input = "Check the current files in the repository. Readme is outdated because it doesn't mention the new benchmark directory. Please update it accordingly."
    
    repo_name = "Baleen"
    example_name = "Fairify"
    output_rubric_path = "rubrics/generated-claude"
    golden_rubric_path = "rubrics/manual"

    if loaded:
        user_input = "[SYSTEM] Continue previous conversation."
    else:
        user_input = f"""
Your task is to create a json rubric for evaluating a Dockerfile's ability to set up an environment for a repository.
Look at how a rubric is composed in the readme and understand its purpose.
Then produce a rubric for repo '{repo_name}' and write it at {output_rubric_path}/{repo_name}.json, referring to:
1. The readme and relevant information about the target repo cloned at data/{repo_name}/.
2. The reference rubric (machine generated and potentially inaccurate) rubrics/deprecated/{repo_name}_refer_to.sh.
In the process, refer to how the {golden_rubric_path}/{example_name} rubric is constructed based on:
1. The example repo at data/{example_name}/.
2. rubrics/deprecated/{example_name}_refer_to.sh script.

Additionally, follow those rules:
1. Evaluations that test file structure should make up LESS than 1/4 the weighted score
2. Check the README of the target repo and other relevant files to understand how the repo is supposed to be run. Test for functionality by seeing if the runs can indeed succeed. Look closely for sections like testing, verifying setup, running the project, etc.

Make sure to follow the rubric structure as shown in the readme, and cover the key aspects as demonstrated in the {example_name} example.
    """
    
    while user_input.lower() != "quit":
        step_count = 0
        try:
            reply, new_scratchpad_json = run_agent_step(
                model, user_input, agent_scratchpad_json, TOOLS,
                is_first_step=True
            )
            step_count += 1
            
            while reply is None:
                # Check if we've reached the step limit
                if step_count % 20 == 0:
                    print(f"\n[INFO] Agent has been working for {step_count} steps without completing the task.")
                    continue_choice = input("[INFO] Continue execution? (y/n/q for quit): ").lower().strip()

                    if continue_choice == 'q':
                        print("[INFO] User chose to quit.")
                        return
                    elif continue_choice != 'y':
                        print("[INFO] Stopping current task. You can enter a new prompt.")
                        break
                    else:
                        print("[INFO] Continuing execution...")
                elif step_count %5 == 0:
                    time.sleep(1)  # brief pause every 5 steps to remain respectful of API
                
                #_ = input("Press Enter to continue to the next step...")
                print("----- New Step -----")
                print(new_scratchpad_json)
                agent_scratchpad_json += new_scratchpad_json
                # Get next response
                reply, new_scratchpad_json = run_agent_step(model, user_input, agent_scratchpad_json, TOOLS)
                step_count += 1
                
            if reply is not None:
                print("----- Final Step -----")
                print(new_scratchpad_json)
                agent_scratchpad_json += new_scratchpad_json
                print("----- Response -----")
                print("Agent:", reply)
        except KeyboardInterrupt:
            print("\n[INFO] Agent execution interrupted by user (Ctrl+C)")
            print("[INFO] You can now enter a new prompt to redirect the agent")
            # Keep the current scratchpad state for context
        finally:
            print("\n[INFO] Auto-saving conversation history...")
            save_conversation_history(agent_scratchpad_json)
            
        try:
            user_input = input("User (type 'quit' to exit, 'save' to save conversation): ")
            if user_input.lower() == 'save':
                filename = save_conversation_history(agent_scratchpad_json)
                if filename:
                    print(f"[INFO] Conversation saved successfully.")
                user_input = input("User (type 'quit' to exit): ")
        except KeyboardInterrupt:
            print("\n[INFO] Exiting...")
            break
        finally:
            if agent_scratchpad_json.strip():
                print("\n[INFO] Auto-saving conversation history...")
                save_conversation_history(agent_scratchpad_json)
    
    # Autosave on exit
    if agent_scratchpad_json.strip():
        print("\n[INFO] Auto-saving conversation history...")
        save_conversation_history(agent_scratchpad_json)

if __name__ == "__main__":
    main()


