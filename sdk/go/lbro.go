// Package lbro provides a Go client for sending security events to LBRO.
//
// No external dependencies — uses only the Go standard library.
//
// Example usage:
//
//	client, err := lbro.NewClient("proj_your_key_here",
//	    lbro.WithBaseURL("https://your-lbro-instance.example.com"),
//	    lbro.WithSourceApplication("my-go-app"),
//	)
//	if err != nil {
//	    log.Fatal(err)
//	}
//
//	result, err := client.SendEvent(context.Background(), lbro.SecurityEvent{
//	    EventType: "auth_failure",
//	    Severity:  "high",
//	    SourceIP:  "192.168.1.100",
//	    Message:   "Failed login attempt",
//	})
package lbro

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

const Version = "1.0.0"

var validEventTypes = map[string]bool{
	"auth_failure": true, "sql_injection": true, "xss": true,
	"brute_force": true, "port_scan": true, "suspicious_request": true,
	"system_log": true, "application_log": true, "nginx_log": true,
	"apache_log": true, "firewall_event": true, "windows_event": true,
	"linux_audit": true, "custom": true,
}

var validSeverities = map[string]bool{
	"info": true, "low": true, "medium": true, "high": true, "critical": true,
}

// ── Errors ────────────────────────────────────────────────────────────────────

// LBROError is the base error type returned by LBRO SDK calls.
type LBROError struct {
	Message    string
	StatusCode int
}

func (e *LBROError) Error() string {
	if e.StatusCode != 0 {
		return fmt.Sprintf("LBRO error (HTTP %d): %s", e.StatusCode, e.Message)
	}
	return "LBRO error: " + e.Message
}

// LBROAuthError is returned when the API key is invalid or missing.
type LBROAuthError struct{ LBROError }

// LBROValidationError is returned when the event payload fails server-side validation.
type LBROValidationError struct{ LBROError }

// ── SecurityEvent ─────────────────────────────────────────────────────────────

// SecurityEvent represents a single security event to be ingested by LBRO.
type SecurityEvent struct {
	EventType         string         `json:"event_type"`
	Severity          string         `json:"severity"`
	SourceIP          string         `json:"source_ip,omitempty"`
	SourceHost        string         `json:"source_host,omitempty"`
	SourceApplication string         `json:"source_application,omitempty"`
	AgentVersion      string         `json:"agent_version,omitempty"`
	Message           string         `json:"message,omitempty"`
	EventTimestamp    string         `json:"event_timestamp,omitempty"`
	Payload           map[string]any `json:"payload,omitempty"`
}

func (e *SecurityEvent) validate() error {
	if !validEventTypes[e.EventType] {
		return &LBROValidationError{LBROError{Message: "invalid event_type: " + e.EventType}}
	}
	if !validSeverities[e.Severity] {
		return &LBROValidationError{LBROError{Message: "invalid severity: " + e.Severity}}
	}
	return nil
}

// ── Client ────────────────────────────────────────────────────────────────────

// Client sends security events to a LBRO instance.
type Client struct {
	apiKey            string
	baseURL           string
	httpClient        *http.Client
	maxRetries        int
	retryDelay        time.Duration
	sourceApplication string
}

// Option is a functional option for configuring a Client.
type Option func(*Client)

// WithBaseURL sets the LBRO server base URL.
func WithBaseURL(url string) Option {
	return func(c *Client) { c.baseURL = strings.TrimRight(url, "/") }
}

// WithTimeout sets the per-request HTTP timeout.
func WithTimeout(d time.Duration) Option {
	return func(c *Client) { c.httpClient.Timeout = d }
}

// WithMaxRetries sets the number of retry attempts on transient errors.
func WithMaxRetries(n int) Option {
	return func(c *Client) { c.maxRetries = n }
}

// WithRetryDelay sets the initial retry delay (doubles on each retry).
func WithRetryDelay(d time.Duration) Option {
	return func(c *Client) { c.retryDelay = d }
}

// WithSourceApplication sets a default source_application for all events.
func WithSourceApplication(app string) Option {
	return func(c *Client) { c.sourceApplication = app }
}

