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
from config import Config
from domain_manager import DomainManager
from validators import validate_email

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
            await self.start_direct_test(chat_id)
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
        """Send comprehensive help message"""
        message = """📖 **EMAIL TESTER BOT - HELP GUIDE**

🚀 **Commands:**
• `/start` - Main menu & quick access
• `/test` - Begin email deliverability testing
• `/domains` - View available test domains
• `/admin` - Domain management (admin only)

📧 **How to Test:**
1. Use `/test` command
2. Enter SMTP details + recipient emails
3. System sends test emails from ALL domains to ALL recipients
4. Get detailed delivery reports

📝 **Input Format:**
`server port username password tls_setting [from_email] recipient_emails...`

🎯 **Examples:**

**Gmail (simple):**
```
smtp.gmail.com 587 user@gmail.com app_password true
recipient1@test.com
recipient2@test.com
```

**Gmail (with custom from_email):**
```
smtp.gmail.com 587 user@gmail.com app_password true sender@company.com
recipient1@test.com
recipient2@test.com
```

**AWS SES:**
```
email-smtp.us-east-1.amazonaws.com 587 AKIAIOSFODNN7EXAMPLE secretkey true sender@verified.com
recipient@test.com
```

**iCloud:**
```
smtp.mail.me.com 587 user@icloud.com app_password true
test1@example.com test2@example.com
```

⚙️ **SMTP Ports:**
• `587` - STARTTLS (recommended)
• `465` - SSL/TLS  
• `25` - Plain SMTP (not recommended)

🎯 **Smart Features:**
• Batch processing (5 domains at a time)
• Progress tracking & statistics
• Connection retry logic
• Comprehensive error reporting
• Campaign management controls

💡 **Pro Tips:**
• Use app-specific passwords for Gmail/Outlook
• Verify sender domains for better delivery
• Test in small batches first
• Monitor success rates

Need help? Just ask! 🤖"""
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
            await self.start_direct_test(chat_id)
        elif data == "view_domains":
            await self.send_domains_list(chat_id)
        elif data == "show_help":
            await self.send_help_message(chat_id)
        elif data.startswith("domain_"):
            domain_url = data.replace("domain_", "")
            await self.start_fast_test(chat_id, domain_url)
        elif data == "send_next_batch":
            await self.send_next_batch(chat_id)
        elif data == "stop_sending":
            await self.stop_sending(chat_id)
        elif data == "show_stats":
            await self.show_campaign_stats(chat_id)
        elif data == "skip_recipient":
            await self.skip_to_next_recipient(chat_id)

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

        await self.send_message(chat_id, """Enter SMTP details & recipient emails:

Format: smtp.mail.me.com 587 user@icloud.com password true [from_email]
eu2@eeu.jp
dassola8080@gmail.com

Note: from_email is optional and comes after 'true'.""", auto_delete=False)

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

    async def start_direct_test(self, chat_id):
        """Start direct test without domain selection"""
        # Clear chat for clean experience
        await self.clear_chat_history(chat_id)
        
        user_id = chat_id
        domains = self.domain_manager.get_domains()
        if not domains:
            await self.send_message(chat_id, "No domains available. Contact admin.", auto_delete=False)
            return

        self.user_sessions[user_id] = {
            "step": "smtp_and_emails",
            "domains": domains,
            "current_domain_index": 0,
            "emails_sent": 0,
            "total_emails_to_send": 0
        }

        await self.send_message(chat_id, """Enter SMTP details and recipient emails:

Format: smtp.mail.me.com 587 user@icloud.com password true [from_email]
eu2@eeu.jp
dassola8080@gmail.com

Note: from_email is optional and comes after 'true'. System will send test emails from ALL domains to ALL recipients.""", auto_delete=False)

    async def send_next_batch(self, chat_id):
        """Send next batch of 5 emails"""
        user_id = chat_id
        session = self.user_sessions.get(user_id)
        if not session:
            await self.send_message(chat_id, "Session expired. Use /test to start again.")
            return

        # Continue sending emails
        await self.send_batch_emails(chat_id, session["smtp_config"], session["recipient_emails"], session)

    async def stop_sending(self, chat_id):
        """Stop sending emails and end session with final report"""
        user_id = chat_id
        session = self.user_sessions.get(user_id)
        
        if session:
            # Generate final report
            import time
            elapsed = time.time() - session.get("start_time", time.time())
            total_successful = session.get("total_successful", 0)
            total_failed = session.get("total_failed", 0)
            total_processed = total_successful + total_failed
            
            if total_processed > 0:
                success_rate = (total_successful / total_processed * 100)
                final_report = f"""🛑 **CAMPAIGN STOPPED**

📊 **Partial Results:**
• ✅ Successful: {total_successful}
• ❌ Failed: {total_failed}
• 📈 Success Rate: {success_rate:.1f}%
• ⏱️ Runtime: {elapsed/60:.1f} minutes

Use /test to start a new campaign."""
                await self.send_message(chat_id, final_report, auto_delete=False)
            else:
                await self.send_message(chat_id, "✅ Campaign stopped. Use /test to start a new test.")
            
            del self.user_sessions[user_id]
        else:
            await self.send_message(chat_id, "✅ No active campaign. Use /test to start a new test.")

    async def show_campaign_stats(self, chat_id):
        """Show current campaign statistics"""
        user_id = chat_id
        session = self.user_sessions.get(user_id)
        
        if not session:
            await self.send_message(chat_id, "No active campaign.")
            return
        
        import time
        elapsed = time.time() - session.get("start_time", time.time())
        current_recipient_index = session.get("current_recipient_index", 0)
        total_recipients = len(session.get("recipient_emails", []))
        total_domains = len(session.get("domains", []))
        total_successful = session.get("total_successful", 0)
        total_failed = session.get("total_failed", 0)
        total_processed = total_successful + total_failed
        
        # Calculate remaining work
        remaining_emails = (total_recipients - current_recipient_index) * total_domains
        completed_recipients = current_recipient_index
        
        # Calculate rates
        success_rate = (total_successful / total_processed * 100) if total_processed > 0 else 0
        overall_progress = (completed_recipients / total_recipients * 100) if total_recipients > 0 else 0
        
        stats_report = f"""📊 **CAMPAIGN STATISTICS**

🎯 **Progress:**
• Recipients: {completed_recipients}/{total_recipients} ({overall_progress:.1f}%)
• Remaining Emails: {remaining_emails}

📈 **Performance:**
• ✅ Successful: {total_successful}
• ❌ Failed: {total_failed}
• Success Rate: {success_rate:.1f}%

⏱️ **Timing:**
• Runtime: {elapsed/60:.1f} minutes
• Avg per Email: {elapsed/max(total_processed, 1):.1f}s

🚀 Keep going! You're doing great!"""
        
        await self.send_message(chat_id, stats_report)

    async def skip_to_next_recipient(self, chat_id):
        """Skip remaining domains for current recipient and move to next"""
        user_id = chat_id
        session = self.user_sessions.get(user_id)
        
        if not session:
            await self.send_message(chat_id, "No active campaign.")
            return
        
        current_recipient_index = session.get("current_recipient_index", 0)
        all_emails = session.get("recipient_emails", [])
        
        if current_recipient_index < len(all_emails):
            current_recipient = all_emails[current_recipient_index]
            
            # Move to next recipient
            session["current_recipient_index"] += 1
            session["current_domain_index"] = 0
            
            remaining_recipients = len(all_emails) - session["current_recipient_index"]
            
            if remaining_recipients > 0:
                await self.send_message(chat_id, f"⏭️ Skipped remaining domains for {current_recipient}")
                await self.send_message(chat_id, f"Ready for next recipient. {remaining_recipients} recipients remaining.")
                
                # Continue with next batch
                await self.send_batch_emails(chat_id, session["smtp_config"], all_emails, session)
            else:
                await self.send_message(chat_id, "🎉 Campaign complete! All recipients processed.")
                del self.user_sessions[user_id]
        else:
            await self.send_message(chat_id, "No more recipients to skip to.")
            del self.user_sessions[user_id]

    async def handle_session_message(self, chat_id, text):
        """Handle messages during active session"""
        user_id = chat_id
        session = self.user_sessions.get(user_id)
        if not session:
            return

        if session["step"] == "smtp_and_emails":
            await self.handle_smtp_and_emails(chat_id, text)
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

