import os
import sys
import hashlib
import requests
import difflib
import json
import smtplib
import ssl
from datetime import datetime
from urllib.parse import urlparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

# --- 配置 ---
SNAPSHOT_DIR = "snapshots"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
TIMEOUT = 30
# 通知中显示的最大差异行数
MAX_DIFF_LINES = 30

def get_safe_filename(url):
    """根据URL生成一个安全的文件名"""
    parsed_url = urlparse(url)
    filename = f"{parsed_url.netloc}{parsed_url.path.replace('/', '_')}"
    safe_filename = "".join(c for c in filename if c.isalnum() or c in ('-', '_', '.')).rstrip()
    if len(safe_filename) > 100:
        return hashlib.md5(url.encode('utf-8')).hexdigest()
    return safe_filename

def fetch_content(url):
    """获取网页内容"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        # 使用 warning 格式输出错误，使其在日志中更显眼
        print(f"::warning::获取 {url} 出错: {e}")
        return None

def get_content_hash(content):
    """计算内容的SHA-256哈希值"""
    return hashlib.sha256(content).hexdigest()

def send_webhook_notification(webhook_urls_str, timestamp, summary):
    """向多个 Webhook 地址发送通知"""
    if not webhook_urls_str:
        return

    urls = [url.strip() for url in webhook_urls_str.split(',') if url.strip()]
    custom_payload_str = os.environ.get("WEBHOOK_CUSTOM_PAYLOAD")

    for url in urls:
        try:
            if custom_payload_str:
                # 优先使用用户自定义的 payload 模板
                payload_str = custom_payload_str.replace("{timestamp}", timestamp).replace("{changes_summary}", summary)
                payload = json.loads(payload_str)
            else:
                # 默认生成企业微信兼容的 text 格式
                text_content = (
                    f"网页变更监控提醒\n"
                    f"检测时间: {timestamp}\n\n"
                    f"{summary}"
                )
                payload = {
                    "msgtype": "text",
                    "text": {
                        "content": text_content
                    }
                }
            
            requests.post(url, json=payload, timeout=10)
            print(f"Webhook 通知已发送至: {url}")
        except Exception as e:
            print(f"::error::发送 Webhook 通知至 {url} 失败: {e}")

def send_email_notification(subject, changes_list, recipients):
    """向多个收件人发送样式丰富的邮件通知"""
    if not recipients:
        print("::notice::未配置任何邮件接收人，跳过邮件通知。")
        return

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = os.environ.get("SMTP_PORT")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    mail_from = os.environ.get("MAIL_FROM")

    if not all([smtp_host, smtp_port, smtp_user, smtp_password, mail_from]):
        print("::notice::SMTP 服务器未完全配置，跳过邮件通知。")
        return
    
    # --- 生成邮件内容 ---
    # 1. 纯文本版本
    plain_text_parts = []
    for change in changes_list:
        part = (
            f"URL: {change['url']}\n"
            f"变更时间: {change['timestamp']}\n"
            f"查看快照: {change['snapshot_url']}\n\n"
            f"变更内容:\n---\n{change['diff']}\n---"
        )
        plain_text_parts.append(part)
    plain_body = "\n\n".join(plain_text_parts)

    # 2. HTML 版本
    html_content_parts = []
    for change in changes_list:
        # 将换行符转换成 <br> 并对特殊 HTML 字符进行转义
        diff_html = change['diff'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
        part = f"""
        <div style="margin-bottom: 25px; padding-bottom: 20px; border-bottom: 1px solid #eeeeee;">
            <p style="margin: 0 0 5px; font-size: 14px; color: #555555;"><strong>URL:</strong> <a href="{change['url']}" style="color: #007bff; text-decoration: none;">{change['url']}</a></p>
            <p style="margin: 0 0 5px; font-size: 14px; color: #555555;"><strong>变更时间:</strong> {change['timestamp']}</p>
            <p style="margin: 0 0 15px; font-size: 14px; color: #555555;"><strong>查看快照:</strong> <a href="{change['snapshot_url']}" style="color: #007bff; text-decoration: none;">在 GitHub 上查看</a></p>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; font-family: 'Courier New', Courier, monospace; font-size: 12px; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word; border: 1px solid #dee2e6;">
                <strong style="font-family: -apple-system, sans-serif; display: block; margin-bottom: 10px; font-size: 13px; color: #333;">变更内容:</strong>
                {diff_html}
            </div>
        </div>
        """
        html_content_parts.append(part)
    html_body_content = "".join(html_content_parts)

    html_template = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject}</title>
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; line-height: 1.6; color: #333333; background-color: #f4f4f4; margin: 0; padding: 0; }}
      .container {{ max-width: 680px; margin: 20px auto; padding: 25px; border-radius: 8px; background-color: #ffffff; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
      .header {{ font-size: 24px; font-weight: 600; color: #c9302c; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 2px solid #eeeeee; text-align: center; }}
      .footer {{ margin-top: 25px; font-size: 12px; text-align: center; color: #888888; }}
    </style>
    </head>
    <body>
      <div class="container">
        <div class="header">网页变更监控提醒</div>
        <div class="content">
          {html_body_content}
        </div>
        <div class="footer">
          <p>此邮件由 GitHub Actions 自动发送。</p>
        </div>
      </div>
    </body>
    </html>
    """

    # --- 组装邮件 ---
    message = MIMEMultipart("alternative")
    # 使用 Header 类来正确编码所有包含非 ASCII 字符的邮件头
    message["Subject"] = Header(subject, 'utf-8')
    message["From"] = Header(mail_from, 'utf-8')
    message["To"] = Header(", ".join(recipients), 'utf-8')

    message.attach(MIMEText(plain_body, "plain", "utf-8"))
    message.attach(MIMEText(html_template, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, int(smtp_port), context=context) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(mail_from, recipients, message.as_string())
            print(f"邮件通知发送成功，共 {len(recipients)} 个收件人。")
    except Exception as e:
        print(f"::error::发送邮件失败: {e}")

def main():
    """脚本主逻辑函数"""
    repo_full_name = os.environ.get("GITHUB_REPOSITORY")
    if not repo_full_name:
        print("::warning::未找到 GITHUB_REPOSITORY 环境变量，无法生成快照链接。")

    if not os.path.exists(SNAPSHOT_DIR):
        os.makedirs(SNAPSHOT_DIR)

    try:
        with open("urls.txt", "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("::error::错误: 未找到 urls.txt 文件。")
        sys.exit(1)

    all_changes = []

    for url in urls:
        print(f"正在检查 {url}...")
        safe_name = get_safe_filename(url)
        url_dir = os.path.join(SNAPSHOT_DIR, safe_name)
        
        if not os.path.exists(url_dir):
            os.makedirs(url_dir)

        latest_hash_file = os.path.join(url_dir, "latest.hash")
        
        current_content = fetch_content(url)
        if current_content is None:
            continue
        
        current_hash = get_content_hash(current_content)
        
        last_hash = None
        if os.path.exists(latest_hash_file):
            with open(latest_hash_file, "r", encoding="utf-8") as f:
                last_hash = f.read().strip()

        if current_hash != last_hash:
            # 使用带标题的 notice 格式，在 Actions UI 中更清晰
            print(f"::notice title=检测到变化::{url}")
            
            now = datetime.now()
            timestamp_str = now.strftime("%Ym%d_%H%M%S")
            
            change_dir = os.path.join(url_dir, timestamp_str)
            os.makedirs(change_dir)
            
            new_snapshot_file = os.path.join(change_dir, "snapshot.html")
            with open(new_snapshot_file, "wb") as f:
                f.write(current_content)
            
            diff_report_content = "新页面，无历史版本可比较。"
            if last_hash:
                history_dirs = sorted([d for d in os.listdir(url_dir) if os.path.isdir(os.path.join(url_dir, d)) and d != timestamp_str])
                if history_dirs:
                    last_snapshot_dir = os.path.join(url_dir, history_dirs[-1])
                    last_snapshot_file = os.path.join(last_snapshot_dir, "snapshot.html")
                    if os.path.exists(last_snapshot_file):
                        with open(last_snapshot_file, "r", encoding='utf-8', errors='ignore') as f_old:
                            old_lines = f_old.readlines()
                        with open(new_snapshot_file, "r", encoding='utf-8', errors='ignore') as f_new:
                            new_lines = f_new.readlines()
                        diff = difflib.unified_diff(old_lines, new_lines, fromfile='old', tofile='new', lineterm='')
                        diff_report_content = '\n'.join(diff)

            diff_report_file = os.path.join(change_dir, "diff.txt")
            with open(diff_report_file, "w", encoding="utf-8") as f:
                f.write(diff_report_content)
            
            with open(latest_hash_file, "w", encoding="utf-8") as f:
                f.write(current_hash)
            
            # 为通知准备结构化信息
            snapshot_url = ""
            if repo_full_name:
                # 假设默认分支为 main，可以根据需要修改
                snapshot_url = f"https://github.com/{repo_full_name}/tree/main/{change_dir}"
            
            # 截断过长的差异内容
            diff_lines = diff_report_content.split('\n')
            if len(diff_lines) > MAX_DIFF_LINES:
                truncated_diff = '\n'.join(diff_lines[:MAX_DIFF_LINES]) + "\n... (内容已截断，请查看快照链接获取完整差异)"
            else:
                truncated_diff = diff_report_content

            change_info = {
                "url": url,
                "timestamp": now.strftime('%Y-%m-%d %H:%M:%S'),
                "snapshot_url": snapshot_url,
                "diff": truncated_diff
            }
            all_changes.append(change_info)
        else:
            # 使用 notice 格式输出无变化的信息
            print(f"::notice title=无变化::{url}")

    if all_changes:
        # --- 汇总并发送通知 ---
        summary_parts = []
        for change in all_changes:
            part = (
                f"URL: {change['url']}\n"
                f"变更时间: {change['timestamp']}\n"
                f"查看快照: {change['snapshot_url']}\n\n"
                f"变更内容:\n---\n{change['diff']}\n---"
            )
            summary_parts.append(part)
        
        summary_for_webhook = "\n\n".join(summary_parts)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print("\n--- 变更摘要 ---")
        print(summary_for_webhook)
        
        # 发送 Webhook
        webhook_urls = os.environ.get("WEBHOOK_URL")
        send_webhook_notification(webhook_urls, now_str, summary_for_webhook)
        
        # --- 收集邮件收件人 ---
        recipients = []
        # 1. 从 Secret `MAIL_TO` 读取 (兼容旧版)
        mail_to_secret = os.environ.get("MAIL_TO")
        if mail_to_secret:
            recipients.extend([email.strip() for email in mail_to_secret.split(',') if email.strip()])
        
        # 2. 从 Variable `MAIL_RECIPIENTS` 读取 (推荐方式)
        mail_recipients_var = os.environ.get("MAIL_RECIPIENTS")
        if mail_recipients_var:
            recipients.extend([email.strip() for email in mail_recipients_var.split(',') if email.strip()])
        
        # 去除重复的邮箱地址
        unique_recipients = sorted(list(set(recipients)))

        # 发送邮件
        email_subject = f"网页变更监控提醒 ({now_str})"
        send_email_notification(email_subject, all_changes, unique_recipients)
        
        # --- 设置 GitHub Action 输出 ---
        now_for_commit = datetime.now().strftime('%Y-%m-%d %H:%M')
        commit_message = f"【自动监控】网页内容发生变化 ({now_for_commit})"
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write('changes_detected=true\n')
                f.write(f'commit_message={commit_message}\n')

# 脚本执行入口
if __name__ == "__main__":
    main()
