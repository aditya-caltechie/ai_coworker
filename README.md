# ai-sidekick

# High-level what the project does

## 1. Multi-agent LangGraph flow

### Worker: 
Helpful assistant that uses tools (Playwright browser) to do tasks. Keeps working until it either has a question for the user or thinks the task is done.
### Evaluator: 
Separate LLM that uses structured output (Pydantic EvaluatorOutput) to decide:
Whether the worker’s last response meets the success criteria
Whether more user input is needed (e.g. clarification, or assistant stuck).
### Loop: 
Worker → (tools or evaluator) → if not done → back to worker; stops when criteria are met or user input is needed.

## 2. Success-criteria–driven behavior
User provides both a request and success criteria. The evaluator checks the worker’s answers against those criteria and can send the worker back with feedback until the answer is good enough or the user must step in.

## 3. State and persistence
State holds: messages, success_criteria, feedback_on_work, success_criteria_met, user_input_needed. Conversation is checkpointed (e.g. MemorySaver) per thread.

## 4. UI
Gradio chat UI: “Sidekick Personal Co-worker” with message + success-criteria inputs and Reset/Go.
So in one line: criteria-checked, tool-using (browser) assistant with an evaluator loop and chat UI.
