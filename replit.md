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

- **July 02, 2025**: Successfully migrated and deployed Telegram Email Tester Bot to Replit
  - ✓ Migrated project from Replit Agent to standard Replit environment
  - ✓ Installed and configured all required dependencies (httpx, python-telegram-bot)
  - ✓ Configured secure environment variables for TELEGRAM_BOT_TOKEN
  - ✓ Verified bot connectivity to Telegram API with proper authentication
  - ✓ Bot is running successfully and ready for email testing functionality
  - **Security Enhancement**: Proper client/server separation with environment-based secrets management
  - **Architecture**: Simple HTTP API implementation maintains reliability while ensuring Replit compatibility

## Changelog

- July 02, 2025: Initial setup and successful bot deployment