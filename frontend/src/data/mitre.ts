/**
 * MITRE ATT&CK mapping for CICIDS2017 attack classifications.
 *
 * Maps CICIDS2017 dataset attack types to MITRE ATT&CK techniques.
 * Reference: https://attack.mitre.org
 */
import type { AttackType, MitreTechnique } from '@/types'
import { MITRE_BASE_URL } from '@/constants'

export const CICIDS_MITRE_MAPPING: Record<AttackType, MitreTechnique | null> = {
  'BENIGN': null,
  'DoS Hulk': {
    technique_id: 'T1499.001',
    name: 'OS Exhaustion Flood',
    tactic: 'Impact',
    description: 'Adversaries flood target OS resources to deny service. Hulk generates unique URLs each request to bypass caching.',
    url: `${MITRE_BASE_URL}/T1499/001/`,
    mitigations: ['Filter-Based Blocking', 'Rate Limiting', 'CDN/WAF'],
  },
  'DDoS': {
    technique_id: 'T1498.001',
    name: 'Direct Network Flood',
    tactic: 'Impact',
    description: 'High-volume UDP/TCP flood from multiple sources to exhaust bandwidth.',
    url: `${MITRE_BASE_URL}/T1498/001/`,
    mitigations: ['ISP Filtering', 'Anycast Routing', 'Scrubbing Centers'],
  },
  'DoS GoldenEye': {
    technique_id: 'T1499.002',
    name: 'Service Exhaustion Flood',
    tactic: 'Impact',
    description: 'HTTP keep-alive abuse to exhaust server thread pool. All connections held open simultaneously.',
    url: `${MITRE_BASE_URL}/T1499/002/`,
    mitigations: ['Connection Limits', 'Load Balancer Tuning', 'WAF Rules'],
  },
  'DoS slowloris': {
    technique_id: 'T1499.002',
    name: 'Service Exhaustion Flood (Slowloris)',
    tactic: 'Impact',
    description: 'Sends partial HTTP headers slowly to keep connections open, exhausting server connection pool.',
    url: `${MITRE_BASE_URL}/T1499/002/`,
    mitigations: ['Connection Timeout', 'Minimum Data Rate', 'mod_reqtimeout'],
  },
  'DoS Slowhttptest': {
    technique_id: 'T1499.002',
    name: 'Service Exhaustion Flood (Slow HTTP)',
    tactic: 'Impact',
    description: 'Slow HTTP POST body exhausts server resources.',
    url: `${MITRE_BASE_URL}/T1499/002/`,
    mitigations: ['Request Body Timeout', 'Content-Length Validation'],
  },
  'FTP-Patator': {
    technique_id: 'T1110.001',
    name: 'Password Guessing',
    tactic: 'Credential Access',
    description: 'Automated FTP credential brute-force using Patator tool.',
    url: `${MITRE_BASE_URL}/T1110/001/`,
    mitigations: ['Account Lockout', 'MFA', 'Fail2ban'],
  },
  'SSH-Patator': {
    technique_id: 'T1110.001',
    name: 'Password Guessing (SSH)',
    tactic: 'Credential Access',
    description: 'Automated SSH credential brute-force using Patator.',
    url: `${MITRE_BASE_URL}/T1110/001/`,
    mitigations: ['SSH Key Authentication', 'Account Lockout', 'Port Knocking'],
  },
  'PortScan': {
    technique_id: 'T1046',
    name: 'Network Service Discovery',
    tactic: 'Discovery',
    description: 'Systematic port scanning to map open services on target hosts.',
    url: `${MITRE_BASE_URL}/T1046/`,
    mitigations: ['Network Segmentation', 'Firewall Rules', 'IDS/IPS'],
  },
  'Bot': {
    technique_id: 'T1071.001',
    name: 'Web Protocols C2',
    tactic: 'Command and Control',
    description: 'Botnet command-and-control traffic over standard web protocols.',
    url: `${MITRE_BASE_URL}/T1071/001/`,
    mitigations: ['Network Filtering', 'DNS Sinkholing', 'Behavioral Analysis'],
  },
  'Infiltration': {
    technique_id: 'T1021.001',
    name: 'Remote Desktop Protocol',
    tactic: 'Lateral Movement',
    description: 'Long-duration bidirectional flows indicating APT lateral movement within network.',
    url: `${MITRE_BASE_URL}/T1021/001/`,
    mitigations: ['Network Segmentation', 'Just-in-Time Access', 'MFA'],
  },
  'Web Attack -- Brute Force': {
    technique_id: 'T1110.003',
    name: 'Password Spraying',
    tactic: 'Credential Access',
    description: 'Automated web form brute-force credential attacks.',
    url: `${MITRE_BASE_URL}/T1110/003/`,
    mitigations: ['CAPTCHA', 'Account Lockout', 'MFA'],
  },
  'Web Attack -- XSS': {
    technique_id: 'T1059.007',
    name: 'JavaScript',
    tactic: 'Execution',
    description: 'Cross-site scripting injection for session hijacking or credential harvesting.',
    url: `${MITRE_BASE_URL}/T1059/007/`,
    mitigations: ['CSP Headers', 'Output Encoding', 'HttpOnly Cookies'],
  },
  'Web Attack -- Sql Injection': {
    technique_id: 'T1190',
    name: 'Exploit Public-Facing Application',
    tactic: 'Initial Access',
    description: 'SQL injection to extract or manipulate backend database.',
    url: `${MITRE_BASE_URL}/T1190/`,
    mitigations: ['Parameterized Queries', 'WAF', 'Least Privilege DB'],
  },
  'Heartbleed': {
    technique_id: 'T1212',
    name: 'Exploitation for Credential Access',
    tactic: 'Credential Access',
    description: 'CVE-2014-0160 OpenSSL buffer over-read leaking server memory including private keys.',
    url: `${MITRE_BASE_URL}/T1212/`,
    mitigations: ['Patch OpenSSL', 'Certificate Reissuance', 'TLS Version Policy'],
  },
}

export function getMitreTechnique(attackType: AttackType): MitreTechnique | null {
  return CICIDS_MITRE_MAPPING[attackType] ?? null
}

// ---- IOC patterns for each attack type --------------------------------------------------------------------------------

export const ATTACK_IOC_PATTERNS: Record<string, readonly string[]> = {
  'DoS Hulk': [
    'Flow packets/sec > 4000',
    'Bwd packet ratio < 1%',
    'Fwd header length / payload ratio > 0.9',
    'Unique URI per request',
  ],
  'DDoS': [
    'UDP flood from multiple sources',
    'SYN/ACK ratio imbalanced',
    'Flow bytes/sec > 1 MB/s sustained',
    'Zero backward packets',
  ],
  'SSH-Patator': [
    'Port 22 repeated authentication attempts',
    'Bidirectional flow symmetry ~50%',
    'Fixed inter-arrival time (automated)',
    'Multiple failed auths from single IP',
  ],
  'Web Attack -- Sql Injection': [
    'UNION SELECT in HTTP payload',
    'Encoded SQL metacharacters',
    'Abnormal response size delta',
    'Error messages in HTTP response',
  ],
  'Infiltration': [
    'Long duration bidirectional flow > 30 min',
    'Non-standard port communication',
    'Internal->Internal traffic anomaly',
    'Low packets/sec with high data volume',
  ],
  'Heartbleed': [
    'TLS heartbeat request oversized',
    'Port 443 / 8443',
    'Response contains memory artifacts',
    'CVE-2014-0160 signature',
  ],
}
