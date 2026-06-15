from langchain_ollama import ChatOllama
from typing import Optional, TypedDict
from langchain_core.messages import AnyMessage
import operator
import json
import base64
from typing import Annotated
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, ToolMessage
from typing_extensions import Literal
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from email.message import EmailMessage
from gmail_auth import get_google_service
import os
import sys

load_dotenv()

class MessageState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    draft_data: Optional[str]
    regenerate: bool

def create_agent_graph(tools: list):
    """
    Create a graph of agents and their relationships.
    """
    llm = ChatGroq(model="qwen/qwen3-32b", api_key=os.getenv("GROQ_API_KEY"))
    # llm = ChatGroq(model="llama-3.1-8b-instant", api_key=os.getenv("GROQ_API_KEY"))
    # llm = ChatOllama(model="llama3.2")
    llm_with_tools = llm.bind_tools(tools)
    tools_by_name = {tool.name: tool for tool in tools}

    async def llm_call(state: MessageState) -> dict:

        prompt = [
            SystemMessage(content=(
            "You are an analytical assistant equipped with specific tools to answer queries accurately and safely. Carefully analyze the user's request: use the provided tools only when real-time data or calculations are needed, making sure not to invent parameters or tools. If you can answer perfectly using general knowledge, do so directly without tools. Finally, if a tool is required but missing critical information, ask the user for clarification instead of guessing.\n"
        ))
        ] + state["messages"]

        response = await llm_with_tools.ainvoke(prompt)
        print("LLM Response: ", response.tool_calls)
        return {
            "messages": [response]
        }

    async def tool_node(state: MessageState) -> dict:

        results = []
        for tool_call in state["messages"][-1].tool_calls:
            tool = tools_by_name[tool_call["name"]]
            args = tool_call["args"]
            observation = await tool.ainvoke(args)

            print(observation, file=sys.stderr)

            final_draft_data = None
            # THIS NEEDED FOR THE GET_CURRENT_DATETIME FUNCTION WHERE
            # THE RETURNED VALUE IS STRAIGHT "STRING"
            if isinstance(observation, str):
                results.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
            else:
                raw_text = observation[0].get("text", {})

                print(f"DEBUG RAW TEXT: {raw_text}")
                print(f"DEBUG RAW TEXT: {type(raw_text)}")

                if isinstance(raw_text, str):
                    try:
                        final_draft_data = json.loads(raw_text)
                        if final_draft_data["action"] == "review_email":
                            results.append(ToolMessage(content="User wants to review the draft.", tool_call_id=tool_call["id"]))
                    except json.JSONDecodeError:
                        pass
                    results.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))

        return {
            "messages": results,
            "draft_data": final_draft_data
        }

    async def human_review_node(state: MessageState):
        draft_data = state.get("draft_data", {})

        user_choice = interrupt(
            f"\n Draft Email\n"
            f"To: {draft_data['to']}\n"
            f"Subject: {draft_data['subject']}\n"
            f"Body: {draft_data['body']}\n\n"
        )
        user_choice = user_choice.strip().lower()

        if user_choice == "yes":
            service = get_google_service(action="email")
            message = EmailMessage()
            message.set_content(state["draft_data"].get("body"))
            message["To"] = state["draft_data"].get("to")
            message["Subject"] = state["draft_data"].get("subject")

            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            create_message = {"raw": encoded_message}
            service.users().messages().send(userId="me", body=create_message).execute()

            return {
                "messages": [SystemMessage(content="Email sent successfully")]
            }
        elif user_choice=="no":
            return {
                "messages": [SystemMessage(content="User wants a new draft. Call draft_send_email again with the same to and subject but rewrite the body.")], 
                "draft_data": None,
                "regenerate": True
            }
        else:
            return {
                "messages": [SystemMessage(content="Email generation cancelled")],
                "draft_data": None,
                "regenerate": False
            }

    def should_continue(state: MessageState) -> Literal["tool_node", "__end__"]:
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tool_node"
        return END

    def human_review(state: MessageState) -> Literal["human_review_node", "llm_call"]:
        if state.get("draft_data", {}) and state.get("draft_data", {})["action"] == "review_email":
            return "human_review_node"
        return "llm_call"
    
    def regenerate_node(state: MessageState) -> Literal["llm_call", "__end__"]:
        if not state.get("regenerate"):
            return "__end__"
        return "llm_call"

    workflow = StateGraph(MessageState)
    workflow.add_node("llm_call", llm_call)
    workflow.add_node("tool_node", tool_node)
    workflow.add_node("human_review_node", human_review_node)
    workflow.add_node("regenerate", regenerate_node)

    workflow.add_edge(START, "llm_call")
    workflow.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
    workflow.add_conditional_edges("tool_node", human_review, ["human_review_node", "llm_call"])
    workflow.add_conditional_edges("human_review_node", regenerate_node, ["llm_call", END])

    return workflow.compile(checkpointer=MemorySaver())