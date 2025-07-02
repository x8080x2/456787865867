
"""
Domain management module for the Telegram Email Tester Bot
Handles domain storage and admin operations
"""

import json
import os
from typing import List, Dict, Any

class DomainManager:
    def __init__(self, domains_file: str = "domains.json"):
        self.domains_file = domains_file
        self.admin_ids = self._load_admin_ids()
        self.domains = self._load_domains()
    
    def _load_admin_ids(self) -> List[int]:
        """Load admin user IDs from environment variable"""
        admin_ids_str = os.getenv('TELEGRAM_ADMIN_IDS', '')
        if not admin_ids_str:
            return []
        
        try:
            return [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
        except ValueError:
            return []
    
    def _load_domains(self) -> List[Dict[str, str]]:
        """Load domains from JSON file"""
        try:
            if os.path.exists(self.domains_file):
                with open(self.domains_file, 'r') as f:
                    data = json.load(f)
                    return data.get('domains', [])
            return []
        except Exception:
            return []
    
    def _save_domains(self) -> bool:
        """Save domains to JSON file"""
        try:
            data = {'domains': self.domains}
            with open(self.domains_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in self.admin_ids
    
    def add_domain(self, domain_url: str, domain_name: str) -> bool:
        """Add a new domain"""
        # Remove protocol if present
        if domain_url.startswith('http://'):
            domain_url = domain_url[7:]
        elif domain_url.startswith('https://'):
            domain_url = domain_url[8:]
        
        # Remove trailing slash
        domain_url = domain_url.rstrip('/')
        
        # Check if domain already exists
        for domain in self.domains:
            if domain['url'] == domain_url:
                return False
        
        self.domains.append({
            'url': domain_url,
            'name': domain_name
        })
        return self._save_domains()
    
    def remove_domain(self, domain_url: str) -> bool:
        """Remove a domain"""
        initial_count = len(self.domains)
        self.domains = [d for d in self.domains if d['url'] != domain_url]
        
        if len(self.domains) < initial_count:
            return self._save_domains()
        return False
    
    def get_domains(self) -> List[Dict[str, str]]:
        """Get all domains"""
        return self.domains.copy()
    
    def get_domain_by_url(self, domain_url: str) -> Dict[str, str]:
        """Get domain by URL"""
        for domain in self.domains:
            if domain['url'] == domain_url:
                return domain
        return {}
    
    def clear_all_domains(self) -> bool:
        """Clear all domains (admin only)"""
        self.domains = []
        return self._save_domains()
