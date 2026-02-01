# -*- coding: utf-8 -*-
"""The tool functions used in the planner example."""
import asyncio
import json
import os
from collections import OrderedDict
from typing import AsyncGenerator

from pydantic import BaseModel, Field

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.mcp import HttpStatelessClient, StdIOStatefulClient
from agentscope.message import Msg, TextBlock
from agentscope.model import DashScopeChatModel
from agentscope.pipeline import stream_printing_messages
from agentscope.tool import (
    ToolResponse,
    Toolkit,
    write_text_file,
    insert_text_file,
    view_text_file,
)
import dashscope
# dashscope.base_http_api_url = "https://vpc-cn-beijing.dashscope.aliyuncs.com/api/v1"

class ResultModel(BaseModel):
    """
    The result model used for the sub worker to summarize the task result.
    """

    success: bool = Field(
        description="Whether the task was successful or not.",
    )
    message: str = Field(
        description=(
            "The specific task result, should include necessary details, "
            "e.g. the file path if any file is generated, the deviation, "
            "and the error message if any."
        ),
    )


def _convert_to_text_block(msgs: list[Msg]) -> list[TextBlock]:
    # Collect all the content blocks
    blocks: list = []
    # Convert tool_use block into text block for streaming tool response
    for _ in msgs:
        for block in _.get_content_blocks():
            if block["type"] == "text":
                blocks.append(block)

            elif block["type"] == "tool_use":
                blocks.append(
                    TextBlock(
                        type="text",
                        text=f"Calling tool {block['name']} ...",
                    ),
                )

    return blocks


