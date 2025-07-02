"""
Validation module for the Telegram Email Tester Bot
Contains validators for email addresses and SMTP configurations
"""

import re
import socket
from typing import Dict, Any

def validate_email(email: str) -> bool:
    """Validate email address format"""
    if not email or not isinstance(email, str):
        return False
    
    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    # Check format
    if not re.match(pattern, email):
        return False
    
    # Additional checks
    if len(email) > 254:  # RFC 5321 limit
        return False
    
    # Check local part (before @)
    local, domain = email.rsplit('@', 1)
    if len(local) > 64:  # RFC 5321 limit
        return False
    
    return True

def validate_smtp_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate SMTP configuration"""
    required_fields = ['host', 'port', 'username', 'password']
    
    # Check if config is a dictionary
    if not isinstance(config, dict):
        return {
            'valid': False,
            'error': 'Configuration must be a JSON object'
        }
    
    # Check required fields
    for field in required_fields:
        if field not in config:
            return {
                'valid': False,
                'error': f'Missing required field: {field}'
            }
        
        if not config[field]:
            return {
                'valid': False,
                'error': f'Field {field} cannot be empty'
            }
    
    # Validate host
    host = config['host']
    if not isinstance(host, str) or len(host.strip()) == 0:
        return {
            'valid': False,
            'error': 'Host must be a non-empty string'
        }
    
    # Validate port
    port = config['port']
    if not isinstance(port, int) or port <= 0 or port > 65535:
        return {
            'valid': False,
            'error': 'Port must be an integer between 1 and 65535'
        }
    
    # Validate username (should be email format for most providers)
    username = config['username']
    if not isinstance(username, str) or len(username.strip()) == 0:
        return {
            'valid': False,
            'error': 'Username must be a non-empty string'
        }
    
    # Validate password
    password = config['password']
    if not isinstance(password, str) or len(password.strip()) == 0:
        return {
            'valid': False,
            'error': 'Password must be a non-empty string'
        }
    
    # Validate boolean flags
    use_tls = config.get('use_tls', True)
    use_ssl = config.get('use_ssl', False)
    
    if not isinstance(use_tls, bool):
        return {
            'valid': False,
            'error': 'use_tls must be a boolean (true/false)'
        }
    
    if not isinstance(use_ssl, bool):
        return {
            'valid': False,
            'error': 'use_ssl must be a boolean (true/false)'
        }
    
    # Check for conflicting SSL/TLS settings
    if use_tls and use_ssl:
        return {
            'valid': False,
            'error': 'Cannot use both TLS and SSL simultaneously. Choose one.'
        }
    
    # Validate common port/security combinations
    common_ports = {
        25: {'tls': False, 'ssl': False, 'note': 'Plain SMTP (not recommended)'},
        587: {'tls': True, 'ssl': False, 'note': 'SMTP with STARTTLS (recommended)'},
        465: {'tls': False, 'ssl': True, 'note': 'SMTP over SSL'},
        2525: {'tls': True, 'ssl': False, 'note': 'Alternative SMTP port with TLS'}
    }
    
    if port in common_ports:
        expected = common_ports[port]
        if use_tls != expected['tls'] or use_ssl != expected['ssl']:
            return {
                'valid': False,
                'error': f'Port {port} typically uses TLS={expected["tls"]}, SSL={expected["ssl"]} - {expected["note"]}'
            }
    
    # Basic hostname validation
    if not _is_valid_hostname(host):
        return {
            'valid': False,
            'error': 'Invalid hostname format'
        }
    
    return {
        'valid': True,
        'message': 'SMTP configuration is valid'
    }

def _is_valid_hostname(hostname: str) -> bool:
    """Validate hostname format"""
    if len(hostname) > 255:
        return False
    
    # Remove trailing dot if present
    if hostname.endswith('.'):
        hostname = hostname[:-1]
    
    # Check each label
    labels = hostname.split('.')
    if not labels:
        return False
    
    for label in labels:
        if not label:
            return False
        if len(label) > 63:
            return False
        if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$', label):
            return False
    
    return True

def validate_email_list(emails: list) -> Dict[str, Any]:
    """Validate a list of email addresses"""
    if not isinstance(emails, list):
        return {
            'valid': False,
            'error': 'Email list must be an array'
        }
    
    if len(emails) == 0:
        return {
            'valid': False,
            'error': 'Email list cannot be empty'
        }
    
    if len(emails) > 100:  # Rate limiting
        return {
            'valid': False,
            'error': 'Maximum 100 emails allowed per test'
        }
    
    valid_emails = []
    invalid_emails = []
    
    for email in emails:
        if validate_email(email):
            valid_emails.append(email)
        else:
            invalid_emails.append(email)
    
    return {
        'valid': len(valid_emails) > 0,
        'valid_emails': valid_emails,
        'invalid_emails': invalid_emails,
        'total': len(emails),
        'valid_count': len(valid_emails),
        'invalid_count': len(invalid_emails)
    }
