"""
Sidekick Gradio UI.

Steps:
  1. On load: create a Sidekick, run setup (tools + graph + memory), store in gr.State.
  2. On message submit / Go: run one superstep (graph.ainvoke), append reply + evaluator feedback to chat.
  3. On Reset: create a fresh Sidekick and clear inputs/chat.
  4. On state delete: cleanup browser/playwright (free_resources).
"""
import gradio as gr
from sidekick import Sidekick


async def setup():
    """Create Sidekick, load tools + build graph; called once on UI load."""
    sidekick = Sidekick()
    await sidekick.setup()
    return sidekick


async def process_message(sidekick, message, success_criteria, history):
    """Run one graph superstep with the user message and success criteria; return updated chat history."""
    results = await sidekick.run_superstep(message, success_criteria, history)
    return results, sidekick


async def reset():
    """Create a new Sidekick and clear message, success_criteria, and chat history."""
    new_sidekick = Sidekick()
    await new_sidekick.setup()
    return "", "", None, new_sidekick


def free_resources(sidekick):
    """Close browser and playwright when Sidekick is removed from state (e.g. reset or tab close)."""
    print("Cleaning up")
    try:
        if sidekick:
            sidekick.cleanup()
    except Exception as e:
        print(f"Exception during cleanup: {e}")


# --- UI layout ---
with gr.Blocks(title="Sidekick") as ui:
    gr.Markdown("## Sidekick Personal Co-Worker")
    sidekick = gr.State(delete_callback=free_resources)

    with gr.Row():
        chatbot = gr.Chatbot(label="Sidekick", height=300)
    with gr.Group():
        with gr.Row():
            message = gr.Textbox(show_label=False, placeholder="Your request to the Sidekick")
        with gr.Row():
            success_criteria = gr.Textbox(
                show_label=False, placeholder="What are your success critiera?"
            )
    with gr.Row():
        reset_button = gr.Button("Reset", variant="stop")
        go_button = gr.Button("Go!", variant="primary")

    # --- Events: load creates Sidekick; submit/click run superstep; reset clears state ---
    ui.load(setup, [], [sidekick])
    message.submit(
        process_message, [sidekick, message, success_criteria, chatbot], [chatbot, sidekick]
    )
    success_criteria.submit(
        process_message, [sidekick, message, success_criteria, chatbot], [chatbot, sidekick]
    )
    go_button.click(
        process_message, [sidekick, message, success_criteria, chatbot], [chatbot, sidekick]
    )
    reset_button.click(reset, [], [message, success_criteria, chatbot, sidekick])

# --- Launch ---
ui.launch(inbrowser=True, theme=gr.themes.Default(primary_hue="emerald"))
