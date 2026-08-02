# Production image referenced by infra/k8s/helm/emailagent — multi-stage
# build served by nginx. For local dev, use Dockerfile.dev (Vite dev server)
# via infra/docker-compose.dev.yml instead.

FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
