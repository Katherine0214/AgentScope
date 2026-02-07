# -*- coding: utf-8 -*-
"""The tool functions used in the planner example."""
import os
import re
import json
import asyncio
import aiohttp
import requests
import dashscope
import trafilatura
import nest_asyncio
from openai import OpenAI
from bs4 import BeautifulSoup
from dashscope import Generation
from typing import AsyncGenerator
from collections import OrderedDict
from pydantic import BaseModel, Field
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright

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


# 允许嵌套事件循环
nest_asyncio.apply()

# dashscope.base_http_api_url = "https://vpc-cn-beijing.dashscope.aliyuncs.com/api/v1"

# 初始化OpenAI客户端（用于generate_article工具）
_openai_client = OpenAI(
    base_url="https://bailian.prd.aigateway.uaes.com/ailab/v1",
    api_key='AhwogtIs3wlHu6T8',
)

# 学术编辑提示词
_ACADEMIC_EDITOR_PROMPT = """# Role
你是一位资深的中文学术期刊（如《计算机学报》、《软件学报》）编辑，同时也是顶尖会议的中文审稿人。你拥有极高的文字驾驭能力，擅长将碎片化、口语化的表达重构为逻辑严密、用词考究的学术文本。

# Task
请阅读我提供的多篇【中文草稿】（可能包含口语、零散的要点或逻辑跳跃；如果个别文章及其不相关性可不纳入考虑），将其重写为一段逻辑连贯、符合中文学术规范的、字数为1000字左右的【论文正文段落】。

# Constraints
1. 格式与排版（Word 适配）：
   - 输出纯净的文本：严禁使用 Markdown 加粗、斜体或标题符号，以便我直接复制粘贴到 Word 中。
   - 标点规范：严格使用中文全角标点符号（，。；：""），数学符号或英文术语周围需保留合理的空格。

2. 逻辑与结构（核心任务）：
   - 逻辑重组：不要机械地逐句润色。先识别输入的逻辑主线，将松散的句子重新串联。必须将列表转化为连贯的段落。
   - 核心聚焦：遵循"一个段落一个核心观点"的原则。确保段落内的所有句子都服务于同一个主题，避免多主题杂糅。
   - 自然流向：根据内容属性选择逻辑顺序（如：从概括到细节、从原因到结果、或按时间演进），而非强制套用论证模板。句与句之间应通过语义自然衔接，避免跳跃。

3. 语言风格：
   - 极度正式：将口语转化为书面语（例如：将"不管是A还是B"改为"无论A抑或B"；将"效果变好了"改为"性能显著提升"）。
   - 客观中立：使用客观陈述语气，避免主观情绪色彩。
   - 术语规范：保留关键技术名词（如 Transformer, CNN, Few-shot），不要强行翻译业界通用的英文术语。

4. 输出格式：
   - Part 1 [Refined Text]：重写后的中文段落。
   - Part 2 [Logic flow]：简要说明你的重构思路（例如：提取了中心句，合并了冗余描述，调整了叙述语序）。
   - 除以上两部分外，不要输出任何多余的对话。

# Execution Protocol
在输出前，请自查：
1. 这种表达是否像一篇高质量的中文核心期刊论文？
2. 是否存在口语化残留？
3. 是否存在Markdown 格式符号？
3. 复制到 Word 里是否会有讨厌的格式符？（如有，请立即删除）

# Input
"""

