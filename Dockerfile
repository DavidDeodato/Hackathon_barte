FROM python:3.14-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src TARVO_ENV=production TARVO_STATE_DIR=/data TARVO_INPUT_DIR=/inputs
COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt openpyxl==3.1.5
COPY src ./src
RUN useradd --uid 10001 --create-home tarvo && mkdir /data /inputs && chown tarvo:tarvo /data /inputs
EXPOSE 8000
CMD ["python", "-m", "tarvo.api.container"]
