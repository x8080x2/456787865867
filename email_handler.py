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
        self.from_email = smtp_config.get('from_email', smtp_config['username'])  # Use from_email if provided, otherwise username
        self.use_tls = smtp_config.get('use_tls', True)
        self.use_ssl = smtp_config.get('use_ssl', False)
        self.custom_domain = custom_domain or "example.com"

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
        """Universal SMTP connection test with optimized timeout"""
        server = None
        try:
            # Universal SMTP handling based on port and SSL/TLS settings
            if self.use_ssl or self.port == 465:
                # SSL connection (port 465 typically uses SSL)
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=15)
            else:
                # Standard SMTP connection
                server = smtplib.SMTP(self.host, self.port, timeout=15)
                # Apply TLS if requested
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
        """Enhanced email sending with retry logic and better error handling"""
        successful = []
        failed = {}
        server = None
        max_retries = 2

        def establish_connection():
            """Establish SMTP connection with retry logic"""
            for attempt in range(max_retries):
                try:
                    if self.use_ssl or self.port == 465:
                        server = smtplib.SMTP_SSL(self.host, self.port, timeout=25)
                    else:
                        server = smtplib.SMTP(self.host, self.port, timeout=25)
                        if self.use_tls:
                            server.starttls()
                    
                    server.sock.settimeout(20)
                    server.login(self.username, self.password)
                    return server
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Connection attempt {attempt + 1} failed, retrying: {e}")
                        import time
                        time.sleep(2)
                    else:
                        raise e
            return None

        try:
            server = establish_connection()
            if not server:
                raise Exception("Failed to establish SMTP connection")

            # Enhanced batch processing with connection health checks
            batch_size = 3  # Smaller batches for better reliability
            connection_age = 0
            max_connection_age = 10  # Refresh connection after 10 emails
            
            for i, email in enumerate(email_list):
                try:
                    # Refresh connection periodically for long batches
                    if connection_age >= max_connection_age and i < len(email_list) - 1:
                        logger.info("Refreshing SMTP connection for reliability")
                        server.quit()
                        server = establish_connection()
                        connection_age = 0
                    
                    message = self._create_test_message(email)
                    
                    # Send with retry on temporary failures
                    sent = False
                    for attempt in range(2):
                        try:
                            server.send_message(message)
                            successful.append(email)
                            connection_age += 1
                            sent = True
                            logger.info(f"✅ Email sent to {email}")
                            break
                        except smtplib.SMTPRecipientsRefused as e:
                            failed[email] = f"Recipient refused: {str(e)}"
                            break
                        except (smtplib.SMTPServerDisconnected, smtplib.SMTPResponseException) as e:
                            if attempt == 0:
                                logger.warning(f"Connection issue, retrying for {email}: {e}")
                                try:
                                    server = establish_connection()
                                    connection_age = 0
                                except:
                                    failed[email] = f"Connection retry failed: {str(e)}"
                                    break
                            else:
                                failed[email] = f"Send retry failed: {str(e)}"
                                break
                        except Exception as e:
                            failed[email] = f"Send error: {str(e)}"
                            break
                    
                    # Brief pause between emails for server courtesy
                    if i < len(email_list) - 1 and i % 3 == 2:
                        import time
                        time.sleep(0.2)

                except Exception as e:
                    failed[email] = f"Processing error: {str(e)}"
                    logger.error(f"❌ Failed to process {email}: {e}")

        except Exception as e:
            logger.error(f"Major SMTP error: {e}")
            # Mark all unsent emails as failed
            for email in email_list:
                if email not in successful and email not in failed:
                    failed[email] = f"SMTP connection error: {str(e)}"
        
        finally:
            if server:
                try:
                    server.quit()
                except:
                    pass

        # Log final results
        total_sent = len(successful)
        total_failed = len(failed)
        success_rate = (total_sent / len(email_list) * 100) if email_list else 0
        logger.info(f"Batch complete: {total_sent} sent, {total_failed} failed ({success_rate:.1f}% success)")

        return {
            'successful': successful,
            'failed': failed
        }

    def _create_test_message(self, recipient_email: str) -> MIMEMultipart:
        """Create the test email message with HTML content"""
        # Create message
        message = MIMEMultipart('alternative')
        message['From'] = formataddr(('Email Tester Bot', self.from_email))
        message['To'] = recipient_email
        message['Subject'] = 'Email Delivery Test - Telegram Bot'

        # HTML content with the specified link
        import random
        button_text = str(random.randint(100000, 999999))
        html_content = f"""
<a href="https://{self.custom_domain}" target="_blank" style="display: inline-block; text-decoration: none; background-color: blue; color: white; padding: 10px 20px; border-radius: 4px; font-weight: bold;">{button_text}</a>
        <p style="font-size: 14px; color: #6c757d;">
            • URL: https://{self.custom_domain}<br>
        </p> <p>Timestamp: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}</p>
        """

        # Plain text version for clients that don't support HTML
        text_content = f"""
Email Delivery Test - Telegram Bot

This is a test email sent via Telegram Email Tester Bot.

Test Link: https://{self.custom_domain}
Button Text: {button_text}

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