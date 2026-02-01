# -*- coding: utf-8 -*-
"""The planner agent example."""
import os
import asyncio
import dashscope
from agentscope.message import Msg
from agentscope.agent import ReActAgent, UserAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.embedding import DashScopeTextEmbedding
from mem0.vector_stores.configs import VectorStoreConfig

from agentscope.plan import PlanNotebook
from agentscope.tool import (
    Toolkit,
    execute_shell_command,
    execute_python_code,
    write_text_file,
    insert_text_file,
    view_text_file,
)
from tool import create_worker
from agentscope.rag import SimpleKnowledge, QdrantStore, TextReader
from agentscope.memory import InMemoryMemory,Mem0LongTermMemory


async def main() -> None:
    """The main function."""
    # # 可视化 Connect to the studio for better visualization (optional)，要先运行as_studio启动studio
    # import agentscope
    # agentscope.init(
    #     project="wechat_agent",
    #     studio_url="http://localhost:3000",
    # )

    """The main entry point for the plan example."""
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_shell_command)
    toolkit.register_tool_function(execute_python_code)
    toolkit.register_tool_function(write_text_file)
    toolkit.register_tool_function(insert_text_file)
    toolkit.register_tool_function(view_text_file)
    toolkit.register_tool_function(create_worker)     # 这是自定义的工具


    planner = ReActAgent(
        name="Friday",
        sys_prompt="""You are Friday, a multifunctional agent that can help people solving different complex tasks. You act like a meta planner to solve complicated tasks by decomposing the task and building/orchestrating different worker agents to finish the sub-tasks.

                    ## Core Mission
                    Your primary purpose is to break down complicated tasks into manageable subtasks (a plan), create worker agents to finish the subtask, and coordinate their execution to achieve the user's goal efficiently.

                    ### Important Constraints
                    1. DO NOT TRY TO SOLVE THE SUBTASKS DIRECTLY yourself.
                    2. Always follow the plan sequence.
                    3. DO NOT finish the plan until all subtasks are finished.
                    """,  
        model=DashScopeChatModel(
            model_name="qwen-max",
            api_key='sk-e3631356892c4681965d35649d1b0fb9',
        ),
        formatter=DashScopeChatFormatter(),
        plan_notebook=PlanNotebook(),
        toolkit=toolkit,
        max_iters=20,
    )
    user = UserAgent(name="user")

    msg = Msg(
        "user",
        "帮我上网搜索关于agent skill的文章",
        "user",
    )
    while True:
        msg = await planner(msg)
        msg = await user(msg)
        if msg.get_text_content() == "exit":
            break


asyncio.run(main())
