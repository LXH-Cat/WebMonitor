# WebMonitor

Made by Gemini & 白隐Hakuin


> 一个基于 GitHub Actions 的全自动工具，用于监控一个或多个静态网页的源代码变化。当变化发生时，它会自动保存快照、生成差异报告，并通过 Commit、Webhook 和邮件等多种方式发送通知

## ✨ 功能特性

* **定时自动执行** **: 默认每6小时运行一次，您可以轻松自定义执行计划。**
* **多目标监控** **: 只需在一个文本文件 (**`<span class="selected">urls.txt</span>`) 中维护您想监控的 URL 列表。
* **智能变更检测** **: 高效地通过哈希值比对内容，仅在有变化时才执行操作。**
* **历史快照与差异记录** **: 自动将新旧网页快照和详细的 **`<span class="selected">diff</span>` 报告存入仓库，永久保留变更历史。
* **清晰的日志输出** **: 在 Actions 的运行日志中，使用醒目的通知格式清晰展示每个 URL 的检测结果。**
* **多种通知渠道** **:**
* **GitHub Commits** **: 每次变更都会生成一条带有精确时间戳的提交记录。**
* **Webhook** **:**
  * **支持向****多个**地址推送。
  * **支持自定义推送格式，可轻松集成到飞书、钉钉、企业微信等平台。**
* **邮件通知** **:**
  * **支持向****多个**邮箱地址发送，并保护每个人的隐私。
  * **提供灵活、安全的收件人管理方式。**
  * **采用美观、简洁的 HTML 邮件样式。**
* **内容丰富的通知** **:**
* **通知中包含具体的** **变更内容摘要** **。**
* **提供一个****直达 GitHub 仓库**的链接，方便您在线查看本次变更的完整快照和差异文件。

## 📂 项目结构

```
.
├── .github/
│   └── workflows/
│       └── monitor.yml       # GitHub Action 核心配置文件
├── snapshots/                # 存放网页快照和历史记录（自动生成）
├── monitor.py                # 执行监控任务的 Python 脚本
├── urls.txt                  # 需要监控的网页 URL 列表
└── README.md                 # 本说明文件


```

## 🚀 快速开始

#### 1. 创建 GitHub 仓库

**建议创建一个 ****私有 (Private)** 仓库，以保护您的监控历史和配置信息不被公开访问。

#### 2. 创建项目文件

**将本项目中的 **`<span class="selected">monitor.py</span>`, `<span class="selected">urls.txt</span>`, 和 `<span class="selected">.github/workflows/monitor.yml</span>` 三个文件上传到您的仓库中。

#### 3. 配置监控目标

**编辑 **`<span class="selected">urls.txt</span>` 文件，将您想要监控的每个网页 URL 分行写入。

**示例 `<span class="selected">urls.txt</span>`:**

```
https://www.example.com
https://www.another-website.org/about.html


```

#### 4. 配置通知方式 (推荐)

**前往您的 GitHub 仓库页面，点击 **`<span class="selected">Settings</span>` -> `<span class="selected">Secrets and variables</span>` -> `<span class="selected">Actions</span>`。

**A. 配置密钥 (Secrets) - 用于存放高度敏感信息**

1. **点击 **`<span class="selected">Secrets</span>` 标签页。
2. **点击 **`<span class="selected">New repository secret</span>`，添加以下密钥：
   * `<span class="selected">SMTP_PASSWORD</span>`: 您的发件邮箱密码或 **应用授权码 (强烈推荐)** **。**
   * `<span class="selected">WEBHOOK_URL</span>`: 您的 Webhook 接收地址。 **如有多个，请用英文逗号 (`<span class="selected">,</span>`) 分隔** **。**

**B. 配置变量 (Variables) - 用于存放普通配置，方便修改**

1. **点击 **`<span class="selected">Variables</span>` 标签页。
2. **点击 **`<span class="selected">New repository variable</span>`，添加以下变量：
   * `<span class="selected">MAIL_RECIPIENTS</span>`:  **邮件接收人列表** **。如有多个，请用英文逗号 (**`<span class="selected">,</span>`) 分隔。
   * `<span class="selected">MAIL_FROM</span>`: 您的发件邮箱地址。
   * `<span class="selected">MAIL_SENDER_NAME</span>`: (可选) 发件人昵称，例如 `<span class="selected">监控机器人</span>`。
   * `<span class="selected">SMTP_HOST</span>`: SMTP 服务器地址 (例如: `<span class="selected">smtp.qq.com</span>`)。
   * `<span class="selected">SMTP_PORT</span>`: SMTP 服务器端口 (通常是 `<span class="selected">465</span>` 或 `<span class="selected">587</span>`)。
   * `<span class="selected">SMTP_USER</span>`: 您的发件邮箱用户名。
   * `<span class="selected">WEBHOOK_CUSTOM_PAYLOAD</span>`: (可选) 自定义 Webhook 的 JSON 模板。

