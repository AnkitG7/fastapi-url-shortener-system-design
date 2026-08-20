# 🎯 URL Shortener — System Design Interview Masterclass

This guide provides the exact step-by-step framework to ace a **System Design Interview** for a URL Shortener (e.g. TinyURL, Bit.ly) at top tech companies.

---

## Step 1: Requirements Gathering (Scope the Problem)

Always spend the first 3–5 minutes clarifying requirements.

### Functional Requirements (What the system must DO)
1. **Shorten URL**: Given a long URL, return a unique shortened URL.
2. **Redirect**: Given a short code, redirect the user to the original long URL with minimum latency.
3. **Custom Aliases**: Users can optionally pick their own custom short code (e.g., `my-custom-link`).
4. **Expiration**: Links can optionally expire after a specified duration.
5. **Analytics**: Track total click counts, 24h trends, top referrers, and user agents.

### Non-Functional Requirements (System Quality Attributes)
1. **High Availability**: The redirect service must have $99.99\%$ uptime.
2. **Ultra-Low Latency**: Redirects must complete in $<10\text{ms}$ (using Redis caching).
3. **High Read-to-Write Ratio**: $100:1$ read-heavy workload.
4. **Unpredictable Short Codes**: Codes should not be sequentially guessable (security against enumeration attacks).
5. **Reliability & Data Durability**: Once written, URLs must never be lost.

---

## Step 2: Back-of-the-Envelope Estimations

### Traffic (QPS)
- **New URLs Created**: $1\text{ Million / day}$
  $$\text{Write QPS} = \frac{1,000,000}{86,400\text{s}} \approx 12\text{ writes/sec}$$
  $$\text{Peak Write QPS} = 12 \times 3 \approx 36\text{ writes/sec}$$

- **URL Redirects (100:1 Ratio)**: $100\text{ Million / day}$
  $$\text{Read QPS} = \frac{100,000,000}{86,400\text{s}} \approx 1,160\text{ reads/sec}$$
  $$\text{Peak Read QPS} \approx 3,500\text{ reads/sec}$$

### Storage Estimations (5-Year Horizon)
- Size per URL record $\approx 600\text{ bytes}$.
- Total records in 5 years:
  $$1\text{M/day} \times 365 \times 5 = 1.825\text{ Billion records}$$
- Total 5-Year Database Storage:
  $$1.825\text{B} \times 600\text{ bytes} \approx 1.1\text{ TB}$$

### Memory (Cache Sizing)
- Applying the **80/20 Pareto Principle**: $20\%$ of links generate $80\%$ of read traffic.
- Daily active URLs to cache: $20\% \times 100\text{M} = 20\text{ Million URLs}$.
- RAM required for Redis:
  $$20\text{M} \times 600\text{ bytes} \approx 12\text{ GB RAM}$$
  *(Can easily fit on a single Redis instance or a 2-node cluster).*

---

## Step 3: API Design

```http
POST /api/v1/shorten
Request:
{
  "original_url": "https://www.example.com/very/long/url",
  "custom_code": "optional-custom-alias",
  "expires_in_hours": 24
}
Response (201 Created):
{
  "short_code": "k5ZgY6b",
  "short_url": "http://localhost/k5ZgY6b",
  "original_url": "https://www.example.com/very/long/url",
  "created_at": "2026-08-20T12:00:00Z",
  "expires_at": "2026-08-21T12:00:00Z"
}

GET /{short_code}
Response: 307 Temporary Redirect (Location: https://www.example.com/very/long/url)

GET /api/v1/urls/{short_code}/analytics
Response (200 OK):
{
  "short_code": "k5ZgY6b",
  "total_clicks": 1420,
  "clicks_last_24h": 350,
  "top_referrers": [{"referrer": "https://twitter.com", "count": 210}],
  "top_user_agents": [{"user_agent": "Chrome Mobile", "count": 180}]
}
```

---

## Step 4: Database Schema Design (SQL vs. NoSQL)

### SQL vs. NoSQL Trade-off
- **Why Relational (PostgreSQL)**:
  - Strong ACID guarantees for URL creation and uniqueness constraints.
  - Relational joins between `urls` and `clicks` tables for analytics.
  - B-tree indexing allows sub-millisecond lookups.
- **When to consider NoSQL (DynamoDB / Cassandra)**:
  - If URL storage exceeds billions of rows and requires multi-region horizontal partitioning across hundreds of nodes.

---

## Step 5: High-Level Architecture Diagram

```
[ Client ] ---> [ Nginx Load Balancer ]
                        |
       +----------------+----------------+
       |                                 |
       v                                 v
[ App Replica 1 ]                [ App Replica 2 ]
       |                                 |
       +---------------+-----------------+
                       |
        +--------------+--------------+
        |                             |
        v                             v
[ Redis Cache ]               [ PostgreSQL DB ]
 (Cache-Aside)                 (Durable Storage)
```

---

## Step 6: Common Interview Deep-Dive Questions & Answers

### Q1: How do you generate unique 7-character short codes?
- **Base62 Encoding**: 62 characters (`[a-z], [A-Z], [0-9]`).
  $$62^7 = 3.52\text{ Trillion unique combinations}$$
- **Approaches**:
  1. *Counter-based Base62*: Use an auto-incrementing ID or distributed ID generator (Twitter Snowflake) and convert the integer to Base62.
  2. *ShortUUID / MD5 Hash with Collision Check*: Hash the URL and take the first 7 characters; if collision occurs in DB/Cache, append salt and retry.

### Q2: What happens if a popular celebrity tweets a link (Hot Key Problem / Thundering Herd)?
1. **Cache-Aside with Redis**: The URL is cached in Redis memory, handling 100,000+ QPS without touching the database.
2. **Local In-Memory Cache (L1 Cache)**: Application instances can cache the hot URL in local process memory for 5 seconds to reduce Redis network traffic.
3. **Async Telemetry**: Click events are sent to an in-memory queue (`EventBus`) so the database is never flooded with millions of individual insert queries.

### Q3: How do you handle expired URLs?
- **Lazy Deletion**: When a user accesses an expired link, check `expires_at < now()`. If expired, delete from cache and DB and return `404 Not Found`.
- **Active Cleanup Worker**: Run a scheduled cron job (e.g. daily at midnight) that deletes all records where `expires_at < now()`.

### Q4: How do you prevent malicious users from abusing the API?
1. **Sliding Window Rate Limiting** using Redis Sorted Sets (`ZSET`).
2. **SSRF Filtering**: Block private IP subnets (`10.0.0.0/8`, `192.168.0.0/16`) and Cloud Metadata (`169.254.169.254`).
3. **Tiered API Keys**: Anonymous (10 req/min), Free (100 req/min), Premium (1000 req/min).
