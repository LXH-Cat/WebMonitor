# WebMonitor

Made by Gemini & 白隐Hakuin

> 一个基于 GitHub Actions 的全自动工具，用于监控一个或多个静态网页的源代码变化。当变化发生时，它会自动保存快照、生成差异报告，并通过 Commit、Webhook 和邮件等多种方式发送通知

## ✨ 核心功能

*   **定时执行**：默认配置为每 6 小时自动运行一次，无需人工干预。支持自定义执行计划（Cron 表达式）。
*   **多目标监控**：通过简洁的 `config.yml` 配置文件，可同时监控：
    *   **网页 URL**：抓取其完整的 HTML 源码。
    *   **API 端点**：通过执行自定义 `curl` 命令获取响应（支持 GET、POST、自定义请求头等复杂场景）。
*   **高效变更检测**：使用哈希值比对内容，仅在检测到实质性差异时触发后续操作（快照保存、通知），减少冗余处理。
*   **统一快照管理**：所有监控目标的快照均按目标 URL（或配置的 `name`）命名并存储于 `snapshots` 目录下，历史记录清晰可查。
*   **多通道通知**：
    *   **GitHub Commits**：每次检测到变更均生成带时间戳的提交记录，永久存档于仓库。
    *   **Webhook**：
        *   支持向多个 Webhook 地址推送通知。
        *   支持完全自定义推送内容的 JSON 格式，便于集成飞书、钉钉、企业微信等平台。
    *   **邮件通知**：
        *   支持向多个收件人发送邮件（为每位收件人单独发送）。
        *   提供灵活的收件人管理方式。
        *   采用简洁的 HTML 邮件格式呈现通知内容。
*   **详细通知内容**：
    *   包含具体的变更内容摘要 (diff)。
    *   提供指向 GitHub 仓库的链接，方便查看完整快照和差异文件。
    *   若配置了 `name`，通知中会同时显示名称和 URL 作为标识。

## 📂 项目结构

```
.
├── .github/
│   └── workflows/
│       └── monitor.yml       # GitHub Actions 工作流配置文件
├── snapshots/                # 存储网页/API 快照及历史记录（自动生成）
├── monitor.py                # 监控任务执行脚本 (Python)
├── config.yml                # 监控目标配置文件
└── README.md                 # 本说明文档

```

## 🚀 快速开始

1.  **创建 GitHub 仓库**
    *   建议创建 **私有 (Private) 仓库** 以保护监控历史和配置隐私。

2.  **上传项目文件**
    *   将 `monitor.py`, `config.yml` 和 `.github/workflows/monitor.yml` 文件上传到您的仓库。

3.  **配置监控目标 (`config.yml`)**
    *   编辑 `config.yml` 文件，添加监控目标。`name` 字段可选，用于备注。

    ```yaml
    # 全局配置 (可选)
    settings:
      email_delay_milliseconds: 1000  # 邮件发送间隔（毫秒），避免频率限制

    # 监控目标列表
    targets:
      - name: "GitHub 状态页"  # 目标备注 (可选)
        type: "url"
        value: "https://www.githubstatus.com/"

      - type: "url"  # 无备注，使用 URL 标识
        value: "https://www.v2ex.com"

      - name: "复杂的 POST 请求示例"
        type: "curl"
        command: |  # 推荐使用 YAML 块样式处理复杂命令
          curl -s -X POST https://httpbin.org/post \
            -H 'Content-Type: application/json' \
            -H 'Referer: https://www.example.com/some-page' \
            -d '{"id": 123, "name": "test"}'
    ```

