FROM python:3.13-alpine

RUN apk add --no-cache postgresql17-client restic tzdata \
    && addgroup -g 10001 ops \
    && adduser -D -H -u 10001 -G ops ops \
    && mkdir -p /ops /backups /restore-target \
    && chown -R ops:ops /ops /backups /restore-target

COPY --chown=ops:ops infra/ops/*.py /ops/

USER 10001:10001
WORKDIR /ops
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python", "/ops/scheduler.py"]
