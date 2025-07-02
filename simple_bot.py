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
                await self.send_message(chat_id, "Access denied. Admin privileges required.")
        elif text.startswith("/domains"):
            await self.send_domains_list(chat_id)
        else:
            await self.send_message(chat_id, "Unknown command. Use /help to see available commands.")

    async def send_start_message(self, chat_id):
        """Send welcome message"""
        message = """Welcome to Email Tester Bot!

This bot helps you test email delivery using your SMTP credentials.

Available commands:
/test - Start email testing
/domains - View available domains
/help - Show help message
/admin - Admin panel (admin only)

Use /test to begin testing your email configuration."""
        await self.send_message(chat_id, message)

    async def send_help_message(self, chat_id):
        """Send help message"""
        message = """Email Tester Bot Help

Commands:
/start - Welcome message
/test - Start email testing process
/domains - View available test domains
/admin - Admin panel (admin only)

How to test emails:
1. Use /test command
2. Select a domain for test links
3. Choose SMTP preset or enter custom config
4. Provide email list to test
5. Bot will send test emails and report results"""
        await self.send_message(chat_id, message)

    async def show_domain_selection(self, chat_id):
        """Show domain selection to user"""
        domains = self.domain_manager.get_domains()
        if not domains:
            await self.send_message(chat_id, "No domains available. Please contact admin to add domains.")
            return

        message = "Select Domain\n\nChoose a domain for your test email link:"
        keyboard_buttons = []
        for domain in domains:
            keyboard_buttons.append([{
                "text": f"Link: {domain['name']}",
                "callback_data": f"domain_{domain['url']}"
            }])

        reply_markup = json.dumps({"inline_keyboard": keyboard_buttons})
        await self.send_message(chat_id, message, reply_markup=reply_markup)

    async def send_admin_panel(self, chat_id):
        """Send admin panel"""
        message = """Admin Panel

Available commands:
/add_domain - Add new domain
/remove_domain - Remove domain
/domains - List all domains

Use these commands to manage test domains."""
        await self.send_message(chat_id, message)

    async def send_domains_list(self, chat_id):
        """Send list of domains"""
        domains = self.domain_manager.get_domains()
        if not domains:
            await self.send_message(chat_id, "No domains configured.")
            return

        message = "Available Domains:\n\n"
        for i, domain in enumerate(domains, 1):
            message += f"{i}. {domain['name']} - {domain['url']}\n"
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