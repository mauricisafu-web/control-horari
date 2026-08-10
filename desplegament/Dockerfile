# Imatge de producció. El contenidor NO sap que és a Firebase: parla amb el
# port de magatzem/rebost.py i prou. Corre igual en local, a Cloud Run o a
# qualsevol altre lloc que executi contenidors.
FROM python:3.12-slim

# tzdata NO és opcional: ni Windows ni les imatges `slim` porten la base de
# zones del sistema, i `core/model.py` fa ZoneInfo('Europe/Madrid') en
# importar-se. Sense això l'aplicació NI ARRENCA.
# ca-certificates: per a l'SMTP i per a la importació de festius.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ENV TZ=Europe/Madrid

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# El .dockerignore és el que impedeix que hi entrin secrets i dades de prova.
COPY . /app

# Corre com un usuari sense privilegis.
RUN useradd --create-home --uid 10001 horari && chown -R horari:horari /app
USER horari

ENV REBOST=firestore \
    DARRERE_PROXY=1 \
    COOKIE_SECURE=1 \
    SESSIO_MINUTS=20 \
    PYTHONUNBUFFERED=1

EXPOSE 8080

# UN sol worker amb fils. No és per estalviar: el comptador d'intents de login
# viu a la memòria del procés, i amb dos workers un atacant tindria el doble
# d'intents abans que el bloquegessin.
CMD exec gunicorn -w 1 --threads 8 -b 0.0.0.0:${PORT:-8080} \
    --access-logfile - --error-logfile - 'app_web:crea_app()'
