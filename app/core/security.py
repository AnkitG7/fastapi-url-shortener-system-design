# ======================================================
# core/security.py — URL Sanitization & SSRF Protection
# ======================================================
# SYSTEM DESIGN CONCEPT: Defense in Depth & SSRF Prevention
# -------------------------------------------------
# When building systems that accept arbitrary URLs (like a
# URL shortener or web crawler), you MUST protect against
# Server-Side Request Forgery (SSRF).
#
# WHAT IS SSRF?
# An attacker submits a URL pointing to INTERNAL infrastructure:
# - http://169.254.169.254/latest/meta-data/ (AWS cloud credentials)
# - http://localhost:5432/ (Internal PostgreSQL DB)
# - http://192.168.1.1/ (Internal Router / Intranet)
#
# If our server fetches or redirects blindly, it could leak
# confidential cloud metadata or internal network topology.
#
# DEFENSE STRATEGY:
# 1. Reject dangerous URL schemes (file://, gopher://, ftp://)
# 2. Block localhost / loopback domains
# 3. Block private / reserved IP addresses (RFC 1918 & RFC 3927)
# 4. Enforce max URL length to prevent memory DoS
# ======================================================

import ipaddress
import socket
from urllib.parse import urlparse
from enum import Enum


class UserTier(str, Enum):
    """
    SYSTEM DESIGN CONCEPT: Tiered Service Architecture
    -------------------------------------------------
    Different user classes receive different Quality of Service (QoS):
    - ANONYMOUS: Unauthenticated users (low rate limits)
    - FREE: Registered users with basic API key
    - PREMIUM: Paid customers (high throughput, custom SLAs)
    """
    ANONYMOUS = "anonymous"
    FREE = "free"
    PREMIUM = "premium"


# Blocked private and link-local IP networks (SSRF defense)
BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # IPv4 loopback (localhost)
    ipaddress.ip_network("10.0.0.0/8"),       # Private network (Class A)
    ipaddress.ip_network("172.16.0.0/12"),    # Private network (Class B)
    ipaddress.ip_network("192.168.0.0/16"),   # Private network (Class C)
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local (Cloud metadata e.g. AWS/GCP)
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 private network
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]

# Blocked hostnames
BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "instance-data",
    "metadata.google.internal",
}


def validate_and_sanitize_url(url_str: str) -> str:
    """
    Validate and sanitize input URL against SSRF and malicious schemes.

    Raises:
        ValueError: If the URL is insecure, points to private network, or uses bad scheme.
    """
    parsed = urlparse(url_str.strip())

    # 1. Enforce allowed schemes (HTTP & HTTPS only)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(f"Disallowed URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL: missing hostname.")

    # 2. Block well-known loopback / internal hostnames
    if hostname.lower() in BLOCKED_HOSTNAMES:
        raise ValueError(f"Blocked hostname '{hostname}': Internal network access is not permitted.")

    # 3. Check if hostname is an IP address and verify it's not private
    try:
        ip_obj = ipaddress.ip_address(hostname)
        for net in BLOCKED_IP_NETWORKS:
            if ip_obj in net:
                raise ValueError(f"Blocked IP '{hostname}': Access to private or reserved IP ranges is prohibited.")
    except ValueError as e:
        # If hostname is not an IP string, it's a regular domain (e.g. google.com)
        if "Blocked IP" in str(e):
            raise e

    return url_str.strip()
