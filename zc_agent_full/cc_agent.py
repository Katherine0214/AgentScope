# -*- coding: utf-8 -*-
"""The main entry point of the plan example."""
"""The agentic usage example for RAG, where the agent is equipped with RAG tools to answer questions based on a knowledge base."""
"""The main entry point of the agent skill example."""
"""Memory example demonstrating long-term memory functionality with mem0."""



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
 

# dashscope.base_http_api_url = "https://vpc-cn-beijing.dashscope.aliyuncs.com/api/v1"


async def main() -> None:
    # # 可视化 Connect to the studio for better visualization (optional)，要先运行as_studio启动studio
    # agentscope.init(
    #     project="cc_agent",
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
    
    
    """Knowledge as tool for RAG"""
    # Create a knowledge base instance
    knowledge = SimpleKnowledge(
        embedding_store=QdrantStore(
            location=":memory:",
            collection_name="test_collection",
            dimensions=1024,  # The dimension of the embedding vectors
        ),
        embedding_model=DashScopeTextEmbedding(
            api_key='sk-e3631356892c4681965d35649d1b0fb9',
            model_name="text-embedding-v4",
        ),
    )
    
    # Store some things into the knowledge base 
    reader = TextReader(chunk_size=1024, split_by="sentence")
    documents = await reader(
        text=(
            "I'm John Doe, 28 years old. My best friend is James Smith. I live in San Francisco."
        ),
    )
    await knowledge.add_documents(documents)

    # Create a toolkit and register the RAG tool function
    toolkit.register_tool_function(
        knowledge.retrieve_knowledge,
        func_description=(  # Provide a clear description for the tool
            """Retrieve relevant documents from the knowledge base, which is relevant to John Doe's profile. 
            Note the `query` parameter is very important for the retrieval quality, and you can try many different queries to get the best results. 
            Adjust the `limit` and `score_threshold` parameters to get more or fewer results."""
        ),
    )
    
    
    """The main entry point of the agent skill example."""
    # toolkit.register_agent_skill("skills/brainstorming")
    
    
    """Initialize long term memory"""
    long_term_memory = Mem0LongTermMemory(
        agent_name="Friday",      # 搜索的就是Friday和user_A的所以聊天记录
        user_name="user",
        model=DashScopeChatModel(
            model_name="qwen-max",
            api_key='sk-e3631356892c4681965d35649d1b0fb9',
            stream=False,
        ),
        embedding_model=DashScopeTextEmbedding(
            model_name="text-embedding-v3",
            api_key='sk-e3631356892c4681965d35649d1b0fb9',
            dimensions=1024,
        ),
        vector_store_config=VectorStoreConfig(
            provider="qdrant",
            config={
                "on_disk": True,
                "path": "./memory/user",  # Specify custom path
                "embedding_model_dims": 1024,
            },
        ),
    )
    
    
    
    

    agent = ReActAgent(
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
        toolkit=toolkit,
        enable_meta_tool=True,
        plan_notebook=PlanNotebook(),
        memory=InMemoryMemory(),
        long_term_memory=long_term_memory,
        long_term_memory_mode="both",
    )
    
    user = UserAgent(name="user")

    msg = Msg(
        "user",
        "帮我写一个关于agent skill的文章",
        "user",
    )
    while True:
        msg = await agent(msg)
        msg = await user(msg)
        if msg.get_text_content() == "exit":
            break

    
    
    
    ######################## 用户的长期记忆会存在memory文件夹中，下方是个检索的示例 ########################
    # msg = Msg(
    #     "user",
    #     "我是John Doe. 请生成一个我的个人说明",
    #     "user",
    # )
    # msg = await agent(msg)

    
    ######################## 用户的长期记忆会存在mempry文件夹中，下方是个检索的示例 ########################
    # msg = Msg(
    #     role="user",
    #     content="我有什么喜好？",
    #     name="user",
    # )
    # msg = await agent(msg)
   

asyncio.run(main())