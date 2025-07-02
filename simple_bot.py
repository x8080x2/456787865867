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

    async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None):
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
            return response.json()

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

        # Check if user has an active session
        if user_id in self.user_sessions:
            await self.handle_session_message(chat_id, text)
            return

        # Handle commands
        if text.startswith("/start"):
            await self.send_start_message(chat_id)
        elif text.startswith("/help"):
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
        await self.send_message(chat_id, "Email Tester Bot - Test your SMTP delivery.", reply_markup=reply_markup)

    async def send_help_message(self, chat_id):
        """Send help message"""
        message = "Commands: /start /test /domains /admin\nUse /test to start email testing."
        await self.send_message(chat_id, message)

    async def show_domain_selection(self, chat_id):
        """Show domain selection to user"""
        domains = self.domain_manager.get_domains()
        if not domains:
            await self.send_message(chat_id, "No domains available. Contact admin.")
            return

        keyboard_buttons = []
        for domain in domains:
            keyboard_buttons.append([{
                "text": f"🔗 {domain['name']}",
                "callback_data": f"domain_{domain['url']}"
            }])

        reply_markup = json.dumps({"inline_keyboard": keyboard_buttons})
        await self.send_message(chat_id, "Choose domain for test link:", reply_markup=reply_markup)

    async def send_admin_panel(self, chat_id):
        """Send admin panel"""
        keyboard = [
            [{"text": "➕ Add Domain", "callback_data": "admin_add"}],
            [{"text": "➖ Remove Domain", "callback_data": "admin_remove"}],
            [{"text": "📋 List Domains", "callback_data": "view_domains"}]
        ]
        reply_markup = json.dumps({"inline_keyboard": keyboard})
        await self.send_message(chat_id, "Admin Panel:", reply_markup=reply_markup)

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

    async def answer_callback_query(self, callback_query_id):
        """Answer callback query"""
        url = f"{self.api_url}/answerCallbackQuery"
        data = {"callback_query_id": callback_query_id}
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(url, json=data)

    async def start_fast_test(self, chat_id, domain_url):
        """Start fast test with selected domain"""
        user_id = chat_id
        self.user_sessions[user_id] = {
            "step": "smtp_and_emails",
            "domain_url": domain_url
        }
        
        await self.send_message(chat_id, "Enter SMTP details and 5 emails:\nserver:port:username:password:tls\nemail1,email2,email3,email4,email5")

    async def handle_admin_action(self, chat_id, action):
        """Handle admin actions"""
        if action == "admin_add":
            await self.send_message(chat_id, "Send domain in format: name|url")
        elif action == "admin_remove":
            await self.send_message(chat_id, "Send domain URL to remove")

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

    async def handle_smtp_and_emails(self, chat_id, text):
        """Handle combined SMTP config and email list input"""
        user_id = chat_id
        session = self.user_sessions.get(user_id)
        if not session:
            return

        lines = text.strip().split('\n')
        if len(lines) != 2:
            await self.send_message(chat_id, "Invalid format. Use:\nserver:port:username:password:tls\nemail1,email2,email3,email4,email5")
            return

        smtp_line = lines[0]
        emails_line = lines[1]

        # Parse SMTP config
        smtp_parts = smtp_line.split(":")
        if len(smtp_parts) != 5:
            await self.send_message(chat_id, "Invalid SMTP format. Use: server:port:username:password:tls")
            return

        # Parse emails
        emails = [email.strip() for email in emails_line.split(",")]
        if len(emails) != 5:
            await self.send_message(chat_id, f"Please enter exactly 5 emails. You entered {len(emails)}.")
            return

        # Store config
        session["smtp_config"] = {
            "server": smtp_parts[0], "port": smtp_parts[1], 
            "username": smtp_parts[2], "password": smtp_parts[3], "tls": smtp_parts[4]
        }
        session["emails"] = emails

        await self.send_message(chat_id, "Test started for 5 emails...")
        
        # Clear session
        del self.user_sessions[user_id]


    async def handle_smtp_config(self, chat_id, text):
        """Handle SMTP configuration"""
        user_id = chat_id
        session = self.user_sessions.get(user_id)
        if not session:
            return

        parts = text.split(":")
        if len(parts) != 5:
            await self.send_message(chat_id, "Invalid format. Use: server:port:username:password:tls")
            return
            
        session["smtp_config"] = {
            "server": parts[0], "port": parts[1], 
            "username": parts[2], "password": parts[3], "tls": parts[4]
        }

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
        await self.send_message(chat_id, message)

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
                await asyncio.sleep(1)
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