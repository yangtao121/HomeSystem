"""
Common authentication utilities for remote services.
"""
import os
import hashlib
import hmac
from typing import Optional
from functools import wraps
from flask import request, jsonify, current_app


def generate_api_key() -> str:
    """Generate a simple API key."""
    import secrets
    return secrets.token_urlsafe(32)


def verify_api_key(provided_key: str, expected_key: str) -> bool:
    """Verify API key using secure comparison."""
    if not provided_key or not expected_key:
        return False
    return hmac.compare_digest(provided_key, expected_key)


def require_api_key(f):
    """Decorator to require API key authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = os.getenv('API_KEY')
        
        # If no API key is configured, skip authentication
        if not api_key:
            return f(*args, **kwargs)
        
        # Check for API key in headers
        provided_key = request.headers.get('X-API-Key') or request.headers.get('Authorization')
        
        if provided_key and provided_key.startswith('Bearer '):
            provided_key = provided_key[7:]  # Remove 'Bearer ' prefix
        
        if not verify_api_key(provided_key, api_key):
            return jsonify({'error': 'Invalid or missing API key'}), 401
        
        return f(*args, **kwargs)
    
    return decorated_function


def get_client_ip() -> str:
    """Get client IP address, considering proxies."""
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        return request.environ['REMOTE_ADDR']
    else:
        return request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()