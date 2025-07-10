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

# --- 配置 ---
SNAPSHOT_DIR = "snapshots"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
TIMEOUT = 30

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
        print(f"获取 {url} 出错: {e}")
        return None

def get_content_hash(content):
    """计算内容的SHA-256哈希值"""
    return hashlib.sha256(content).hexdigest()

def send_webhook_notification(webhook_url, timestamp, summary):
    """发送 Webhook 通知，支持自定义格式"""
    if not webhook_url:
        return

    custom_payload_str = os.environ.get("WEBHOOK_CUSTOM_PAYLOAD")
    
    try:
        if custom_payload_str:
            # 替换模板中的变量
            payload_str = custom_payload_str.replace("{timestamp}", timestamp).replace("{changes_summary}", summary)
            payload = json.loads(payload_str)
        else:
            # 使用默认的简单格式
            payload = {"msg_type": "text", "content": {"text": f"网页变更提醒 时间: {timestamp}\n\n{summary}"}}
        
        requests.post(webhook_url, json=payload, timeout=10)
        print("Webhook 通知已发送。")
    except Exception as e:
        print(f"发送 Webhook 通知失败: {e}")

def send_email_notification(subject, body):
    """发送邮件通知"""
    mail_to = os.environ.get("MAIL_TO")
    if not mail_to:
        print("未配置邮件接收人，跳过邮件通知。")
        return

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = os.environ.get("SMTP_PORT")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    mail_from = os.environ.get("MAIL_FROM")

    if not all([smtp_host, smtp_port, smtp_user, smtp_password, mail_from]):
        print("SMTP 服务器未完全配置，跳过邮件通知。")
        return
    
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = mail_from
    message["To"] = mail_to

    # 同时创建纯文本和HTML版本的邮件内容
    part1 = MIMEText(body, "plain", "utf-8")
    part2 = MIMEText(body.replace("\n", "<br>"), "html", "utf-8")
    message.attach(part1)
    message.attach(part2)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, int(smtp_port), context=context) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(mail_from, mail_to.split(','), message.as_string())
            print("邮件通知发送成功。")
    except Exception as e:
        print(f"发送邮件失败: {e}")

def main():
    """脚本主逻辑函数"""
    if not os.path.exists(SNAPSHOT_DIR):
        os.makedirs(SNAPSHOT_DIR)

    try:
        with open("urls.txt", "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("错误: 未找到 urls.txt 文件。")
        sys.exit(1)

    all_changes_details = []

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
            print(f"检测到 {url} 发生变化")
            
            now = datetime.now()
            timestamp_str = now.strftime("%Y%m%d_%H%M%S")
            
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

            all_changes_details.append(f"URL: {url}\n变更时间: {now.strftime('%Y-%m-%d %H:%M:%S')}\n快照路径: {change_dir}")
        else:
            print(f"未检测到 {url} 发生变化")

    if all_changes_details:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        summary = "\n\n".join(all_changes_details)
        
        print("\n--- 变更摘要 ---")
        print(summary)
        
        # 发送 Webhook
        webhook_url = os.environ.get("WEBHOOK_URL")
        send_webhook_notification(webhook_url, now_str, summary)
        
        # 发送邮件
        email_subject = f"网页变更监控提醒 ({now_str})"
        send_email_notification(email_subject, summary)
        
        # 设置 GitHub Action 输出
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write('changes_detected=true\n')

# 脚本执行入口
if __name__ == "__main__":
    main()
