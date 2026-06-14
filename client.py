import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from agent import create_agent_graph
from langchain_core.messages import HumanMessage
from langgraph.types import Command

async def assistant():
    config = {
        "p_a_server": {
            "transport": "streamable_http",
            "url": "http://127.0.0.1:8000/mcp"
        }
    }

    client = MultiServerMCPClient(config)
    tools = await client.get_tools()
    for tool in tools:
        print(tool.name)

    app = create_agent_graph(tools)
    run_config = {"configurable": {"thread_id": "thread_1"}}

    while True:
        user_input = (await asyncio.to_thread(input, "User: ")).strip()
        if user_input.lower() in ["exit", "quit", "bye"]:
            print("Exiting...")
            break

        initial_state = {"messages": [HumanMessage(content=user_input)], "draft_data": None, "regenerate": False}
        response = await app.ainvoke(initial_state, config=run_config)

        while response.get("__interrupt__"):
            interrupt = response["__interrupt__"][0]
            print(f"\nAssistant: {interrupt.value}")
            user_reply = input(f"You, (yes / no / cancel): ").strip().lower()
            print(f"\nResuming with: {user_reply!r}")
            response = await app.ainvoke(
                Command(resume=user_reply),
                config=run_config,
            )

        print("============ Final Response ====================")
        print(response["messages"][-1].content)

if __name__ == "__main__":
    asyncio.run(assistant())
