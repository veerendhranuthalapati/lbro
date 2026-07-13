package io.lbro.sdk;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * LBRO Java SDK — send security events to LBRO from Java applications.
 *
 * <pre>{@code
 * LBROClient client = new LBROClient.Builder("proj_your_key_here")
 *         .baseUrl("https://your-lbro-instance.example.com")
 *         .sourceApplication("my-java-app")
 *         .build();
 *
 * client.sendEvent(SecurityEvent.builder()
 *         .eventType("auth_failure")
 *         .severity("high")
 *         .sourceIp("192.168.1.100")
 *         .message("Failed login attempt")
 *         .build());
 * }</pre>
 *
 * No external dependencies — uses only the Java standard library.
 */
public final class LBROClient {

    public static final String VERSION = "1.0.0";

    private static final Set<String> VALID_EVENT_TYPES = new HashSet<>(Arrays.asList(
            "auth_failure", "sql_injection", "xss", "brute_force", "port_scan",
            "suspicious_request", "system_log", "application_log", "nginx_log",
            "apache_log", "firewall_event", "windows_event", "linux_audit", "custom"
    ));

    private static final Set<String> VALID_SEVERITIES = new HashSet<>(Arrays.asList(
            "info", "low", "medium", "high", "critical"
    ));

    private final String apiKey;
    private final String baseUrl;
    private final int timeoutMs;
    private final int maxRetries;
    private final long retryDelayMs;
    private final String sourceApplication;

    private LBROClient(Builder builder) {
        this.apiKey = builder.apiKey;
        this.baseUrl = builder.baseUrl.replaceAll("/+$", "");
        this.timeoutMs = builder.timeoutMs;
        this.maxRetries = builder.maxRetries;
        this.retryDelayMs = builder.retryDelayMs;
        this.sourceApplication = builder.sourceApplication;
    }

    // ── Public API ────────────────────────────────────────────────────────────

    /**
     * Send a single security event. Returns the API response as a map.
     */
    public Map<String, Object> sendEvent(SecurityEvent event) throws LBROException {
        String body = buildSingleEventJson(event);
        return post("/api/v1/events", body);
    }

    /**
     * Send a batch of security events (up to 1000). Returns the batch response.
     */
    public Map<String, Object> sendEvents(List<SecurityEvent> events) throws LBROException {
        if (events == null || events.isEmpty()) {
            throw new LBROValidationException("events list must not be empty");
        }
        if (events.size() > 1000) {
            throw new LBROValidationException("batch size must not exceed 1000 events");
        }
        String body = buildBatchJson(events);
        return post("/api/v1/events/batch", body);
    }

    /**
     * Ping the LBRO server. Returns true if reachable and API key is valid.
     */
    public boolean ping() {
        try {
            URL url = new URL(baseUrl + "/api/v1/health");
            HttpURLConnection conn = openConnection(url);
            conn.setRequestMethod("GET");
            conn.setRequestProperty("Authorization", "Bearer " + apiKey);
            conn.setConnectTimeout(timeoutMs);
            conn.setReadTimeout(timeoutMs);
            int code = conn.getResponseCode();
            return code >= 200 && code < 300;
        } catch (Exception e) {
            return false;
        }
    }

    // ── HTTP ──────────────────────────────────────────────────────────────────

    @SuppressWarnings("unchecked")
    private Map<String, Object> post(String path, String jsonBody) throws LBROException {
        byte[] bodyBytes = jsonBody.getBytes(StandardCharsets.UTF_8);
        LBROException lastException = null;

        for (int attempt = 0; attempt <= maxRetries; attempt++) {
            if (attempt > 0) {
                long delay = retryDelayMs * (1L << (attempt - 1)); // exponential backoff
                try { Thread.sleep(delay); } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    throw new LBROException("Interrupted during retry backoff", ie);
                }
            }
            try {
                URL url = new URL(baseUrl + path);
                HttpURLConnection conn = openConnection(url);
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Authorization", "Bearer " + apiKey);
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setRequestProperty("User-Agent", "lbro-java-sdk/" + VERSION);
                conn.setRequestProperty("Content-Length", String.valueOf(bodyBytes.length));
                conn.setDoOutput(true);
                conn.setConnectTimeout(timeoutMs);
                conn.setReadTimeout(timeoutMs);

                try (OutputStream os = conn.getOutputStream()) {
                    os.write(bodyBytes);
                }

                int code = conn.getResponseCode();

                if (code >= 200 && code < 300) {
                    String responseBody = readStream(conn.getInputStream());
                    return parseJsonObject(responseBody);
                }

                String errorBody = "";
                try {
                    errorBody = readStream(conn.getErrorStream());
                } catch (Exception ignored) {}

                if (code == 401) {
                    throw new LBROAuthException("Authentication failed (HTTP 401): " + errorBody);
                }
                if (code == 422) {
                    throw new LBROValidationException("Validation failed (HTTP 422): " + errorBody);
                }
                // 5xx: retryable
                lastException = new LBROException("HTTP " + code + ": " + errorBody);

            } catch (LBROAuthException | LBROValidationException e) {
                throw e; // non-retryable
            } catch (LBROException e) {
                lastException = e;
            } catch (IOException e) {
                lastException = new LBROException("Network error: " + e.getMessage(), e);
            }
        }

