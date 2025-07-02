#!/usr/bin/env python3
"""
Simple Telegram Email Tester Bot
A basic implementation without complex telegram.ext dependencies
"""

import os
import json
import asyncio
import logging
import httpx
from email_handler import EmailHandler
from validators import validate_email_list, validate_smtp_config
from config import Config

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
        self.user_sessions = {}  # Store user session data temporarily
        
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
            
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data)
            return response.json()
    
    async def get_updates(self, offset=None):
        """Get updates from Telegram"""
        url = f"{self.api_url}/getUpdates"
        params = {"timeout": 10}
        if offset:
            params["offset"] = offset
            
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            return response.json()
    
    async def handle_message(self, message):
        """Handle incoming messages"""
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()
        
        if text == "/start":
            await self.send_start_message(chat_id)
        elif text == "/help":
            await self.send_help_message(chat_id)
        elif text == "/test":
            await self.start_test_process(chat_id)
        elif chat_id in self.user_sessions:
            await self.handle_session_message(chat_id, text)
        else:
            await self.send_message(chat_id, "Please use /test to start email testing or /help for more information.")
    
    async def handle_callback_query(self, callback_query):
        """Handle inline keyboard button callbacks"""
        chat_id = callback_query["message"]["chat"]["id"]
        callback_data = callback_query["data"]
        query_id = callback_query["id"]
        
        # Answer the callback query to remove loading state
        await self.answer_callback_query(query_id)
        
        if callback_data == "start_test":
            await self.start_test_process(chat_id)
        elif callback_data == "show_help":
            await self.send_help_message(chat_id)
        elif callback_data.startswith("preset_"):
            preset_name = callback_data.replace("preset_", "")
            await self.handle_smtp_preset(chat_id, preset_name)
        elif callback_data == "cancel_test":
            if chat_id in self.user_sessions:
                del self.user_sessions[chat_id]
            await self.send_message(chat_id, "❌ Test cancelled. Use /test to start again.")
    
    async def answer_callback_query(self, callback_query_id, text=None):
        """Answer callback query"""
        url = f"{self.api_url}/answerCallbackQuery"
        data = {"callback_query_id": callback_query_id}
        if text:
            data["text"] = text
            
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data)
            return response.json()
    
    async def send_start_message(self, chat_id):
        """Send welcome message"""
        message = """🤖 *Email Tester Bot*

Welcome! I help you test email delivery using your SMTP credentials.

*How it works:*
1. Click "Start Email Test" below
2. Provide your SMTP configuration
3. Provide email addresses to test
4. I'll send a test email with blue button linking to https://fb.com

Choose an option below:"""
        
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🚀 Start Email Test", "callback_data": "start_test"}
                ],
                [
                    {"text": "📖 Help & Documentation", "callback_data": "show_help"}
                ]
            ]
        }
        
        await self.send_message(chat_id, message, parse_mode="Markdown", reply_markup=keyboard)
    
    async def send_help_message(self, chat_id):
        """Send help message"""
        message = """📖 *Detailed Help*

*SMTP Configuration Format:*
Send SMTP config as JSON:
```
{
  "host": "smtp.gmail.com",
  "port": 587,
  "username": "your-email@gmail.com",
  "password": "your-app-password",
  "use_tls": true,
  "use_ssl": false
}
```

*Common Providers:*
• Gmail: smtp.gmail.com:587 (TLS)
• Outlook: smtp-mail.outlook.com:587 (TLS)  
• Yahoo: smtp.mail.yahoo.com:587 (TLS)

*Email List Format:*
Send emails separated by commas or one per line:
```
email1@example.com, email2@example.com
```

*What the test does:*
Sends HTML email with blue button linking to https://fb.com

*Commands:*
/start - Welcome message
/test - Start email testing
/help - This help message"""
        
        await self.send_message(chat_id, message, parse_mode="Markdown")
    
    async def start_test_process(self, chat_id):
        """Start the testing process"""
        self.user_sessions[chat_id] = {
            'state': 'waiting_smtp',
            'smtp_config': None,
            'emails': []
        }
        
        message = """🔧 *Email Testing Setup*

Choose how you want to configure your SMTP settings:"""
        
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📧 Gmail", "callback_data": "preset_gmail"},
                    {"text": "📨 Outlook", "callback_data": "preset_outlook"}
                ],
                [
                    {"text": "📮 Yahoo", "callback_data": "preset_yahoo"}
                ],
                [
                    {"text": "⚙️ Custom JSON", "callback_data": "preset_custom"}
                ],
                [
                    {"text": "❌ Cancel", "callback_data": "cancel_test"}
                ]
            ]
        }
        
        await self.send_message(chat_id, message, parse_mode="Markdown", reply_markup=keyboard)
    
    async def handle_session_message(self, chat_id, text):
        """Handle messages during active session"""
        session = self.user_sessions[chat_id]
        
        if session['state'] == 'waiting_smtp':
            await self.handle_smtp_config(chat_id, text)
        elif session['state'] == 'waiting_emails':
            await self.handle_email_list(chat_id, text)
    
    async def handle_smtp_preset(self, chat_id, preset_name):
        """Handle SMTP preset selection"""
        if preset_name == "custom":
            message = """⚙️ *Custom SMTP Configuration*

Please send me your SMTP configuration as JSON format:

```json
{
  "host": "your-smtp-server.com",
  "port": 587,
  "username": "your-email@domain.com",
  "password": "your-password",
  "use_tls": true,
  "use_ssl": false
}
```"""
            await self.send_message(chat_id, message, parse_mode="Markdown")
            return
            
        preset = self.config.get_smtp_preset(preset_name)
        if preset:
            preset_msg = f"""📋 *{preset_name.capitalize()} Preset*

```json
{{
  "host": "{preset['host']}",
  "port": {preset['port']},
  "username": "YOUR_EMAIL_HERE",
  "password": "YOUR_APP_PASSWORD_HERE",
  "use_tls": {str(preset['use_tls']).lower()},
  "use_ssl": {str(preset['use_ssl']).lower()}
}}
```

Replace YOUR_EMAIL_HERE and YOUR_APP_PASSWORD_HERE with your actual credentials, then send the complete JSON.

*Note:* {preset.get('note', '')}"""
            await self.send_message(chat_id, preset_msg, parse_mode="Markdown")

    async def handle_smtp_config(self, chat_id, text):
        """Handle SMTP configuration"""
        try:
            
            # Try to parse as JSON
            smtp_config = json.loads(text)
            
            # Validate configuration
            validation = validate_smtp_config(smtp_config)
            if not validation['valid']:
                await self.send_message(chat_id, f"❌ Configuration error: {validation['error']}\n\nPlease check your SMTP settings and try again.")
                return
            
            # Test SMTP connection
            await self.send_message(chat_id, "🔄 Testing SMTP connection...")
            
            email_handler = EmailHandler(smtp_config)
            connection_result = await email_handler.test_connection()
            
            if connection_result['success']:
                # Save config and move to next step
                self.user_sessions[chat_id]['smtp_config'] = smtp_config
                self.user_sessions[chat_id]['state'] = 'waiting_emails'
                
                await self.send_message(chat_id, "✅ SMTP connection successful!\n\n📧 Now please send me the email addresses you want to test.\n\n*Formats accepted:*\n• Comma separated: email1@example.com, email2@example.com\n• Line separated: one email per line\n• Maximum 100 emails per test")
            else:
                await self.send_message(chat_id, f"❌ SMTP connection failed: {connection_result['error']}\n\nPlease check your credentials and try again.")
                
        except json.JSONDecodeError:
            await self.send_message(chat_id, "❌ Invalid JSON format. Please send valid JSON configuration or use preset shortcuts (gmail, outlook, yahoo).")
        except Exception as e:
            logger.error(f"Error handling SMTP config: {e}")
            await self.send_message(chat_id, f"❌ Error processing configuration: {str(e)}")
    
    async def handle_email_list(self, chat_id, text):
        """Handle email list input"""
        try:
            # Parse email list
            if ',' in text:
                emails = [email.strip() for email in text.split(',')]
            else:
                emails = [email.strip() for email in text.split('\n')]
            
            # Remove empty entries
            emails = [email for email in emails if email]
            
            # Validate email list
            validation = validate_email_list(emails)
            
            if not validation['valid']:
                await self.send_message(chat_id, f"❌ Email validation error: {validation['error']}")
                return
            
            if validation['invalid_count'] > 0:
                invalid_list = ', '.join(validation['invalid_emails'][:5])
                if validation['invalid_count'] > 5:
                    invalid_list += f" and {validation['invalid_count'] - 5} more"
                
                await self.send_message(chat_id, f"⚠️ Found {validation['invalid_count']} invalid emails: {invalid_list}\n\nContinuing with {validation['valid_count']} valid emails.")
            
            # Start sending emails
            valid_emails = validation['valid_emails']
            await self.send_message(chat_id, f"📤 Sending test emails to {len(valid_emails)} recipients...\n\nThis may take a moment.")
            
            # Send emails
            smtp_config = self.user_sessions[chat_id]['smtp_config']
            email_handler = EmailHandler(smtp_config)
            
            result = await email_handler.send_test_emails(valid_emails)
            
            # Report results
            successful_count = len(result['successful'])
            failed_count = len(result['failed'])
            
            if successful_count > 0:
                success_msg = f"✅ Successfully sent to {successful_count} emails"
                if successful_count <= 10:
                    success_msg += f":\n• " + "\n• ".join(result['successful'])
                await self.send_message(chat_id, success_msg)
            
            if failed_count > 0:
                failed_msg = f"❌ Failed to send to {failed_count} emails"
                if failed_count <= 5:
                    failed_list = [f"{email}: {error}" for email, error in list(result['failed'].items())[:5]]
                    failed_msg += f":\n• " + "\n• ".join(failed_list)
                await self.send_message(chat_id, failed_msg)
            
            # Clean up session
            del self.user_sessions[chat_id]
            
            message = "🎉 Email testing completed!"
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "🔄 Run Another Test", "callback_data": "start_test"}
                    ],
                    [
                        {"text": "📖 Help", "callback_data": "show_help"}
                    ]
                ]
            }
            
            await self.send_message(chat_id, message, reply_markup=keyboard)
            
        except Exception as e:
            logger.error(f"Error handling email list: {e}")
            await self.send_message(chat_id, f"❌ Error processing email list: {str(e)}")
    
    async def run(self):
        """Run the bot"""
        logger.info("Starting Simple Telegram Email Tester Bot...")
        offset = None
        
        while True:
            try:
                updates = await self.get_updates(offset)
                
                if updates.get("ok"):
                    for update in updates.get("result", []):
                        offset = update["update_id"] + 1
                        
                        if "message" in update:
                            await self.handle_message(update["message"])
                        elif "callback_query" in update:
                            await self.handle_callback_query(update["callback_query"])
                
                await asyncio.sleep(1)  # Small delay between requests
                
            except Exception as e:
                logger.error(f"Error in bot loop: {e}")
                logger.exception("Full traceback:")
                await asyncio.sleep(5)  # Wait longer on error

async def main():
    """Main function"""
    config = Config()
    
    # Validate configuration
    validation = config.validate_config()
    if not validation['valid']:
        logger.error("Configuration validation failed:")
        for error in validation['errors']:
            logger.error(f"  - {error}")
        return
    
    # Create and run bot
    bot = SimpleTelegramBot(config.bot_token)
    await bot.run()

if __name__ == '__main__':
    asyncio.run(main())