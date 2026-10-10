# Generate the Python API reference from the exact source tree being built.
FROM python:3.13-slim AS api-reference
WORKDIR /repo
COPY . .
RUN python docs/scripts/generate_api_reference.py --output /generated

# Docusaurus emits static assets. Nginx serves them in the runtime image.
FROM node:22-bookworm-slim AS site-build
WORKDIR /repo
ARG DOCS_URL=https://localhost
ENV DOCS_URL=${DOCS_URL}
COPY . .
COPY --from=api-reference /generated ./docs/docs/reference/generated
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /repo/docs
RUN npm install --no-audit --no-fund
RUN ./node_modules/.bin/docusaurus build

FROM nginx:stable-alpine AS runtime
COPY docs/nginx.conf /etc/nginx/nginx.conf
RUN rm -f /etc/nginx/conf.d/default.conf
COPY --from=site-build /repo/docs/build/ /usr/share/nginx/html/
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
