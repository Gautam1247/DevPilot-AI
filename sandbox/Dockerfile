FROM python:3.12-slim
RUN pip install --no-cache-dir pytest==8.4.2 && useradd --uid 10001 --create-home runner
COPY runner.py pytest.ini /runner/
USER 10001:10001
WORKDIR /project
ENV PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-I", "/runner/runner.py"]
