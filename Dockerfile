# Serviços administrativos do RFM em modo headless (VPS Linux/Windows):
# aplica as migrações, coleta métricas e executa backups — sem interface.
# A interface desktop (PySide6) roda no Windows e não faz parte desta imagem.
#
#   docker build -t rfm-services .
#   docker run -d -v rfm-data:/data \
#       -e RFM_DATABASE_URL=postgresql+psycopg://usuario:senha@db:5432/rfm rfm-services
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RFM_ENV=production RFM_DATA_DIR=/data
WORKDIR /srv/rfm

# Sem PySide6: o modo headless não importa a interface.
RUN pip install --no-cache-dir "SQLAlchemy>=2.0.40" "alembic>=1.14" "psutil>=6.0" \
    "python-dotenv>=1.0" "psycopg[binary]>=3.2"

COPY alembic.ini ./
COPY app ./app

RUN useradd --create-home rfm && mkdir /data && chown rfm /data
USER rfm
VOLUME /data

CMD ["python", "-m", "app.main", "--headless"]
