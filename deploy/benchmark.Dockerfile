FROM python:3.12-slim
WORKDIR /opt/osintgym
COPY pyproject.toml README.md LICENSE LICENSE-DATA.md NOTICE ./
COPY src/ src/
RUN pip install --no-cache-dir ".[anthropic]" && useradd --system --uid 10001 osintgym
USER osintgym
EXPOSE 8080 8081
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/healthz', timeout=2)" || exit 1
ENTRYPOINT ["osintgym"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8080", "--control-port", "8081"]
