from django.apps import AppConfig


class HotelcrmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hotelcrm"
    verbose_name = "Hotel CRM"

    def ready(self):
        from . import stock_signals  # noqa: F401
