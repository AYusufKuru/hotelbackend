"""Sunucu metriklerini API'ye gönderen agent.

Örnek:
  python manage.py it_monitor_agent --token=AGENT_TOKEN --interval=30
  python manage.py it_monitor_agent --token=AGENT_TOKEN --api-url=http://127.0.0.1:8000
"""

import os
import time

import requests
from django.core.management.base import BaseCommand

from hotelcrm.it_monitoring_service import collect_psutil_metrics


class Command(BaseCommand):
    help = "IT izleme agent — psutil ile metrik toplar ve heartbeat API'sine gönderir."

    def add_arguments(self, parser):
        parser.add_argument("--token", required=True, help="IntegrationConnection agent_token")
        parser.add_argument(
            "--api-url",
            default=os.environ.get("HOTERFEA_API_URL", "http://127.0.0.1:8000"),
            help="Django API kök URL",
        )
        parser.add_argument("--interval", type=int, default=30, help="Saniye cinsinden gönderim aralığı")

    def handle(self, *args, **options):
        token = options["token"]
        base = str(options["api_url"]).rstrip("/")
        interval = max(5, int(options["interval"]))
        url = f"{base}/api/it-monitor/heartbeat/"

        self.stdout.write(self.style.SUCCESS(f"Agent başladı → {url} (her {interval}s)"))

        while True:
            metrics = collect_psutil_metrics(interval_sec=1.0)
            if not metrics:
                self.stderr.write("psutil yok — pip install psutil")
                return

            payload = {"agent_token": token, **metrics}
            try:
                resp = requests.post(url, json=payload, timeout=15)
                if resp.ok:
                    self.stdout.write(f"OK {metrics['cpu_percent']}% CPU")
                else:
                    self.stderr.write(f"Hata {resp.status_code}: {resp.text[:200]}")
            except requests.RequestException as exc:
                self.stderr.write(f"Bağlantı hatası: {exc}")

            time.sleep(interval)
