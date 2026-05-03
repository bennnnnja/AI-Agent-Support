FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# uv provides `uvx`, which is used by app.services.jira_mcp to launch
# the mcp-atlassian server on demand.
RUN pip install --no-cache-dir "uv>=0.4.0"

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY app ./app
COPY health_check.py ./

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:8080/health',timeout=3).status==200 else 1)"

CMD ["python", "-m", "app.main"]
