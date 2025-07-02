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
import concurrent.futures
import datetime

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
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, self._test_connection_sync)
            return result
        except Exception as e:
            logger.error(f"Connection test error: {e}")
            return {
                'success': False,
                'error': f"Connection test failed: {str(e)}"
            }

    def _test_connection_sync(self) -> Dict[str, Any]:
        """Fast SMTP connection test with optimized timeout"""
        server = None
        try:
            # Special handling for iCloud SMTP
            if 'mail.me.com' in self.host or 'icloud' in self.host.lower():
                server = smtplib.SMTP(self.host, self.port, timeout=15)
                server.starttls()  # iCloud requires STARTTLS
            elif self.use_ssl:
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=15)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=15)
                if self.use_tls:
                    server.starttls()

            # Set timeout for login
            server.sock.settimeout(12)
            server.login(self.username, self.password)
            
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
        finally:
            if server:
                try:
                    server.quit()
                except:
                    pass

    async def send_test_emails(self, email_list: List[str]) -> Dict[str, Any]:
        """Send test emails to the provided list"""
        try:
            # Run email sending in thread pool
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, self._send_emails_sync, email_list)
            return result
        except Exception as e:
            logger.error(f"Email sending error: {e}")
            return {
                'successful': [],
                'failed': {email: str(e) for email in email_list}
            }

    def _send_emails_sync(self, email_list: List[str]) -> Dict[str, Any]:
        """Optimized synchronous email sending with connection reuse"""
        successful = []
        failed = {}
        server = None

        try:
            # Establish SMTP connection with timeout
            if 'mail.me.com' in self.host or 'icloud' in self.host.lower():
                server = smtplib.SMTP(self.host, self.port, timeout=20)
                server.starttls()  # iCloud requires STARTTLS
            elif self.use_ssl:
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=20)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=20)
                if self.use_tls:
                    server.starttls()

            # Set timeout for operations
            server.sock.settimeout(15)
            server.login(self.username, self.password)

            # Send emails in batches for better performance
            batch_size = 5
            for i in range(0, len(email_list), batch_size):
                batch = email_list[i:i + batch_size]
                
                for email in batch:
                    try:
                        message = self._create_test_message(email)
                        # Use send_message which is more efficient
                        server.send_message(message)
                        successful.append(email)
                        logger.info(f"Email sent to {email}")

                    except Exception as e:
                        failed[email] = str(e)
                        logger.error(f"Failed to send to {email}: {e}")
                
                # Small delay between batches to avoid overwhelming the server
                if i + batch_size < len(email_list):
                    import time
                    time.sleep(0.1)

        except Exception as e:
            # If connection fails, mark all remaining emails as failed
            for email in email_list:
                if email not in successful and email not in failed:
                    failed[email] = f"SMTP connection error: {str(e)}"
        
        finally:
            if server:
                try:
                    server.quit()
                except:
                    pass

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
        <p>Timestamp: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}</p>
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

        # Create message parts
        text_part = MIMEText(text_content, 'plain')
        html_part = MIMEText(html_content, 'html')

        # Attach parts
        message.attach(text_part)
        message.attach(html_part)

        return message