# 0303 · 实战：本地 Markdown 知识库

> 目标：用 Resource 暴露原文、Tool 做检索、Prompt 固定回答格式，做一个零依赖的 RAG 基线。
> 难度 ★★★ ｜ 前置：0105 0106 0109 ｜ 依赖：无 ｜ 端口：无 ｜ 预计：35 分钟

## 1. 你会学到

- 同一个知识库，为什么三者都要：Resource（原文）、Tool（检索）、Prompt（回答格式）。
- 一个可解释的检索基线：标题命中加权 + 正文词频，不引入向量库。
- 检索结果必须带 `source`，否则模型无法给出可核验的引用。
- 资源模板的路径安全与文件名白名单。

## 2. 先跑起来

```bash
cd 0303-docs-kb
uv run python client.py
```

预期输出（截断）：

```text
--- 知识库目录 ---
  tool-design: FastMCP 工具设计 (238 字)
  resource-vs-prompt: 资源与提示的分工 (...)
  transports: 传输与协议 (...)
  security: 安全清单 (...)

--- search('工具设计') ---
  [23] FastMCP 工具设计 → kb://tool-design
      # FastMCP 工具设计
  [2] 资源与提示的分工 → kb://resource-vs-prompt

--- search('路径穿越') ---
  [3] 安全清单 → kb://security
      - 资源模板必须防路径穿越。

--- 回答模板 ---
请先调用 search 工具检索：如何做资源路径安全？（limit=3）。
然后只根据检索结果回答，每个结论后用 [来源](kb://文件名) 标注出处。
```

```bash
uv run pytest . -q
# 5 passed
```

## 3. 代码地图

| 文件 | 作用 |
|---|---|
| `server.py` | 启动时加载 4 篇 Markdown；检索、索引、原文、提示 |
| `data/*.md` | 语料；改这里就能观察检索结果变化 |
| `client.py` | 目录 → 三次检索 → 读原文 → 渲染提示 |
| `test_server.py` | 索引、排序、limit 校验、路径安全、提示内容 |

## 4. 三元组各司其职

| 原语 | 本例实现 | 为什么 |
|---|---|---|
| Resource | `kb://index`、`kb://{name}` | 原文可缓存、可被引用、体积大 |
| Tool | `search(query, limit)` | 有计算、有排序、参数由模型填 |
| Prompt | `answer_with_citations` | 固定「先检索、再回答、带出处」的流程 |

只给 Tool 会丢掉原文引用；只给 Resource 模型不会检索；只给 Prompt 没有数据支撑。**三者组合才是可用的知识库。**

## 5. 检索基线

```python
title_hits = sum(1 for term in terms if term in title.lower())
body_hits = sum(text.lower().count(term) for term in terms)
score = title_hits * 5 + body_hits
```

- 标题命中权重 ×5：标题是最强信号；
- 中文按 2 字滑窗切分，英文按单词；
- 返回 `score` 与 `snippet`，让调用方/模型能判断相关性；
- 不引入向量库：先有一个**可解释、可测试**的基线，再考虑升级。

升级路径：BM25（`rank_bm25`）→ 混合检索 → 向量库。接口保持 `search(query, limit) -> hits` 不变即可。

## 6. 引用与防幻觉

提示模板强制三条：

1. 先调 `search`，不许直接回答；
2. 每个结论后标 `[来源](kb://文件名)`；
3. 检索结果不足时明说「知识库中没有相关信息」。

这比单纯在工具描述里写「请勿编造」有效得多，因为它把流程固化了。

## 7. 路径安全

```python
if "/" in name or "\\" in name or name not in DOCS:
    raise ResourceError(f"文档不存在：{name}")
```

- 文件名白名单比黑名单可靠；
- 模板参数 `{name}` 本身不跨 `/`，但仍要防 `..`、编码变形；
- 读取范围限定在 `DOCS` 字典，根本不碰文件系统。

## 8. 三种验证方式

**client.py**：目录、检索、原文、提示一次看全。

**Inspector**：改 `data/security.md` 加一句话，重启后重新检索，观察排序变化。

**接入宿主**：配置同 0101。在对话里问「资源模板怎么防路径穿越？请给出处」，观察模型是否调用 `search` 并引用 `kb://security`。

## 9. 常见坑

**① 检索结果不带出处**

模型只能给出「根据文档」这种无法核验的回答。`source` 是必填字段。

**② 中文按空格分词**

中文没有空格，必须用 n-gram 或分词器；否则「路径穿越」永远匹配不到。

**③ 把整篇文档塞进工具结果**

上下文瞬间爆炸。只返回 snippet，原文让模型按需读 Resource。

**④ 用 `os.path.join` 拼用户输入**

路径穿越的经典入口。用白名单或 `resolve()` + `is_relative_to()`。

**⑤ 索引在每次调用时重建**

文件多时很慢。启动时加载一次，或用文件 watcher 增量更新。

**⑥ 没有「无结果」分支**

返回空列表时，模型容易编造。提示里明确要求「不足则说不知道」。

## 10. 与 2.x / 3.x 的差异

- 资源模板、`ResourceError` 的用法在 2.x/3.x 基本一致。
- 4.x 默认开启资源路径安全，框架会先拦一层；业务白名单仍不可少。
- `ctx.read_resource` 返回 `ResourceResult` 的结构在 4.x 有调整（见 0107）。
- 完整差异见 [`docs/03-compat.md`](../docs/03-compat.md)。

## 11. 练习

1. 把检索换成 BM25，保持 `search` 的输入输出不变，用现有测试回归。
2. 加一个 `kb://{name}{?max_chars}`，限制返回原文长度，默认 2000 字。
3. 给 `search` 加 `tag` 过滤，标签写在每篇 Markdown 的 front matter 里。
4. 写一个 `answer_offline(question)` 工具，内部完成「检索 + 拼接引用」，不依赖模型。

## 12. 延伸阅读

- FastMCP Resources：<https://gofastmcp.com/docs/servers/resources>
- FastMCP Prompts：<https://gofastmcp.com/docs/servers/prompts>
- BM25 原理：<https://en.wikipedia.org/wiki/Okapi_BM25>