# 去AI化提示词
_DE_AI_PROMPT = """# Role
你是一位计算机科学领域的资深学术编辑，专注于提升论文的自然度与可读性。你的任务是将大模型生成的机械化文本重写为符合顶级会议（如 ACL, NeurIPS）标准的自然学术表达。

# Task
请对我提供的【中文文章】进行"去 AI 化"重写，使其语言风格接近人类母语研究者。

# Constraints
1. 词汇规范化：
   - 优先使用朴实、精准的学术词汇。避免使用被过度滥用的复杂词汇。
   - 只有在必须表达特定技术含义时才使用术语，避免为了形式上的"高级感"而堆砌辞藻。

2. 结构自然化：
   - 移除机械连接词：删除生硬的过渡词，应通过句子间的逻辑递进自然连接。
   - 减少插入符号：尽量减少破折号（—）的使用，建议使用逗号、括号或从句结构替代。

3. 修改阈值（关键）：
   - 宁缺毋滥：如果输入的文本已经非常自然、地道且没有明显的 AI 特征，请保留原文，不要为了修改而修改。
   - 正向反馈：对于高质量的输入，应在 Part 2 中给予明确的肯定和正向评价。

4. 输出格式：
   - Part 1 [Paper]：输出重写后的文章（如果原文已足够好，则输出原文）。
   - Part 2 [Modification Log]：
     * 如果进行了修改：简要说明调整了哪些机械化表达。
     * 如果未修改：请直接输出中文评价："[检测通过] 原文表达地道自然，无明显 AI 味，建议保留。"
   - 除以上两个部分外，不要输出任何多余的对话。

# Execution Protocol
在输出前，请自查：
1. 拟人度检查：确认文本语气自然。
2. 必要性检查：当前的修改是否真的提升了可读性？如果是为了换词而换词，请撤销修改并判定为"检测通过"。

# Input
"""



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
            "e.g. the reference sources, the file path if any file is generated, the deviation, "
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


def search_online(query: str) -> ToolResponse:
    """Search online using Qwen model with internet search capability.

    Args:
        query (`str`):
            The search query or question to search online.

    Returns:
        `ToolResponse`:
            The search result and references from the internet.
    """
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": query},
    ]

    try:
        response = Generation.call(
            api_key='sk-e3631356892c4681965d35649d1b0fb9',
            model="qwen-max",
            messages=messages,
            enable_search=True,
            search_options={
                "forced_search": True,  # 强制联网搜索
                "search_strategy": "max",  # 配置搜索策略为高性能模式
                "enable_source": True,
            },
            enable_text_image_mixed=True, # 启用图文混合输出
            result_format="message",
        )

        if response.status_code == 200:
            # 获取主要搜索结果内容
            result_text = response.output.choices[0].message.content

            # 获取参考文献
            references = ""
            if hasattr(response.output, 'search_info') and response.output.search_info:
                search_results = response.output.search_info.get("search_results", [])
                if search_results:
                    references = "\n\n参考文献：\n"
                    for web in search_results:
                        references += f"[{web['index']}]: [{web['title']}]({web['url']})\n"

            # 合并主要内容和参考文献
            result_text = result_text + references
        else:
            result_text = f"搜索失败 - HTTP返回码：{response.status_code}，错误码：{response.code}，错误信息：{response.message}"
    except Exception as e:
        result_text = f"搜索过程中发生错误：{str(e)}"

    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=result_text,
            ),
        ],
    )


