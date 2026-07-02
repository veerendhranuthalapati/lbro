# ── Stage 1: Dependency cache ────────────────────────────────────────────────
# Separated so Docker layer cache is not busted when source changes
FROM node:20-alpine AS deps

# Security: run as non-root in all stages
RUN addgroup -g 1001 -S lbro && adduser -S lbro -u 1001 -G lbro

WORKDIR /app
COPY package.json package-lock.json* ./

# Use ci for reproducible installs; ignore scripts to reduce supply-chain risk
RUN npm ci --frozen-lockfile --ignore-scripts && \
    npm cache clean --force

# ── Stage 2: Build ────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

RUN addgroup -g 1001 -S lbro && adduser -S lbro -u 1001 -G lbro

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY --chown=lbro:lbro . .

USER lbro

# Build args for runtime injection
ARG VITE_API_URL=http://localhost:8000
ARG VITE_APP_VERSION=unknown
ARG VITE_APP_NAME=LBRO

ENV VITE_API_URL=$VITE_API_URL \
    VITE_APP_VERSION=$VITE_APP_VERSION \
    VITE_APP_NAME=$VITE_APP_NAME \
    NODE_ENV=production

RUN npm run build

# ── Stage 3: Audit (optional — runs in CI) ───────────────────────────────────
FROM node:20-alpine AS audit
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json* ./
RUN npm audit --audit-level=high --omit=dev || true

# ── Stage 4: Serve ────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS final

# Remove default nginx user and use non-root
RUN addgroup -g 1001 -S lbro && \
    adduser -S lbro -u 1001 -G lbro && \
    # Remove default html
    rm -rf /usr/share/nginx/html/* && \
    # Allow nginx to write its pid and cache as non-root
    chown -R lbro:lbro /var/cache/nginx /var/run /var/log/nginx && \
    touch /run/nginx.pid && chown lbro:lbro /run/nginx.pid

COPY --chown=lbro:lbro nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder --chown=lbro:lbro /app/dist /usr/share/nginx/html

USER lbro

EXPOSE 80

# Health check so orchestrators know when nginx is ready
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:80/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