// NewClient constructs a new LBRO client. The apiKey must start with "proj_".
func NewClient(apiKey string, opts ...Option) (*Client, error) {
	if !strings.HasPrefix(apiKey, "proj_") {
		return nil, &LBROValidationError{LBROError{Message: "LBRO project API keys must start with \'proj_\'"}}
	}
	c := &Client{
		apiKey:     apiKey,
		baseURL:    "http://localhost:8000",
		httpClient: &http.Client{Timeout: 30 * time.Second},
		maxRetries: 3,
		retryDelay: time.Second,
	}
	for _, o := range opts {
		o(c)
	}
	return c, nil
}

// SendEvent sends a single security event. Returns the parsed API response.
func (c *Client) SendEvent(ctx context.Context, event SecurityEvent) (map[string]any, error) {
	if event.SourceApplication == "" && c.sourceApplication != "" {
		event.SourceApplication = c.sourceApplication
	}
	if event.AgentVersion == "" {
		event.AgentVersion = Version
	}
	if event.EventTimestamp == "" {
		event.EventTimestamp = time.Now().UTC().Format(time.RFC3339)
	}
	if err := event.validate(); err != nil {
		return nil, err
	}
	body, err := json.Marshal(event)
	if err != nil {
		return nil, &LBROError{Message: "failed to serialize event: " + err.Error()}
	}
	return c.post(ctx, "/api/v1/events", body)
}

// SendEvents sends a batch of up to 1000 security events.
func (c *Client) SendEvents(ctx context.Context, events []SecurityEvent) (map[string]any, error) {
	if len(events) == 0 {
		return nil, &LBROValidationError{LBROError{Message: "events slice must not be empty"}}
	}
	if len(events) > 1000 {
		return nil, &LBROValidationError{LBROError{Message: "batch size must not exceed 1000 events"}}
	}
	for i := range events {
		if events[i].SourceApplication == "" && c.sourceApplication != "" {
			events[i].SourceApplication = c.sourceApplication
		}
		if events[i].AgentVersion == "" {
			events[i].AgentVersion = Version
		}
		if events[i].EventTimestamp == "" {
			events[i].EventTimestamp = time.Now().UTC().Format(time.RFC3339)
		}
		if err := events[i].validate(); err != nil {
			return nil, fmt.Errorf("event[%d]: %w", i, err)
		}
	}
	body, err := json.Marshal(map[string]any{"events": events})
	if err != nil {
		return nil, &LBROError{Message: "failed to serialize batch: " + err.Error()}
	}
	return c.post(ctx, "/api/v1/events/batch", body)
}

// Ping returns true if the LBRO server is reachable and the API key is valid.
func (c *Client) Ping(ctx context.Context) bool {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+"/api/v1/health", nil)
	if err != nil {
		return false
	}
	req.Header.Set("Authorization", "Bearer "+c.apiKey)
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return false
	}
	resp.Body.Close()
	return resp.StatusCode >= 200 && resp.StatusCode < 300
}

// ── Internal HTTP ─────────────────────────────────────────────────────────────

func (c *Client) post(ctx context.Context, path string, body []byte) (map[string]any, error) {
	var lastErr error
	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		if attempt > 0 {
			delay := c.retryDelay * (1 << (attempt - 1))
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(delay):
			}
		}

		result, retryable, err := c.doPost(ctx, path, body)
		if err == nil {
			return result, nil
		}
		if !retryable {
			return nil, err
		}
		lastErr = err
	}
	return nil, fmt.Errorf("failed after %d retries: %w", c.maxRetries, lastErr)
}

func (c *Client) doPost(ctx context.Context, path string, body []byte) (map[string]any, bool, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+path, bytes.NewReader(body))
	if err != nil {
		return nil, false, &LBROError{Message: "failed to build request: " + err.Error()}
	}
	req.Header.Set("Authorization", "Bearer "+c.apiKey)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "lbro-go-sdk/"+Version)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, true, &LBROError{Message: "network error: " + err.Error()}
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))

	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		var result map[string]any
		if jsonErr := json.Unmarshal(respBody, &result); jsonErr != nil {
			return map[string]any{"raw": string(respBody)}, false, nil
		}
		return result, false, nil
	}

	msg := strings.TrimSpace(string(respBody))
	switch resp.StatusCode {
	case 401:
		return nil, false, &LBROAuthError{LBROError{Message: msg, StatusCode: 401}}
	case 422:
		return nil, false, &LBROValidationError{LBROError{Message: msg, StatusCode: 422}}
	default:
		// 5xx and other codes are retryable
		return nil, resp.StatusCode >= 500, &LBROError{Message: msg, StatusCode: resp.StatusCode}
	}
}
