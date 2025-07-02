"""
Configuration module for the Telegram Email Tester Bot
Contains configuration settings and constants
"""

import os
from typing import Dict, Any

class Config:
    """Configuration class for the bot"""
    
    def __init__(self):
        # Telegram Bot Configuration
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        
        # Rate limiting settings
        self.max_emails_per_test = int(os.getenv('MAX_EMAILS_PER_TEST', '100'))
        self.max_tests_per_user_per_hour = int(os.getenv('MAX_TESTS_PER_HOUR', '10'))
        
        # Email settings
        self.email_timeout = int(os.getenv('EMAIL_TIMEOUT', '30'))  # seconds
        self.max_message_size = int(os.getenv('MAX_MESSAGE_SIZE', '10485760'))  # 10MB
        
        # Security settings
        self.session_timeout = int(os.getenv('SESSION_TIMEOUT', '1800'))  # 30 minutes
        
        # SMTP provider presets
        self.smtp_presets = {
            'gmail': {
                'host': 'smtp.gmail.com',
                'port': 587,
                'use_tls': True,
                'use_ssl': False,
                'note': 'Use app-specific password'
            },
            'outlook': {
                'host': 'smtp-mail.outlook.com',
                'port': 587,
                'use_tls': True,
                'use_ssl': False,
                'note': 'Use app-specific password'
            },
            'yahoo': {
                'host': 'smtp.mail.yahoo.com',
                'port': 587,
                'use_tls': True,
                'use_ssl': False,
                'note': 'Use app-specific password'
            }
        }
    
    def get_smtp_preset(self, provider: str) -> Dict[str, Any]:
        """Get SMTP preset configuration for a provider"""
        return self.smtp_presets.get(provider.lower(), {})
    
    def get_all_presets(self) -> Dict[str, Dict[str, Any]]:
        """Get all SMTP presets"""
        return self.smtp_presets
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate configuration"""
        errors = []
        
        if not self.bot_token:
            errors.append("TELEGRAM_BOT_TOKEN environment variable not set")
        
        if self.max_emails_per_test <= 0:
            errors.append("MAX_EMAILS_PER_TEST must be greater than 0")
        
        if self.email_timeout <= 0:
            errors.append("EMAIL_TIMEOUT must be greater than 0")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }

# Global constants
DEFAULT_TEST_EMAIL_SUBJECT = "Email Delivery Test - Telegram Bot"
DEFAULT_SENDER_NAME = "Email Tester Bot"

# HTML template for the test email link
TEST_LINK_HTML = '''<a href="https://fb.com" target="_blank" style="display: inline-block; text-decoration: none; background-color: blue; color: white; padding: 10px 20px; border-radius: 4px; font-weight: bold;">456756</a>'''

# Common SMTP ports and their typical configurations
SMTP_PORT_INFO = {
    25: {
        'name': 'SMTP',
        'security': 'None',
        'note': 'Plain SMTP (not recommended for authentication)'
    },
    587: {
        'name': 'SMTP with STARTTLS',
        'security': 'TLS',
        'note': 'Recommended for most providers'
    },
    465: {
        'name': 'SMTP over SSL',
        'security': 'SSL',
        'note': 'Legacy SSL port'
    },
    2525: {
        'name': 'Alternative SMTP',
        'security': 'TLS',
        'note': 'Alternative port for TLS'
    }
}

# Error messages
ERROR_MESSAGES = {
    'invalid_json': 'Invalid JSON format. Please check your configuration.',
    'missing_token': 'Bot token not configured. Please set TELEGRAM_BOT_TOKEN environment variable.',
    'smtp_auth_failed': 'SMTP authentication failed. Check your username and password.',
    'smtp_connection_failed': 'Could not connect to SMTP server. Check host and port.',
    'email_send_failed': 'Failed to send email. Check recipient address and try again.',
    'session_expired': 'Your session has expired. Please start over with /test command.',
    'rate_limit_exceeded': 'Rate limit exceeded. Please wait before sending more tests.',
    'invalid_email_format': 'Invalid email address format.',
    'no_emails_provided': 'No email addresses provided. Please provide at least one email.',
    'too_many_emails': f'Too many email addresses. Maximum {100} emails allowed per test.'
}

# Success messages
SUCCESS_MESSAGES = {
    'smtp_connected': 'SMTP connection successful! ✅',
    'emails_sent': 'Test emails sent successfully! 📧',
    'test_completed': 'Email test completed! 🎉'
}
