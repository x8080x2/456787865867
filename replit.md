# Telegram Email Tester Bot

## Overview

This project is a Telegram bot designed to test email delivery functionality using user-provided SMTP credentials. The bot allows users to configure SMTP settings, validate email addresses, and send test emails to verify email delivery capabilities. It's built using Python with the python-telegram-bot library and includes comprehensive validation, rate limiting, and security features.

## System Architecture

### Architecture Type
Monolithic Python application with modular design, consisting of:
- **Bot Interface Layer**: Telegram bot handlers and user interaction
- **Email Processing Layer**: SMTP connection handling and email sending
- **Validation Layer**: Input validation for emails and SMTP configurations
- **Configuration Layer**: Environment-based configuration management

### Communication Pattern
- Synchronous Telegram API interactions for user commands
- Asynchronous email operations to prevent blocking
- Thread pool execution for SMTP operations

## Key Components

### 1. Main Bot Application (`main.py`)
- **Purpose**: Core bot logic and Telegram API integration
- **Key Features**: 
  - Command handlers for user interactions
  - Session management for user data
  - Conversation flow management
- **Architecture Decision**: Uses python-telegram-bot framework for robust Telegram integration

### 2. Email Handler (`email_handler.py`)
- **Purpose**: SMTP connection management and email sending
- **Key Features**:
  - Asynchronous SMTP operations
  - Support for TLS/SSL connections
  - Connection testing capabilities
- **Architecture Decision**: Async wrapper around synchronous SMTP operations to prevent bot blocking

### 3. Validation Module (`validators.py`)
- **Purpose**: Input validation for security and reliability
- **Key Features**:
  - Email format validation with RFC compliance
  - SMTP configuration validation
  - Security checks for input sanitization
- **Architecture Decision**: Separate validation layer for maintainability and security

### 4. Configuration Management (`config.py`)
- **Purpose**: Centralized configuration handling
- **Key Features**:
  - Environment variable management
  - Rate limiting settings
  - SMTP provider presets
- **Architecture Decision**: Environment-based configuration for deployment flexibility

## Data Flow

### Email Testing Process
1. User initiates `/test` command
2. Bot prompts for SMTP configuration
3. Configuration is validated using validators module
4. Bot requests target email addresses
5. Email addresses are validated
6. EmailHandler creates SMTP connection
7. Test emails are sent asynchronously
8. Results are reported back to user

### Session Management
- Temporary in-memory storage for user session data
- Session timeout mechanism for security
- No persistent data storage (stateless design)

## External Dependencies

### Core Dependencies
- **python-telegram-bot**: Telegram Bot API integration
- **smtplib**: Built-in Python SMTP client
- **asyncio**: Asynchronous operation support
- **ssl**: Secure connection handling

### SMTP Provider Support
- Gmail (smtp.gmail.com:587)
- Outlook (smtp-mail.outlook.com:587)
- Yahoo (smtp.mail.yahoo.com:587)
- Custom SMTP servers

## Deployment Strategy

### Environment Configuration
- Uses environment variables for sensitive configuration
- Required environment variables:
  - `TELEGRAM_BOT_TOKEN`: Bot authentication token
  - Optional rate limiting and security parameters

### Security Considerations
- No persistent storage of user credentials
- Session timeout mechanisms
- Rate limiting to prevent abuse
- Input validation and sanitization

### Scalability Design
- Stateless architecture for horizontal scaling
- Async operations for concurrent user handling
- Configurable rate limits per user

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes

- **July 29, 2025**: Enhanced Bot Flow with Auto-Domain Cycling and Batch Processing
  - ✓ Eliminated manual domain selection step for streamlined user experience
  - ✓ Implemented automatic domain cycling - system cycles through all available domains
  - ✓ Added batch email processing - sends 5 emails at a time with continue/stop options
  - ✓ Enhanced session management to track email progress and domain rotation
  - ✓ Added interactive buttons for "Send Next 5" and "Stop Sending" functionality
  - ✓ Fixed SMTP parsing logic - password now correctly detected after username (not before)
  - ✓ Removed email limit restriction - now supports unlimited recipient emails
  - **User Experience**: Simplified flow from SMTP input directly to batch email sending
  - **Architecture**: Maintained async operations with improved batch processing logic
  - **Format**: `server port username password from_email tls_setting recipient_emails...`

- **July 29, 2025**: Successfully completed migration from Replit Agent to standard Replit environment
  - ✓ Verified all dependencies installed correctly (httpx, python-telegram-bot, telegram)
  - ✓ Fixed missing `handle_email_list` method in session management
  - ✓ Configured TELEGRAM_BOT_TOKEN environment variable securely
  - ✓ Bot successfully connected to Telegram API and running
  - ✓ All core features operational: email testing, domain management, admin panel
  - **Security**: Proper environment-based secrets management implemented
  - **Architecture**: Maintained modular design with async operations for Replit compatibility

- **July 29, 2025**: Comprehensive SMTP Parsing Logic Fix 
  - ✓ Fixed critical password detection bug - now correctly looks AFTER username instead of before
  - ✓ Updated all parsing methods across entire project with unified smart parsing logic
  - ✓ Fixed error messages and help documentation to show correct format examples
  - ✓ Verified parsing works with various SMTP providers (iCloud, Gmail, AWS SES, etc.)
  - ✓ Maintained backward compatibility while fixing core parsing logic
  - **Critical Fix**: Password now correctly parsed from position after username in format
  - **Format**: `server port username password from_email tls_setting recipient_emails...`

- **July 08, 2025**: Enhanced SMTP Configuration with Custom From Email Support
  - ✓ Added from_email field to SMTP configuration allowing separate sender and authentication emails
  - ✓ Updated email handler to use custom from_email when provided, fallback to username
  - ✓ Enhanced smart parsing to detect and handle multiple email addresses in configuration
  - ✓ Updated help documentation with new format examples and usage instructions
  - **Enhancement**: Users can now specify different sender email addresses for better deliverability

- **July 08, 2025**: Successfully migrated and deployed Telegram Email Tester Bot to Replit
  - ✓ Migrated project from Replit Agent to standard Replit environment
  - ✓ Installed and configured all required dependencies (httpx, python-telegram-bot, telegram)
  - ✓ Configured secure environment variables for TELEGRAM_BOT_TOKEN
  - ✓ Verified bot connectivity to Telegram API with proper authentication
  - ✓ Bot is running successfully and ready for email testing functionality
  - ✓ Migration completed successfully with full functionality preserved
  - **Security Enhancement**: Proper client/server separation with environment-based secrets management
  - **Architecture**: Maintains modular Python architecture with async operations for reliable Replit compatibility

## Changelog

- July 02, 2025: Initial setup and successful bot deployment