#!/usr/bin/env python3
"""
Simple Telegram Email Tester Bot
A basic implementation without complex telegram.ext dependencies
"""

import json
import asyncio
import logging
import httpx
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
        user_id = message["from"]["id"]
        text = message.get("text", "").strip()

        # Admin commands
        if self.domain_manager.is_admin(user_id):
            if text == "/admin":
                await self.send_admin_panel(chat_id)
                return
            elif text.startswith("/add_domain "):
                await self.handle_add_domain(chat_id, text)
                return
            elif text.startswith("/remove_domain "):
                await self.handle_remove_domain(chat_id, text)
                return
            elif text == "/list_domains":
                await self.send_domains_list(chat_id, is_admin=True)
                return
            elif text == "/bulk_add_domain":
                await self.send_bulk_add_instructions(chat_id)
                return

        # Regular commands
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
        user_id = callback_query["from"]["id"]
        callback_data = callback_query["data"]
        query_id = callback_query["id"]

        # Answer the callback query to remove loading state
        await self.answer_callback_query(query_id)

        if callback_data == "test_fast":
            await self.show_domain_selection(chat_id)
        elif callback_data == "show_help":
            await self.send_help_message(chat_id)
        elif callback_data.startswith("domain_"):
            domain_url = callback_data.replace("domain_", "")
            await self.start_fast_test(chat_id, domain_url)
        elif callback_data.startswith("preset_"):
            preset_name = callback_data.replace("preset_", "")
            await self.handle_smtp_preset(chat_id, preset_name)
        elif callback_data == "cancel_test":
            if chat_id in self.user_sessions:
                del self.user_sessions[chat_id]
            await self.send_message(chat_id, "❌ Test cancelled. Use /start to begin again.")
        elif callback_data == "admin_add_domain" and self.domain_manager.is_admin(user_id):
            await self.send_message(chat_id, "Please use the command: /add_domain <domain_url> <domain_name>\n\nExample: /add_domain facebook.com Facebook")
        elif callback_data == "admin_bulk_add" and self.domain_manager.is_admin(user_id):
            await self.send_bulk_add_instructions(chat_id)
        elif callback_data == "admin_list_domains" and self.domain_manager.is_admin(user_id):
            await self.send_domains_list(chat_id, is_admin=True)

    async def answer_callback_query(self, callback_query_id, text=None):
        """Answer callback query"""
        url = f"{self.api_url}/answerCallbackQuery"
        data = {"callback_query_id": callback_query_id}
        if text:
            data["text"] = text

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=data)
            return response.json()

    async def send_start_message(self, chat_id):
        """Send welcome message"""
        message = """🤖 *Email Tester Bot*

Choose an option below:"""

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "⚡ Test Fast", "callback_data": "test_fast"}
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

    async def show_domain_selection(self, chat_id):
        """Show domain selection to user"""
        domains = self.domain_manager.get_domains()

        if not domains:
            await self.send_message(chat_id, "❌ No domains available. Please contact admin to add domains.")
            return

        message = """🌐 *Select Domain*

Choose a domain for your test email link:"""

        keyboard_buttons = []
        for domain in domains:
            keyboard_buttons.append([{
                "text": f"🔗 {domain['name']}", 
                "callback_data": f"domain_{domain['url']}"
            }])

        keyboard_buttons.append([{"text": "❌ Cancel", "callback_data": "cancel_test"}])

        keyboard = {"inline_keyboard": keyboard_buttons}
        await self.send_message(chat_id, message, parse_mode="Markdown", reply_markup=keyboard)

    async def start_fast_test(self, chat_id, domain_url):
        """Start fast test with selected domain"""
        domain = self.domain_manager.get_domain_by_url(domain_url)
        if not domain:
            await self.send_message(chat_id, "❌ Domain not found. Please try again.")
            return

        self.user_sessions[chat_id] = {
            'state': 'waiting_combined_input',
            'selected_domain': domain,
            'smtp_config': None,
            'emails': []
        }

        message = f"""⚡ *Fast Test Mode*

Selected Domain: *{domain['name']}* ({domain['url']})

Now send me your SMTP configuration and email list together in this format:

```json
{{
  "smtp": {{
    "host": "smtp.gmail.com",
    "port": 587,
    "username": "your-email@gmail.com",
    "password": "your-app-password",
    "use_tls": true,
    "use_ssl": false
  }},
  "emails": [
    "test1@example.com",
    "test2@example.com"
  ]
}}
```

The test email will contain a blue button linking to: *https://{domain['url']}*"""

        await self.send_message(chat_id, message, parse_mode="Markdown")

    async def send_admin_panel(self, chat_id):
        """Send admin panel"""
        domains = self.domain_manager.get_domains()

        message = f"""👑 *Admin Panel*

Current domains: {len(domains)}

*Commands:*
/add_domain <url> <name> - Add new domain
/remove_domain <url> - Remove domain
/list_domains - Show all domains
/bulk_add_domain - Add multiple domains

*Example:*
/add_domain facebook.com Facebook"""

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "➕ Add Domain", "callback_data": "admin_add_domain"}
                ],
                [
                    {"text": "➕ Bulk Add Domains", "callback_data": "admin_bulk_add"}
                ],
                [
                    {"text": "📋 List Domains", "callback_data": "admin_list_domains"}
                ]
            ]
        }

        await self.send_message(chat_id, message, parse_mode="Markdown", reply_markup=keyboard)

    async def handle_add_domain(self, chat_id, text):
        """Handle add domain command"""
        parts = text.split(' ', 2)
        if len(parts) < 3:
            await self.send_message(chat_id, "❌ Usage: /add_domain <domain_url> <domain_name>\n\nExample: /add_domain facebook.com Facebook")
            return

        domain_url = parts[1]
        domain_name = parts[2]

        if self.domain_manager.add_domain(domain_url, domain_name):
            await self.send_message(chat_id, f"✅ Domain added successfully!\n\n🔗 {domain_name} ({domain_url})")
        else:
            await self.send_message(chat_id, f"❌ Failed to add domain. It may already exist.")

    async def handle_remove_domain(self, chat_id, text):
        """Handle remove domain command"""
        parts = text.split(' ', 1)
        if len(parts) < 2:
            await self.send_message(chat_id, "❌ Usage: /remove_domain <domain_url>\n\nExample: /remove_domain facebook.com")
            return

        domain_url = parts[1]

        if self.domain_manager.remove_domain(domain_url):
            await self.send_message(chat_id, f"✅ Domain removed: {domain_url}")
        else:
            await self.send_message(chat_id, f"❌ Domain not found: {domain_url}")

    async def send_domains_list(self, chat_id, is_admin=False):
        """Send list of domains"""
        domains = self.domain_manager.get_domains()

        if not domains:
            await self.send_message(chat_id, "📋 No domains configured.")
            return

        message = "📋 *Available Domains:*\n\n"
        for i, domain in enumerate(domains, 1):
            message += f"{i}. *{domain['name']}*\n   🔗 {domain['url']}\n\n"

        if is_admin:
            message += "\n*Admin Commands:*\n"
            message += "/remove_domain <url> - Remove domain\n"
            message += "/add_domain <url> <name> - Add domain\n"
            message += "/bulk_add_domain - Add multiple domains"

        await self.send_message(chat_id, message, parse_mode="Markdown")

    async def handle_session_message(self, chat_id, text):
        """Handle messages during active session"""
        session = self.user_sessions[chat_id]

        if session['state'] == 'waiting_combined_input':
            await self.handle_combined_input(chat_id, text)
        elif session['state'] == 'waiting_smtp':
            await self.handle_smtp_config(chat_id, text)
        elif session['state'] == 'waiting_emails':
            await self.handle_email_list(chat_id, text)
        elif session['state'] == 'waiting_bulk_domains':
            await self.handle_bulk_domain_add(chat_id, text)

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

    async def handle_combined_input(self, chat_id, text):
        """Handle combined SMTP config and email list input"""
        try:
            # Parse JSON input
            data = json.loads(text)

            # Validate structure
            if 'smtp' not in data or 'emails' not in data:
                await self.send_message(chat_id, "❌ Invalid format. Please include both 'smtp' and 'emails' fields.")
                return

            smtp_config = data['smtp']
            emails = data['emails']

            # Validate SMTP configuration
            validation = validate_smtp_config(smtp_config)
            if not validation['valid']:
                await self.send_message(chat_id, f"❌ SMTP configuration error: {validation['error']}")
                return

            # Validate email list
            email_validation = validate_email_list(emails)
            if not email_validation['valid']:
                await self.send_message(chat_id, f"❌ Email validation error: {email_validation['error']}")
                return

            # Test SMTP connection
            await self.send_message(chat_id, "🔄 Testing SMTP connection...")

            email_handler = EmailHandler(smtp_config)
            connection_result = await email_handler.test_connection()

            if not connection_result['success']:
                await self.send_message(chat_id, f"❌ SMTP connection failed: {connection_result['error']}")
                return

            await self.send_message(chat_id, "✅ SMTP connection successful!")

            # Report email validation results
            if email_validation['invalid_count'] > 0:
                invalid_list = ', '.join(email_validation['invalid_emails'][:5])
                if email_validation['invalid_count'] > 5:
                    invalid_list += f" and {email_validation['invalid_count'] - 5} more"

                await self.send_message(chat_id, f"⚠️ Found {email_validation['invalid_count']} invalid emails: {invalid_list}\n\nContinuing with {email_validation['valid_count']} valid emails.")

            # Get selected domain
            selected_domain = self.user_sessions[chat_id]['selected_domain']
            valid_emails = email_validation['valid_emails']

            await self.send_message(chat_id, f"📤 Sending test emails to {len(valid_emails)} recipients...\n\nDomain: {selected_domain['name']} ({selected_domain['url']})\n\nThis may take a moment.")

            # Send emails with custom domain
            email_handler = EmailHandler(smtp_config, selected_domain['url'])
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
                        {"text": "⚡ Test Fast Again", "callback_data": "test_fast"}
                    ],
                    [
                        {"text": "📖 Help", "callback_data": "show_help"}
                    ]
                ]
            }

            await self.send_message(chat_id, message, reply_markup=keyboard)

        except json.JSONDecodeError:
            await self.send_message(chat_id, "❌ Invalid JSON format. Please check your input and try again.")
        except Exception as e:
            logger.error(f"Error handling combined input: {e}")
            await self.send_message(chat_id, f"❌ Error processing input: {str(e)}")

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

                        try:
                            if "message" in update:
                                await self.handle_message(update["message"])
                            elif "callback_query" in update:
                                await self.handle_callback_query(update["callback_query"])
                        except Exception as e:
                            logger.error(f"Error handling update: {e}")

                await asyncio.sleep(0.5)  # Small delay between requests

            except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                logger.warning(f"Timeout error: {e}")
                await asyncio.sleep(2)  # Short wait for timeout
            except Exception as e:
                logger.error(f"Error in bot loop: {e}")
                logger.exception("Full traceback:")
                await asyncio.sleep(5)  # Wait longer on error

    async def send_bulk_add_instructions(self, chat_id):
        """Send instructions for bulk adding domains."""
        # Set up session for bulk add
        self.user_sessions[chat_id] = {
            'state': 'waiting_bulk_domains'
        }

        message = """👑 *Bulk Add Domains Instructions*

Send me a list of domains, one per line:

```
domain1.com
domain2.net  
domain3.org
example.com
```

I'll add them all at once and show you the results."""
        await self.send_message(chat_id, message, parse_mode="Markdown")

    async def handle_bulk_domain_add(self, chat_id, text):
        """Handle bulk domain addition"""
        try:
            result = self.domain_manager.add_bulk_domains(text)

            if result['success']:
                added_count = len(result['added'])
                skipped_count = len(result['skipped'])

                message = f"✅ *Bulk Domain Add Complete!*\n\n"
                message += f"📈 Added: {added_count} domains\n"
                message += f"⏭️ Skipped: {skipped_count} domains (already exist)\n"

                if added_count > 0:
                    message += f"\n*Added domains:*\n"
                    for domain in result['added'][:10]:  # Show first 10
                        message += f"• {domain}\n"
                    if added_count > 10:
                        message += f"• ... and {added_count - 10} more\n"

                if skipped_count > 0:
                    message += f"\n*Skipped domains:*\n"
                    for domain in result['skipped'][:5]:  # Show first 5
                        message += f"• {domain}\n"
                    if skipped_count > 5:
                        message += f"• ... and {skipped_count - 5} more\n"

                await self.send_message(chat_id, message, parse_mode="Markdown")
            else:
                await self.send_message(chat_id, f"❌ Failed to add domains: {result.get('error', 'Unknown error')}")

            # Clean up session
            del self.user_sessions[chat_id]

        except Exception as e:
            logger.error(f"Error handling bulk domain add: {e}")
            await self.send_message(chat_id, f"❌ Error processing domain list: {str(e)}")
            del self.user_sessions[chat_id]

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