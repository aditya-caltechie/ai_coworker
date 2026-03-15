"""
Offline eval: run Sidekick on a list of prompts and collect reply + evaluator outcome.

Run from repo root:
  uv run python scripts/run_eval.py

Requires OPENAI_API_KEY. Optional: SERPER_API_KEY, PUSHOVER_* for tools.
Playwright: run `uv run playwright install chromium` if the worker uses browser.
"""
import asyncio
import json
import os
import sys

# Repo root = parent of scripts/
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)

from sidekick import Sidekick

EVAL_PROMPTS = [
    {
        "message": "What is 2 + 2?",
        "success_criteria": "The answer should be correct and concise.",
    },
    {
        "message": "What is the capital of France?",
        "success_criteria": "The answer should be accurate and one sentence.",
    },
]


async def run_one(sidekick: Sidekick, message: str, success_criteria: str) -> dict:
    """Run one superstep and return last assistant reply and evaluator feedback."""
    history = []
    result = await sidekick.run_superstep(message, success_criteria, history)
    reply = result[-2]["content"] if len(result) >= 2 else ""
    feedback = result[-1]["content"] if len(result) >= 1 else ""
    return {"reply": reply, "feedback": feedback}


async def main():
    sidekick = Sidekick()
    await sidekick.setup()
    outcomes = []
    for item in EVAL_PROMPTS:
        out = await run_one(sidekick, item["message"], item["success_criteria"])
        outcomes.append({"message": item["message"], "criteria": item["success_criteria"], **out})
        print(f"Message: {item['message'][:50]}... -> feedback: {out['feedback'][:80]}...")
    sidekick.cleanup()
    out_path = os.path.join(ROOT, "eval_outcomes.json")
    with open(out_path, "w") as f:
        json.dump(outcomes, f, indent=2)
    print(f"Wrote {len(outcomes)} outcomes to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
