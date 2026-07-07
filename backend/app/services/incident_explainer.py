"""
Rule-based incident explanation engine.

Maps every AttackCategory to a developer-friendly explanation:
  - plain_english  : what actually happened, jargon-free
  - business_impact: what this means for revenue, users, reputation
  - technical_impact: what systems/data are at risk
  - likelihood     : how likely this is to escalate (Low/Medium/High/Critical)
  - owasp          : OWASP Top 10 mapping
  - mitre_attack   : MITRE ATT&CK technique(s)
  - recommended_fixes: ordered list of actionable steps
  - severity_hint  : suggested triage severity if not already set
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IncidentExplanation:
    category: str
    plain_english: str
    business_impact: str
    technical_impact: str
    likelihood: str                  # "Low" | "Medium" | "High" | "Critical"
    owasp: Optional[str]
    mitre_attack: list[str]
    recommended_fixes: list[str]
    severity_hint: str               # "info" | "low" | "medium" | "high" | "critical"
    learn_more_url: Optional[str] = None


_EXPLANATIONS: dict[str, IncidentExplanation] = {

    "BENIGN": IncidentExplanation(
        category="BENIGN",
        plain_english=(
            "This traffic was flagged by the ML model but is likely normal application "
            "activity. No real attack was detected."
        ),
        business_impact="No business impact expected.",
        technical_impact="No systems are at risk from this event.",
        likelihood="Low",
        owasp=None,
        mitre_attack=[],
        recommended_fixes=[
            "Confirm this is expected traffic from your logs.",
            "If this false-positive fires repeatedly, consider retraining the ML model with "
            "more labelled data from your application.",
        ],
        severity_hint="info",
    ),

    "PortScan": IncidentExplanation(
        category="PortScan",
        plain_english=(
            "An attacker (or automated tool) systematically tried to find open doors "
            "into your server. Think of it like a burglar testing every lock on your building "
            "before deciding where to break in."
        ),
        business_impact=(
            "A port scan is reconnaissance — it means someone is actively mapping your "
            "infrastructure before attempting a deeper attack. Left unresponded, it often "
            "precedes a targeted intrusion attempt."
        ),
        technical_impact=(
            "The attacker now knows which services and ports are exposed on this host. "
            "Any unpatched service discovered during the scan becomes a potential entry point."
        ),
        likelihood="Medium",
        owasp="A05:2021 - Security Misconfiguration",
        mitre_attack=["T1046 - Network Service Discovery", "T1595 - Active Scanning"],
        recommended_fixes=[
            "Block the source IP at your firewall or WAF immediately.",
            "Audit which ports are open — close anything not required for your application.",
            "Enable firewall rules to allow only known IP ranges to reach sensitive ports.",
            "Set up rate-limiting or fail2ban to auto-block IPs that scan multiple ports.",
            "Review your cloud security groups (AWS/GCP/Azure) to ensure minimal exposure.",
        ],
        severity_hint="medium",
        learn_more_url="https://attack.mitre.org/techniques/T1046/",
    ),

    "DoS Hulk": IncidentExplanation(
        category="DoS Hulk",
        plain_english=(
            "Your server was flooded with a huge volume of fake HTTP requests using a tool "
            "called HULK. This is designed to exhaust your server's resources so that real "
            "users cannot access your application."
        ),
        business_impact=(
            "Your application becomes slow or completely unavailable during the attack. "
            "Every minute of downtime costs revenue and damages user trust. "
            "E-commerce or SaaS outages can mean direct financial loss."
        ),
        technical_impact=(
            "CPU, memory, and connection pools on your web server are exhausted. "
            "The server may crash, restart, or become unresponsive. "
            "Databases connected to the server may also be affected."
        ),
        likelihood="High",
        owasp="A05:2021 - Security Misconfiguration",
        mitre_attack=["T1499 - Endpoint Denial of Service", "T1499.002 - Service Exhaustion Flood"],
        recommended_fixes=[
            "Enable DDoS protection via your cloud provider (AWS Shield, Cloudflare, etc.).",
            "Configure rate-limiting on your load balancer or API gateway.",
            "Set connection limits and request timeouts on your web server (nginx/Apache).",
            "Use a CDN to absorb and filter malicious traffic before it reaches your origin.",
            "Consider auto-scaling to handle sudden traffic spikes while you block the source.",
            "Block the attacking IP range at your network edge.",
        ],
        severity_hint="high",
        learn_more_url="https://attack.mitre.org/techniques/T1499/",
    ),

    "DDoS": IncidentExplanation(
        category="DDoS",
        plain_english=(
            "Thousands of different machines (often infected computers in a botnet) are "
            "simultaneously sending traffic to overwhelm your application. Unlike a regular "
            "DoS, the attack comes from many sources at once — making it much harder to block."
        ),
        business_impact=(
            "Your application goes offline for real users. A sustained DDoS can last hours "
            "or days. For revenue-generating applications this is an emergency-level event. "
            "It may also be a distraction while attackers attempt a secondary breach."
        ),
        technical_impact=(
            "Your network bandwidth, server CPU, and connection tables are saturated. "
            "Even upstream providers (CDN, DNS) can be affected. "
            "All services on the same infrastructure are at risk."
        ),
        likelihood="Critical",
        owasp="A05:2021 - Security Misconfiguration",
        mitre_attack=["T1498 - Network Denial of Service", "T1498.001 - Direct Network Flood"],
        recommended_fixes=[
            "Activate DDoS mitigation immediately (AWS Shield Advanced, Cloudflare Under Attack mode).",
            "Contact your ISP or cloud provider — they can filter at the network level.",
            "Enable anycast routing to distribute attack traffic across multiple data centres.",
            "Implement IP reputation lists to block known botnet IP ranges.",
            "Review whether this DDoS is masking a simultaneous intrusion attempt.",
        ],
        severity_hint="critical",
        learn_more_url="https://attack.mitre.org/techniques/T1498/",
    ),

    "DoS GoldenEye": IncidentExplanation(
        category="DoS GoldenEye",
        plain_english=(
            "An attacker used the GoldenEye tool to send many simultaneous HTTP GET/POST "
            "requests, keeping connections open and waiting — slowly draining your server's "
            "connection capacity. It's designed to be harder to detect than volume-based attacks."
        ),
        business_impact=(
            "Your application becomes progressively slower until it can no longer accept "
            "new connections. Legitimate users see timeouts and errors."
        ),
        technical_impact=(
            "Your HTTP server's connection pool is depleted. "
            "Each open connection holds server memory and a thread/process. "
            "New requests queue and eventually time out."
        ),
        likelihood="High",
        owasp="A05:2021 - Security Misconfiguration",
        mitre_attack=["T1499 - Endpoint Denial of Service"],
        recommended_fixes=[
            "Set aggressive connection timeouts on your web server (e.g., nginx keepalive_timeout 5s).",
            "Limit the number of connections per IP at the load balancer level.",
            "Enable Cloudflare or similar reverse proxy to detect and block HTTP-layer DoS.",
            "Block the source IP immediately.",
        ],
        severity_hint="high",
    ),

    "DoS slowloris": IncidentExplanation(
        category="DoS slowloris",
        plain_english=(
            "The Slowloris attack works by opening many connections to your server and sending "
            "HTTP headers very slowly — just fast enough to avoid timeout, but never completing "
            "the request. This ties up server connections until no new users can connect."
        ),
        business_impact=(
            "Your site becomes inaccessible to real users as the attacker's zombie connections "
            "consume all available connection slots."
        ),
        technical_impact=(
            "Apache and older web servers are especially vulnerable. "
            "Connection tables fill up and the server stops accepting new requests, "
            "even though CPU and memory usage remain low."
        ),
        likelihood="High",
        owasp="A05:2021 - Security Misconfiguration",
        mitre_attack=["T1499.001 - OS Exhaustion Flood"],
        recommended_fixes=[
            "Switch to or configure nginx (it handles slow connections much better than Apache).",
            "Set RequestReadTimeout in Apache: RequestReadTimeout header=10-20,MinRate=500.",
            "Use mod_reqtimeout or mod_limitipconn (Apache) to limit per-IP connections.",
            "Add rate limiting at the CDN/WAF layer.",
            "Block the attacking IP immediately.",
        ],
        severity_hint="high",
        learn_more_url="https://en.wikipedia.org/wiki/Slowloris_(computer_security)",
    ),

    "DoS Slowhttptest": IncidentExplanation(
        category="DoS Slowhttptest",
        plain_english=(
            "Similar to Slowloris, this attack sends very slow HTTP request bodies "
            "to keep connections open and exhaust your server. It uses a tool called "
            "slowhttptest that can simulate several types of slow-HTTP attacks."
        ),
        business_impact="Application slowdown or complete unavailability for real users.",
        technical_impact=(
            "Server connection pool exhaustion. Application threads blocked waiting for "
            "request bodies that never arrive."
        ),
        likelihood="High",
        owasp="A05:2021 - Security Misconfiguration",
        mitre_attack=["T1499.001 - OS Exhaustion Flood"],
        recommended_fixes=[
            "Set maximum request body size limits on your web server.",
            "Configure aggressive read timeouts on incoming HTTP connections.",
            "Use a WAF that detects slow-body attacks.",
            "Enable connection rate limits per IP.",
            "Block the attacking IP immediately.",
        ],
        severity_hint="high",
    ),

    "FTP-Patator": IncidentExplanation(
        category="FTP-Patator",
        plain_english=(
            "An attacker used an automated tool called Patator to guess username and password "
            "combinations on your FTP server. This is a brute-force credential attack."
        ),
        business_impact=(
            "If successful, the attacker gains access to files stored on your FTP server. "
            "This could expose customer data, source code, backups, or proprietary files."
        ),
        technical_impact=(
            "FTP credentials compromised. Attacker can download, upload, or delete files. "
            "FTP sends credentials in plaintext — any successful login also exposes the "
            "password on the network."
        ),
        likelihood="High",
        owasp="A07:2021 - Identification and Authentication Failures",
        mitre_attack=["T1110 - Brute Force", "T1110.001 - Password Guessing"],
        recommended_fixes=[
            "Disable FTP entirely — use SFTP or SCP instead (encrypted alternatives).",
            "If FTP is required, restrict access to known IP addresses only.",
            "Enable account lockout after 5 failed attempts.",
            "Use strong, unique passwords and consider key-based authentication.",
            "Block the attacking IP at the firewall.",
            "Review FTP access logs for any successful logins from this IP.",
        ],
        severity_hint="high",
        learn_more_url="https://attack.mitre.org/techniques/T1110/",
    ),

    "SSH-Patator": IncidentExplanation(
        category="SSH-Patator",
        plain_english=(
            "An automated tool tried thousands of username/password combinations "
            "on your SSH server — the remote access system that lets developers log "
            "into your server. This is a brute-force attack targeting server access."
        ),
        business_impact=(
            "If successful, the attacker gets a shell (terminal) on your server with "
            "the compromised user's permissions. From there they can steal data, install "
            "malware, create backdoors, or pivot to other internal systems."
        ),
        technical_impact=(
            "Full or partial server access depending on the compromised account. "
            "Attackers typically attempt to escalate to root. "
            "The entire server and any connected services are at risk."
        ),
        likelihood="Critical",
        owasp="A07:2021 - Identification and Authentication Failures",
        mitre_attack=["T1110 - Brute Force", "T1021.004 - Remote Services: SSH"],
        recommended_fixes=[
            "Disable SSH password authentication — use SSH keys only (PasswordAuthentication no).",
            "Move SSH to a non-standard port (e.g., 2222) to reduce automated scanning.",
            "Install fail2ban to auto-block IPs after repeated failures.",
            "Restrict SSH access to specific IP addresses using firewall rules.",
            "Check /var/log/auth.log immediately for successful logins from this IP.",
            "Disable root SSH login (PermitRootLogin no).",
        ],
        severity_hint="critical",
        learn_more_url="https://attack.mitre.org/techniques/T1110/",
    ),

    "Bot": IncidentExplanation(
        category="Bot",
        plain_english=(
            "Automated bot traffic was detected. Bots can be benign (search engine crawlers) "
            "or malicious (scrapers, credential stuffers, spam bots). This traffic pattern "
            "indicates non-human automated behaviour targeting your application."
        ),
        business_impact=(
            "Malicious bots can scrape your content, abuse your APIs, overload your infrastructure, "
            "create fake accounts, or probe for vulnerabilities. They inflate your hosting costs "
            "and can degrade performance for real users."
        ),
        technical_impact=(
            "API rate limits hit prematurely. Database queries from bot traffic consume resources. "
            "If credential stuffing, user accounts may be compromised."
        ),
        likelihood="Medium",
        owasp="A04:2021 - Insecure Design",
        mitre_attack=["T1583.005 - Botnet", "T1078 - Valid Accounts"],
        recommended_fixes=[
            "Implement rate limiting per IP and per user account.",
            "Add CAPTCHA or bot detection (hCaptcha, Cloudflare Turnstile) on sensitive flows.",
            "Use a WAF with bot management capabilities.",
            "Monitor for unusual patterns: too-fast form submissions, sequential user enumeration.",
            "Block the bot's IP or ASN if traffic is clearly malicious.",
        ],
        severity_hint="medium",
    ),

    "Web Attack - Brute Force": IncidentExplanation(
        category="Web Attack - Brute Force",
        plain_english=(
            "An attacker made many repeated login attempts to guess a user's password. "
            "Automated tools can try hundreds of common passwords per second until they "
            "find one that works."
        ),
        business_impact=(
            "User accounts can be hijacked. If any account is compromised, the attacker "
            "can access that user's data, make purchases, or use the account as a foothold. "
            "For admin accounts, this is a critical risk."
        ),
        technical_impact=(
            "Account takeover for affected users. Possible lateral movement if compromised "
            "accounts have elevated permissions. Auth systems under load from attack volume."
        ),
        likelihood="High",
        owasp="A07:2021 - Identification and Authentication Failures",
        mitre_attack=["T1110 - Brute Force", "T1110.003 - Password Spraying"],
        recommended_fixes=[
            "Enforce account lockout after N failed attempts (e.g., lock for 15 min after 5 failures).",
            "Require MFA on all accounts — a guessed password alone won't be enough.",
            "Add CAPTCHA after 3 failed login attempts.",
            "Block the attacking IP at your WAF or firewall.",
            "Check if any logins succeeded from this IP — if so, force password reset and notify user.",
            "Implement progressive delays on failed logins.",
        ],
        severity_hint="high",
        learn_more_url="https://attack.mitre.org/techniques/T1110/",
    ),

    "Web Attack - XSS": IncidentExplanation(
        category="Web Attack - XSS",
        plain_english=(
            "An attacker tried to inject malicious JavaScript code into your web pages. "
            "If successful, this script runs in the browsers of other users who visit the "
            "affected page — like planting a spy inside every visitor's browser session."
        ),
        business_impact=(
            "XSS can steal user session cookies (logging attackers in as victims), "
            "redirect users to phishing sites, capture keystrokes including passwords, "
            "or deface your website. This directly damages user trust and can trigger "
            "GDPR/CCPA breach notification obligations."
        ),
        technical_impact=(
            "Session hijacking, cookie theft, credential harvesting from active users. "
            "The attacker runs arbitrary code in the context of your domain — bypassing "
            "same-origin protections for everything the victim can access."
        ),
        likelihood="High",
        owasp="A03:2021 - Injection",
        mitre_attack=["T1059.007 - JavaScript", "T1185 - Browser Session Hijacking"],
        recommended_fixes=[
            "Sanitise all user input before rendering it in HTML — never insert raw user data into the DOM.",
            "Implement a strict Content Security Policy (CSP) header to block inline scripts.",
            "Use framework-provided escaping (React, Angular auto-escape by default — avoid dangerouslySetInnerHTML).",
            "Set HttpOnly and Secure flags on session cookies to prevent JavaScript theft.",
            "Run a security scanner (OWASP ZAP, Burp Suite) to identify all XSS entry points.",
        ],
        severity_hint="high",
        learn_more_url="https://owasp.org/www-community/attacks/xss/",
    ),

    "Web Attack - Sql Injection": IncidentExplanation(
        category="Web Attack - Sql Injection",
        plain_english=(
            "Someone attempted to manipulate your application's database by sending malicious "
            "SQL commands through a form field, URL parameter, or API input. If successful, "
            "they can read, modify, or delete any data in your database."
        ),
        business_impact=(
            "SQL injection is one of the most damaging attacks possible. The attacker can "
            "exfiltrate your entire customer database, user credentials, payment records, or "
            "proprietary business data. A successful attack almost certainly triggers mandatory "
            "breach notifications under GDPR, CCPA, and HIPAA."
        ),
        technical_impact=(
            "Complete database compromise. Attacker can bypass authentication, extract all table data, "
            "modify or delete records, and in some configurations execute commands on the database server. "
            "Entire data confidentiality, integrity and availability is at risk."
        ),
        likelihood="Critical",
        owasp="A03:2021 - Injection",
        mitre_attack=["T1190 - Exploit Public-Facing Application", "T1213 - Data from Information Repositories"],
        recommended_fixes=[
            "Use parameterised queries / prepared statements for ALL database queries — never concatenate user input into SQL.",
            "Use an ORM (SQLAlchemy, Prisma, Hibernate) which handles parameterisation automatically.",
            "Validate and whitelist all user inputs on the server side.",
            "Limit database user permissions — your app's DB user should only have SELECT/INSERT/UPDATE on tables it needs.",
            "Deploy a WAF with SQLi detection rules.",
            "Audit all query-building code immediately to identify vulnerable endpoints.",
        ],
        severity_hint="critical",
        learn_more_url="https://owasp.org/www-community/attacks/SQL_Injection",
    ),

    "Infiltration": IncidentExplanation(
        category="Infiltration",
        plain_english=(
            "An attacker has bypassed perimeter defences and gained a foothold inside "
            "your network or application. They are now attempting to move deeper — "
            "accessing internal systems, stealing data, or installing persistent backdoors."
        ),
        business_impact=(
            "This is a high-severity breach scenario. The attacker is already inside. "
            "They may be exfiltrating customer data, IP, financial records, or credentials. "
            "Regulatory breach notification timelines (72 hours for GDPR) may already be running."
        ),
        technical_impact=(
            "Potential full network compromise depending on segmentation. "
            "Internal APIs, databases, admin panels, and other services are all exposed to the attacker. "
            "Backdoors may already be installed for persistent access."
        ),
        likelihood="Critical",
        owasp="A04:2021 - Insecure Design",
        mitre_attack=[
            "T1055 - Process Injection",
            "T1083 - File and Directory Discovery",
            "T1570 - Lateral Tool Transfer",
        ],
        recommended_fixes=[
            "Isolate the affected host immediately — disconnect from the network if possible.",
            "Initiate your incident response plan and consider engaging a security firm.",
            "Audit all outbound connections from the affected host for data exfiltration.",
            "Check for new user accounts, scheduled tasks, or modified system files.",
            "Review all authentication logs for lateral movement to other systems.",
            "Notify your legal/compliance team — breach notification may be required.",
            "After containment: full forensic analysis before restoring the system.",
        ],
        severity_hint="critical",
        learn_more_url="https://attack.mitre.org/techniques/T1055/",
    ),

    "Heartbleed": IncidentExplanation(
        category="Heartbleed",
        plain_english=(
            "The Heartbleed attack exploits a famous bug in OpenSSL (the software that powers "
            "HTTPS encryption). By sending a crafted request, an attacker can read 64KB of "
            "memory from your server at a time — repeatedly — leaking secrets including "
            "private SSL keys and user session data."
        ),
        business_impact=(
            "If your private SSL/TLS key is stolen, attackers can decrypt all past and future "
            "HTTPS traffic, impersonate your server, and intercept user credentials. "
            "This is a catastrophic breach requiring immediate certificate revocation."
        ),
        technical_impact=(
            "Server memory exposed. SSL private keys, session tokens, cookies, and plaintext "
            "passwords of recently logged-in users can all be read from memory. "
            "Full TLS compromise."
        ),
        likelihood="Critical",
        owasp="A06:2021 - Vulnerable and Outdated Components",
        mitre_attack=["T1190 - Exploit Public-Facing Application"],
        recommended_fixes=[
            "Update OpenSSL to 1.0.1g or later IMMEDIATELY — this vulnerability was patched in 2014.",
            "If you're running a vulnerable version, assume your private key is compromised.",
            "Revoke and reissue all SSL/TLS certificates.",
            "Force all users to log out and reset session tokens.",
            "Investigate how this vulnerability exists — all systems should have been patched years ago.",
        ],
        severity_hint="critical",
        learn_more_url="https://heartbleed.com/",
    ),

    "Unknown": IncidentExplanation(
        category="Unknown",
        plain_english=(
            "The ML model detected anomalous traffic that doesn't match a known attack pattern. "
            "This could be a new attack type, unusual legitimate traffic, or a false positive."
        ),
        business_impact=(
            "Unknown threat impact until further analysis. Treat as potentially malicious "
            "until investigation clears it."
        ),
        technical_impact="Unknown — manual investigation required.",
        likelihood="Medium",
        owasp=None,
        mitre_attack=["T1027 - Obfuscated Files or Information"],
        recommended_fixes=[
            "Review the full network flow data for this incident in the Evidence section.",
            "Compare the source IP against threat intelligence databases (AbuseIPDB, VirusTotal).",
            "Check if other incidents from the same source IP have occurred recently.",
            "If traffic looks suspicious, block the source IP as a precaution.",
            "Report unusual patterns to your security team for deeper analysis.",
        ],
        severity_hint="medium",
    ),

    # ── ML model short-form categories ────────────────────────────────────────
    "Remote Code Execution": IncidentExplanation(
        category="Remote Code Execution",
        plain_english=(
            "An attacker managed (or attempted) to run their own code on your server. "
            "This is one of the most serious attacks possible — if successful, they can do "
            "anything your server can do: steal data, install malware, pivot to other systems, "
            "or hold your infrastructure for ransom."
        ),
        business_impact=(
            "Complete server compromise is possible. Attackers can exfiltrate customer data, "
            "deploy ransomware, mine cryptocurrency, or use your servers to attack others. "
            "Regulatory fines and legal liability may follow a confirmed breach."
        ),
        technical_impact=(
            "The attacker may have gained shell access, read or modified files, created "
            "backdoor accounts, or installed persistent malware on the affected host. "
            "All data and credentials on that host should be considered compromised."
        ),
        likelihood="Critical",
        owasp="A03:2021 - Injection",
        mitre_attack=[
            "T1059 - Command and Scripting Interpreter",
            "T1203 - Exploitation for Client Execution",
            "T1190 - Exploit Public-Facing Application",
        ],
        recommended_fixes=[
            "Isolate the affected host immediately — take it offline or quarantine it.",
            "Identify the vulnerable entry point (unpatched software, unsafe deserialization, "
            "template injection, OS command injection) from application logs.",
            "Rotate all credentials and secrets on the compromised host.",
            "Audit audit logs for lateral movement to other systems.",
            "Patch or remove the vulnerable component before bringing the host back online.",
            "Deploy a WAF rule to block known RCE payloads (e.g., Log4Shell, Shellshock).",
        ],
        severity_hint="critical",
        learn_more_url="https://owasp.org/www-community/attacks/Code_Injection",
    ),

    "SSRF": IncidentExplanation(
        category="SSRF",
        plain_english=(
            "An attacker tricked your application into making HTTP requests on their behalf — "
            "to internal systems that should never be reachable from the internet. "
            "It's like convincing a trusted employee inside your office to hand over internal documents. "
            "In cloud environments, SSRF is commonly used to steal cloud credentials from the "
            "instance metadata service (e.g., AWS IMDS at 169.254.169.254)."
        ),
        business_impact=(
            "SSRF can expose cloud credentials, internal APIs, database connection strings, "
            "and other secrets. With cloud credentials, an attacker can access or delete all "
            "your cloud resources. This is how many high-profile cloud breaches have started."
        ),
        technical_impact=(
            "The attacker can probe your internal network, access metadata endpoints "
            "(e.g., 169.254.169.254 for AWS credentials), read internal services not exposed "
            "to the internet, and potentially pivot to other systems in your VPC."
        ),
        likelihood="High",
        owasp="A10:2021 - Server-Side Request Forgery",
        mitre_attack=[
            "T1090 - Proxy",
            "T1552.005 - Unsecured Credentials: Cloud Instance Metadata API",
        ],
        recommended_fixes=[
            "Block all outbound requests to cloud metadata IPs (169.254.169.254, fd00:ec2::254) "
            "at the network level.",
            "Validate and allowlist URLs your application is permitted to fetch — reject "
            "requests to private IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16).",
            "Rotate any cloud credentials (IAM keys, service account tokens) that may have "
            "been exposed via the metadata service.",
            "Use IMDSv2 (AWS) or equivalent on all EC2/compute instances — it requires a "
            "session token that SSRF cannot easily obtain.",
            "Review application code for any feature that fetches user-supplied URLs.",
        ],
        severity_hint="high",
        learn_more_url="https://owasp.org/Top10/A10_2021-Server-Side_Request_Forgery_%28SSRF%29/",
    ),

    "IDOR": IncidentExplanation(
        category="IDOR",
        plain_english=(
            "An attacker accessed another user's data simply by changing a number or ID in a "
            "web request. For example, changing '/api/orders/1001' to '/api/orders/1002' to "
            "see someone else's order. Your application wasn't checking whether the requester "
            "was actually allowed to see that record."
        ),
        business_impact=(
            "Any user's data may have been read or modified by another user without authorisation. "
            "Depending on what's exposed — personal info, payment data, private messages, "
            "medical records — this can trigger GDPR breach notifications, regulatory fines, "
            "and significant reputational damage."
        ),
        technical_impact=(
            "An attacker can enumerate objects (orders, users, files, invoices) by iterating "
            "numeric or sequential IDs. If write operations are also vulnerable, they may have "
            "modified or deleted other users' records."
        ),
        likelihood="High",
        owasp="A01:2021 - Broken Access Control",
        mitre_attack=[
            "T1078 - Valid Accounts",
            "T1530 - Data from Cloud Storage",
        ],
        recommended_fixes=[
            "Enforce object-level authorization on every API endpoint — always check that the "
            "requesting user owns or is permitted to access the requested resource.",
            "Replace sequential integer IDs with UUIDs in public-facing APIs to prevent "
            "enumeration (though this is defence-in-depth, not a substitute for auth checks).",
            "Audit all affected endpoints to determine the full scope of what was accessible.",
            "Review your codebase for any endpoint that looks up records by user-supplied ID "
            "without checking ownership.",
            "Add automated tests that verify cross-user access is rejected (e.g., user A "
            "cannot access user B's resources).",
        ],
        severity_hint="high",
        learn_more_url="https://owasp.org/Top10/A01_2021-Broken_Access_Control/",
    ),
}

# Normalise keys to handle case/spacing differences from the DB
_KEY_MAP = {k.lower().replace(" ", "").replace("-", ""): k for k in _EXPLANATIONS}

# ML model emits uppercase_underscored short-form categories.
# These aliases map normalised ML output → canonical _EXPLANATIONS key.
# The normalize step removes spaces and hyphens but NOT underscores, so
# "BRUTE_FORCE" → "brute_force" which won't match "webattackbruteforce".
_ML_ALIASES: dict[str, str] = {
    "brute_force":        "Web Attack - Brute Force",
    "data_exfiltration":  "Infiltration",
    "rce":                "Remote Code Execution",
    "ssrf":               "SSRF",
    "idor":               "IDOR",
}
_KEY_MAP.update(_ML_ALIASES)


def explain_incident(
    attack_category: str,
    incident_title: str,
    incident_severity: str,
    source_ip: str | None = None,
    destination_port: int | None = None,
    flow_duration_ms: float | None = None,
) -> dict:
    """
    Return a plain-English explanation for an incident.

    Falls back to the "Unknown" entry for unrecognised categories.
    """
    # Normalised lookup
    key = attack_category.lower().replace(" ", "").replace("-", "")
    canonical = _KEY_MAP.get(key, "Unknown")
    exp = _EXPLANATIONS.get(canonical, _EXPLANATIONS["Unknown"])

    # Build context-aware additions
    context_notes = []
    if source_ip:
        context_notes.append(f"The attack originated from IP address {source_ip}.")
    if destination_port:
        context_notes.append(
            f"The targeted port was {destination_port} — "
            + _port_hint(destination_port)
        )
    if flow_duration_ms is not None and flow_duration_ms > 0:
        secs = flow_duration_ms / 1000
        if secs < 60:
            context_notes.append(f"The attack lasted approximately {secs:.1f} seconds.")
        else:
            context_notes.append(f"The attack lasted approximately {secs/60:.1f} minutes.")

    return {
        "category": attack_category,
        "plain_english": exp.plain_english,
        "context": " ".join(context_notes) if context_notes else None,
        "business_impact": exp.business_impact,
        "technical_impact": exp.technical_impact,
        "likelihood": exp.likelihood,
        "owasp": exp.owasp,
        "mitre_attack": exp.mitre_attack,
        "recommended_fixes": exp.recommended_fixes,
        "severity_hint": exp.severity_hint,
        "learn_more_url": exp.learn_more_url,
    }


def _port_hint(port: int) -> str:
    hints = {
        21:   "this is the FTP port (file transfer).",
        22:   "this is the SSH port (remote server access).",
        23:   "this is Telnet (unencrypted remote access — should be disabled).",
        25:   "this is SMTP (email sending).",
        53:   "this is DNS (domain name resolution).",
        80:   "this is standard HTTP (unencrypted web traffic).",
        443:  "this is HTTPS (encrypted web traffic).",
        3306: "this is MySQL — your database port is exposed.",
        5432: "this is PostgreSQL — your database port is exposed.",
        6379: "this is Redis — exposed Redis instances are a critical risk.",
        27017:"this is MongoDB — an exposed MongoDB is a serious risk.",
        3389: "this is RDP (Windows remote desktop).",
        8080: "this is a common alternative HTTP port.",
        8443: "this is a common alternative HTTPS port.",
    }
    return hints.get(port, "review whether this port should be publicly accessible.")
