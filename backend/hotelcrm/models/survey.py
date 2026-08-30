import uuid

from django.db import models

from .property_guest import Guest, Hotel

STANDARD_SURVEY_QUESTIONS = [
    {"id": "overall", "type": "rating", "label": "Genel memnuniyetiniz", "max": 5},
    {"id": "cleanliness", "type": "rating", "label": "Oda temizliği", "max": 5},
    {"id": "staff", "type": "rating", "label": "Personel ilgisi ve davranışı", "max": 5},
    {"id": "food", "type": "rating", "label": "Yemek / kahvaltı kalitesi", "max": 5},
    {"id": "recommend", "type": "yesno", "label": "Bizi arkadaşlarınıza tavsiye eder misiniz?"},
    {"id": "comment", "type": "text", "label": "Ek yorumunuz (isteğe bağlı)"},
]


class HotelSurveySmsSettings(models.Model):
    class Provider(models.TextChoices):
        MOCK = "mock", "Test (konsola yaz)"
        NETGSM = "netgsm", "Netgsm"
        HTTP = "http", "HTTP Webhook"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.OneToOneField(Hotel, on_delete=models.CASCADE, related_name="survey_sms_settings")
    provider = models.CharField(max_length=16, choices=Provider.choices, default=Provider.MOCK)
    api_username = models.CharField(max_length=128, blank=True)
    api_password = models.CharField(max_length=256, blank=True)
    sender_id = models.CharField(max_length=32, blank=True, help_text="Netgsm başlık / gönderen")
    webhook_url = models.URLField(max_length=512, blank=True)
    message_template = models.TextField(
        default=(
            "Sayın {guest_name}, {hotel_name} konaklamanız için 2 dakikalık anketimiz: {link} "
            "Teşekkürler."
        ),
    )
    public_base_url = models.URLField(
        max_length=512,
        blank=True,
        help_text="Misafirin anketi açacağı adres (örn. http://192.168.1.10:8000)",
    )
    is_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hotelcrm_hotelsurveysmssettings"


class SurveyInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Bekliyor"
        SENT = "sent", "Gönderildi"
        FAILED = "failed", "Başarısız"
        OPENED = "opened", "Açıldı"
        COMPLETED = "completed", "Tamamlandı"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="survey_invitations")
    guest = models.ForeignKey(
        Guest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="survey_invitations",
    )
    guest_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32)
    room_number = models.CharField(max_length=16, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    sms_message = models.TextField(blank=True)
    sms_error = models.TextField(blank=True)
    answers = models.JSONField(default=dict, blank=True)
    overall_score = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "hotelcrm_surveyinvitation"
        ordering = ["-created_at"]
