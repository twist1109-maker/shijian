# GitHub参考与改进说明

调研日期：2026-11-13。仅参考公开的业务设计与工程思路；本轮没有复制这些仓库的代码，也没有引入它们的框架依赖。

## 1. Marketing Content Generator
项目：https://github.com/uyanga-gb/marketing-content-generator

实际阅读：
- README：营销需求收集、渠道规划、内容生成、校验与反馈修改。
- [validation_agent.py](https://github.com/uyanga-gb/marketing-content-generator/blob/2ebec8489004eb8ffb3021512ef18fa9a96d98c7/backend/agents/validation_agent.py)：渠道规则、错误与提示分开、结果包组织。
- [refinement_agent.py](https://github.com/uyanga-gb/marketing-content-generator/blob/2ebec8489004eb8ffb3021512ef18fa9a96d98c7/backend/agents/refinement_agent.py)：结合当前正文和用户反馈修改，保留历史。

落地到本项目：微信公众号/小红书/电商详情页的教学渠道建议；价格、销量、篇幅等规则分级；质量与依据页；将上一保存版本和最近退回意见提供给真实模型。

没有照搬多Agent、Claude、AWS与生图流水线。实训只要求两个业务工具与一个可运行闭环，当前保持Python标准库+SQLite+单个模型工具循环。

许可证说明：检查根目录LICENSE时返回404，不能据此断言仓库没有其他形式许可；本项目未复制其代码或素材。

## 2. OpenAI Agents SDK for Python
项目：https://github.com/openai/openai-agents-python

实际阅读：
- README：Agent、tools、tracing、human-in-the-loop。
- [tools.py](https://github.com/openai/openai-agents-python/blob/main/examples/basic/tools.py)，阅读时blob SHA：3a465bb7057d69a37fa7e64ff22ae5036d71bce0。
- [trace_redaction.py](https://github.com/openai/openai-agents-python/blob/main/examples/basic/trace_redaction.py)，阅读时blob SHA：33beb1931c551a289533542b6e6da841701657cc。
- LICENSE：MIT，Copyright (c) 2025 OpenAI。

落地到本项目：模型按结构化schema选择工具，执行结果回传；次数/时间受限；可按任务关联工具记录；导出证据时屏蔽密钥；后端业务权限独立于模型。

没有安装或复制SDK。本项目采用兼容Chat Completions的HTTP接口，自行实现最小工具循环，兼容DeepSeek与OpenAI。

## 3. 未采用的搜索结果
检索过LangGraph人工介入示例。其中一个仓库README仅含一行项目名，没有足够说明，不作为本轮实现依据。未把搜索到的所有项目都宣称为已深入学习。

## 本项目来源
需求依据：用户提供的实训任务书与课程记录。代码由AI辅助编写和测试；样例书目、作者、文字与示意封面为教学模拟。学生应如实填写需求确认、资料核对、配置、运行、测试与展示等本人实际工作。
