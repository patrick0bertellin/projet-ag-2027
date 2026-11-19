# Image pour le VPS Infomaniak (derrière nginx)
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 TZ=Europe/Paris
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home appli && chown -R appli /app
USER appli
EXPOSE 8000
CMD gunicorn "app:create_app()" --workers 1 --threads 4 --timeout 60 --bind 0.0.0.0:$PORT
