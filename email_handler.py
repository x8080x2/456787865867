"""
Email handling module for the Telegram Email Tester Bot
Handles SMTP connections and email sending
"""

import smtplib
import asyncio
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from typing import Dict, List, Any
import ssl

logger = logging.getLogger(__name__)

class EmailHandler:
    def __init__(self, smtp_config: Dict[str, Any], custom_domain: str = None):
        """Initialize email handler with SMTP configuration"""
        self.smtp_config = smtp_config
        self.host = smtp_config['host']
        self.port = smtp_config['port']
        self.username = smtp_config['username']
        self.password = smtp_config['password']
        self.use_tls = smtp_config.get('use_tls', True)
        self.use_ssl = smtp_config.get('use_ssl', False)
        self.custom_domain = custom_domain or "fb.com"
        
    async def test_connection(self) -> Dict[str, Any]:
        """Test SMTP connection"""
        try:
            # Run connection test in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._test_connection_sync)
            return result
        except Exception as e:
            logger.error(f"Connection test error: {e}")
            return {
                'success': False,
                'error': f"Connection test failed: {str(e)}"
            }
    
    def _test_connection_sync(self) -> Dict[str, Any]:
        """Synchronous SMTP connection test"""
        try:
            if self.use_ssl:
                # Use SSL connection
                server = smtplib.SMTP_SSL(self.host, self.port)
            else:
                # Use regular connection
                server = smtplib.SMTP(self.host, self.port)
                
                if self.use_tls:
                    # Start TLS if required
                    server.starttls()
            
            # Login to verify credentials
            server.login(self.username, self.password)
            server.quit()
            
            return {
                'success': True,
                'message': 'SMTP connection successful'
            }
            
        except smtplib.SMTPAuthenticationError as e:
            return {
                'success': False,
                'error': f"Authentication failed: {str(e)}"
            }
        except smtplib.SMTPServerDisconnected as e:
            return {
                'success': False,
                'error': f"Server disconnected: {str(e)}"
            }
        except smtplib.SMTPException as e:
            return {
                'success': False,
                'error': f"SMTP error: {str(e)}"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Connection error: {str(e)}"
            }
    
    async def send_test_emails(self, email_list: List[str]) -> Dict[str, Any]:
        """Send test emails to the provided list"""
        try:
            # Run email sending in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._send_emails_sync, email_list)
            return result
        except Exception as e:
            logger.error(f"Email sending error: {e}")
            return {
                'successful': [],
                'failed': {email: str(e) for email in email_list}
            }
    
    def _send_emails_sync(self, email_list: List[str]) -> Dict[str, Any]:
        """Synchronous email sending"""
        successful = []
        failed = {}
        
        try:
            # Establish SMTP connection
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.host, self.port)
            else:
                server = smtplib.SMTP(self.host, self.port)
                if self.use_tls:
                    server.starttls()
            
            server.login(self.username, self.password)
            
            # Send emails one by one
            for email in email_list:
                try:
                    message = self._create_test_message(email)
                    server.send_message(message)
                    successful.append(email)
                    logger.info(f"Email sent successfully to {email}")
                    
                except Exception as e:
                    failed[email] = str(e)
                    logger.error(f"Failed to send email to {email}: {e}")
            
            server.quit()
            
        except Exception as e:
            # If connection fails, mark all emails as failed
            for email in email_list:
                if email not in successful and email not in failed:
                    failed[email] = f"SMTP connection error: {str(e)}"
        
        return {
            'successful': successful,
            'failed': failed
        }
    
    def _create_test_message(self, recipient_email: str) -> MIMEMultipart:
        """Create the test email message with HTML content"""
        # Create message
        message = MIMEMultipart('alternative')
        message['From'] = formataddr(('Email Tester Bot', self.username))
        message['To'] = recipient_email
        message['Subject'] = 'Email Delivery Test - Telegram Bot'
        
        # HTML content with the specified link
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Test</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
        <h1 style="color: #2c3e50; margin-bottom: 10px;">📧 Email Delivery Test</h1>
        <p style="margin-bottom: 0; color: #666;">This is a test email sent via Telegram Email Tester Bot</p>
    </div>
    
    <div style="background-color: #ffffff; padding: 20px; border: 1px solid #dee2e6; border-radius: 8px; margin-bottom: 20px;">
        <h2 style="color: #495057; margin-top: 0;">Test Link</h2>
        <p>Click the button below to test the HTML link functionality:</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="https://{self.custom_domain}" target="_blank" style="display: inline-block; text-decoration: none; background-color: blue; color: white; padding: 10px 20px; border-radius: 4px; font-weight: bold;">456756</a>
        </div>
        
        <p style="font-size: 14px; color: #6c757d;">
            <strong>Link Details:</strong><br>
            • URL: https://{self.custom_domain}<br>
            • Target: _blank (opens in new tab)<br>
            • Style: Blue background, white text, bold font
        </p>
    </div>
    
    <div style="background-color: #e8f5e8; padding: 15px; border-radius: 8px; border-left: 4px solid #28a745;">
        <h3 style="color: #155724; margin-top: 0;">✅ Test Results</h3>
        <p style="color: #155724; margin-bottom: 0;">
            If you received this email, your SMTP configuration is working correctly!
        </p>
    </div>
    
    <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; font-size: 12px; color: #6c757d; text-align: center;">
        <p>This email was sent by Telegram Email Tester Bot</p>
        <p>Timestamp: {{timestamp}}</p>
    </div>
</body>
</html>
        """
        
        # Plain text version for clients that don't support HTML
        text_content = f"""
Email Delivery Test - Telegram Bot

This is a test email sent via Telegram Email Tester Bot.

Test Link: https://{self.custom_domain}
Button Text: 456756

If you received this email, your SMTP configuration is working correctly!

---
This email was sent by Telegram Email Tester Bot
        """
        
        # Add timestamp
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        html_content = html_content.format(timestamp=timestamp)
        
        # Create message parts
        text_part = MIMEText(text_content, 'plain')
        html_part = MIMEText(html_content, 'html')
        
        # Attach parts
        message.attach(text_part)
        message.attach(html_part)
        
        return message
