FROM python:3.12-slim

# Dependances de compilation et d'execution des paquets Python d'Odoo
# (psycopg2 et lxml sont compiles depuis les sources epinglees par requirements.txt),
# plus wkhtmltopdf pour le rendu PDF des rapports.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libxml2-dev libxslt1-dev \
        libldap2-dev libsasl2-dev \
        libjpeg-dev zlib1g-dev libffi-dev \
        wkhtmltopdf fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Le sous-module doit etre materialise avant le build :
#   git submodule update --init --depth 1 erp/odoo
COPY odoo/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

EXPOSE 8069
CMD ["python3", "/opt/odoo/odoo-bin", "-c", "/etc/odoo/odoo.conf"]
