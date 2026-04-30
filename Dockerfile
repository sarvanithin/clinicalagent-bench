FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e ".[dev]"
EXPOSE 8000
CMD ["uvicorn", "clinicalagent_bench.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
