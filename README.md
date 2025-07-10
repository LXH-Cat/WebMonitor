# WebMonitor

Made by Gemini & 白隐Hakuin

> 一个基于 GitHub Actions 的全自动工具，用于监控一个或多个静态网页的源代码变化。当变化发生时，它会自动保存快照、生成差异报告，并通过 Commit、Webhook 和邮件等多种方式发送通知

## ✨ 功能特性

* **定时自动执行** : 默认每6小时运行一次，无需人工干预。
* **多目标监控** : 只需在一个文本文件中维护您想监控的 URL 列表。
* **智能变更检测** : 高效地通过哈希值比对内容，仅在有变化时才执行操作。
* **历史快照与差异记录** : 自动将新旧网页快照和详细的 `diff` 报告存入仓库，永久保留变更历史。
* **多种通知渠道** :
* **GitHub Commits** : 每次变更都会生成一条清晰的提交记录。
* **Webhook** : 支持自定义推送格式，可轻松集成到飞书、钉钉、Slack、Discord 等平台。
* **邮件通知** : 在发生变更时，向指定邮箱发送提醒邮件。
* **易于部署** : 只需将几个文件放入您的 GitHub 仓库并配置 Secrets 即可。

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

建议创建一个 **私有 (Private)** 仓库，以保护您的监控历史和配置信息不被公开访问。

#### 2. 创建项目文件

将本项目中的 `monitor.py`, `urls.txt`, 和 `.github/workflows/monitor.yml` 三个文件上传到您的仓库中。

#### 3. 配置监控目标

编辑 `urls.txt` 文件，将您想要监控的每个网页 URL 分行写入。

**示例 `urls.txt`:**

```
https://www.example.com
https://www.another-website.org/about.html

```

#### 4. 配置通知方式 (可选)

前往您的 GitHub 仓库页面，点击 `Settings` -> `Secrets and variables` -> `Actions`，然后点击 `New repository secret` 添加以下密钥：

* **Webhook 通知** :
* `WEBHOOK_URL`: 您的 Webhook 接收地址。默认格式为企业微信 Webhook 格式。
* **邮件通知** (如需使用，请**全部**配置):
  * `MAIL_TO`: 您的接收邮箱地址。
  * `MAIL_FROM`: 您用于发送邮件的邮箱地址。
  * `SMTP_HOST`: SMTP 服务器地址 (例如: `smtp.qq.com`)。
  * `SMTP_PORT`: SMTP 服务器端口 (通常是 `465` 或 `587`)。
  * `SMTP_USER`: 您的发件邮箱用户名。
  * `SMTP_PASSWORD`: 您的发件邮箱密码或 **应用授权码 (强烈推荐)** 。
* **自定义 Webhook 格式** (详见下文):
  * `WEBHOOK_CUSTOM_PAYLOAD`: 一个 JSON 格式的字符串模板。

完成以上步骤后，GitHub Action 将会按照 `monitor.yml` 中设定的 `cron` 计划自动运行。您也可以在仓库的 `Actions` 标签页手动触发一次以进行测试。

## ⚙️ 配置详解

### 自定义 Webhook

通过设置 `WEBHOOK_CUSTOM_PAYLOAD` 这个 Secret，您可以完全自定义发送到 Webhook 的 JSON 数据结构。在模板中，以下变量会被自动替换：

* `{timestamp}`: 变更被检测到的时间 (格式: `YYYY-MM-DD HH:MM:SS`)。
* `{changes_summary}`: 本次运行检测到的所有变更的摘要信息。

**示例 (用于飞书机器人):**

```
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": { "tag": "plain_text", "content": "🚨 网页变更监控提醒" },
      "template": "red"
    },
    "elements": [
      { "tag": "div", "text": { "tag": "lark_md", "content": "**检测时间:** {timestamp}" } },
      { "tag": "div", "text": { "tag": "lark_md", "content": "**变更摘要:**\n{changes_summary}" } }
    ]
  }
}

```

## 🔍 如何工作

1. **定时触发** : GitHub Actions 根据 `monitor.yml` 中的 `schedule` 定时启动一个虚拟机。
2. **检出代码** : Action 将您的仓库代码拉取到虚拟机中。
3. **运行脚本** : `monitor.py` 脚本被执行。
4. 循环检查: 脚本读取 urls.txt，并对每个 URL 执行以下操作：
   a. 获取当前网页的源代码。
   b. 计算源代码的 SHA-256 哈希值。
   c. 读取本地存储的上一次哈希值 (snapshots/`<sitename>`/latest.hash)。
   d. 比较哈希值:
   - 如果不同: 判定为发生变更。脚本会创建带有时间戳的新目录，保存新的网页快照 (snapshot.html) 和差异文件 (diff.txt)，并更新 latest.hash。
   - 如果相同: 无操作，检查下一个 URL。
5. 汇总与通知: 如果在本次运行中有任何一个 URL 发生了变化，脚本会：
   a. 生成一份包含所有变更信息的摘要。
   b. 调用 Webhook 和邮件功能发送通知。
   c. 设置一个输出变量 changes_detected=true。
6. **提交变更** : `monitor.yml` 中的最后一步会检查这个输出变量。如果为 `true`，则执行 `git` 命令，将 `snapshots` 目录下的所有新文件提交并推送到您的仓库。

## 📜 查看历史

* **Commit 记录** : 在仓库主页的提交历史中，所有由机器人产生的提交信息都以 `【自动监控】` 开头。
* **文件浏览器** : 直接在仓库中浏览 `snapshots` 目录。每个被监控的网站都有一个独立的子目录，其中包含了历次变更的详细快照和差异报告。
