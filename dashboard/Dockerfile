# ── Stage 1: Build ────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json .
RUN npm install

COPY public/ ./public/
COPY src/ ./src/
RUN npm run build

# ── Stage 2: Serve with nginx ──────────────────────────────────────────────────
FROM nginx:alpine

COPY --from=builder /app/build /usr/share/nginx/html

# nginx config that proxies /api to transaction-service
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