Required Format (5-6 parameters + recipient emails):
server port username password tls_setting [from_email]

Examples:
smtp.gmail.com 587 user@gmail.com password true
smtp.gmail.com 587 user@gmail.com password true sender@company.com
recipient1@example.com
recipient2@example.com""")
            return

        if not emails:
            await self.send_message(chat_id, f"Need at least 1 email. Found {len(emails) if emails else 0}.")
            return

        session["smtp_config"] = smtp_config
        session["recipient_emails"] = emails
        session["total_emails_to_send"] = len(emails)

        # Clear previous input message for clean chat
        await self.clear_chat_history(chat_id)
        total_emails_to_send = len(emails) * len(session['domains'])
        await self.send_message(chat_id, f"✅ Test started: {len(emails)} recipients × {len(session['domains'])} domains = {total_emails_to_send} total emails to send...", auto_delete=False)

        # Start batch email sending
        await self.send_batch_emails(chat_id, smtp_config, emails, session)

    def parse_smart_input(self, text):
        """Enhanced smart parsing with better email validation and SMTP detection"""
        import re

        # Clean and split text
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        # Enhanced email regex pattern for better validation
        email_pattern = r'\b[A-Za-z0-9][A-Za-z0-9._%-]*@[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z]{2,}\b'
        emails = re.findall(email_pattern, text)

        # Validate and clean emails
        valid_emails = []
        for email in emails:
            if validate_email(email):
                valid_emails.append(email.lower().strip())
        
        emails = list(set(valid_emails))  # Remove duplicates
        
        if len(emails) < 1:
            return {
                'smtp_config': None,
                'emails': None,
                'error': 'No valid email addresses found'
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

        # Find username (first email in SMTP line)
        username = None
        for word in words:
            if '@' in word:
                username = word
                break

        # Fallback: use first email found anywhere
        if not username and emails:
            username = emails[0]

        # Find password (word that comes after username)
        password = None
        if username:
            username_index = -1
            for i, word in enumerate(words):
                if word == username:  # Exact match
                    username_index = i
                    break

            # Look for password after username (should be the word immediately after the email)
            if username_index >= 0 and username_index + 1 < len(words):
                next_word = words[username_index + 1]
                # Password should be the word immediately after username
                if '@' not in next_word and next_word.lower() not in ['true', 'false', '1', '0'] and not next_word.isdigit() and '.' not in next_word:
                    password = next_word

        # Determine TLS setting - smart defaults based on port
        tls = True  # Default to True for security
        if port:
            port_num = int(port)
            if port_num == 465:
                tls = True  # SSL port - will be handled as SSL in email_handler
            elif port_num == 25:
                tls = False  # Plain SMTP
            else:
                tls = True  # Default to TLS for other ports (587, 2525, etc.)
        
        # Check for explicit TLS setting in the input
        tls_index = -1
        for i, word in enumerate(words):
            if word.lower() in ['true', 'false', '1', '0']:
                tls = word.lower() in ['true', '1']
                tls_index = i
                break

        # Find from_email (optional email after TLS setting)
        from_email = username  # Default to username
        if tls_index >= 0 and tls_index + 1 < len(words):
            potential_from_email = words[tls_index + 1]
            if '@' in potential_from_email and validate_email(potential_from_email):
                from_email = potential_from_email

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
            'emails': recipient_emails,
            'error': None
        }

    

    async def send_batch_emails(self, chat_id, smtp_config, all_emails, session):
        """Send emails in batches with enhanced progress tracking and error recovery"""
        user_id = chat_id
        domains = session["domains"]
        
        # Initialize session tracking with comprehensive stats
        if "current_domain_batch" not in session:
            session["current_domain_batch"] = 0  # Track which batch of 5 domains we're on
        if "total_successful" not in session:
            session["total_successful"] = 0
        if "total_failed" not in session:
            session["total_failed"] = 0
        if "start_time" not in session:
            import time
            session["start_time"] = time.time()
        
        current_domain_batch = session["current_domain_batch"]
        domains_per_batch = 5
        
        # Check if all domain batches are sent
        total_domain_batches = (len(domains) + domains_per_batch - 1) // domains_per_batch
        if current_domain_batch >= total_domain_batches:
            import time
            elapsed = time.time() - session["start_time"]
            total_sent = len(all_emails) * len(domains)
            success_rate = (session["total_successful"] / total_sent * 100) if total_sent > 0 else 0
            
            final_report = f"""🎉 **CAMPAIGN COMPLETE!**

