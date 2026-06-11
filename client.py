import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from agent import create_agent_graph
from langchain_core.messages import HumanMessage

async def assistant():
    
    server_path = os.path.join(os.path.dirname(__file__), "server.py")
    config = {
        "p_a_server": {
            "transport": "stdio",
            "command": "uv",
            "args": ["run", server_path]
        }
    }

    client = MultiServerMCPClient(config)
    tools = await client.get_tools()
    for tool in tools:
        print(tool.name)

    app = create_agent_graph(tools)

    while True:
        user_input = input("User: ").lower().strip()
        if user_input in ["exit", "quit", "bye"]:
            print("Exiting...")
            break
        inital_state = {
            "messages": [HumanMessage(content=user_input)]
        }

        final_response = await app.ainvoke(inital_state)
        print("============ Final Response ====================")
        print(final_response["messages"][-1].content)