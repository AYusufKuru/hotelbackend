"""
Asistan sohbeti — tamamen yerel/kurumi LLM HTTP ucu (JWT: POST /api/assistant/chat/).

Django içinde model ağırlıkları yok; Ollama (veya uyumlu sunucu) aynı makinede/LAN'da çalışır,
açık kaynak önceden eğitilmiş modelleri size ait ortamınızda çalıştırır. Özel GPT eğitmek değil,
verinizden çıkmadan sohbet API'sidir.
"""

from __future__ import annotations

import logging
import json
import os
import re
from typing import Any, TypedDict

import requests
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from hotelcrm.assistant_context import (
    build_hotel_digest,
    is_guest_names_question,
    is_inside_guest_count_question,
    is_navigate_new_reservation,
    looks_like_volunteered_inhouse_count_reply,
    reply_guest_names_from_digest,
    reply_inside_guest_count_from_digest,
    resolve_hotel_id,
)

logger = logging.getLogger(__name__)

MAX_MESSAGES = 24
MAX_CONTENT_LEN = 12_000
MAX_SNAPSHOT_CHARS = 20_000

DEFAULT_MODEL = "llama3.2"

SYSTEM_PROMPT_BASE = """Sen HotelCRM adlı otel yönetim yazılımının gömülü Türkçe asistanısın.

DİL (ZORUNLU):
- Tüm yanıtın %100 Türkçe olmalı. İngilizce kelime, kısaltma veya karışık cümle YASAK (örnek: adult, guest, hotel, booking, checkout, check-in, reservation, currently, room, balance vb. kullanma).
- Aynı bilgiyi hem Türkçe hem İngilizce iki kez söyleme (ör. "1 yetişkin ve 1 adult" kesinlikle yasak). Tek, tutarlı Türkçe cümle kur.
- Veri alanlarında `yetiskin_sayi_alani` geçiyorsa Türkçe "yetişkin sayısı (form alanı)" de; başka dile çevirme.
- Özetteki teknik alan adlarını (`rezervasyon_kodu` vb.) kullanıcıya okurken mümkünse doğal Türkçe'ye çevir (ör. "rezervasyon kodu").

DAVRANIŞ:
- Kısa ve net yanıt ver.
- **ÖNEMLİ:** Kullanıcı açıkça içerideki misafir/rezervasyon **sayısı**nı, doluluğu veya "otelde / İÇERİDE kaç kişi" sorusunu sormadıysa, özetteki `sidebar_iceride_ekran_eslemesi` rakamını **kendiliğinden verme** ve "otelde kaç kişi" formatında yanıt verme. Belirsiz veya tek kelimelik mesajlarda (ör. yalnızca "rezervasyon", "yardım") önce ne yapmak istediğini kısaca netleştir veya ilgili modüle yönlendir.
- İçeride / otelde kaç kişi veya aynı anlama gelen sorularda: `sidebar_iceride_ekran_eslemesi`.`iceride_gosterilen_sayi` ekrandaki **İÇERİDE** ile uyumludur (aktif check-in **rezervasyon** adedi; tek rezervasyon = 1).
- Ek kişi/yetişkin detayı sorulunca `check_in_rezervasyonlarinin_toplam_yetiskin_alani` ve liste altındaki `yetiskin_sayi_alani` kullan — ama kullanıcıyı **ekrandaki rakam rezervasyon adedi**, form alanı farklı olabilir diye gerektiğinde kısa açıkla.
- Aşağıdaki VERİTABANI_ÖZETİ Django’dan gelir.
- Özette yazmayan isimleri uydurmak yasak.
- Özeti kapsamaz (ör. muhasebe, SPA, stok): "Bu özette görünmüyor; ilgili modülden kontrol edin" de.

İŞLEM SINIRI:
- Bu sohbet **veritabanına yazmaz**. Rezervasyon/görev oluşturma yapılmış gibi söyleme; kullanıcıyı ilgili ekrana yönlendir."""


def sanitize_assistant_reply_tr(text: str) -> str:
    """Model İngilizce sızdırırsa zararsız yaygın kelimeleri Türkçeleştirir."""
    if not text:
        return text
    t = text
    subs = [
        (r"\byetiskin\b", "yetişkin"),
        (r"\badult\b", "yetişkin"),
        (r"\bguests\b", "misafirler"),
        (r"\bguest\b", "misafir"),
        (r"\bbookings\b", "rezervasyonlar"),
        (r"\bbooking\b", "rezervasyon"),
        (r"\bcheck-outs?\b", "çıkış"),
        (r"\bcheck-ins?\b", "giriş"),
        (r"\breservations\b", "rezervasyonlar"),
        (r"\breservation\b", "rezervasyon"),
    ]
    for pat, rep in subs:
        t = re.sub(pat, rep, t, flags=re.IGNORECASE)
    return t



def _last_user_text(raw_messages: list[Any]) -> str:
    for m in reversed(raw_messages):
        if isinstance(m, dict) and m.get("role") == "user":
            c = m.get("content")
            return str(c).strip() if c is not None else ""
    return ""


class _LlmEndpoint(TypedDict):
    url: str
    api_key: str | None
    model: str
    timeout: int


def _strip(s: str | None) -> str:
    return (s or "").strip()