async def create_worker(
    task_description: str,
) -> AsyncGenerator[ToolResponse, None]:
    """Create a sub-worker to finish the given task.

    Args:
        task_description (`str`):
            The description of the task to be done by the sub-worker, should
            contain all the necessary information.

    Returns:
        `AsyncGenerator[ToolResponse, None]`:
            An async generator yielding ToolResponse objects.
    """
    toolkit = Toolkit()

    # Browser MCP client
    toolkit.create_tool_group(
        group_name="browser_tools",
        description="Web browsing related tools.",
    )
    browser_client = StdIOStatefulClient(
        name="playwright-mcp",
        command="npx",
        args=["@playwright/mcp@latest"],
    )
    await browser_client.connect()
    await toolkit.register_mcp_client(
        browser_client,
        group_name="browser_tools",
    )

    # Track all connected clients for cleanup
    connected_clients = [browser_client]

    # DuckDuckGo Search MCP client (Free, no API key required)
    try:
        toolkit.create_tool_group(
            group_name="duckduckgo_search_tools",
            description="DuckDuckGo web search tools for finding information online.",
        )
        duckduckgo_client = StdIOStatefulClient(
            name="duckduckgo-mcp",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-duckduckgo"],
        )
        await duckduckgo_client.connect()
        await toolkit.register_mcp_client(
            duckduckgo_client,
            group_name="duckduckgo_search_tools",
        )
        connected_clients.append(duckduckgo_client)
    except Exception as e:
        print(
            f"Warning: Failed to connect DuckDuckGo MCP client: {e}. "
            "Continuing without DuckDuckGo search tools.",
        )

    # Brave Search MCP client (Free, no API key required for basic usage)
    try:
        toolkit.create_tool_group(
            group_name="brave_search_tools",
            description="Brave web search tools for finding information online.",
        )
        brave_client = StdIOStatefulClient(
            name="brave-search-mcp",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-brave-search"],
        )
        await brave_client.connect()
        await toolkit.register_mcp_client(
            brave_client,
            group_name="brave_search_tools",
        )
        connected_clients.append(brave_client)
    except Exception as e:
        print(
            f"Warning: Failed to connect Brave Search MCP client: {e}. "
            "Continuing without Brave search tools.",
        )

    # arXiv Paper Search MCP client (Free, no API key required, accessible in China)
    try:
        toolkit.create_tool_group(
            group_name="arxiv_search_tools",
            description="arXiv academic paper search and retrieval tools.",
        )
        arxiv_client = StdIOStatefulClient(
            name="arxiv-mcp",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-arxiv"],
        )
        await arxiv_client.connect()
        await toolkit.register_mcp_client(
            arxiv_client,
            group_name="arxiv_search_tools",
        )
        connected_clients.append(arxiv_client)
    except Exception as e:
        print(
            f"Warning: Failed to connect arXiv MCP client: {e}. "
            "Continuing without arXiv search tools.",
        )

    # Wikipedia MCP client (Free, no API key required, accessible in China via mirrors)
    try:
        toolkit.create_tool_group(
            group_name="wikipedia_tools",
            description="Wikipedia knowledge search and article retrieval tools.",
        )
        wikipedia_client = StdIOStatefulClient(
            name="wikipedia-mcp",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-wikipedia"],
        )
        await wikipedia_client.connect()
        await toolkit.register_mcp_client(
            wikipedia_client,
            group_name="wikipedia_tools",
        )
        connected_clients.append(wikipedia_client)
    except Exception as e:
        print(
            f"Warning: Failed to connect Wikipedia MCP client: {e}. "
            "Continuing without Wikipedia tools.",
        )

    # Fetch (HTTP Request) MCP client (Free, no API key required, works in China)
    try:
        toolkit.create_tool_group(
            group_name="fetch_tools",
            description="HTTP request tools for fetching web content and APIs.",
        )
        fetch_client = StdIOStatefulClient(
            name="fetch-mcp",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-fetch"],
        )
        await fetch_client.connect()
        await toolkit.register_mcp_client(
            fetch_client,
            group_name="fetch_tools",
        )
        connected_clients.append(fetch_client)
    except Exception as e:
        print(
            f"Warning: Failed to connect Fetch MCP client: {e}. "
            "Continuing without Fetch tools.",
        )

    # # Optional: Chinese Search Services (Uncomment to enable)
    # # Note: These services may require specific network conditions or may not be stable
    #
    # # Bing CN MCP client (Free, no API key required)
    # try:
    #     toolkit.create_tool_group(
    #         group_name="bing_search_tools",
    #         description="Bing search tools for Chinese content.",
    #     )
    #     bing_client = StdIOStatefulClient(
    #         name="bing-cn-mcp",
    #         command="npx",
    #         args=["-y", "@slcatwujian/bing-cn-mcp-server"],
    #     )
    #     await bing_client.connect()
    #     await toolkit.register_mcp_client(
    #         bing_client,
    #         group_name="bing_search_tools",
    #     )
    #     connected_clients.append(bing_client)
    # except Exception as e:
    #     print(
    #         f"Warning: Failed to connect Bing CN MCP client: {e}. "
    #         "Continuing without Bing search tools.",
    #     )
    #
    # # WeChat Search MCP client (Free, no API key required)
    # try:
    #     toolkit.create_tool_group(
    #         group_name="wechat_search_tools",
    #         description="WeChat article search tools.",
    #     )
    #     wechat_client = StdIOStatefulClient(
    #         name="weixin-search-mcp",
    #         command="npx",
    #         args=["-y", "weixin_search_mcp"],
    #     )
    #     await wechat_client.connect()
    #     await toolkit.register_mcp_client(
    #         wechat_client,
    #         group_name="wechat_search_tools",
    #     )
    #     connected_clients.append(wechat_client)
    # except Exception as e:
    #     print(
    #         f"Warning: Failed to connect WeChat Search MCP client: {e}. "
    #         "Continuing without WeChat search tools.",
    #     )
    #
    # # Rednote (Xiaohongshu) MCP client (Free, no API key required)
    # try:
    #     toolkit.create_tool_group(
    #         group_name="rednote_search_tools",
    #         description="Xiaohongshu (Rednote) content search tools.",
    #     )
    #     rednote_client = StdIOStatefulClient(
    #         name="rednote-mcp",
    #         command="npx",
    #         args=["-y", "rednote-mcp-server"],
    #     )
    #     await rednote_client.connect()
    #     await toolkit.register_mcp_client(
    #         rednote_client,
    #         group_name="rednote_search_tools",
    #     )
    #     connected_clients.append(rednote_client)
    # except Exception as e:
    #     print(
    #         f"Warning: Failed to connect Rednote MCP client: {e}. "
    #         "Continuing without Rednote search tools.",
    #     )

    # # GitHub MCP client
    # if os.getenv("GITHUB_TOKEN"):
    #     toolkit.create_tool_group(
    #         group_name="github_tools",
    #         description="GitHub related tools, including repository "
    #         "search and code file retrieval.",
    #     )
    #     github_client = HttpStatelessClient(
    #         name="github",
    #         transport="streamable_http",
    #         url="https://api.githubcopilot.com/mcp/",
    #         headers={"Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}"},
    #     )
    #     await toolkit.register_mcp_client(
    #         github_client,
    #         group_name="github_tools",
    #     )

    # else:
    #     print(
    #         "Warning: GITHUB_TOKEN not set in environment, skipping GitHub "
    #         "MCP client registration.",
    #     )


    # # Gaode MCP client
    # if os.getenv("GAODE_API_KEY"):
    #     toolkit.create_tool_group(
    #         group_name="amap_tools",
    #         description="Map-related tools, including geocoding, routing, and "
    #         "place search.",
    #     )
    #     client = HttpStatelessClient(
    #         name="amap_mcp",
    #         transport="streamable_http",
    #         url=f"https://mcp.amap.com/mcp?key={os.environ['GAODE_API_KEY']}",
    #     )
    #     await toolkit.register_mcp_client(client, group_name="amap_tools")
    # else:
    #     print(
    #         "Warning: GAODE_API_KEY not set in environment, skipping Gaode "
    #         "MCP client registration.",
    #     )


    # Basic read/write tools
    toolkit.register_tool_function(write_text_file)
    toolkit.register_tool_function(insert_text_file)
    toolkit.register_tool_function(view_text_file)

    # Create a new sub-agent to finish the given task
    sub_agent = ReActAgent(
        name="Worker",
        sys_prompt=f"""You're an agent named Worker.

                    ## Your Target
                    Your target is to finish the given task with your tools.

                    ## IMPORTANT
                    You MUST use the `{ReActAgent.finish_function_name}` to generate the final answer after finishing the task.
                    """,  # noqa: E501  # pylint: disable=C0301
        model=DashScopeChatModel(
            model_name="qwen-max",
            api_key='sk-e3631356892c4681965d35649d1b0fb9',
        ),
        enable_meta_tool=True,
        formatter=DashScopeChatFormatter(),
        toolkit=toolkit,
        max_iters=20,
    )

    # disable the console output of the sub-agent
    sub_agent.set_console_output_enabled(False)

    # Collect the execution process content
    msgs = OrderedDict()

    # Wrap the sub-agent in a coroutine task to obtain the final
    # structured output
    result = []

    async def call_sub_agent() -> None:
        msg_res = await sub_agent(
            Msg(
                "user",
                content=task_description,
                role="user",
            ),
            structured_model=ResultModel,
        )
        result.append(msg_res)

    # Use stream_printing_message to get the streaming response as the
    # sub-agent works
    async for msg, _ in stream_printing_messages(
        agents=[sub_agent],
        coroutine_task=call_sub_agent(),
    ):
        msgs[msg.id] = msg

        # Collect all the content blocks
        yield ToolResponse(
            content=_convert_to_text_block(
                list(msgs.values()),
            ),
            stream=True,
            is_last=False,
        )

        # Expose the interruption signal to the caller
        if msg.metadata and msg.metadata.get("_is_interrupted", False):
            raise asyncio.CancelledError()

    # Obtain the last message from the coroutine task
    if result:
        yield ToolResponse(
            content=[
                *_convert_to_text_block(
                    list(msgs.values()),
                ),
                TextBlock(
                    type="text",
                    text=json.dumps(
                        result[0].metadata,
                        indent=2,
                        ensure_ascii=False,
                    ),
                ),
            ],
            stream=True,
            is_last=True,
        )

    # Close all MCP clients
    for client in connected_clients:
        try:
            await client.close()
        except Exception as e:
            print(f"Warning: Failed to close MCP client {client.name}: {e}")