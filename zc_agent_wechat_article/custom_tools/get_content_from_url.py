import asyncio
import os
import re
import json
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright
import trafilatura
import aiohttp


def sanitize_filename(filename: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", filename).strip()


# 根据 Content-Type 映射扩展名
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
    """下载图片，并根据响应头自动设置正确扩展名"""
    try:
        async with session.get(img_url) as resp:
            content_type = resp.headers.get('content-type', '').lower()
            if not content_type.startswith('image/'):
                print(f"⚠️ 非图片资源（{content_type}）: {img_url}")
                return

            # 确定扩展名
            ext = CONTENT_TYPE_MAP.get(content_type, '')
            if not ext:
                # 尝试从 URL 提取原始扩展名（如 .html）
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
            print(f"✅ 已保存图片: {save_path}")

    except Exception as e:
        print(f"❌ 下载图片出错: {e} - {img_url}")


async def extract_article_content(url: str, headless: bool = True):
    async with async_playwright() as p:
        # 添加更多浏览器选项来避免被检测
        browser = await p.chromium.launch(
            headless=headless,
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
            print(f"正在加载页面: {url}")
            await page.goto(
                url,
                wait_until="networkidle",
                timeout=60000
            )
            
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
                return "", "", []

            data = json.loads(meta_extract)
            title = data.get("title", "未命名文章")
            clean_title = sanitize_filename(title)

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
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_extract, "html.parser")
                for img in soup.find_all("img", src=True):
                    src = img["src"]
                    abs_url = urljoin(url, src)
                    if abs_url.startswith(("http://", "https://")):
                        img_urls.append(abs_url)

            return clean_title, data.get("text", ""), img_urls

        except Exception as e:
            print(f"❌ 提取失败: {e}")
            return "", "", []
        finally:
            await context.close()
            await browser.close()


async def main():
    url = "https://blog.csdn.net/m0_48891301/article/details/157393845"

    title, content, img_urls = await extract_article_content(url, headless=True)

    if not content:
        print("❌ 未能提取文章内容")
        return

    print("✅ 文章内容提取成功！\n")
    print("=" * 50)
    print(content[:1000] + "..." if len(content) > 1000 else content)
    print("=" * 50)

    # 保存正文
    txt_path = f"{title}.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n📄 正文已保存至: {txt_path}")

    # 下载正文中的图片（包括 .html 结尾的）
    if img_urls:
        print(f"\n🖼️ 发现 {len(img_urls)} 张正文图片，开始下载...")
        connector = aiohttp.TCPConnector(limit=10)
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = []
            for i, img_url in enumerate(img_urls, start=1):
                base_name = f"{title}_{i}"
                tasks.append(download_image(session, img_url, base_name))
            await asyncio.gather(*tasks)
    else:
        print("\n🖼️ 正文中未发现图片")


if __name__ == "__main__":
    asyncio.run(main())