def read_urls_from_file(file_path: str) -> ToolResponse:
    """从指定文件中读取所有URL链接。

    该函数会解析文件内容，提取其中的URL链接（以 http:// 或 https:// 开头）。

    Args:
        file_path (`str`):
            要读取的文件路径（相对于项目根目录）

    Returns:
        `ToolResponse`:
            提取到的URL列表，每行一个URL及其来源信息
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 使用正则表达式提取所有 URL
        url_pattern = r'https?://[^\s\)\]]+'
        urls = re.findall(url_pattern, content)

        if not urls:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"在文件 {file_path} 中未找到任何URL链接。",
                    ),
                ],
            )

        # 构建结果文本，保留原始上下文信息
        result_lines = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            for url in urls:
                if url in line:
                    result_lines.append(f"行 {i}: {url}")

        result_text = f"从文件 {file_path} 中提取到 {len(urls)} 个URL链接：\n\n" + "\n".join(result_lines)

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=result_text,
                ),
            ],
        )
    except FileNotFoundError:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"文件 {file_path} 不存在，请检查文件路径是否正确。",
                ),
            ],
        )
    except Exception as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"读取文件时发生错误：{str(e)}",
                ),
            ],
        )


def generate_article(source_dir: str = "saved/full_content", output_dir: str = "saved") -> ToolResponse:
    """根据指定目录下的txt文件生成学术论文。

    该工具会读取指定目录中的所有txt文件，进行学术段落重写和去AI化处理，
    最终生成一篇符合学术规范的论文文本。

    Args:
        source_dir (`str`):
            包含待处理txt文件的目录路径，默认为 "saved/full_content"
        output_dir (`str`):
            输出目录路径，最终论文将保存到该目录下的 final_paper.txt，默认为 "saved"

    Returns:
        `ToolResponse`:
            处理结果，包含处理状态、输出路径和摘要信息
    """

    # ==================== 辅助函数 ====================

    def read_txt_files(directory: str) -> str:
        """读取指定目录下的所有txt文件并合并内容"""
        combined_content = []

        if not os.path.exists(directory):
            print(f"错误：目录 {directory} 不存在")
            return ""

        txt_files = [f for f in os.listdir(directory) if f.endswith('.txt')]

        if not txt_files:
            print(f"警告：目录 {directory} 中没有找到txt文件")
            return ""

        txt_files.sort()

        print(f"找到 {len(txt_files)} 个txt文件：")
        for txt_file in txt_files:
            print(f"  - {txt_file}")

        for txt_file in txt_files:
            file_path = os.path.join(directory, txt_file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    combined_content.append(f"\n\n{'='*60}\n")
                    combined_content.append(f"【文件名：{txt_file}】\n")
                    combined_content.append(f"{'='*60}\n\n")
                    combined_content.append(content)
            except Exception as e:
                print(f"读取文件 {txt_file} 时出错：{e}")

        return ''.join(combined_content)

    def call_llm_with_refinement(content: str) -> tuple[str, str]:
        """调用LLM进行学术段落重写"""
        user_message = _ACADEMIC_EDITOR_PROMPT + "\n" + content

        completion = _openai_client.chat.completions.create(
            model="kimi-k2.5",
            messages=[{"role": "user", "content": user_message}],
            extra_body={"enable_thinking": True},
            stream=True,
        )

        reasoning_content = ""
        answer_content = ""
        is_answering = False

        print("\n" + "=" * 60)
        print("思考过程（Reasoning Process）")
        print("=" * 60 + "\n")

        for chunk in completion:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                    if not is_answering:
                        print(delta.reasoning_content, end="", flush=True)
                    reasoning_content += delta.reasoning_content
                if hasattr(delta, "content") and delta.content:
                    if not is_answering:
                        print("\n" + "=" * 60)
                        print("完整回复（Complete Response）")
                        print("=" * 60 + "\n")
                        is_answering = True
                    print(delta.content, end="", flush=True)
                    answer_content += delta.content

        print("\n" + "=" * 60)
        print("处理完成")
        print("=" * 60 + "\n")

        return reasoning_content, answer_content

    def extract_refined_text(answer_content: str) -> str:
        """从LLM回复中提取Part 1 [Refined Text]的内容"""
        part1_start = answer_content.find("Part 1 [Refined Text]")

        if part1_start == -1:
            part1_start = answer_content.find("[Refined Text]")

        if part1_start == -1:
            return answer_content.strip()

        content_start = answer_content.find("\n", part1_start)
        if content_start == -1:
            content_start = part1_start + len("Part 1 [Refined Text]")
        else:
            content_start += 1

        part2_start = answer_content.find("Part 2 [Logic flow]", content_start)

        if part2_start != -1:
            refined_text = answer_content[content_start:part2_start].strip()
        else:
            refined_text = answer_content[content_start:].strip()

        return refined_text

    def extract_final_paper(answer_content: str) -> str:
        """从去AI化处理的回复中提取Part 1 [Paper]的内容"""
        part1_start = answer_content.find("Part 1 [Paper]")

        if part1_start == -1:
            part1_start = answer_content.find("[Paper]")

        if part1_start == -1:
            return answer_content.strip()

        content_start = answer_content.find("\n", part1_start)
        if content_start == -1:
            content_start = part1_start + len("Part 1 [Paper]")
        else:
            content_start += 1

        part2_start = answer_content.find("Part 2 [Modification Log]", content_start)

        if part2_start != -1:
            final_paper = answer_content[content_start:part2_start].strip()
        else:
            final_paper = answer_content[content_start:].strip()

        return final_paper

    def call_llm_with_de_ai(content: str) -> tuple[str, str]:
        """调用LLM进行去AI化处理"""
        user_message = _DE_AI_PROMPT + "\n" + content

        completion = _openai_client.chat.completions.create(
            model="kimi-k2.5",
            messages=[{"role": "user", "content": user_message}],
            extra_body={"enable_thinking": True},
            stream=True,
        )

        reasoning_content = ""
        answer_content = ""
        is_answering = False

        print("\n" + "=" * 60)
        print("去AI化处理 - 思考过程")
        print("=" * 60 + "\n")

        for chunk in completion:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                    if not is_answering:
                        print(delta.reasoning_content, end="", flush=True)
                    reasoning_content += delta.reasoning_content
                if hasattr(delta, "content") and delta.content:
                    if not is_answering:
                        print("\n" + "=" * 60)
                        print("去AI化处理 - 完整回复")
                        print("=" * 60 + "\n")
                        is_answering = True
                    print(delta.content, end="", flush=True)
                    answer_content += delta.content

        print("\n" + "=" * 60)
        print("去AI化处理完成")
        print("=" * 60 + "\n")

        return reasoning_content, answer_content

    def save_output(reasoning_content: str, answer_content: str, de_ai_reasoning: str,
                    de_ai_answer: str, refined_text: str, final_paper: str) -> None:
        """保存所有处理结果到文件"""
        os.makedirs(output_dir, exist_ok=True)
        full_content_dir = os.path.join(output_dir, "full_content")
        os.makedirs(full_content_dir, exist_ok=True)

        reasoning_file = os.path.join(full_content_dir, "reasoning_process.txt")
        with open(reasoning_file, 'w', encoding='utf-8') as f:
            f.write(reasoning_content)
        print(f"第一次思考过程已保存到：{reasoning_file}")

        answer_file = os.path.join(full_content_dir, "refined_paragraph.txt")
        with open(answer_file, 'w', encoding='utf-8') as f:
            f.write(answer_content)
        print(f"第一次重写后的段落已保存到：{answer_file}")

        refined_text_file = os.path.join(full_content_dir, "extracted_refined_text.txt")
        with open(refined_text_file, 'w', encoding='utf-8') as f:
            f.write(refined_text)
        print(f"提取的Refined Text已保存到：{refined_text_file}")

        de_ai_reasoning_file = os.path.join(full_content_dir, "de_ai_reasoning_process.txt")
        with open(de_ai_reasoning_file, 'w', encoding='utf-8') as f:
            f.write(de_ai_reasoning)
        print(f"去AI化思考过程已保存到：{de_ai_reasoning_file}")

        de_ai_answer_file = os.path.join(full_content_dir, "de_ai_result.txt")
        with open(de_ai_answer_file, 'w', encoding='utf-8') as f:
            f.write(de_ai_answer)
        print(f"去AI化处理结果已保存到：{de_ai_answer_file}")

        final_paper_file = os.path.join(output_dir, "final_paper.txt")
        with open(final_paper_file, 'w', encoding='utf-8') as f:
            f.write(final_paper)
        print(f"最终论文文本已保存到：{final_paper_file}")

    # ==================== 主函数体 ====================

    try:
        result_text = f"开始生成论文...\n"
        result_text += f"源目录: {source_dir}\n"
        result_text += f"输出目录: {output_dir}\n\n"

        # 检查源目录是否存在
        if not os.path.exists(source_dir):
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"错误：源目录 {source_dir} 不存在，无法生成论文。",
                    ),
                ],
            )

        # 读取txt文件
        combined_content = read_txt_files(source_dir)

        if not combined_content:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"错误：目录 {source_dir} 中没有找到有效内容，无法生成论文。",
                    ),
                ],
            )

        result_text += f"✓ 已读取 {len(combined_content)} 字符的内容\n\n"

        # 第一步：学术段落重写
        result_text += "第一步：学术段落重写...\n"
        reasoning_content, answer_content = call_llm_with_refinement(combined_content)

        # 提取Part 1 [Refined Text]的内容
        refined_text = extract_refined_text(answer_content)
        result_text += f"✓ 重写完成，提取了 {len(refined_text)} 字符的文本\n\n"

        # 第二步：去AI化处理
        result_text += "第二步：去AI化处理...\n"
        de_ai_reasoning, de_ai_answer = call_llm_with_de_ai(refined_text)

        # 提取最终的Paper内容
        final_paper = extract_final_paper(de_ai_answer)
        result_text += f"✓ 去AI化完成，最终论文 {len(final_paper)} 字符\n\n"

        # 保存所有结果
        save_output(
            reasoning_content,
            answer_content,
            de_ai_reasoning,
            de_ai_answer,
            refined_text,
            final_paper
        )

        final_paper_path = os.path.join(output_dir, "final_paper.txt")
        result_text += f"✓ 论文生成完成！\n"
        result_text += f"最终论文已保存到: {final_paper_path}\n"
        result_text += f"字数: {len(final_paper)}\n\n"
        result_text += "="*60 + "\n"
        result_text += "论文预览（前500字）:\n"
        result_text += "="*60 + "\n"
        result_text += final_paper[:500]
        if len(final_paper) > 500:
            result_text += "..."

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=result_text,
                ),
            ],
        )

    except Exception as e:
        error_msg = f"生成论文时发生错误：{str(e)}\n\n"
        error_msg += f"请检查：\n1. 源目录 {source_dir} 是否存在且包含txt文件\n2. OpenAI API配置是否正确\n3. 网络连接是否正常"
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=error_msg,
                ),
            ],
        )


def generate_title(file_path: str = "saved/final_paper.txt", output_dir: str = "saved") -> ToolResponse:
    """为论文生成5个公众号爆款标题。

    该工具会读取指定路径的论文文件，调用LLM生成5个不同风格的简洁、有吸引力的公众号爆款标题，
    并将标题保存到指定目录。

    Args:
        file_path (`str`):
            论文文件路径，默认为 "saved/final_paper.txt"
        output_dir (`str`):
            输出目录路径，标题将保存到该目录下的 final_paper_titles.txt，默认为 "saved"

    Returns:
        `ToolResponse`:
            生成结果，包含5个标题内容、保存路径和生成摘要信息
    """

    # 公众号爆款标题生成提示词
    TITLE_GENERATION_PROMPT = """# Role
