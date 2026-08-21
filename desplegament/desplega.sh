#!/usr/bin/env bash
# Construeix i desplega. Un sol lloc on siguin els noms i les banderes.
#
#   ./desplegament/desplega.sh una-etiqueta-curta
#
set -euo pipefail

ETIQUETA="${1:-$(date +%s)}"
PROJECTE=control-horari-torre-espanyol
REGIO=europe-west1
IMATGE="europe-west1-docker.pkg.dev/$PROJECTE/cloud-run-source-deploy/control-horari"

# El proxy de l'ajuntament intercepta el TLS: sense aquest magatzem
# d'autoritats, tant gcloud com les biblioteques de Google peten amb
# «self-signed certificate in certificate chain».
CERTS="$HOME/.certs/ca-amb-netskope.pem"
if [ -f "$CERTS" ]; then
  export REQUESTS_CA_BUNDLE="$CERTS" SSL_CERT_FILE="$CERTS"
  export GRPC_DEFAULT_SSL_ROOTS_FILE_PATH="$CERTS"
fi

gcloud builds submit --project="$PROJECTE" \
  --config=desplegament/cloudbuild.yaml \
  --substitutions="_IMATGE=$IMATGE,_ETIQUETA=$ETIQUETA" .

gcloud run deploy control-horari --project="$PROJECTE" --region="$REGIO" \
  --image="$IMATGE:$ETIQUETA"

echo "Desplegat $IMATGE:$ETIQUETA"
