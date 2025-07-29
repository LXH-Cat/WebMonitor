import os
import sys
import hashlib
import requests
import difflib
import json
import smtplib
import ssl
import yaml
import subprocess
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr

# --- 配置 ---
SNAPSHOT_DIR = "snapshots"
CONFIG_FILE = "config.yml"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
TIMEOUT = 30
# 通知中显示的最大差异行数
MAX_DIFF_LINES = 30
# 定义时区为 UTC+8
CST_TZ = timezone(timedelta(hours=8))

def get_safe_filename_from_url(url):
    """根据URL生成一个安全的文件名"""
    if not url:
        return None
    try:
        parsed_url = urlparse(url)
        # 结合域名和路径，替换斜杠
        filename = f"{parsed_url.netloc}{parsed_url.path.replace('/', '_')}"
        # 清理文件名中的不安全字符
        safe_filename = "".join(c for c in filename if c.isalnum() or c in ('-', '_', '.')).rstrip()
        # 如果文件名过长，则使用其哈希值
        if len(safe_filename) > 100:
            return hashlib.md5(url.encode('utf-8')).hexdigest()
        return safe_filename
    except Exception as e:
        print(f"::warning::从 URL '{url}' 生成文件名失败: {e}")
        return None

def extract_url_from_curl(command):
    """从 curl 命令中提取主要的目标 URL (通常是第一个)"""
    urls = re.findall(r'https?://[^\s\'"]+', command)
    if urls:
        # 返回第一个匹配到的 URL，这通常是主请求的目标
        return urls[0]
    return None

