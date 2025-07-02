"""
Validation module for the Telegram Email Tester Bot
Contains validation functions for emails and SMTP configurations
"""

import re
from typing import Dict, List, Any

def validate_email(email: str) -> bool:
    """Validate email address format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_email_list(emails: List[str]) -> Dict[str, Any]:
    """Validate a list of email addresses"""
    if not emails:
        return {
            'valid': False,
            'error': 'No email addresses provided',
            'valid_emails': [],
            'invalid_emails': [],
            'valid_count': 0,
            'invalid_count': 0
        }

    if len(emails) > 100:
        return {
            'valid': False,
            'error': 'Too many email addresses. Maximum 100 allowed per test',
            'valid_emails': [],
            'invalid_emails': [],
            'valid_count': 0,
            'invalid_count': 0
        }

    valid_emails = []
    invalid_emails = []

    for email in emails:
        email = email.strip()
        if not email:
            continue

        if validate_email(email):
            valid_emails.append(email)
        else:
            invalid_emails.append(email)

    return {
        'valid': len(valid_emails) > 0,
        'error': None if len(valid_emails) > 0 else 'No valid email addresses found',
        'valid_emails': valid_emails,
        'invalid_emails': invalid_emails,
        'valid_count': len(valid_emails),
        'invalid_count': len(invalid_emails)
    }

def validate_smtp_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate SMTP configuration"""
    required_fields = ['host', 'port', 'username', 'password']

    for field in required_fields:
        if field not in config:
            return {
                'valid': False,
                'error': f'Missing required field: {field}'
            }

    # Validate port
    try:
        port = int(config['port'])
        if port < 1 or port > 65535:
            return {
                'valid': False,
                'error': 'Port must be between 1 and 65535'
            }
    except (ValueError, TypeError):
        return {
            'valid': False,
            'error': 'Port must be a valid number'
        }

    # Validate boolean fields
    boolean_fields = ['use_tls', 'use_ssl']
    for field in boolean_fields:
        if field in config and not isinstance(config[field], bool):
            return {
                'valid': False,
                'error': f'{field} must be true or false'
            }

    # Validate that both TLS and SSL are not enabled
    if config.get('use_tls', False) and config.get('use_ssl', False):
        return {
            'valid': False,
            'error': 'Cannot use both TLS and SSL simultaneously'
        }

    # Basic validation for host and credentials
    if not config['host'].strip():
        return {
            'valid': False,
            'error': 'Host cannot be empty'
        }

    if not config['username'].strip():
        return {
            'valid': False,
            'error': 'Username cannot be empty'
        }

    if not config['password'].strip():
        return {
            'valid': False,
            'error': 'Password cannot be empty'
        }

    return {
        'valid': True,
        'error': None
    }