## UI Production Image (Multi-stage)
# 1. Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY . .
# Ensure clean build output
RUN npm run build

# 2. Runtime stage (nginx for static serving)
FROM nginx:1.27-alpine AS runtime
WORKDIR /usr/share/nginx/html
RUN rm -rf ./*
COPY --from=build /app/dist .
RUN printf 'OK' > /usr/share/nginx/html/health.txt
# Add SPA fallback config
RUN printf 'server {\n  listen 80;\n  root /usr/share/nginx/html;\n  index index.html;\n  location /assets/ { try_files $uri =404; add_header Cache-Control "public, max-age=31536000, immutable"; }\n  location /health.txt { add_header Cache-Control "no-store"; }\n  location / { try_files $uri /index.html; add_header Cache-Control "no-store"; }\n}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK CMD wget -q -O - http://localhost/health.txt || exit 1
CMD ["nginx", "-g", "daemon off;"]

# Usage (PowerShell):
# docker build -t stewie-ui:latest ./ui
# docker run --rm -p 5173:80 stewie-ui:latest