**完成以上步骤后，GitHub Action 将会按照 **`<span class="selected">monitor.yml</span>` 中设定的 `<span class="selected">cron</span>` 计划自动运行。您也可以在仓库的 `<span class="selected">Actions</span>` 标签页手动触发一次以进行测试。

## ⚙️ 配置详解

### 自定义执行时间

**您可以编辑 **`<span class="selected">.github/workflows/monitor.yml</span>` 文件来修改 `<span class="selected">cron</span>` 表达式，以调整自动执行的时间。

* **默认值** **: **`<span class="selected">'0 4,10,16,22 * * *'</span>`
* **这对应 ****UTC 时间** 的 04:00, 10:00, 16:00, 22:00。
* **换算成 ****UTC+8 时间**，即每天的  **12:00, 18:00, 00:00, 06:00** **。**
* **您可以使用 **[Crontab Guru](https://crontab.guru/ "null") 这样的工具来轻松生成您想要的 `<span class="selected">cron</span>` 表达式。

### 自定义 Webhook

**通过设置 **`<span class="selected">WEBHOOK_CUSTOM_PAYLOAD</span>` 这个 Variable，您可以完全自定义发送到 Webhook 的 JSON 数据结构。在模板中，以下变量会被自动替换：

* `<span class="selected">{timestamp}</span>`: 变更被检测到的时间 (格式: `<span class="selected">YYYY-MM-DD HH:MM:SS</span>`)。
* `<span class="selected">{changes_summary}</span>`: 本次运行检测到的所有变更的详细信息汇总。

**示例 (用于企业微信的 Markdown 格式):**

```
{
  "msgtype": "markdown",
  "markdown": {
    "content": "## 网页变更监控提醒\n> 检测时间: <font color=\"comment\">{timestamp}</font>\n\n<font color=\"warning\">检测到以下页面发生变更:</font>\n\n{changes_summary}"
  }
}


```

> **注意** **: 如果不设置此变量，默认会发送企业微信兼容的****纯文本**格式消息。

## 🔍 如何工作

1. **定时触发** **: GitHub Actions 根据 **`<span class="selected">monitor.yml</span>` 中的 `<span class="selected">schedule</span>` 定时启动一个虚拟机。
2. **注入配置** **: Action 将您在 **`<span class="selected">Secrets</span>` 和 `<span class="selected">Variables</span>` 中设置的配置项作为环境变量注入到虚拟机中。
3. **运行脚本** **: **`<span class="selected">monitor.py</span>` 脚本被执行。
4. 循环检查: 脚本读取 urls.txt，并对每个 URL 执行以下操作：
   a. 获取当前网页的源代码。
   b. 计算源代码的 SHA-256 哈希值。
   c. 读取本地存储的上一次哈希值。
   d. 比较哈希值:
   * **如果不同** **: 判定为发生变更。脚本会创建带有时间戳的新目录，保存新的网页快照 (**`<span class="selected">snapshot.html</span>`) 和差异文件 (`<span class="selected">diff.txt</span>`)，并更新哈希记录。
   * **如果相同** **: 无操作，继续检查下一个。**
5. 汇总与通知: 如果在本次运行中有任何一个 URL 发生了变化，脚本会：
   a. 生成一份包含所有变更信息的摘要，包括变更内容和GitHub快照链接。
   b. 调用 Webhook 和邮件功能，向所有配置的地址发送通知。
   c. 设置一个输出变量 changes_detected=true 和 commit_message。
6. **提交变更** **: **`<span class="selected">monitor.yml</span>` 中的最后一步会检查这个输出变量。如果为 `<span class="selected">true</span>`，则执行 `<span class="selected">git</span>` 命令，将 `<span class="selected">snapshots</span>` 目录下的所有新文件提交并推送到您的仓库。

## 📜 查看历史

* **Commit 记录** **: 在仓库主页的提交历史中，所有由机器人产生的提交信息都以 **`<span class="selected">【自动监控】</span>` 开头，并附带时间戳。
* **文件浏览器** **: 直接在仓库中浏览 **`<span class="selected">snapshots</span>` 目录。每个被监控的网站都有一个独立的子目录，其中包含了历次变更的详细快照和差异报告。
* **Action 日志** **: 在仓库的 **`<span class="selected">Actions</span>` 标签页，您可以点开每一次运行记录，在日志概要中直接看到每个 URL 的检查结果（"检测到变化" 或 "无变化"）。
