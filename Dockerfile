FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY alto/ alto/
COPY engine/timeline_template.html engine/home_template.html \
     engine/reports_template.html engine/TEMPLATE_MANIFEST.json engine/
ENV ALTO_STORE=firestore
ENV PYTHONUNBUFFERED=1
CMD exec uvicorn alto.web:app --host 0.0.0.0 --port ${PORT:-8080}
