# Trading Engine

Тестове завдання: простий торговий двигун з підтримкою:
- роботи з біржами через API (Gate.io, Bybit)
- створення та супровід **TP/SL ордерів**
- простого **веб-інтерфейсу** (на FastAPI + Uvicorn) для моніторингу та управління
- можливості запуску через **Docker**

---

## 🚀 Запуск локально (без Docker)

**1. Клонування проєкту**
```bash
git clone <repo_url>
cd Trading-Engine
python -m venv .venv
source .venv/bin/activate   # (або .venv\Scripts\activate на Windows)
pip install -r requirements.txt
```
**2. Запуск**
```bash
python -m trading_engine.main --config config.json
```
---
## **🐳 Запуск у Docker**
1. Зібрати образ

```bash
docker build -t trading-engine .
```
2. Запустити контейнер

```bash
docker run -it --rm -p 8000:8000 trading-engine --config /app/config.json
```
3. Веб-інтерфейс
Після запуску відкрий у браузері: http://localhost:8000

---

## **⚙️ Конфігурація**

Файл config.json повинен знаходитись у корені проекту (або передаватись іншим шляхом).

Приклад:

```json
{
  "account": "Bybit/Testnet",
  "symbol": "BTC/USDT:USDT",
  "side": "short",
  "market_order_amount": 2000,
  "stop_loss_percent": 7,
  "trailing_sl_offset_percent": 3,
  "limit_orders_amount": 2000,
  "leverage": 10,
  "move_sl_to_breakeven": true,
  "tp_orders": [
    {
      "price_percent": 0.5,
      "quantity_percent": 25.0
    },
    {
      "price_percent": 2.0,
      "quantity_percent": 25.0
    },
    {
      "price_percent": 1.5,
      "quantity_percent": 25.0
    },
    {
      "price_percent": 1.0,
      "quantity_percent": 25.0
    }
  ],
  "limit_orders": {
    "range_percent": 5.0,
    "orders_count": 6,
    "engine_deal_duration_minutes": 110
  }
}
```
Підтримка Docker для швидкого розгортання

Позиція, TP/SL ордери і стан двигуна доступні через веб-інтерфейс