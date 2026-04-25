# Hotel CRM API (geçici geliştirme backend’i)

## Kurulum

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
```

## Örnek otel (girişte “Kayıtlı otel bulunamadı” için)

```powershell
python manage.py seed_demo_hotel
```

Kod `DEMO`, ad `Demo Otel` — zaten varsa tekrar oluşturmaz.

## Demo kullanıcı

İlk kurulumda:

```powershell
python manage.py createsuperuser
```

veya:

```powershell
python manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model();
U.objects.create_user('demo', 'demo@local', 'demo1234') if not U.objects.filter(username='demo').exists() else print('demo var')"
```

## Çalıştırma

```powershell
python manage.py runserver 127.0.0.1:8000
```

## Giriş API

`POST http://127.0.0.1:8000/api/auth/login/`

```json
{
  "username": "demo",
  "password": "demo1234"
}
```

Yanıt: `access`, `refresh`, `user` (id, username, email).

Token yenileme: `POST /api/auth/refresh/` body: `{ "refresh": "<refresh_token>" }`.

## Merkez lisansı devreye alma

1. **Admin** sunucusunu çalıştırın (`admin` klasörü, `uvicorn`, port örn. 9000).  
2. Panelden **Yeni lisans** oluşturup **lisans anahtarını (UUID)** kopyalayın.  
3. `backend` içinde: `copy .env.example .env` — `.env` dosyasında `LICENSE_SERVER_URL` ve `LICENSE_KEY` doldurun (aynı makinede admin varsa genelde `http://127.0.0.1:9000`).  
4. `pip install -r requirements.txt` (ilk kez `python-dotenv` için).  
5. `DJANGO_ALLOWED_HOSTS` içine bu bilgisayarın **IPv4** adresini de ekleyin (başka PC’den desktop bağlanacaksa).  
6. Django’yu yeniden başlatın.

**`LICENSE_ENFORCE=1`** (`.env`): URL veya key eksikse giriş dahil tüm `/api/` **403** olur (anahtar olmadan çalışmasın istiyorsan bunu aç). Yerel denemede lisans kapalı kalsın dersen `LICENSE_ENFORCE=0` veya satırı sil; ayrıca `LICENSE_SERVER_URL` / `LICENSE_KEY` boş bırakılabilir.

İkisi dolu ve merkez “aktif” değilse yine **403**. Panelde lisansı **askıya almak** veya süre bitirmek de aynı etkiyi yapar.

Ayrıntı: `../admin/README.md`.

## Vercel’e deploy

1. [Vercel](https://vercel.com)’de yeni proje: bu Git repo’yu bağla. **Root Directory** `backend` olmalı (kök sadece `backend/` altında `manage.py` varsa).
2. Proje depolama: [Vercel Storage Postgres](https://vercel.com/docs/storage) veya Neon/Supabase vb. bir **PostgreSQL** bağla; Vercel otomatik `DATABASE_URL` (veya sen aynı isimle) env verir. Sunucusuz ortamda **kalıcı SQLite yok.**
3. Vercel **Environment variables** (Production / Preview ayrı ayrı isteğe göre):
   - `DJANGO_SECRET_KEY` — üretim için güçlü, gizli anahtar (zorunlu)
   - `DATABASE_URL` — Postgres (veritabanı sağlayıcın adım adım eklemişse doldurulur)
   - İsteğe: `DJANGO_CORS_EXTRA_ORIGINS` — web arayüzü URL’leri, virgülle (ör. `https://uydomain.com,https://www...`)
   - İsteğe: `DJANGO_DEBUG=1` — sadece hata ararken; normalde açık bırakma
4. **İlk ve şema değişikliklerinde:** lokalde `npx vercel@latest link` (veya Vercel CLI) ile projeyi bağla, ardından `npx vercel@latest env pull` ile `.env.local` al; `cd backend` → `python manage.py migrate`. Gerekirse `createsuperuser` / `seed_demo_hotel`.
5. Otomatik: Vercel Django için `collectstatic` çalıştırır; `STATIC_ROOT` `settings` içinde tanımlı.

Detay: [Vercel Django](https://vercel.com/docs/frameworks/full-stack/django).

### Admin + backend aynı PC, desktop başka PC

- **Desktop `api-config.json`:** Sadece **Django adresi** → `http://<API_PC_IP>:8000` (admin URL’si burada **yok**).
- **Backend `.env` `LICENSE_SERVER_URL`:** Lisans sunucusu bu makinede → `http://127.0.0.1:9000` (Django’nun admin’e localhost ile sorması yeterli).
- **`DJANGO_ALLOWED_HOSTS`:** API PC’nin IPv4’ü dahil olsun.
- **CORS:** Paketlenmiş Electron için `.env` → `DJANGO_CORS_ALLOW_ALL=1` (LAN testi); yoksa tarayıcı konsolunda CORS hatası görülür, giriş “hatalı” gibi hissedilir.