4.  **配置通知渠道 (GitHub Secrets & Variables)**
    *   在 GitHub 仓库页面，导航至 `Settings > Secrets and variables > Actions`。

    *   **A. 配置 Secrets (敏感信息)**
        *   点击 `Secrets` 标签页 > `New repository secret`。
        *   添加：
            *   `SMTP_PASSWORD`: 发件邮箱密码或应用授权码 (**必需**)。
            *   `WEBHOOK_URL`: Webhook 接收地址 (多个地址用英文逗号 `,` 分隔)。

    *   **B. 配置 Variables (常规配置)**
        *   点击 `Variables` 标签页 > `New repository variable`。
        *   添加：
            *   `MAIL_RECIPIENTS`: 邮件接收人列表 (多个地址用英文逗号 `,` 分隔)。
            *   `MAIL_FROM`: 发件邮箱地址。
            *   `MAIL_SENDER_NAME`: (可选) 发件人显示名称 (e.g., `监控机器人`)。
            *   `SMTP_HOST`: SMTP 服务器地址 (e.g., `smtp.qq.com`)。
            *   `SMTP_PORT`: SMTP 服务器端口 (e.g., `465`, `587`)。
            *   `SMTP_USER`: 发件邮箱用户名 (通常与 `MAIL_FROM` 相同)。
            *   `WEBHOOK_CUSTOM_PAYLOAD`: (可选) 自定义 Webhook JSON 模板。

**完成配置后**，监控任务将按 `monitor.yml` 设定的计划自动运行。您也可以在仓库的 `Actions` 标签页手动触发一次 `monitor` 工作流进行测试。

## ⚙️ 进阶配置

*   **自定义执行计划**
    *   编辑 `.github/workflows/monitor.yml` 文件中的 `schedule.cron` 表达式。
    *   默认值: `'0 4,10,16,22 * * *'` (UTC 时间 04:00, 10:00, 16:00, 22:00 / UTC+8 时间 12:00, 18:00, 00:00, 06:00)。
    *   使用在线工具 (如 [Crontab Guru](https://crontab.guru/)) 生成所需表达式。

*   **自定义 Webhook 载荷**
    *   通过设置 `WEBHOOK_CUSTOM_PAYLOAD` 变量，自定义发送到 Webhook 的 JSON 结构。模板中以下占位符会被替换：
        *   `{timestamp}`: 检测到变更的时间 (`YYYY-MM-DD HH:MM:SS`)。
        *   `{changes_summary}`: 本次运行检测到的所有变更的详细信息汇总。
    *   **示例 (企业微信 Markdown 格式):**
        ```json
        {
          "msgtype": "markdown",
          "markdown": {
            "content": "## 监控提醒\n> 检测时间: <font color=\"comment\">{timestamp}</font>\n\n<font color=\"warning\">检测到以下目标发生变更:</font>\n\n{changes_summary}"
          }
        }
        ```
    *   *注意*：未设置此变量时，默认发送企业微信兼容的纯文本格式消息。

## 🔍 工作原理

1.  **定时触发**：GitHub Actions 根据 `monitor.yml` 中的 `schedule` 在指定时间启动一个 Runner (虚拟机)。
2.  **注入配置**：Runner 加载配置的 Secrets 和 Variables 作为环境变量。
3.  **运行监控脚本**：执行 `monitor.py` 脚本，解析 `config.yml`。
4.  **目标检测循环**：脚本遍历配置的每个目标：
    *   根据 `type` (`url` 或 `curl`) 获取目标当前内容。
    *   计算内容哈希值并与历史记录比较。
5.  **变更处理与通知**：
    *   若检测到变更，保存新快照并生成差异报告。
    *   汇总所有变更信息。
    *   调用配置的 Webhook 和邮件服务发送通知。
    *   设置标志表明有变更发生。
6.  **提交变更**：工作流最后一步检查标志，若为真，则执行 `git commit` 和 `git push`，将 `snapshots` 目录下的新文件提交到仓库。

## 📜 查看历史记录

*   **提交历史 (Commits)**：仓库的提交历史中以 `【自动监控】` 开头的记录均由本工具生成，包含时间戳。
*   **文件快照 (Snapshots)**：直接浏览仓库中的 `snapshots` 目录。每个目标有独立子目录，存储历次变更的快照 (`*.html`/`*.txt`) 和差异报告 (`*.diff`)。
*   **工作流日志 (Actions Logs)**：在仓库的 `Actions` 标签页，查看每次 `monitor` 工作流的运行日志。日志中清晰记录每个目标的检测结果 (`检测到变化` 或 `无变化`)。