def fetch_content_from_url(url):
    """从 URL 获取内容, 将 HTTP 错误视为一种内容状态"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        # 不再使用 response.raise_for_status()
        if response.ok: # 检查状态码是否为 2xx
            return response.content
        else:
            # 如果是 4xx 或 5xx 错误，我们将其视为一种"状态"，但不保存页面内容
            # 返回一个独特的字符串来代表这个状态
            error_state_content = f"HTTP Error: {response.status_code} {response.reason}"
            return error_state_content.encode('utf-8')
    except requests.RequestException as e:
        # 对于连接错误等，也视为一种状态
        print(f"::warning::获取 URL '{url}' 出错: {e}")
        error_state_content = f"Connection Error: {type(e).__name__}"
        return error_state_content.encode('utf-8')

def fetch_content_from_curl(command):
    """执行 curl 命令并获取其输出, 将命令失败视为一种内容状态"""
    try:
        # 使用 shell=True 来执行完整的命令字符串
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True, timeout=TIMEOUT)
        return result.stdout.encode('utf-8') # 哈希和保存需要 bytes
    except subprocess.CalledProcessError as e:
        print(f"::warning::执行 curl 命令失败。命令: [{command}], 错误: {e.stderr}")
        # 将命令执行失败视为一种状态
        error_state_content = f"cURL Command Failed with Exit Code {e.returncode}\nError: {e.stderr.strip()}"
        return error_state_content.encode('utf-8')
    except subprocess.TimeoutExpired:
        print(f"::warning::执行 curl 命令超时。命令: [{command}]")
        error_state_content = f"cURL Command Timed Out"
        return error_state_content.encode('utf-8')
    except Exception as e:
        print(f"::error::执行 curl 命令时发生未知错误: {e}")
        error_state_content = f"Unknown cURL Error: {type(e).__name__}"
        return error_state_content.encode('utf-8')

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
                payload_str = custom_payload_str.replace("{timestamp}", timestamp).replace("{changes_summary}", summary)
                payload = json.loads(payload_str)
            else:
                text_content = (f"网页/API 变更监控提醒\n检测时间: {timestamp}\n\n{summary}")
                payload = {"msgtype": "text", "text": {"content": text_content}}
            
            requests.post(url, json=payload, timeout=10)
            print(f"Webhook 通知已发送至: {url}")
        except Exception as e:
            print(f"::error::发送 Webhook 通知至 {url} 失败: {e}")

def send_email_notification(subject, changes_list, recipients):
    """向多个收件人单独发送邮件，保护隐私"""
    if not recipients:
        print("::notice::未配置任何邮件接收人，跳过邮件通知。")
        return

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = os.environ.get("SMTP_PORT")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    mail_from = os.environ.get("MAIL_FROM")
    sender_name = os.environ.get("MAIL_SENDER_NAME")

    if not all([smtp_host, smtp_port, smtp_user, smtp_password, mail_from]):
        print("::notice::SMTP 服务器未完全配置，跳过邮件通知。")
        return
    
    # --- 生成邮件内容 (只需生成一次) ---
    plain_text_parts = []
    for change in changes_list:
        display_name = f"{change['name']} ({change['url']})" if change.get('name') else change['url']
        part = (f"监控目标: {display_name}\n变更时间: {change['timestamp']}\n查看快照: {change['snapshot_url']}\n\n变更内容:\n---\n{change['diff']}\n---")
        plain_text_parts.append(part)
    plain_body = "\n\n".join(plain_text_parts)

    html_content_parts = []
    for change in changes_list:
        display_name = f"{change['name']} <span class='url-display'>({change['url']})</span>" if change.get('name') else f"<a href='{change['url']}' class='link'>{change['url']}</a>"
        diff_html = change['diff'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
        part = f"""
        <div class="change-block">
            <p><strong>监控目标:</strong> {display_name}</p>
            <p><strong>变更时间:</strong> {change['timestamp']}</p>
            <p><strong>查看快照:</strong> <a href="{change['snapshot_url']}" class="link">在 GitHub 上查看</a></p>
            <div class="diff-box">
                <strong class="diff-title">变更内容:</strong>
                {diff_html}
            </div>
        </div>
        """
        html_content_parts.append(part)
    html_body_content = "".join(html_content_parts)

    html_template = f"""
    <!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>{subject}</title><style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; line-height: 1.6; color: #333333; background-color: #f7f8fa; margin: 0; padding: 0; }}
      .container {{ max-width: 680px; margin: 20px auto; padding: 30px; border-radius: 8px; background-color: #ffffff; border: 1px solid #e9e9e9; }}
      .header {{ font-size: 24px; font-weight: 600; color: #2c3e50; margin-bottom: 25px; padding-bottom: 20px; border-bottom: 1px solid #eeeeee; text-align: center; }}
      .change-block {{ margin-bottom: 25px; padding: 20px; border-radius: 6px; border: 1px solid #dfe6e9; border-left: 4px solid #3498db; }}
      .change-block p {{ margin: 0 0 8px; font-size: 14px; color: #555555; }}
      .link {{ color: #3498db; text-decoration: none; }}.link:hover {{ text-decoration: underline; }}
      .url-display {{ color: #7f8c8d; }}
      .diff-box {{ background-color: #fdfdfd; padding: 15px; margin-top: 15px; border-radius: 5px; font-family: 'Courier New', Courier, monospace; font-size: 12px; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word; border: 1px solid #f0f0f0; }}
      .diff-title {{ font-family: -apple-system, sans-serif; display: block; margin-bottom: 10px; font-size: 13px; color: #333; font-weight: 600; }}
      .footer {{ margin-top: 30px; font-size: 12px; text-align: center; color: #999999; }}
    </style></head><body><div class="container"><div class="header">网页/API 变更监控提醒</div><div class="content">{html_body_content}</div><div class="footer"><p>此邮件由 GitHub Actions 自动发送。</p></div></div></body></html>
    """

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, int(smtp_port), context=context) as server:
            server.login(smtp_user, smtp_password)
            for recipient in recipients:
                message = MIMEMultipart("alternative")
                message["Subject"] = Header(subject, 'utf-8')
                if sender_name:
                    message["From"] = formataddr((Header(sender_name, 'utf-8').encode(), mail_from))
                else:
                    message["From"] = mail_from
                message["To"] = recipient
                message.attach(MIMEText(plain_body, "plain", "utf-8"))
                message.attach(MIMEText(html_template, "html", "utf-8"))
                server.sendmail(mail_from, [recipient], message.as_string())
                print(f"邮件已发送至: {recipient}")
            print(f"邮件通知流程完成，共成功发送给 {len(recipients)} 个收件人。")
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
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            targets = config.get("targets", [])
    except FileNotFoundError:
        print(f"::error::错误: 未找到配置文件 {CONFIG_FILE}。")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"::error::错误: 配置文件 {CONFIG_FILE} 格式不正确: {e}")
        sys.exit(1)

    all_changes = []

    for target in targets:
        name = target.get("name") # name 是可选的
        type = target.get("type")
        
        # --- 确定 URL 和内容获取方式 ---
        target_url = None
        content = None
        if type == "url":
            target_url = target.get("value")
            if not target_url:
                print(f"::warning::类型为 'url' 的目标缺少 'value' 字段，已跳过。")
                continue
            content = fetch_content_from_url(target_url)
        elif type == "curl":
            command = target.get("command")
            if not command:
                print(f"::warning::类型为 'curl' 的目标缺少 'command' 字段，已跳过。")
                continue
            target_url = extract_url_from_curl(command)
            if not target_url:
                print(f"::error::无法从 curl 命令中解析出 URL，请检查命令: [{command}]")
                continue
            content = fetch_content_from_curl(command)
        else:
            print(f"::warning::不支持的类型 '{type}'，目标 '{name or '未命名'}' 已跳过。")
            continue

        if content is None:
            # fetch_... 函数现在会返回错误信息的 bytes，所以这里不再需要检查 None
            # 但保留以防未来有其他返回 None 的情况
            print(f"::warning::无法获取目标 '{name or target_url}' 的内容，已跳过。")
            continue
        
        # --- 统一使用 URL 命名文件夹 ---
        safe_name = get_safe_filename_from_url(target_url)
        if not safe_name:
            print(f"::warning::无法为 URL '{target_url}' 生成文件夹名，已跳过。")
            continue

        display_name = name or target_url
        print(f"正在检查 '{display_name}'...")

        url_dir = os.path.join(SNAPSHOT_DIR, safe_name)
        if not os.path.exists(url_dir):
            os.makedirs(url_dir)

        latest_hash_file = os.path.join(url_dir, "latest.hash")
        current_hash = get_content_hash(content)
        
        last_hash = None
        if os.path.exists(latest_hash_file):
            with open(latest_hash_file, "r", encoding="utf-8") as f:
                last_hash = f.read().strip()

        if current_hash != last_hash:
            print(f"::notice title=检测到变化::{display_name}")
            
            now = datetime.now(CST_TZ)
            timestamp_str = now.strftime("%Y%m%d_%H%M%S")
            change_dir = os.path.join(url_dir, timestamp_str)
            os.makedirs(change_dir)
            
            snapshot_filename = "response.txt" # 统一用 txt 保存，因为内容可能是错误信息
            new_snapshot_file = os.path.join(change_dir, snapshot_filename)
            with open(new_snapshot_file, "wb") as f:
                f.write(content)
            
            diff_report_content = "新目标，无历史版本可比较。"
            if last_hash:
                history_dirs = sorted([d for d in os.listdir(url_dir) if os.path.isdir(os.path.join(url_dir, d)) and d != timestamp_str])
                if history_dirs:
                    last_snapshot_dir = os.path.join(url_dir, history_dirs[-1])
                    last_snapshot_path = None
                    # 寻找上一个快照文件，现在统一为 response.txt
                    potential_file = os.path.join(last_snapshot_dir, "response.txt")
                    if os.path.exists(potential_file):
                        last_snapshot_path = potential_file
                    
                    if last_snapshot_path:
                        with open(last_snapshot_path, "r", encoding='utf-8', errors='ignore') as f_old:
                            old_lines = f_old.readlines()
                        # 新文件也可能是错误信息文本，所以用同样的方式读取
                        with open(new_snapshot_file, "r", encoding='utf-8', errors='ignore') as f_new:
                            new_lines = f_new.readlines()
                        diff = difflib.unified_diff(old_lines, new_lines, fromfile='old', tofile='new', lineterm='')
                        diff_report_content = '\n'.join(diff)

            diff_report_file = os.path.join(change_dir, "diff.txt")
            with open(diff_report_file, "w", encoding="utf-8") as f:
                f.write(diff_report_content)
            
            with open(latest_hash_file, "w", encoding="utf-8") as f:
                f.write(current_hash)
            
            snapshot_url = ""
            if repo_full_name:
                snapshot_url = f"https://github.com/{repo_full_name}/tree/main/{change_dir.replace(os.sep, '/')}"
            
            diff_lines = diff_report_content.split('\n')
            truncated_diff = '\n'.join(diff_lines[:MAX_DIFF_LINES])
            if len(diff_lines) > MAX_DIFF_LINES:
                truncated_diff += "\n... (内容已截断，请查看快照链接获取完整差异)"

            all_changes.append({
                "name": name, "url": target_url,
                "timestamp": now.strftime('%Y-%m-%d %H:%M:%S %Z'),
                "snapshot_url": snapshot_url, "diff": truncated_diff
            })
        else:
            print(f"::notice title=无变化::{display_name}")

    if all_changes:
        summary_parts = []
        for change in all_changes:
            display_name = f"{change['name']} ({change['url']})" if change.get('name') else change['url']
            part = (f"监控目标: {display_name}\n变更时间: {change['timestamp']}\n查看快照: {change['snapshot_url']}\n\n变更内容:\n---\n{change['diff']}\n---")
            summary_parts.append(part)
        
        summary_for_webhook = "\n\n".join(summary_parts)
        now_for_notification = datetime.now(CST_TZ)
        now_str = now_for_notification.strftime('%Y-%m-%d %H:%M:%S %Z')
        
        print("\n--- 变更摘要 ---")
        print(summary_for_webhook)
        
        webhook_urls = os.environ.get("WEBHOOK_URL")
        send_webhook_notification(webhook_urls, now_str, summary_for_webhook)
        
        recipients = []
        mail_recipients_var = os.environ.get("MAIL_RECIPIENTS")
        if mail_recipients_var:
            recipients.extend([email.strip() for email in mail_recipients_var.split(',') if email.strip()])
        unique_recipients = sorted(list(set(recipients)))

        email_subject = f"网页/API 变更监控提醒 ({now_str})"
        send_email_notification(email_subject, all_changes, unique_recipients)
        
        now_for_commit = now_for_notification.strftime('%Y-%m-%d %H:%M')
        commit_message = f"【自动监控】内容发生变化 ({now_for_commit})"
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write('changes_detected=true\n')
                f.write(f'commit_message={commit_message}\n')

if __name__ == "__main__":
    main()
