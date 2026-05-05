# 🛍 Do'kon Telegram Bot

Do'kon uchun Telegram bot — mahsulot katalogi, savatcha, buyurtmalar va qarz tizimi bilan.

## Funksiyalar

### Mijoz:
- 🛍 Katalogni ko'rish (rasm, nom, narx)
- 🛒 Savatga qo'shish va buyurtma berish
- 💰 Qisman to'lov qilish (qolgan qismi qarz sifatida saqlanadi)
- 💳 Qarzini to'lash (admin tasdiqlaydi)
- 📋 Buyurtmalar tarixini ko'rish

### Admin:
- ➕ Mahsulot qo'shish (rasm, nom, narx)
- 📦 Mahsulotlarni ko'rish / o'chirish
- 👥 Mijozlar ro'yxati
- 💳 Qarzlar ro'yxati (umumiy statistika)
- ✅ To'lovlarni tasdiqlash / rad etish

---

## O'rnatish

### 1. Bot yaratish
[@BotFather](https://t.me/BotFather) da yangi bot yarating va tokenni oling.

### 2. Local ishga tushirish

```bash
# Virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Paketlarni o'rnatish
pip install -r requirements.txt

# .env fayl yarating
cp .env.example .env
# .env faylni tahrirlang
```

**.env fayl:**
```
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

```bash
# Botni ishga tushirish
python bot.py
```

---

## Render ga Deploy qilish

### 1. GitHub ga yuklash
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/username/shop-bot.git
git push -u origin main
```

### 2. Render.com da sozlash

1. [render.com](https://render.com) ga kiring
2. **New** → **Web Service** bosing
3. GitHub reponi ulang
4. Quyidagi sozlamalarni kiriting:

| Sozlama | Qiymat |
|---------|--------|
| **Name** | shop-bot |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python bot.py` |

### 3. Environment Variables qo'shish

Render dashboard → **Environment** bo'limida:

```
BOT_TOKEN = your_bot_token
ADMIN_IDS = 123456789
DATABASE_URL = your_postgresql_url
```

### 4. PostgreSQL yaratish (Render)

1. **New** → **PostgreSQL** bosing
2. Free plan tanlang
3. Yaratilgach, **Internal Database URL** ni nusxalang
4. Uni `DATABASE_URL` ga qo'ying

---

## Admin ID ni topish

[@userinfobot](https://t.me/userinfobot) ga /start yuboring — ID ni ko'rsatadi.

---

## Fayl tuzilishi

```
shop_bot/
├── bot.py          # Asosiy bot kodi
├── database.py     # PostgreSQL bilan ishlash
├── requirements.txt
└── README.md
```
