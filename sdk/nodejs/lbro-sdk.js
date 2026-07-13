/**
 * LBRO Node.js SDK
 *
 * Lightweight SDK for sending security events to LBRO from Node.js applications.
 *
 * @example
 * const { LBROClient } = require('./lbro-sdk');
 *
 * const client = new LBROClient({
 *   apiKey: 'proj_your_project_api_key',
 *   baseUrl: 'https://your-lbro-instance.example.com',
 *   sourceApplication: 'my-node-app',
 * });
 *
 * // Single event
 * await client.sendEvent({
 *   eventType: 'auth_failure',
 *   severity: 'high',
 *   sourceIp: '203.0.113.42',
 *   message: 'Failed login attempt',
 *   payload: { username: 'admin', attempts: 10 },
 * });
 *
 * // Batch
 * await client.sendEvents([
 *   { eventType: 'sql_injection', severity: 'critical', message: 'SQL injection in /search' },
 *   { eventType: 'xss', severity: 'medium', message: 'XSS in comment field' },
 * ]);
 */
'use strict';

const https = require('https');
const http = require('http');
const { URL } = require('url');

const SDK_VERSION = '1.0.0';

const ALLOWED_EVENT_TYPES = new Set([
  'auth_failure', 'sql_injection', 'xss', 'brute_force', 'port_scan',
  'suspicious_request', 'system_log', 'application_log', 'nginx_log',
  'apache_log', 'firewall_event', 'windows_event', 'linux_audit', 'custom',
]);

const ALLOWED_SEVERITIES = new Set(['critical', 'high', 'medium', 'low', 'info']);

class LBROError extends Error {
  constructor(message, statusCode = null) {
    super(message);
    this.name = 'LBROError';
    this.statusCode = statusCode;
  }
}

class LBROAuthError extends LBROError {
  constructor(message) {
    super(message, 401);
    this.name = 'LBROAuthError';
  }
}

class LBROValidationError extends LBROError {
  constructor(message) {
    super(message, 422);
    this.name = 'LBROValidationError';
  }
}

class LBROClient {
  /**
   * @param {object} options
   * @param {string} options.apiKey          - Project API key (starts with proj_)
   * @param {string} [options.baseUrl]       - LBRO base URL. Default: http://localhost:8000
   * @param {number} [options.timeout]       - Request timeout ms. Default: 10000
   * @param {number} [options.maxRetries]    - Max retries on 5xx/network error. Default: 3
   * @param {number} [options.retryDelay]    - Base retry delay ms. Default: 1000
   * @param {string} [options.sourceApplication] - Default app name for all events
   */
  constructor({ apiKey, baseUrl = 'http://localhost:8000', timeout = 10000,
                maxRetries = 3, retryDelay = 1000, sourceApplication = null } = {}) {
    if (!apiKey || !apiKey.startsWith('proj_')) {
      throw new LBROAuthError("LBRO project API keys must start with 'proj_'");
    }
    this._apiKey = apiKey;
    this._baseUrl = baseUrl.replace(/\/$/, '');
    this._timeout = timeout;
    this._maxRetries = maxRetries;
    this._retryDelay = retryDelay;
    this._sourceApplication = sourceApplication;
  }

  /**
   * Send a single security event.
   * @param {object} event
   * @returns {Promise<object>} LBRO response
   */
  async sendEvent({ eventType, severity = 'medium', sourceIp = null, sourceHost = null,
                    message = null, payload = {}, eventTimestamp = null } = {}) {
    this._validateEventType(eventType);
    this._validateSeverity(severity);
    const body = this._buildEventBody({ eventType, severity, sourceIp, sourceHost,
                                         message, payload, eventTimestamp });
    return this._post('/api/v1/events', body);
  }

  /**
   * Send multiple events in a single batch request (max 1000).
   * @param {object[]} events
   * @returns {Promise<object>} Summary with accepted/rejected counts
   */
  async sendEvents(events) {
    if (!Array.isArray(events) || events.length === 0) {
      return { accepted: 0, rejected: 0, events: [], errors: [] };
    }
    if (events.length > 1000) {
      throw new LBROValidationError('Batch size cannot exceed 1000 events');
    }
    const bodies = events.map(e => {
      this._validateEventType(e.eventType);
      this._validateSeverity(e.severity || 'medium');
      return this._buildEventBody(e);
    });
    return this._post('/api/v1/events/batch', { events: bodies });
  }