📊 **Final Stats:**
• Recipients: {len(all_emails)}
• Domains: {len(domains)}
• Total Emails: {total_sent}
• ✅ Successful: {session["total_successful"]}
• ❌ Failed: {session["total_failed"]}
• 📈 Success Rate: {success_rate:.1f}%
• ⏱️ Time: {elapsed/60:.1f} minutes

🚀 All email deliverability tests completed!"""
            
            await self.send_message(chat_id, final_report, auto_delete=False)
            del self.user_sessions[user_id]
            return

        # Test SMTP connection once per batch
        if current_domain_batch == 0:
            connection_result = await self.test_smtp_connection(smtp_config)
            if not connection_result['success']:
                error_msg = f"❌ SMTP connection failed: {connection_result['error']}"
                await self.send_message(chat_id, error_msg)
                del self.user_sessions[user_id]
                return
            await self.send_message(chat_id, "✅ SMTP connection established!")

        # Calculate which domains to send in this batch
        start_domain_index = current_domain_batch * domains_per_batch
        end_domain_index = min(start_domain_index + domains_per_batch, len(domains))
        domains_in_batch = domains[start_domain_index:end_domain_index]
        
        # Progress indicator
        batch_progress = (current_domain_batch / total_domain_batches * 100)
        progress_bar = "▓" * int(batch_progress / 5) + "░" * (20 - int(batch_progress / 5))
        
        await self.send_message(chat_id, f"📤 Sending batch {current_domain_batch + 1}/{total_domain_batches} ({len(domains_in_batch)} domains) to {len(all_emails)} recipients...\n[{progress_bar}] {batch_progress:.1f}%")
        
        # Send emails to ALL recipients for the current domain batch
        batch_successful = 0
        batch_failed = 0
        recipient_results = []
        
        for recipient_email in all_emails:
            recipient_success = 0
            recipient_failures = 0
            domain_results = []
            
            for domain in domains_in_batch:
                domain_url = domain["url"]
                try:
                    result = await self.send_single_email(smtp_config, recipient_email, domain_url)
                    if result['success']:
                        recipient_success += 1
                        batch_successful += 1
                        domain_results.append(f"✅ {domain_url}")
                    else:
                        recipient_failures += 1
                        batch_failed += 1
                        domain_results.append(f"❌ {domain_url}")
                        
                except Exception as e:
                    recipient_failures += 1
                    batch_failed += 1
                    domain_results.append(f"❌ {domain_url}")
            
            # Track recipient results
            recipient_rate = (recipient_success / len(domains_in_batch) * 100) if domains_in_batch else 0
            recipient_results.append(f"📧 {recipient_email}: {recipient_success}/{len(domains_in_batch)} ({recipient_rate:.0f}%)")
        
        # Update session stats
        session["current_domain_batch"] += 1
        session["total_successful"] += batch_successful
        session["total_failed"] += batch_failed
        
        # Show batch results summary
        batch_rate = (batch_successful / (len(all_emails) * len(domains_in_batch)) * 100) if (len(all_emails) * len(domains_in_batch)) > 0 else 0
        batch_summary = f"""📊 **Batch {current_domain_batch}/{total_domain_batches} Results:**
