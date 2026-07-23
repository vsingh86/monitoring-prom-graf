"""db-exporter entrypoint.

Routes:
  GET /                        -- HTML index of configured databases, linking to their metrics
  GET /metrics?target=<name>  -- vendor-native metrics for one configured database
  GET /metrics                -- exporter process metrics + self-health for all targets
  GET /health                 -- trivial liveness check
"""
import logging
import os
import sys
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest

from src.config import ConfigError, load_config
from src.registry import TargetNotFound, TargetRegistry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONFIG_PATH = os.environ.get("DB_EXPORTER_CONFIG", "config.yaml")
LISTEN_PORT = int(os.environ.get("DB_EXPORTER_PORT", "9433"))


def build_registry() -> TargetRegistry:
    try:
        config = load_config(CONFIG_PATH)
    except FileNotFoundError:
        logger.error(
            "%s not found -- copy config.example.yaml to config.yaml (and fill in "
            "real connection details) before starting db-exporter",
            CONFIG_PATH,
        )
        sys.exit(1)
    except ConfigError as e:
        logger.error("failed to load %s: %s", CONFIG_PATH, e)
        sys.exit(1)
    logger.info("loaded %d database target(s) from %s", len(config.databases), CONFIG_PATH)
    return TargetRegistry(config)


target_registry = build_registry()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format_str, *args):
        logger.info("%s - %s", self.address_string(), format_str % args)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self._respond_html(200, self._render_index())
            return

        if parsed.path == "/health":
            self._respond_text(200, "OK")
            return

        if parsed.path != "/metrics":
            self._respond_text(404, "not found")
            return

        target = parse_qs(parsed.query).get("target", [None])[0]

        if target is None:
            body = generate_latest(REGISTRY) + generate_latest(target_registry.scrape_all_self_health())
            self._respond_metrics(body)
            return

        try:
            registry = target_registry.scrape(target)
        except TargetNotFound:
            self._respond_text(404, f"unknown target '{target}' -- check config.yaml")
            return

        self._respond_metrics(generate_latest(registry))

    def _render_index(self) -> str:
        targets = target_registry.list_targets()
        if not targets:
            rows = "<p>No databases configured in config.yaml.</p>"
        else:
            items = "\n".join(
                f'<li><a href="/metrics?target={quote(t.name)}">{escape(t.name)}</a> '
                f"<span class=\"db-type\">({escape(t.db_type)})</span></li>"
                for t in targets
            )
            rows = f"<ul>\n{items}\n</ul>"
        return (
            "<!doctype html><html><head><title>db-exporter</title>"
            "<style>body{font-family:sans-serif;margin:2rem}"
            "li{margin:0.3rem 0}.db-type{color:#666}</style></head><body>"
            f"<h1>db-exporter</h1>{rows}</body></html>"
        )

    def _respond_html(self, status: int, html: str):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _respond_metrics(self, body: bytes):
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE_LATEST)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _respond_text(self, status: int, text: str):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    server = ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), Handler)
    logger.info("db-exporter listening on :%d", LISTEN_PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
