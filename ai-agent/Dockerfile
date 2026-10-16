# The household finance agent — its own image on purpose.
#
# LangChain, LangGraph and deepagents pull in a large dependency tree that
# the main API has no use for, and an agent run that takes thirty seconds
# should not occupy a worker that is also serving the transaction list.
# Separate image, separate process, separate scaling.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8100

WORKDIR /app

# Dependencies first, so a source-only change does not reinstall them.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY main.py ./

# No writable state of its own: the agent reads the backend's database
# and holds nothing. Running unprivileged costs nothing here.
RUN useradd --create-home --uid 10002 agent
USER agent

EXPOSE 8100

# /health is unauthenticated and reports database reachability, so a
# container that cannot see the database is reported unhealthy rather
# than accepting requests it will fail.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["sh", "-c", "python -c \"import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8100')+'/health').read()\""]

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8100}"]