• Total Sent: {batch_successful + batch_failed}
• ✅ Successful: {batch_successful}
• ❌ Failed: {batch_failed}
• 📈 Batch Success Rate: {batch_rate:.1f}%

**Per Recipient:**
""" + "\n".join(recipient_results[:5])
        
        if len(recipient_results) > 5:
            batch_summary += f"\n... and {len(recipient_results) - 5} more recipients"
            
        await self.send_message(chat_id, batch_summary)
        
        # Check if more batches to send
        if session["current_domain_batch"] < total_domain_batches:
            remaining_batches = total_domain_batches - session["current_domain_batch"]
            remaining_domains = len(domains) - (session["current_domain_batch"] * domains_per_batch)
            overall_progress = (session["current_domain_batch"] / total_domain_batches * 100)
            
            keyboard = [
                [{"text": f"📧 Send Next Batch ({remaining_batches} batches, {remaining_domains} domains left)", "callback_data": "send_next_batch"}],
                [{"text": "📊 View Stats", "callback_data": "show_stats"}],
                [{"text": "🛑 Stop Campaign", "callback_data": "stop_sending"}]
            ]
            reply_markup = json.dumps({"inline_keyboard": keyboard})
            
            progress_msg = f"📈 Campaign Progress: {overall_progress:.1f}% complete\n{remaining_batches} batches remaining ({remaining_domains} domains)"
            await self.send_message(chat_id, progress_msg, reply_markup=reply_markup)
        else:
            # All batches complete - this will be handled by the completion check above
            pass

    async def test_smtp_connection(self, smtp_config):
        """Test SMTP connection"""
        try:
            config = {
                'host': smtp_config['server'],
                'port': int(smtp_config['port']),
                'username': smtp_config['username'],
                'password': smtp_config['password'],
                'from_email': smtp_config.get('from_email', smtp_config['username']),
                'use_tls': smtp_config['tls'],
                'use_ssl': False
            }
            
            email_handler = EmailHandler(config, "test.com")
            return await email_handler.test_connection()
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def send_single_email(self, smtp_config, email, domain_url):
        """Send single email"""
        try:
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
            result = await email_handler.send_test_emails([email])
            
            return {
                'success': len(result['successful']) > 0,
                'error': result.get('failed', {}).get(email, '')
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    

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