def _resolve_llm() -> _LlmEndpoint | None:
    """Yalnızca AI_CHAT_* — OpenAI/bulut yok."""
    base = _strip(os.environ.get("AI_CHAT_API_BASE"))
    if not base:
        return None

    base = base.rstrip("/")
    url = f"{base}/chat/completions"

    model = _strip(os.environ.get("AI_CHAT_MODEL")) or DEFAULT_MODEL

    api_key = _strip(os.environ.get("AI_CHAT_API_KEY")) or None

    timeout_raw = _strip(os.environ.get("AI_CHAT_TIMEOUT_SECONDS"))
    try:
        timeout = max(30, min(600, int(timeout_raw))) if timeout_raw else 120
    except ValueError:
        timeout = 120

    return {
        "url": url,
        "api_key": api_key,
        "model": model,
        "timeout": timeout,
    }


class AssistantChatView(APIView):
    """POST JSON: { \"messages\": [ {\"role\":\"user\"|\"assistant\", \"content\": \"...\"} ] }"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw_messages = request.data.get("messages")
        if not isinstance(raw_messages, list) or not raw_messages:
            return Response(
                {"detail": "Geçerli bir 'messages' listesi gerekli."},
                status=400,
            )

        raw_hotel = request.data.get("hotel_id") or request.data.get("hotelId")
        hotel_pk = resolve_hotel_id(raw_hotel)
        if hotel_pk is None:
            return Response(
                {
                    "detail": (
                        "Geçerli `hotel_id` gerekli — çok otelli kurulumda masaüstünden "
                        "seçili otelin UUID değerini gönderin."
                    ),
                },
                status=400,
            )

        last_q = _last_user_text(raw_messages)
        if last_q and is_navigate_new_reservation(last_q):
            return Response(
                {
                    "reply": "Yeni rezervasyon ekranına geçiriyorum.",
                    "navigate": {"module_id": "new-reservation"},
                },
            )

        cfg = _resolve_llm()
        if cfg is None:
            return Response(
                {
                    "detail": (
                        "Yerel asistan kapalı. `AI_CHAT_API_BASE` ayarlayın "
                        "(örn. Ollama: http://127.0.0.1:11434/v1) ve `AI_CHAT_MODEL` ile model adını verin."
                    ),
                    "disabled": True,
                },
                status=503,
            )

        try:
            digest = build_hotel_digest(hotel_pk)
        except ValueError:
            return Response({"detail": "Otel bulunamadı."}, status=404)

        if last_q:
            if is_inside_guest_count_question(last_q):
                return Response(
                    {
                        "reply": sanitize_assistant_reply_tr(
                            reply_inside_guest_count_from_digest(digest),
                        ),
                    },
                )
            if is_guest_names_question(last_q):
                return Response(
                    {
                        "reply": sanitize_assistant_reply_tr(
                            reply_guest_names_from_digest(digest),
                        ),
                    },
                )

        snapshot = json.dumps(digest, ensure_ascii=False, indent=2)

        if len(snapshot) > MAX_SNAPSHOT_CHARS:
            snapshot = (
                snapshot[:MAX_SNAPSHOT_CHARS]
                + "\n… (özet kesildi — veri çok uzun)"
            )

        system_content = (
            SYSTEM_PROMPT_BASE
            + "\n\n=== VERITABANI_OZETI ===\n"
            + snapshot
            + "\n=== VERİ ÖZETİ SONU ===\n"
        )

        llm_messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
        for m in raw_messages[-MAX_MESSAGES:]:
            if not isinstance(m, dict):
                continue
            role = m.get("role")
            content = m.get("content")
            if role not in ("user", "assistant"):
                continue
            if not isinstance(content, str):
                continue
            text = content.strip()
            if not text:
                continue
            if len(text) > MAX_CONTENT_LEN:
                text = text[:MAX_CONTENT_LEN] + "…"
            llm_messages.append({"role": role, "content": text})

        if len(llm_messages) <= 1:
            return Response(
                {"detail": "En az bir kullanıcı veya asistan mesajı gerekli."},
                status=400,
            )

        payload: dict[str, Any] = {
            "model": cfg["model"],
            "messages": llm_messages,
            "temperature": 0.22,
            "max_tokens": 1024,
        }

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if cfg["api_key"]:
            headers["Authorization"] = f"Bearer {cfg['api_key']}"

        try:
            r = requests.post(
                cfg["url"],
                headers=headers,
                json=payload,
                timeout=cfg["timeout"],
            )
        except requests.RequestException as e:
            logger.exception("Assistant yerel LLM isteği başarısız: %s", e)
            return Response(
                {
                    "detail": (
                        "Yerel yapay zekaya bağlanılamadı (Ollama çalışıyor mu, "
                        "`AI_CHAT_API_BASE` doğru mu kontrol edin)."
                    )
                },
                status=502,
            )

        if not r.ok:
            logger.warning("Yerel LLM HTTP %s: %s", r.status_code, r.text[:500])
            return Response(
                {
                    "detail": (
                        "Model yanıt veremedi — `AI_CHAT_MODEL` için `ollama pull` yapılmış mı bakın."
                    )
                },
                status=502,
            )

        try:
            data = r.json()
            reply = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            reply = (reply or "").strip()
        except (ValueError, TypeError, IndexError) as e:
            logger.warning("Yerel LLM yanlış JSON: %s", e)
            return Response(
                {"detail": "Yanıt işlenemedi."},
                status=502,
            )

        reply = sanitize_assistant_reply_tr(reply)

        if looks_like_volunteered_inhouse_count_reply(last_q, reply):
            reply = (
                "Tam net anlayamadım. İçeride kaç rezervasyon veya kişi, konaklayan isimleri, "
                "yeni rezervasyon veya başka bir işlem istiyorsanız kısaca yazın; "
                "uygulamada ilgili modülleri de kullanabilirsiniz."
            )

        if not reply:
            return Response(
                {"detail": "Model boş yanıt döndü."},
                status=502,
            )

        return Response({"reply": reply})
