import logging
import traceback

from flask import Flask, jsonify

from lib.logger import setup_logging
from settings import APP, PROCESS, LOG_PATH, ENVIRONMENT

logger = logging.getLogger(__name__)

app = Flask(__name__)

setup_logging(
    env=ENVIRONMENT,
    app=APP,
    process=PROCESS,
    log_path=LOG_PATH)

for logger_name in ["werkzeug"]:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)


@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(
        "Unhandled exception: %s",
        e,
        extra={"traceback": traceback.format_exc()},
    )
    return jsonify(error=str(e)), 500


@app.get("/div/<int:a>/<int:b>")
def divide(a: int, b: int):
    return dict(result=a / b)