from langchain_core.messages import AIMessage

def emergency_node(state):
    reasoning = state.get("triage_reasoning", "")
    city = state.get("city", "your area")

    if reasoning:
        reasoning_text = f"\n\n📋 **Why this is an emergency:** {reasoning}"
    else:
        reasoning_text = ""

    msg = (
        f"🚨 **EMERGENCY!** Call **112** (India) or go to the nearest Emergency Room immediately.{reasoning_text}\n\n"
        f"📍 **Nearby ERs in {city}:**\n"
        f"- Check Google Maps for the closest hospital\n"
        f"- Ask someone to drive you or call an ambulance\n\n"
        f"⚠️ Do **not** wait. Every minute matters."
    )

    messages = list(state.get("messages", []))
    messages.append(AIMessage(content=msg))
    return {**state, "messages": messages}