        throw (lastException != null ? lastException
                : new LBROException("Failed after " + maxRetries + " retries"));
    }

    private HttpURLConnection openConnection(URL url) throws IOException {
        return (HttpURLConnection) url.openConnection();
    }

    private static String readStream(InputStream is) throws IOException {
        if (is == null) return "";
        StringBuilder sb = new StringBuilder();
        byte[] buf = new byte[4096];
        int read;
        while ((read = is.read(buf)) != -1) {
            sb.append(new String(buf, 0, read, StandardCharsets.UTF_8));
        }
        return sb.toString();
    }

    // ── JSON serialization (no external deps) ────────────────────────────────

    private String buildSingleEventJson(SecurityEvent event) {
        validate(event);
        StringBuilder sb = new StringBuilder("{");
        appendField(sb, "event_type", event.getEventType(), false);
        appendField(sb, "severity", event.getSeverity(), true);
        if (event.getSourceIp() != null) appendField(sb, "source_ip", event.getSourceIp(), true);
        if (event.getSourceHost() != null) appendField(sb, "source_host", event.getSourceHost(), true);
        if (event.getMessage() != null) appendField(sb, "message", event.getMessage(), true);
        String app = event.getSourceApplication() != null ? event.getSourceApplication() : sourceApplication;
        if (app != null) appendField(sb, "source_application", app, true);
        if (event.getAgentVersion() != null) appendField(sb, "agent_version", event.getAgentVersion(), true);
        if (event.getEventTimestamp() != null) appendField(sb, "event_timestamp", event.getEventTimestamp(), true);
        if (event.getPayload() != null) {
            sb.append(","payload":").append(event.getPayload());
        }
        sb.append("}");
        return sb.toString();
    }

    private String buildBatchJson(List<SecurityEvent> events) {
        StringBuilder sb = new StringBuilder("{"events":[");
        for (int i = 0; i < events.size(); i++) {
            if (i > 0) sb.append(",");
            sb.append(buildSingleEventJson(events.get(i)));
        }
        sb.append("]}");
        return sb.toString();
    }

    private static void appendField(StringBuilder sb, String key, String value, boolean comma) {
        if (comma) sb.append(",");
        sb.append('"').append(key).append("":"").append(escapeJson(value)).append('"');
    }

    private static String escapeJson(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> parseJsonObject(String json) {
        // Minimal JSON object parser for API responses.
        Map<String, Object> result = new LinkedHashMap<>();
        json = json.trim();
        if (json.startsWith("{")) {
            json = json.substring(1, json.length() - 1).trim();
        }
        // Tokenize key-value pairs (handles strings and numbers only — sufficient for LBRO responses)
        int i = 0;
        while (i < json.length()) {
            while (i < json.length() && (json.charAt(i) == ',' || Character.isWhitespace(json.charAt(i)))) i++;
            if (i >= json.length()) break;
            if (json.charAt(i) != '"') break;
            int keyStart = i + 1;
            int keyEnd = json.indexOf('"', keyStart);
            String key = json.substring(keyStart, keyEnd);
            i = keyEnd + 1;
            while (i < json.length() && (json.charAt(i) == ':' || Character.isWhitespace(json.charAt(i)))) i++;
            if (i >= json.length()) break;
            char c = json.charAt(i);
            if (c == '"') {
                int valStart = i + 1;
                int valEnd = json.indexOf('"', valStart);
                result.put(key, json.substring(valStart, valEnd));
                i = valEnd + 1;
            } else {
                int valEnd = i;
                while (valEnd < json.length() && json.charAt(valEnd) != ',' && json.charAt(valEnd) != '}') valEnd++;
                String raw = json.substring(i, valEnd).trim();
                if (raw.equals("true")) result.put(key, Boolean.TRUE);
                else if (raw.equals("false")) result.put(key, Boolean.FALSE);
                else if (raw.equals("null")) result.put(key, null);
                else {
                    try { result.put(key, Long.parseLong(raw)); }
                    catch (NumberFormatException e) {
                        try { result.put(key, Double.parseDouble(raw)); }
                        catch (NumberFormatException e2) { result.put(key, raw); }
                    }
                }
                i = valEnd;
            }
        }
        return result;
    }

    private void validate(SecurityEvent event) {
        if (event.getEventType() == null || !VALID_EVENT_TYPES.contains(event.getEventType())) {
            throw new LBROValidationException("Invalid event_type: " + event.getEventType());
        }
        if (event.getSeverity() == null || !VALID_SEVERITIES.contains(event.getSeverity())) {
            throw new LBROValidationException("Invalid severity: " + event.getSeverity());
        }
    }

    // ── Builder ───────────────────────────────────────────────────────────────

    public static final class Builder {
        private final String apiKey;
        private String baseUrl = "http://localhost:8000";
        private int timeoutMs = 30_000;
        private int maxRetries = 3;
        private long retryDelayMs = 1_000;
        private String sourceApplication;

        public Builder(String apiKey) {
            if (apiKey == null || !apiKey.startsWith("proj_")) {
                throw new IllegalArgumentException("LBRO project API keys must start with \'proj_\'");
            }
            this.apiKey = apiKey;
        }

        public Builder baseUrl(String baseUrl) { this.baseUrl = baseUrl; return this; }
        public Builder timeoutMs(int ms) { this.timeoutMs = ms; return this; }
        public Builder maxRetries(int n) { this.maxRetries = n; return this; }
        public Builder retryDelayMs(long ms) { this.retryDelayMs = ms; return this; }
        public Builder sourceApplication(String app) { this.sourceApplication = app; return this; }

        public LBROClient build() { return new LBROClient(this); }
    }

    // ── SecurityEvent ─────────────────────────────────────────────────────────

    public static final class SecurityEvent {
        private final String eventType;
        private final String severity;
        private final String sourceIp;
        private final String sourceHost;
        private final String sourceApplication;
        private final String agentVersion;
        private final String message;
        private final String eventTimestamp;
        private final String payload; // raw JSON string

        private SecurityEvent(EventBuilder b) {
            this.eventType = b.eventType;
            this.severity = b.severity;
            this.sourceIp = b.sourceIp;
            this.sourceHost = b.sourceHost;
            this.sourceApplication = b.sourceApplication;
            this.agentVersion = b.agentVersion;
            this.message = b.message;
            this.eventTimestamp = b.eventTimestamp != null ? b.eventTimestamp : Instant.now().toString();
            this.payload = b.payload;
        }

        public String getEventType() { return eventType; }
        public String getSeverity() { return severity; }
        public String getSourceIp() { return sourceIp; }
        public String getSourceHost() { return sourceHost; }
        public String getSourceApplication() { return sourceApplication; }
        public String getAgentVersion() { return agentVersion; }
        public String getMessage() { return message; }
        public String getEventTimestamp() { return eventTimestamp; }
        public String getPayload() { return payload; }

        public static EventBuilder builder() { return new EventBuilder(); }

        public static final class EventBuilder {
            private String eventType;
            private String severity = "info";
            private String sourceIp;
            private String sourceHost;
            private String sourceApplication;
            private String agentVersion;
            private String message;
            private String eventTimestamp;
            private String payload;

            public EventBuilder eventType(String v) { this.eventType = v; return this; }
            public EventBuilder severity(String v) { this.severity = v; return this; }
            public EventBuilder sourceIp(String v) { this.sourceIp = v; return this; }
            public EventBuilder sourceHost(String v) { this.sourceHost = v; return this; }
            public EventBuilder sourceApplication(String v) { this.sourceApplication = v; return this; }
            public EventBuilder agentVersion(String v) { this.agentVersion = v; return this; }
            public EventBuilder message(String v) { this.message = v; return this; }
            public EventBuilder eventTimestamp(String v) { this.eventTimestamp = v; return this; }
            public EventBuilder payload(String rawJson) { this.payload = rawJson; return this; }
            public SecurityEvent build() { return new SecurityEvent(this); }
        }
    }

    // ── Exceptions ────────────────────────────────────────────────────────────

    public static class LBROException extends RuntimeException {
        public LBROException(String message) { super(message); }
        public LBROException(String message, Throwable cause) { super(message, cause); }
    }

    public static class LBROAuthException extends LBROException {
        public LBROAuthException(String message) { super(message); }
    }

    public static class LBROValidationException extends LBROException {
        public LBROValidationException(String message) { super(message); }
    }
}
