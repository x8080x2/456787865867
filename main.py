#!/usr/bin/env python3
"""
Telegram Email Tester Bot
A bot that tests email delivery using user-provided SMTP credentials
"""

import os
import logging
import asyncio
import json
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode
from email_handler import EmailHandler
from validators import validate_email, validate_smtp_config
from config import Config

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class EmailTesterBot:
    def __init__(self):
        self.config = Config()
        self.user_sessions = {}  # Store user session data temporarily
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        welcome_message = """
🤖 *Email Tester Bot*

Welcome! I help you test email delivery using your SMTP credentials.

*Commands:*
/start - Show this welcome message
/test - Start email testing process
/help - Show detailed help

*How it works:*
1. Use /test command
2. Provide your SMTP configuration
3. Provide email addresses to test
4. I'll send a test email and report results

Let's get started with /test!
        """
        
        await update.message.reply_text(
            welcome_message, 
            parse_mode=ParseMode.MARKDOWN
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command handler"""
        help_text = """
📖 *Detailed Help*

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
/help - This help message
        """
        
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN
        )

    async def test_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start email testing process"""
        user_id = update.effective_user.id
        
        # Initialize user session
        self.user_sessions[user_id] = {
            'state': 'waiting_smtp',
            'smtp_config': None,
            'emails': [],
            'timestamp': asyncio.get_event_loop().time()
        }
        
        message = """
🔧 *Email Testing Setup*

Please send me your SMTP configuration as JSON format.

*Example:*
```json
{
  "host": "smtp.gmail.com",
  "port": 587,
  "username": "your-email@gmail.com",
  "password": "your-app-password",
  "use_tls": true,
  "use_ssl": false
}
```

*Quick presets available:*
• Type "gmail" for Gmail preset
• Type "outlook" for Outlook preset  
• Type "yahoo" for Yahoo preset

Then you'll just need to add your username and password.
        """
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user messages during the testing flow"""
        user_id = update.effective_user.id
        message_text = update.message.text.strip()
        
        # Check if user has active session
        if user_id not in self.user_sessions:
            await update.message.reply_text(
                "Please start with /test command to begin email testing."
            )
            return
        
        session = self.user_sessions[user_id]
        
        # Handle different states
        if session['state'] == 'waiting_smtp':
            await self._handle_smtp_config(update, context, message_text)
        elif session['state'] == 'waiting_emails':
            await self._handle_email_list(update, context, message_text)

    async def _handle_smtp_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
        """Handle SMTP configuration input"""
        user_id = update.effective_user.id
        
        try:
            # Check for preset shortcuts
            if message_text.lower() in ['gmail', 'outlook', 'yahoo']:
                preset = self.config.get_smtp_preset(message_text.lower())
                if preset:
                    preset_msg = f"""
📋 *{message_text.capitalize()} Preset*

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

*Note:* {preset.get('note', '')}
                    """
                    await update.message.reply_text(preset_msg, parse_mode=ParseMode.MARKDOWN)
                    return
            
            # Try to parse as JSON
            smtp_config = json.loads(message_text)
            
            # Validate configuration
            validation = validate_smtp_config(smtp_config)
            if not validation['valid']:
                await update.message.reply_text(
                    f"❌ Configuration error: {validation['error']}\n\nPlease check your SMTP settings and try again."
                )
                return
            
            # Test SMTP connection
            await update.message.reply_text("🔄 Testing SMTP connection...")
            
            email_handler = EmailHandler(smtp_config)
            connection_result = await email_handler.test_connection()
            
            if connection_result['success']:
                # Save config and move to next step
                self.user_sessions[user_id]['smtp_config'] = smtp_config
                self.user_sessions[user_id]['state'] = 'waiting_emails'
                
                await update.message.reply_text(
                    "✅ SMTP connection successful!\n\n📧 Now please send me the email addresses you want to test.\n\n*Formats accepted:*\n• Comma separated: email1@example.com, email2@example.com\n• Line separated: one email per line\n• Maximum 100 emails per test"
                )
            else:
                await update.message.reply_text(
                    f"❌ SMTP connection failed: {connection_result['error']}\n\nPlease check your credentials and try again."
                )
                
        except json.JSONDecodeError:
            await update.message.reply_text(
                "❌ Invalid JSON format. Please send valid JSON configuration or use preset shortcuts (gmail, outlook, yahoo)."
            )
        except Exception as e:
            logger.error(f"Error handling SMTP config: {e}")
            await update.message.reply_text(
                f"❌ Error processing configuration: {str(e)}"
            )

    async def _handle_email_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
        """Handle email list input"""
        user_id = update.effective_user.id
        
        try:
            # Parse email list
            if ',' in message_text:
                # Comma separated
                emails = [email.strip() for email in message_text.split(',')]
            else:
                # Line separated
                emails = [email.strip() for email in message_text.split('\n')]
            
            # Remove empty entries
            emails = [email for email in emails if email]
            
            # Validate email list
            from validators import validate_email_list
            validation = validate_email_list(emails)
            
            if not validation['valid']:
                await update.message.reply_text(
                    f"❌ Email validation error: {validation['error']}"
                )
                return
            
            if validation['invalid_count'] > 0:
                invalid_list = ', '.join(validation['invalid_emails'][:5])
                if validation['invalid_count'] > 5:
                    invalid_list += f" and {validation['invalid_count'] - 5} more"
                
                await update.message.reply_text(
                    f"⚠️ Found {validation['invalid_count']} invalid emails: {invalid_list}\n\nContinuing with {validation['valid_count']} valid emails."
                )
            
            # Start sending emails
            valid_emails = validation['valid_emails']
            await update.message.reply_text(
                f"📤 Sending test emails to {len(valid_emails)} recipients...\n\nThis may take a moment."
            )
            
            # Send emails
            smtp_config = self.user_sessions[user_id]['smtp_config']
            email_handler = EmailHandler(smtp_config)
            
            result = await email_handler.send_test_emails(valid_emails)
            
            # Report results
            successful_count = len(result['successful'])
            failed_count = len(result['failed'])
            
            if successful_count > 0:
                success_msg = f"✅ Successfully sent to {successful_count} emails"
                if successful_count <= 10:
                    success_msg += f":\n• " + "\n• ".join(result['successful'])
                await update.message.reply_text(success_msg)
            
            if failed_count > 0:
                failed_msg = f"❌ Failed to send to {failed_count} emails"
                if failed_count <= 5:
                    failed_list = [f"{email}: {error}" for email, error in list(result['failed'].items())[:5]]
                    failed_msg += f":\n• " + "\n• ".join(failed_list)
                await update.message.reply_text(failed_msg)
            
            # Clean up session
            del self.user_sessions[user_id]
            
            await update.message.reply_text(
                "🎉 Email testing completed!\n\nUse /test to run another test."
            )
            
        except Exception as e:
            logger.error(f"Error handling email list: {e}")
            await update.message.reply_text(
                f"❌ Error processing email list: {str(e)}"
            )

def main():
    """Start the bot"""
    config = Config()
    
    # Validate configuration
    validation = config.validate_config()
    if not validation['valid']:
        logger.error("Configuration validation failed:")
        for error in validation['errors']:
            logger.error(f"  - {error}")
        return
    
    # Create bot instance
    bot = EmailTesterBot()
    
    # Create application
    app = Application.builder().token(config.bot_token).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("help", bot.help_command))
    app.add_handler(CommandHandler("test", bot.test_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Start bot
    logger.info("Starting Telegram Email Tester Bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