你是一位资深的公众号运营专家和爆款文案写手，擅长创作吸睛、具有传播力的公众号标题。你深刻理解读者的心理需求，能够准确抓住文章核心价值并提炼出吸引眼球的标题。

# Task
请根据提供的【文章内容】，生成5个不同风格的公众号爆款标题。

# Constraints
1. 标题要求：
   - 必须生成5个标题
   - 每个标题简洁明了
   - 具有吸引力和传播力，能够激发读者阅读兴趣
   - 突出文章的核心价值或亮点
   - 语言生动，富有感染力
   - 5个标题应有不同的风格和角度（如：数据型、疑问型、故事型、痛点型、价值型等）

2. 避免以下情况：
   - 过度夸张或虚假宣传
   - 标题与内容严重不符
   - 使用过多的特殊符号或表情

3. 输出格式：
   - 按照以下格式输出，每个标题占一行，前面加上序号：
     1. [标题1]
     2. [标题2]
     3. [标题3]
     4. [标题4]
     5. [标题5]
   - 不要输出 "标题："、"Title:" 等其他前缀
   - 确保输出5个完整的标题

# Input
"""

    def read_paper_content(path: str) -> str:
        """读取论文文件内容"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"文件 {path} 不存在")

        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content

    def call_llm_generate_title(content: str) -> tuple[str, str]:
        """调用LLM生成标题"""
        user_message = TITLE_GENERATION_PROMPT + "\n" + content

        completion = _openai_client.chat.completions.create(
            model="kimi-k2.5",
            messages=[{"role": "user", "content": user_message}],
            extra_body={"enable_thinking": True},
            stream=True,
        )

        reasoning_content = ""
        answer_content = ""
        is_answering = False

        for chunk in completion:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                    reasoning_content += delta.reasoning_content
                if hasattr(delta, "content") and delta.content:
                    answer_content += delta.content

        return reasoning_content, answer_content

    def save_title_to_file(titles: list[str], output_path: str) -> None:
        """保存标题到文件"""
        os.makedirs(output_dir, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, title in enumerate(titles, 1):
                f.write(f"{i}. {title}\n")

    def extract_titles_from_response(answer_content: str) -> list[str]:
        """从LLM回复中提取5个标题"""
        titles = []
        lines = answer_content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            # 匹配序号格式，如 "1. 标题内容" 或 "1)[标题内容]" 等
            match = re.match(r'^\d+[.)\]]?\s*(.+)$', line)
            if match:
                title = match.group(1).strip()
                # 去除可能的前缀标记
                title = re.sub(r'^[\[(【][标题]*[\])]】]?\s*', '', title)
                if title:
                    titles.append(title)
            elif line and not re.match(r'^[#-]+', line) and len(titles) < 5:
                # 如果没有序号前缀且标题数量不足5个，尝试直接使用
                titles.append(line)
        
        # 确保最多返回5个标题
        return titles[:5]

    try:
        result_text = f"开始生成标题...\n"
        result_text += f"论文文件: {file_path}\n"
        result_text += f"输出目录: {output_dir}\n\n"

        # 检查文件是否存在
        if not os.path.exists(file_path):
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"错误：论文文件 {file_path} 不存在，无法生成标题。",
                    ),
                ],
            )

        # 读取论文内容
        content = read_paper_content(file_path)
        result_text += f"✓ 已读取论文内容，共 {len(content)} 字符\n\n"

        # 生成标题
        result_text += "调用LLM生成标题...\n"
        reasoning_content, answer_content = call_llm_generate_title(content)

        # 提取5个标题
        titles = extract_titles_from_response(answer_content)
        result_text += f"✓ 标题生成完成，共生成 {len(titles)} 个标题\n\n"
        
        result_text += "生成的标题：\n"
        result_text += "=" * 60 + "\n"
        for i, title in enumerate(titles, 1):
            result_text += f"{i}. {title}\n"
        result_text += "=" * 60 + "\n\n"

        # 保存标题
        output_path = os.path.join(output_dir, "final_paper_titles.txt")
        save_title_to_file(titles, output_path)
        result_text += f"✓ 标题已保存到: {output_path}\n"

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=result_text,
                ),
            ],
        )

    except FileNotFoundError as e:
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"错误：{str(e)}\n请检查论文文件路径是否正确。",
                ),
            ],
        )
    except Exception as e:
        error_msg = f"生成标题时发生错误：{str(e)}\n\n"
        error_msg += f"请检查：\n1. 论文文件 {file_path} 是否存在\n2. OpenAI API配置是否正确\n3. 网络连接是否正常"
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=error_msg,
                ),
            ],
        )


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除不合法字符。"""
    return re.sub(r'[\\/*?:"<>|]', "_", filename).strip()


def extract_content_from_url(url: str, save_dir: str = "saved") -> ToolResponse:
    """从指定URL提取文章内容并保存到本地文件。

    该函数会使用 Playwright 和 trafilatura 提取网页文章的标题、正文内容和图片，
    并将正文保存为txt文件，图片下载到指定目录。

    Args:
        url (`str`):
            要提取内容的URL地址
        save_dir (`str`):
            保存文件的目录路径，默认为 "saved"

    Returns:
        `ToolResponse`:
            提取结果，包含文章标题、保存路径和提取的内容摘要
    """

    async def _extract_and_save():
        """内部异步函数，执行实际的提取和保存操作。"""
        async with async_playwright() as p:
            # 添加反浏览器自动化检测的启动参数
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process'
                ]
            )

            # 创建新的上下文，添加反检测头部信息
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='zh-CN',
                timezone_id='Asia/Shanghai',
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0'
                }
            )

            # 添加初始化脚本，隐藏 webdriver 属性
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });

                Object.defineProperty(navigator, 'languages', {
                    get: () => ['zh-CN', 'zh', 'en']
                });
            """)

            page = await context.new_page()

            try:
                # 设置更长的超时时间和更完整的等待策略
                await page.goto(url, wait_until="networkidle", timeout=60000)

                # 额外等待，模拟人类行为
                await page.wait_for_timeout(2000)

                html = await page.content()

                # 检查是否有 403 错误页面
                if "403 Forbidden" in html or "WAF" in html:
                    print("⚠️ 检测到 WAF 阻止，尝试等待更长时间...")
                    await page.wait_for_timeout(3000)
                    html = await page.content()

                    # 如果仍然是 403，尝试重新加载
                    if "403 Forbidden" in html or "WAF" in html:
                        print("⚠️ 仍然被阻止，尝试刷新页面...")
                        await page.reload(wait_until="networkidle", timeout=60000)
                        await page.wait_for_timeout(2000)
                        html = await page.content()

                # 尝试等待主要内容区域加载（针对常见网站结构）
                try:
                    await page.wait_for_selector('article, .article, main, .main, .content, #content', timeout=5000)
                except:
                    pass  # 如果没有这些选择器也继续

                html = await page.content()

                # 提取元数据
                meta_extract = trafilatura.extract(
                    html,
                    url=url,
                    with_metadata=True,
                    output_format="json",
                    include_comments=False,
                    include_tables=True,
                    no_fallback=False
                )

                if not meta_extract:
                    return None, None, []

                data = json.loads(meta_extract)
                title = data.get("title", "未命名文章")
                clean_title = sanitize_filename(title)

                # 提取HTML格式内容以获取图片
                html_extract = trafilatura.extract(
                    html,
                    url=url,
                    output_format="html",
                    include_comments=False,
                    include_tables=True,
                    no_fallback=False
                )

                img_urls = []
                if html_extract:
                    soup = BeautifulSoup(html_extract, "html.parser")
                    for img in soup.find_all("img", src=True):
                        src = img["src"]
                        abs_url = urljoin(url, src)
                        if abs_url.startswith(("http://", "https://")):
                            img_urls.append(abs_url)

                return clean_title, data.get("text", ""), img_urls

            except Exception as e:
                raise e
            finally:
                await context.close()
                await browser.close()

    try:
        # 确保保存目录存在
        os.makedirs(save_dir, exist_ok=True)

        # 执行异步提取
        try:
            title, content, img_urls = asyncio.run(_extract_and_save())
        except RuntimeError as e:
            # 处理事件循环相关的错误
            if "This event loop is already running" in str(e):
                # 如果已经在事件循环中，使用 nest_asyncio
                loop = asyncio.get_event_loop()
                title, content, img_urls = loop.run_until_complete(_extract_and_save())
            else:
                raise e

        if not content:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=f"从URL {url} 提取内容失败，未能获取到文章内容。可能原因：\n1. 页面内容为空或无法解析\n2. 网站使用了复杂的反爬虫机制\n3. 页面需要登录才能访问\n建议：检查URL是否可以正常访问，或尝试其他URL。",
                    ),
                ],
            )

        # 保存正文
        txt_path = os.path.join(save_dir, f"{title}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"标题: {title}\n")
            f.write(f"来源: {url}\n")
            f.write("=" * 50 + "\n\n")
            f.write(content)

        result_text = f"✅ 成功从 {url} 提取文章内容\n\n"
        result_text += f"标题: {title}\n"
        result_text += f"正文已保存至: {txt_path}\n"
        result_text += f"内容长度: {len(content)} 字符\n"

        # 下载图片
        if img_urls:
            result_text += f"\n发现 {len(img_urls)} 张图片，开始下载...\n"

            async def download_all_images():
                # 内容类型映射
                CONTENT_TYPE_MAP = {
                    'image/jpeg': '.jpg',
                    'image/jpg': '.jpg',
                    'image/png': '.png',
                    'image/gif': '.gif',
                    'image/webp': '.webp',
                    'image/bmp': '.bmp',
                    'image/svg+xml': '.svg',
                }

                async def download_image(session, img_url, base_name):
                    """下载图片，并根据响应头自动设置正确扩展名。"""
                    try:
                        async with session.get(img_url) as resp:
                            content_type = resp.headers.get('content-type', '').lower()
                            if not content_type.startswith('image/'):
                                return

                            ext = CONTENT_TYPE_MAP.get(content_type, '')
                            if not ext:
                                parsed = urlparse(img_url)
                                original_ext = os.path.splitext(parsed.path)[1]
                                ext = original_ext if original_ext else '.jpg'

                            save_path = f"{base_name}{ext}"

                            # 防止覆盖
                            counter = 1
                            original_save_path = save_path
                            while os.path.exists(save_path):
                                name, ext_ = os.path.splitext(original_save_path)
                                save_path = f"{name}_{counter}{ext_}"
                                counter += 1

                            content = await resp.read()
                            with open(save_path, "wb") as f:
                                f.write(content)

                    except Exception:
                        pass

                connector = aiohttp.TCPConnector(limit=10)
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    tasks = []
                    for i, img_url in enumerate(img_urls, start=1):
                        base_name = os.path.join(save_dir, f"{title}_{i}")
                        tasks.append(download_image(session, img_url, base_name))
                    await asyncio.gather(*tasks)

            asyncio.run(download_all_images())
            result_text += f"图片已保存到 {save_dir} 目录\n"
        else:
            result_text += "\n未发现图片\n"

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=result_text,
                ),
            ],
        )

    except Exception as e:
        error_msg = f"提取URL内容时发生错误：{str(e)}\nURL: {url}\n\n"

        # 提供更详细的错误信息和建议
        if "timeout" in str(e).lower():
            error_msg += "错误类型：超时\n建议：网页加载时间过长，可能是网络问题或网站响应慢，请稍后重试。"
        elif "navigation" in str(e).lower():
            error_msg += "错误类型：导航错误\n建议：页面可能正在重定向或内容动态加载，已增加等待时间，请重试。"
        elif "net::" in str(e).lower():
            error_msg += "错误类型：网络错误\n建议：无法连接到目标网站，请检查URL是否正确或网络连接。"
        else:
            error_msg += "建议：请检查URL是否有效，或该网站可能有访问限制。"

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=error_msg,
                ),
            ],
        )




