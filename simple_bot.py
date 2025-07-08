#!/usr/bin/env python3
"""
Simple Telegram Email Tester Bot
"""

import json
import asyncio
import logging
import httpx
import os
from email_handler import EmailHandler
from validators import validate_email_list, validate_smtp_config
from config import Config
from domain_manager import DomainManager

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class SimpleTelegramBot:
    def __init__(self, token):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.config = Config()
        self.domain_manager = DomainManager()
        self.user_sessions = {}
        self.user_message_history = {}  # Track messages for cleanup
        self.user_rate_limits = {}  # Rate limiting per user
        self.max_requests_per_minute = 10
        # Start background cleanup task
        asyncio.create_task(self.cleanup_old_messages())

    async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None, auto_delete=True):
        """Send a message to a chat"""
        url = f"{self.api_url}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text
        }
        if parse_mode:
            data["parse_mode"] = parse_mode
        if reply_markup:
            data["reply_markup"] = reply_markup

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data)
            result = response.json()
            
            # Track message for potential cleanup
            if auto_delete and result.get("ok"):
                message_id = result["result"]["message_id"]
                if chat_id not in self.user_message_history:
                    self.user_message_history[chat_id] = []
                self.user_message_history[chat_id].append(message_id)
                
                # Keep only last 2 messages per chat (more aggressive cleanup)
                if len(self.user_message_history[chat_id]) > 2:
                    old_message_id = self.user_message_history[chat_id].pop(0)
                    # Add small delay before deletion
                    asyncio.create_task(self.delete_message_delayed(chat_id, old_message_id, delay=1))
            
            return result

    async def delete_message(self, chat_id, message_id):
        """Delete a message"""
        url = f"{self.api_url}/deleteMessage"
        data = {
            "chat_id": chat_id,
            "message_id": message_id
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=data)
                if response.status_code != 200:
                    logger.debug(f"Failed to delete message {message_id}: {response.text}")
        except Exception as e:
            logger.debug(f"Error deleting message {message_id}: {e}")

    async def delete_message_delayed(self, chat_id, message_id, delay=1.0):
        """Delete a message after a delay"""
        await asyncio.sleep(delay)
        await self.delete_message(chat_id, message_id)

    async def clear_chat_history(self, chat_id):
        """Clear all tracked messages for a chat"""
        if chat_id in self.user_message_history:
            # Delete messages in batches with small delays to avoid rate limits
            for i, message_id in enumerate(self.user_message_history[chat_id]):
                asyncio.create_task(self.delete_message_delayed(chat_id, message_id, delay=float(i * 0.1)))
            self.user_message_history[chat_id] = []

    async def get_updates(self, offset=None):
        """Get updates from Telegram"""
        url = f"{self.api_url}/getUpdates"
        params = {"timeout": 10}
        if offset:
            params["offset"] = offset

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            return response.json()

    async def handle_message(self, message):
        """Handle incoming messages"""
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        user_id = message["from"]["id"]

        # Rate limiting check
        if not self.check_rate_limit(user_id):
            await self.send_message(chat_id, "Too many requests. Please wait a minute.")
            return

        # Handle /start command first (always resets the bot)
        if text.startswith("/start"):
            # Clear any active session when /start is used
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
            await self.clear_chat_history(chat_id)
            await self.send_start_message(chat_id)
            return

        # Check if user has an active session
        if user_id in self.user_sessions:
            await self.handle_session_message(chat_id, text)
            return

        # Handle other commands
        if text.startswith("/help"):
            await self.send_help_message(chat_id)
        elif text.startswith("/test"):
            await self.show_domain_selection(chat_id)
        elif text.startswith("/admin"):
            if self.domain_manager.is_admin(user_id):
                await self.send_admin_panel(chat_id)
            else:
                await self.send_message(chat_id, "Admin access required.")
        elif text.startswith("/domains"):
            await self.send_domains_list(chat_id)
        else:
            await self.send_message(chat_id, "Use /help for commands.")

    async def send_start_message(self, chat_id):
        """Send welcome message"""
        keyboard = [
            [{"text": "🚀 Start Test", "callback_data": "start_test"}],
            [{"text": "📋 View Domains", "callback_data": "view_domains"}],
            [{"text": "ℹ️ Help", "callback_data": "show_help"}]
        ]
        reply_markup = json.dumps({"inline_keyboard": keyboard})
        await self.send_message(chat_id, "Email Tester Bot - Test your SMTP delivery.", reply_markup=reply_markup, auto_delete=False)

    async def send_help_message(self, chat_id):
        """Send help message"""
        message = """Commands: /start /test /domains /admin

Use /test to start email testing.

Expected Format:
server port username password from_email tls_setting recipient_emails...

Example:
smtp.mail.me.com 587 aristoblisdrlevan@icloud.com buoo-nvam-psex-zmaw aristoblisdrlevan@icloud.com true DANW@e-mc7.com
gjunca@aquatherm.lat
ana@specialtyofficeproduct.com

AWS SES Example:
email-smtp.us-east-1.amazonaws.com 587 AKIAIOSFODNN7EXAMPLE secretkey sender@verified.com true recipient@test.com"""
        await self.send_message(chat_id, message, auto_delete=False)

    async def show_domain_selection(self, chat_id):
        """Show domain selection to user"""
        # Clear previous messages
        await self.clear_chat_history(chat_id)
        
        domains = self.domain_manager.get_domains()
        if not domains:
            await self.send_message(chat_id, "No domains available. Contact admin.", auto_delete=False)
            return

        keyboard_buttons = []
        for domain in domains:
            keyboard_buttons.append([{
                "text": f"🔗 {domain['name']}",
                "callback_data": f"domain_{domain['url']}"
            }])

        reply_markup = json.dumps({"inline_keyboard": keyboard_buttons})
        await self.send_message(chat_id, "Choose domain for test link:", reply_markup=reply_markup, auto_delete=True)

    async def send_admin_panel(self, chat_id):
        """Send admin panel"""
        keyboard = [
            [{"text": "➕ Add Domain", "callback_data": "admin_add"}],
            [{"text": "📥 Bulk Import", "callback_data": "admin_bulk"}],
            [{"text": "➖ Remove Domain", "callback_data": "admin_remove"}],
            [{"text": "🗑️ Clear All Domains", "callback_data": "admin_clear_all"}],
            [{"text": "📋 List Domains", "callback_data": "view_domains"}]
        ]
        reply_markup = json.dumps({"inline_keyboard": keyboard})
        await self.send_message(chat_id, "Admin Panel:", reply_markup=reply_markup, auto_delete=True)

    async def handle_callback_query(self, callback_query):
        """Handle inline keyboard button callbacks"""
        chat_id = callback_query["message"]["chat"]["id"]
        user_id = callback_query["from"]["id"]
        data = callback_query["data"]

        await self.answer_callback_query(callback_query["id"])

        if data == "start_test":
            await self.show_domain_selection(chat_id)
        elif data == "view_domains":
            await self.send_domains_list(chat_id)
        elif data == "show_help":
            await self.send_help_message(chat_id)
        elif data.startswith("domain_"):
            domain_url = data.replace("domain_", "")
            await self.start_fast_test(chat_id, domain_url)

        elif data.startswith("admin_"):
            if self.domain_manager.is_admin(user_id):
                await self.handle_admin_action(chat_id, data)
            else:
                await self.send_message(chat_id, "Admin access required.")
        elif data == "confirm_clear_all":
            if self.domain_manager.is_admin(user_id):
                success = self.domain_manager.clear_all_domains()
                if success:
                    await self.send_message(chat_id, "✅ All domains cleared successfully.")
                else:
                    await self.send_message(chat_id, "❌ Failed to clear domains.")
            else:
                await self.send_message(chat_id, "Admin access required.")
        elif data == "cancel_clear":
            await self.send_message(chat_id, "Operation cancelled.")

    async def answer_callback_query(self, callback_query_id):
        """Answer callback query"""
        url = f"{self.api_url}/answerCallbackQuery"
        data = {"callback_query_id": callback_query_id}
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(url, json=data)

    async def start_fast_test(self, chat_id, domain_url):
        """Start fast test with selected domain"""
        # Clear chat for clean experience
        await self.clear_chat_history(chat_id)
        
        user_id = chat_id
        self.user_sessions[user_id] = {
            "step": "smtp_and_emails",
            "domain_url": domain_url
        }
        
        await self.send_message(chat_id, """Enter SMTP details and recipient emails:

Format: server port username password from_email tls_setting recipient_emails...

Sample:
smtp.mail.me.com 587 aristoblisdrlevan@icloud.com buoo-nvam-psex-zmaw aristoblisdrlevan@icloud.com true DANW@e-mc7.com
gjunca@aquatherm.lat
ana@specialtyofficeproduct.com

You can put recipient emails on the same line or separate lines.""", auto_delete=False)

    async def handle_admin_action(self, chat_id, action):
        """Handle admin actions"""
        user_id = chat_id
        if action == "admin_add":
            self.user_sessions[user_id] = {"step": "admin_add_domain"}
            await self.send_message(chat_id, "Send domain in format: name|url")
        elif action == "admin_remove":
            self.user_sessions[user_id] = {"step": "admin_remove_domain"}
            await self.send_message(chat_id, "Send domain URL to remove")
        elif action == "admin_clear_all":
            await self.confirm_clear_all_domains(chat_id)
        elif action == "admin_bulk":
            self.user_sessions[user_id] = {"step": "admin_bulk_domains"}
            await self.send_message(chat_id, "Send domains list (one per line):\nanicul.info\nbernrueda.info\nblogbird.info\n...")

    async def confirm_clear_all_domains(self, chat_id):
        """Confirm clearing all domains"""
        keyboard = [
            [{"text": "🗑️ Yes, Clear All", "callback_data": "confirm_clear_all"}],
            [{"text": "❌ Cancel", "callback_data": "cancel_clear"}]
        ]
        reply_markup = json.dumps({"inline_keyboard": keyboard})
        await self.send_message(chat_id, "⚠️ Delete ALL domains? This cannot be undone.", reply_markup=reply_markup)

    async def handle_session_message(self, chat_id, text):
        """Handle messages during active session"""
        user_id = chat_id
        session = self.user_sessions.get(user_id)
        if not session:
            return
        
        if session["step"] == "smtp_and_emails":
            await self.handle_smtp_and_emails(chat_id, text)
        elif session["step"] == "smtp_config":
            await self.handle_smtp_config(chat_id, text)
        elif session["step"] == "email_list":
            await self.handle_email_list(chat_id, text)
        elif session["step"] == "admin_bulk_domains":
            await self.handle_bulk_domains(chat_id, text)
        elif session["step"] == "admin_add_domain":
            await self.handle_add_domain(chat_id, text)
        elif session["step"] == "admin_remove_domain":
            await self.handle_remove_domain(chat_id, text)

    async def handle_smtp_and_emails(self, chat_id, text):
        """Handle combined SMTP config and email list input"""
        user_id = chat_id
        session = self.user_sessions.get(user_id)
        if not session:
            return

        parsed_result = self.parse_smart_input(text)
        smtp_config = parsed_result['smtp_config']
        emails = parsed_result['emails']
        
        if not smtp_config:
            await self.send_message(chat_id, """❌ Invalid SMTP format.

Expected Format:
server port username password from_email tls_setting recipient_emails...

Example:
smtp.mail.me.com 587 user@icloud.com password user@icloud.com true recipient@test.com

AWS SES Example:
email-smtp.us-east-1.amazonaws.com 587 AKIAIOSFODNN7EXAMPLE secretkey sender@verified.com true recipient@test.com""")
            return
            
        if not emails:
            await self.send_message(chat_id, f"Need 1-5 emails. Found {len(emails) if emails else 0}.")
            return

        session["smtp_config"] = smtp_config
        session["emails"] = emails
        
        # Clear previous input message for clean chat
        await self.clear_chat_history(chat_id)
        await self.send_message(chat_id, f"✅ Test started for {len(emails)} email(s)...", auto_delete=False)
        
        # Send emails asynchronously
        await self.send_test_emails(chat_id, smtp_config, emails, session["domain_url"])
        
        # Clear session
        del self.user_sessions[user_id]

    def parse_smart_input(self, text):
        """Parse various input formats smartly"""
        import re
        
        # Split text into lines for better parsing
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Extract emails using regex from all text
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        
        # Accept 1-5 emails
        if len(emails) < 1 or len(emails) > 5:
            return {
                'smtp_config': None,
                'emails': None
            }
        
        # Find SMTP config line (usually the first line or line without standalone emails)
        smtp_line = None
        for line in lines:
            # Skip lines that are just email addresses
            line_emails = re.findall(email_pattern, line)
            line_without_emails = line
            for email in line_emails:
                line_without_emails = line_without_emails.replace(email, "")
            
            # Check if this line has SMTP config (server, port, username, password)
            words = line_without_emails.split()
            if len(words) >= 3:  # At least server, port, some other info
                smtp_line = line
                break
        
        if not smtp_line:
            # Fallback: use the first line
            smtp_line = lines[0] if lines else text
            
        # Parse SMTP configuration from the line
        words = smtp_line.split()
        
        # Look for server (contains dots, not an email)
        server = None
        for word in words:
            if '.' in word and '@' not in word and not word.isdigit():
                server = word
                break
        
        # Look for port (numeric, common SMTP ports)
        port = None
        for word in words:
            if word.isdigit() and 25 <= int(word) <= 65535:
                port = word
                break
        
        # Find username and from_email by position in the SMTP line
        username = None
        from_email = None
        
        # Look for emails in the SMTP line by position
        email_positions = []
        for i, word in enumerate(words):
            if '@' in word:
                email_positions.append((i, word))
        
        if len(email_positions) >= 2:
            # First email is username, second is from_email
            username = email_positions[0][1]
            from_email = email_positions[1][1]
        elif len(email_positions) == 1:
            # Only one email, use for both
            username = email_positions[0][1]
            from_email = email_positions[0][1]
        
        # Fallback: use first email found anywhere
        if not username and emails:
            username = emails[0]
            from_email = emails[0]
        
        # Find password (word that comes after username)
        password = None
        if username:
            username_index = -1
            for i, word in enumerate(words):
                if word == username:  # Exact match
                    username_index = i
                    break
            
            # Look for password before username (should be the word immediately before the first email)
            if username_index >= 1:
                prev_word = words[username_index - 1]
                # Password should be the word immediately before username
                if '@' not in prev_word and prev_word.lower() not in ['true', 'false', '1', '0'] and not prev_word.isdigit() and '.' not in prev_word:
                    password = prev_word
        
        # Determine TLS setting - default to True, especially for common providers
        tls = True
        if server and ('mail.me.com' in server or 'icloud' in server.lower()):
            tls = True  # iCloud requires TLS
        elif 'gmail' in server.lower() if server else False:
            tls = True  # Gmail requires TLS
        else:
            # Check for explicit TLS setting
            for word in words:
                if word.lower() in ['true', 'false', '1', '0']:
                    tls = word.lower() in ['true', '1']
                    break
        
        # Build SMTP config if we have minimum required fields
        smtp_config = None
        if server and port and username and password:
            smtp_config = {
                "server": server.strip(),
                "port": port.strip(),
                "username": username.strip(),
                "password": password.strip(),
                "from_email": from_email.strip() if from_email else username.strip(),
                "tls": tls
            }
        
        # Filter out SMTP username and from_email from recipient emails
        recipient_emails = []
        for email in emails:
            if smtp_config:
                # Exclude both username and from_email from recipients
                if email != smtp_config.get("username") and email != smtp_config.get("from_email"):
                    recipient_emails.append(email)
            else:
                recipient_emails.append(email)
        
        # If no recipients found, use all emails except SMTP-related ones
        if not recipient_emails and emails:
            if smtp_config:
                smtp_emails_set = {smtp_config.get("username"), smtp_config.get("from_email")}
                recipient_emails = [email for email in emails if email not in smtp_emails_set]
            else:
                recipient_emails = emails
        
        return {
            'smtp_config': smtp_config,
            'emails': recipient_emails
        }

    async def send_test_emails(self, chat_id, smtp_config, emails, domain_url):
        """Send test emails asynchronously"""
        try:
            # Convert config format
            config = {
                'host': smtp_config['server'],
                'port': int(smtp_config['port']),
                'username': smtp_config['username'],
                'password': smtp_config['password'],
                'from_email': smtp_config.get('from_email', smtp_config['username']),
                'use_tls': smtp_config['tls'],
                'use_ssl': False
            }
            
            email_handler = EmailHandler(config, domain_url)
            
            # Test connection first
            await self.send_message(chat_id, "🔄 Testing SMTP connection...")
            connection_result = await email_handler.test_connection()
            if not connection_result['success']:
                error_msg = connection_result['error']
                if 'amazonaws.com' in smtp_config['server'] and 'Authentication' in error_msg:
                    await self.send_message(chat_id, f"""❌ AWS SES Authentication Failed

Common fixes:
1. Verify your SMTP credentials in AWS SES console
2. Ensure sender email ({smtp_config.get('from_email', smtp_config['username'])}) is verified in AWS SES
3. Check if you're using correct SMTP username/password (not AWS Access Keys)
4. Verify your AWS region matches the SMTP endpoint

Error: {error_msg}""")
                else:
                    await self.send_message(chat_id, f"❌ Connection failed: {error_msg}")
                return
            
            await self.send_message(chat_id, "✅ SMTP connection successful!")
            
            # Send emails
            result = await email_handler.send_test_emails(emails)
            
            # Report results
            successful = result['successful']
            failed = result['failed']
            
            if successful:
                await self.send_message(chat_id, f"✅ Successfully sent to {len(successful)} email(s)")
            
            if failed:
                await self.send_message(chat_id, f"❌ Failed to send to {len(failed)} email(s)")
                
        except Exception as e:
            await self.send_message(chat_id, f"❌ Error: {str(e)}")

    def check_rate_limit(self, user_id):
        """Check if user is within rate limits"""
        import time
        current_time = time.time()
        
        if user_id not in self.user_rate_limits:
            self.user_rate_limits[user_id] = []
        
        # Remove old requests (older than 1 minute)
        self.user_rate_limits[user_id] = [
            req_time for req_time in self.user_rate_limits[user_id] 
            if current_time - req_time < 60
        ]
        
        # Check if user has exceeded limit
        if len(self.user_rate_limits[user_id]) >= self.max_requests_per_minute:
            return False
        
        # Add current request
        self.user_rate_limits[user_id].append(current_time)
        return True

    async def cleanup_old_messages(self):
        """Background task to cleanup old messages periodically"""
        while True:
            try:
                await asyncio.sleep(30)  # Run every 30 seconds
                for chat_id in list(self.user_message_history.keys()):
                    if len(self.user_message_history[chat_id]) > 5:
                        # Keep only the last 2 messages
                        messages_to_delete = self.user_message_history[chat_id][:-2]
                        self.user_message_history[chat_id] = self.user_message_history[chat_id][-2:]
                        
                        # Delete old messages
                        for message_id in messages_to_delete:
                            await self.delete_message(chat_id, message_id)
                            await asyncio.sleep(0.1)  # Small delay between deletions
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)


    async def handle_smtp_config(self, chat_id, text):
        """Handle SMTP configuration"""
        user_id = chat_id
        session = self.user_sessions.get(user_id)
        if not session:
            return

        # Use smart parsing for SMTP config
        parsed_result = self.parse_smart_input(text)
        if not parsed_result['smtp_config']:
            await self.send_message(chat_id, """❌ Invalid SMTP format.

Expected Format:
server port username password from_email tls_setting recipient_emails...

Example:
smtp.mail.me.com 587 user@icloud.com password user@icloud.com true recipient@test.com

AWS SES Example:
email-smtp.us-east-1.amazonaws.com 587 AKIAIOSFODNN7EXAMPLE secretkey sender@verified.com true recipient@test.com""")
            return
            
        session["smtp_config"] = parsed_result['smtp_config']
        session["step"] = "email_list"
        await self.send_message(chat_id, "Enter exactly 5 email addresses (comma-separated):")

    async def handle_email_list(self, chat_id, text):
        """Handle email list input"""
        user_id = chat_id
        session = self.user_sessions.get(user_id)
        if not session:
            return

        emails = [email.strip() for email in text.split(",")]
        if len(emails) != 5:
            await self.send_message(chat_id, f"Please enter exactly 5 emails. You entered {len(emails)}.")
            return
            
        await self.send_message(chat_id, "Test started for 5 emails...")
        
        # Clear session
        del self.user_sessions[user_id]

    async def send_domains_list(self, chat_id):
        """Send list of domains"""
        domains = self.domain_manager.get_domains()
        if not domains:
            await self.send_message(chat_id, "No domains configured.")
            return

        message = "Available Domains:\n"
        for i, domain in enumerate(domains, 1):
            message += f"{i}. {domain['name']}\n"
        await self.send_message(chat_id, message, auto_delete=True)

    async def handle_bulk_domains(self, chat_id, domain_list):
        """Handle bulk domain import"""
        user_id = chat_id
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        
        result = self.domain_manager.add_bulk_domains(domain_list)
        
        if result["success"]:
            message = f"✅ Bulk import complete!\n"
            message += f"Added: {len(result['added'])} domains\n"
            if result['skipped']:
                message += f"Skipped: {len(result['skipped'])} (already exist)\n"
            await self.send_message(chat_id, message)
        else:
            await self.send_message(chat_id, f"❌ Error: {result.get('error', 'Unknown error')}")

    async def handle_add_domain(self, chat_id, text):
        """Handle single domain addition"""
        user_id = chat_id
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        
        if "|" in text:
            parts = text.split("|", 1)
            name = parts[0].strip()
            url = parts[1].strip()
        else:
            # Use domain as both name and URL
            url = text.strip()
            name = url.title()
        
        if self.domain_manager.add_domain(url, name):
            await self.send_message(chat_id, f"✅ Added domain: {name}")
        else:
            await self.send_message(chat_id, "❌ Failed to add domain or already exists")

    async def handle_remove_domain(self, chat_id, text):
        """Handle domain removal"""
        user_id = chat_id
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        
        url = text.strip()
        if self.domain_manager.remove_domain(url):
            await self.send_message(chat_id, f"✅ Removed domain: {url}")
        else:
            await self.send_message(chat_id, "❌ Domain not found")

    async def run(self):
        """Run the bot"""
        logger.info("Starting Simple Telegram Email Tester Bot...")
        offset = None
        
        while True:
            try:
                result = await self.get_updates(offset)
                if result.get("ok"):
                    updates = result.get("result", [])
                    for update in updates:
                        offset = update["update_id"] + 1
                        if "message" in update:
                            await self.handle_message(update["message"])
                        elif "callback_query" in update:
                            await self.handle_callback_query(update["callback_query"])
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Error in bot loop: {e}")
                await asyncio.sleep(5)

async def main():
    """Main function"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
        return

    bot = SimpleTelegramBot(token)
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())