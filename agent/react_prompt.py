def add_react_context(agent_scratchpad_json: str, tools: list) -> str:
    prompt = f"""
Complete the user's task as best as you can. You have access to the following tools:

{''.join([f"{tool.name}: {tool.description}\n" for tool in tools])}

Think before you respond. You could either call a tool or talk to the user.
1. To call a tool, format your response as a json codeblock with the following structure:
```json
{{
    "thought": "string, e.g. The user has asked me ..., I need to think about what to do step by step, ...",
    "action": "string, the tool to use, should be one of [{', '.join([tool.name for tool in tools])}]",
    "action_input": "the input to the tool, simply a string"
}}
```
Then you will get
```json
{{
    "observation": "the result of the action"
}}
```
After which you should continue to respond with the format of thought/action/action_input, until you are ready to talk to the user directly.
2. To chat with the user directly, format your response as such:
When you are ready to reply to the user, respond with json codeblock with the following structure:
```json
{{
    "thought": "string, e.g. The user has asked me ..., let me check if I have everything I need to report, ...",
    "reply": "a string that goes directly to the user"
}}
```
Your response MUST be either a thought/action/action_input json or a thought/reply json, nothing else.

Here's the previous conversation and actions you have taken:

{agent_scratchpad_json}

Now provide your next response:
"""
    return prompt
