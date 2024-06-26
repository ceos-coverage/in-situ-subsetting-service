import os

APP_CONFIG = {
    'SOLR_URL': "http://localhost/solr/",
    'OUTPUT_DIR': os.path.relpath('./data'),
    'AVAILABLE_FORMATS': {
        "csv": "text/csv",
        "json": "application/json",
        "zip": " application/zip"
    },
    'DEFAULT_FORMAT': "application/zip",
    'CACHE_FILES': False
}
