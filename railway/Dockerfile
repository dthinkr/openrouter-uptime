# Collector image for the Railway cron service.
#
# Deliberately minimal: poll.py uses only the standard library, so the image
# carries Python, git, and CA certificates and nothing else. Every dependency
# added here is one that can break a collection run, and a missed observation
# cannot be re-taken.

FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY railway/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# The repository is cloned at runtime onto the mounted volume rather than baked
# in, so the collector always runs the scripts currently on main.
ENV WORKDIR=/data/repo \
    BRANCH=main \
    PYTHONUNBUFFERED=1

CMD ["/app/entrypoint.sh"]