async def create_worker(
    task_description: str,
) -> AsyncGenerator[ToolResponse, None]:
    """Create a sub-worker to finish the given task.

    Args:
        task_description (`str`):
            The description of the task to be done by the sub-worker, should
            contain all the necessary information, ESPECIALLY the reference sources

    Returns:
        `AsyncGenerator[ToolResponse, None]`:
            An async generator yielding ToolResponse objects.
    """
    toolkit = Toolkit()
    # Basic read/write tools
    toolkit.register_tool_function(write_text_file)
    toolkit.register_tool_function(insert_text_file)
    toolkit.register_tool_function(view_text_file)

    # Custom tools
    toolkit.register_tool_function(search_online)
    toolkit.register_tool_function(read_urls_from_file)
    toolkit.register_tool_function(extract_content_from_url)
    toolkit.register_tool_function(generate_article)
    toolkit.register_tool_function(generate_title)
    
    
    
    # Create a new sub-agent to finish the given task
    sub_agent = ReActAgent(
        name="Worker",
        sys_prompt=f"""You're an agent named Worker.

                    ## Your Target
                    Your target is to finish the given task with your tools.

                    ## IMPORTANT
                    You MUST use the `{ReActAgent.finish_function_name}` to generate the final answer after finishing the task.
                    You MUST use `search_online` tool as the search engine when you need to perform a web search. If there are reference sources, they MUST be preserved and passed along without being lost during transmission.
                    """,  
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
        
