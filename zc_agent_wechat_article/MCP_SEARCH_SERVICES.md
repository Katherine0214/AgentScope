# MCP 搜索服务配置说明

## 概述

本文档说明了 `tool.py` 中配置的各种 MCP 搜索服务，包括哪些需要 API Key，哪些可以免费使用，以及哪些在中国网络环境下可以正常访问。

## 当前启用的服务（适合中国网络环境）

### 1. Browser Tools (Playwright)
- **状态**: ✅ 已启用
- **API Key**: ❌ 不需要
- **中国可用**: ✅ 是
- **功能**: 网页浏览、截图、表单填写等
- **包名**: `@playwright/mcp@latest`

### 2. DuckDuckGo Search
- **状态**: ✅ 已启用（带错误处理）
- **API Key**: ❌ 不需要
- **中国可用**: ⚠️ 可能受限
- **功能**: 免费网页搜索
- **包名**: `@modelcontextprotocol/server-duckduckgo`
- **特点**: 完全免费，无需注册，隐私友好
- **注意**: 在中国可能需要特殊网络环境

### 3. Brave Search
- **状态**: ✅ 已启用（带错误处理）
- **API Key**: ❌ 基础使用不需要
- **中国可用**: ⚠️ 可能受限
- **功能**: 网页搜索
- **包名**: `@modelcontextprotocol/server-brave-search`
- **特点**: 基础功能免费，高级功能可能需要 API Key
- **注意**: 在中国可能需要特殊网络环境

### 4. arXiv Paper Search ⭐ 推荐
- **状态**: ✅ 已启用（带错误处理）
- **API Key**: ❌ 不需要
- **中国可用**: ✅ 是
- **功能**: 学术论文搜索和检索
- **包名**: `@modelcontextprotocol/server-arxiv`
- **特点**:
  - 完全免费，无需注册
  - 在中国可以直接访问
  - 适合搜索计算机科学、物理、数学等领域的论文
  - 可以按标题、作者、摘要等搜索

### 5. Wikipedia ⭐ 推荐
- **状态**: ✅ 已启用（带错误处理）
- **API Key**: ❌ 不需要
- **中国可用**: ✅ 是（通过镜像）
- **功能**: 维基百科知识搜索和文章检索
- **包名**: `@modelcontextprotocol/server-wikipedia`
- **特点**:
  - 完全免费，无需注册
  - 可以访问中文维基百科
  - 适合查询百科知识、概念解释等

### 6. Fetch (HTTP Request) ⭐ 推荐
- **状态**: ✅ 已启用（带错误处理）
- **API Key**: ❌ 不需要
- **中国可用**: ✅ 是
- **功能**: HTTP 请求工具，可以抓取网页内容和调用 API
- **包名**: `@modelcontextprotocol/server-fetch`
- **特点**:
  - 完全免费，无需注册
  - 可以访问任何可达的网站
  - 适合抓取特定网页内容、调用公开 API
  - 在中国网络环境下工作良好

## 已注释的服务（需要 API Key）

### 1. Gaode (高德地图) MCP
- **状态**: 💤 已注释
- **API Key**: ✅ 需要 `GAODE_API_KEY`
- **功能**: 地图服务、地理编码、路线规划、地点搜索
- **获取方式**: 在高德开放平台注册获取

### 2. GitHub MCP
- **状态**: 💤 已注释
- **API Key**: ✅ 需要 `GITHUB_TOKEN`
- **功能**: GitHub 仓库搜索、代码文件检索
- **获取方式**: 在 GitHub 设置中生成 Personal Access Token

## 可选的中文搜索服务（已注释）

以下服务已添加到代码中但被注释掉，您可以根据需要启用它们。这些服务可能需要特定的网络环境或可能不够稳定。

### 1. Bing CN MCP Server
- **状态**: 💤 已注释（可选启用）
- **API Key**: ❌ 不需要
- **功能**: 必应中文搜索
- **包名**: `@slcatwujian/bing-cn-mcp-server`
- **参考**: https://www.modelscope.cn/mcp/servers/slcatwujian/bing-cn-mcp-server
- **启用方法**: 在 `tool.py` 中取消注释相关代码块

### 2. WeChat Search MCP
- **状态**: 💤 已注释（可选启用）
- **API Key**: ❌ 不需要
- **功能**: 微信公众号文章搜索
- **包名**: `weixin_search_mcp`
- **参考**: https://github.com/fancyboi999/weixin_search_mcp
- **启用方法**: 在 `tool.py` 中取消注释相关代码块

