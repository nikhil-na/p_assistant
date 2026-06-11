from langchain_ollama import ChatOllama
from typing import TypedDict
from langchain_core.messages import AnyMessage
import operator
from typing import Annotated
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from typing_extensions import Literal
from dotenv import load_dotenv
from langchain_groq import ChatGroq
import os

load_dotenv()

class MessageState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]

def create_agent_graph(tools: list):
    """
    Create a graph of agents and their relationships.
    """
    llm = ChatGroq(model="qwen/qwen3-32b", api_key=os.getenv("GROQ_API_KEY"))
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
            results.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))

        return {
            "messages": results
        }

    def should_continue(state: MessageState) -> Literal["tool_node", END]:
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tool_node"
        return END

    workflow = StateGraph(MessageState)
    workflow.add_node("llm_call", llm_call)
    workflow.add_node("tool_node", tool_node)

    workflow.add_edge(START, "llm_call")
    workflow.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
    workflow.add_edge("tool_node", "llm_call")

    return workflow.compile()