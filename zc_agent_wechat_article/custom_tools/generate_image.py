import os
import requests
from datetime import datetime 
# Install SDK:  pip install 'volcengine-python-sdk[ark]' .
from volcenginesdkarkruntime import Ark


# 读取 saved/final_paper.txt 的内容
paper_file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'saved', 'final_paper.txt')
try:
    with open(paper_file_path, 'r', encoding='utf-8') as f:
        paper_content = f.read()
    print(f"成功读取论文内容，共 {len(paper_content)} 个字符")
except FileNotFoundError:
    print(f"错误：文件 {paper_file_path} 不存在")
    exit(1)
except Exception as e:
    print(f"读取文件时出错：{e}")
    exit(1)

# 构建提示词
system_prompt = """# Role
你是一位世界顶尖的学术插画专家，专注于为计算机视觉与人工智能领域的顶级会议论文（如 CVPR, NeurIPS, ICLR）绘制高质量、直观且美观的论文架构图。

# Task
请阅读我提供的【中文文章】，首先深刻理解其核心机制、模块组成和数据流向。然后，基于你的理解，设计并绘制一张专业、卡通的学术架构图。

# Visual Constraints
1. 风格基调：
   - 多些卡通感、油画感或过度艺术化。
   - 不要只有冷冰冰的文字，多些可爱的图标。

2. 内容与布局：
   - 将理解到的方法论转化为清晰的模块和数据流箭头。
   - 生成图片的内容一定要符合论文逻辑。

3. 文字规范：
   - 图中所有文字必须使用英文。
   - 图中的文字不许出现拼写错误。

4. 【重要！】禁止事项：
   - 不允许文字模糊，错误，扭曲。
   - 不允许生成的图片低分辨率，低画质
   - 不允许图片逻辑与文章逻辑不一致。

# Input Methodology
【中文文章】如下："""

# 将论文内容插入到提示词中
final_prompt = f"{system_prompt}\n\n{paper_content}"


############################ 豆包 ###############################
# 创建客户端
client = Ark(
    # The base URL for model invocation
    base_url="https://ark.prd.aigateway.uaes.com/ailab/api/v3", 
    api_key="AhwogtIs3wlHu6T8", 
)
# 生成图片
print("正在生成图片，请稍候...")
imagesResponse = client.images.generate( 
    # Replace with Model ID
    model="doubao-seedream-4-0-250828",
    prompt=final_prompt,
    size="2K",
    response_format="url",
    watermark=False
) 
print("\n图片生成成功！")
print(f"图片URL: {imagesResponse.data[0].url}")

# 下载图片到 final_paper.txt 的同级目录
image_url = imagesResponse.data[0].url
saved_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'saved')

# 确保保存目录存在
os.makedirs(saved_dir, exist_ok=True)

# 生成图片文件名
image_filename = "final_paper_image.png"
image_save_path = os.path.join(saved_dir, image_filename)

# 下载图片
print(f"\n正在下载图片到: {image_save_path}")
try:
    response = requests.get(image_url, stream=True)
    response.raise_for_status()
    with open(image_save_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"图片下载成功！已保存到: {image_save_path}")
except requests.exceptions.RequestException as e:
    print(f"下载图片时出错：{e}")
    exit(1)