### 3. Rednote (小红书) MCP
- **状态**: 💤 已注释（可选启用）
- **API Key**: ❌ 不需要
- **功能**: 小红书内容搜索
- **包名**: `rednote-mcp-server`
- **参考**: https://github.com/JonaFly/RednoteMCP
- **启用方法**: 在 `tool.py` 中取消注释相关代码块

## 如何启用可选服务

1. 打开 `tool.py` 文件
2. 找到对应服务的注释代码块（搜索 "Optional: Chinese Search Services"）
3. 删除代码块前的 `#` 注释符号
4. 保存文件并重新运行程序

## 错误处理机制

所有搜索服务都配置了 try-except 错误处理：
- 如果某个服务连接失败，程序会打印警告信息但继续运行
- 不会因为单个服务失败而导致整个程序崩溃
- 所有成功连接的客户端会在任务结束时自动关闭

## 使用建议（针对中国网络环境）

1. **学术研究**: 使用 arXiv 搜索学术论文，完全免费且在中国可直接访问
2. **知识查询**: 使用 Wikipedia 查询百科知识，支持中文内容
3. **网页抓取**: 使用 Fetch 工具抓取特定网站内容或调用公开 API
4. **网页浏览**: 使用 Browser Tools 进行复杂的网页交互
5. **通用搜索**: DuckDuckGo 和 Brave Search 可能需要特殊网络环境
6. **中文内容**: 可以尝试启用 Bing CN、WeChat Search 或 Rednote（需取消注释）

## 中国网络环境推荐配置

**最佳组合**（已启用）：
- ✅ Browser Tools - 网页浏览
- ✅ arXiv - 学术论文搜索
- ✅ Wikipedia - 百科知识
- ✅ Fetch - HTTP 请求和网页抓取

**可选组合**（需取消注释）：
- Bing CN - 中文搜索
- WeChat Search - 微信公众号文章
- Rednote - 小红书内容

## 使用示例

### 搜索学术论文
```python
# Agent 可以使用 arXiv 工具搜索论文
"搜索关于 transformer 架构的最新论文"
```

### 查询百科知识
```python
# Agent 可以使用 Wikipedia 工具查询知识
"查询人工智能的定义和历史"
```

### 抓取网页内容
```python
# Agent 可以使用 Fetch 工具抓取网页
"抓取 https://example.com 的内容"
```

### 浏览网页
```python
# Agent 可以使用 Browser 工具进行复杂交互
"打开网页并截图"
```

## 故障排查

如果遇到连接错误：
1. 检查网络连接是否正常
2. 确认 Node.js 和 npx 已正确安装
3. 查看错误信息中的具体包名是否正确
4. 尝试手动运行 `npx -y <package-name>` 测试包是否可用
5. 如果某个服务持续失败，可以将其注释掉

## 总结

| 服务名称 | 需要 API Key | 状态 | 中国可用 | 推荐度 |
|---------|-------------|------|---------|--------|
| Browser Tools | ❌ | 已启用 | ✅ | ⭐⭐⭐⭐⭐ |
| **arXiv** | ❌ | 已启用 | ✅ | ⭐⭐⭐⭐⭐ |
| **Wikipedia** | ❌ | 已启用 | ✅ | ⭐⭐⭐⭐⭐ |
| **Fetch** | ❌ | 已启用 | ✅ | ⭐⭐⭐⭐⭐ |
| DuckDuckGo | ❌ | 已启用 | ⚠️ | ⭐⭐⭐ |
| Brave Search | ❌ | 已启用 | ⚠️ | ⭐⭐⭐ |
| Gaode | ✅ | 已注释 | ✅ | ⭐⭐⭐ |
| GitHub | ✅ | 已注释 | ⚠️ | ⭐⭐⭐⭐ |
| Bing CN | ❌ | 已注释 | ✅ | ⭐⭐⭐ |
| WeChat Search | ❌ | 已注释 | ✅ | ⭐⭐⭐ |
| Rednote | ❌ | 已注释 | ✅ | ⭐⭐⭐ |

**图例**：
- ✅ = 完全可用
- ⚠️ = 可能受限或需要特殊网络环境
- ❌ = 不需要
- ✅ = 需要

**针对中国用户的特别推荐**：
1. **arXiv** - 学术论文搜索的最佳选择
2. **Wikipedia** - 百科知识查询的最佳选择
3. **Fetch** - 网页抓取和 API 调用的最佳选择
4. **Browser Tools** - 复杂网页交互的最佳选择