  /** Check connectivity. Returns true if LBRO is reachable. */
  async ping() {
    try {
      await this._get('/health');
      return true;
    } catch (_) {
      return false;
    }
  }

  // ── Private ────────────────────────────────────────────────────────────────

  _buildEventBody({ eventType, severity = 'medium', sourceIp, sourceHost,
                    message, payload = {}, eventTimestamp } = {}) {
    const body = {
      event_type: eventType,
      severity,
      payload,
      event_timestamp: eventTimestamp || new Date().toISOString(),
    };
    if (sourceIp)          body.source_ip = sourceIp;
    if (sourceHost)        body.source_host = sourceHost;
    if (message)           body.message = message;
    if (this._sourceApplication) body.source_application = this._sourceApplication;
    return body;
  }

  _validateEventType(eventType) {
    if (!ALLOWED_EVENT_TYPES.has(eventType)) {
      throw new LBROValidationError(
        `Unknown eventType '${eventType}'. Allowed: ${[...ALLOWED_EVENT_TYPES].sort().join(', ')}`
      );
    }
  }

  _validateSeverity(severity) {
    if (!ALLOWED_SEVERITIES.has(severity)) {
      throw new LBROValidationError(
        `Unknown severity '${severity}'. Allowed: ${[...ALLOWED_SEVERITIES].sort().join(', ')}`
      );
    }
  }

  async _post(path, body) {
    return this._request('POST', path, body);
  }

  async _get(path) {
    return this._request('GET', path);
  }

  async _request(method, path, body = null) {
    const url = new URL(this._baseUrl + path);
    const isHttps = url.protocol === 'https:';
    const transport = isHttps ? https : http;
    const bodyStr = body ? JSON.stringify(body) : null;

    const options = {
      hostname: url.hostname,
      port: url.port || (isHttps ? 443 : 80),
      path: url.pathname + url.search,
      method,
      headers: {
        Authorization: `Bearer ${this._apiKey}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'User-Agent': `lbro-nodejs-sdk/${SDK_VERSION}`,
        ...(bodyStr ? { 'Content-Length': Buffer.byteLength(bodyStr) } : {}),
      },
    };

    let lastError = null;
    for (let attempt = 0; attempt <= this._maxRetries; attempt++) {
      try {
        return await new Promise((resolve, reject) => {
          const req = transport.request(options, (res) => {
            let data = '';
            res.on('data', chunk => { data += chunk; });
            res.on('end', () => {
              const status = res.statusCode;
              if (status === 401) return reject(new LBROAuthError(`Invalid project API key: ${data}`));
              if (status === 422) return reject(new LBROValidationError(`Validation error: ${data}`));
              if (status >= 500) return reject(new LBROError(`Server error HTTP ${status}: ${data}`, status));
              if (status >= 400) return reject(new LBROError(`HTTP ${status}: ${data}`, status));
              try { resolve(data ? JSON.parse(data) : {}); }
              catch (e) { resolve({}); }
            });
          });
          req.setTimeout(this._timeout, () => {
            req.destroy();
            reject(new LBROError(`Request timeout after ${this._timeout}ms`));
          });
          req.on('error', reject);
          if (bodyStr) req.write(bodyStr);
          req.end();
        });
      } catch (err) {
        lastError = err;
        if (err instanceof LBROAuthError || err instanceof LBROValidationError) throw err;
        if (attempt < this._maxRetries) {
          const delay = this._retryDelay * Math.pow(2, attempt);
          await new Promise(r => setTimeout(r, delay));
          continue;
        }
      }
    }
    throw new LBROError(`Request failed after ${this._maxRetries} retries: ${lastError?.message}`, null);
  }
}

module.exports = { LBROClient, LBROError, LBROAuthError, LBROValidationError, ALLOWED_EVENT_TYPES, ALLOWED_SEVERITIES };
