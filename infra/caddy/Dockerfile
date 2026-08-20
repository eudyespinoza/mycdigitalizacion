FROM caddy:2.10-alpine

RUN addgroup -g 1000 caddyapp \
    && adduser -D -H -u 1000 -G caddyapp caddyapp \
    && chown -R caddyapp:caddyapp /data /config /etc/caddy
COPY --chown=caddyapp:caddyapp infra/caddy/Caddyfile /etc/caddy/Caddyfile

USER 1000:1000
EXPOSE 8080 8443
