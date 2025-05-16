import discord
from discord.ext import commands, tasks
import datetime
import os
import requests
from bs4 import BeautifulSoup
import pytz

TOKEN = os.getenv("TOKEN")
CHANNEL_IDS = [1307089130341142558, 1307089152898236486, 1307089168282685552, 1372662168167907468]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

scheduled_news = []
KYIV_TZ = pytz.timezone("Europe/Kiev")


@bot.event
async def on_ready():
    print(f'✅ Бот запущено як {bot.user}')
    for channel_id in CHANNEL_IDS:
        channel = bot.get_channel(channel_id)
        

    scheduled_messages.start()
    fetch_news.start()
    send_news_reminders.start()
    morning_news.start()
    noon_news.start()


@tasks.loop(seconds=60)
async def scheduled_messages():
    now = datetime.datetime.now(KYIV_TZ).strftime('%H:%M')

    messages = {
        "08:45": "🇩🇪 FRANK Session will start in 15 minutes",
        "09:00": "🇩🇪 FRANK Session start",
        "09:45": "🇪🇺 LONDON Session will start in 15 minutes",
        "10:00": "🇪🇺 LONDON Session start",
        "12:00": "🍽 Lunch start",
        "14:45": "🇺🇸 NY Session will start in 15 minutes",
        "15:00": "🇺🇸 NY Start",
        "17:00": "🕔 OTT close"
    }

    if now in messages:
        for channel_id in CHANNEL_IDS:
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(messages[now])


@tasks.loop(time=datetime.time(hour=8, minute=0, tzinfo=KYIV_TZ))
async def fetch_news():
    await parse_news()


async def parse_news():
    global scheduled_news
    scheduled_news.clear()

    url = "https://www.forexfactory.com/calendar"
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"Помилка отримання сторінки: {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.select("tr.calendar__row")

    today = datetime.datetime.now(KYIV_TZ).date()

    for row in rows:
        time_cell = row.select_one("td.calendar__cell.calendar__time")
        impact_span = row.select_one("td.calendar__cell.calendar__impact span.impact")
        currency_cell = row.select_one("td.calendar__cell.calendar__currency")
        event_cell = row.select_one("td.calendar__cell.calendar__event")

        if not all([time_cell, impact_span, currency_cell, event_cell]):
            continue

        time_str = time_cell.text.strip()
        impact_classes = impact_span.get("class", [])
        currency = currency_cell.text.strip()
        event = event_cell.text.strip()

        # Фільтрація валют
        if currency not in ["EUR", "USD", "GBP"]:
            continue

        # Пропускаємо новини без часу
        if time_str.lower() in ["all day", "tentative", ""]:
            continue

        # Визначення емодзі
        if "impact--red" in impact_classes:
            impact_emoji = "🟥"
        elif "impact--orange" in impact_classes:
            impact_emoji = "🟧"
        else:
            continue

        try:
            hour, minute = map(int, time_str.split(":"))
        except ValueError:
            continue

        # Створюємо datetime у київському часі
        news_time = KYIV_TZ.localize(datetime.datetime.combine(today, datetime.time(hour, minute)))
        remind_time = (news_time - datetime.timedelta(minutes=15)).strftime('%H:%M')

        # Формуємо текст новини
        text = f"{impact_emoji} {currency} — {event} о {news_time.strftime('%H:%M')}"

        scheduled_news.append({
            "remind_time": remind_time,
            "news_time": news_time.strftime('%H:%M'),
            "text": text
        })

    print(f"Знайдено новин: {len(scheduled_news)}")


@tasks.loop(seconds=60)
async def send_news_reminders():
    now = datetime.datetime.now(KYIV_TZ).strftime('%H:%M')
    for news in scheduled_news:
        if news["remind_time"] == now:
            for channel_id in CHANNEL_IDS:
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(news["text"])


@tasks.loop(time=datetime.time(hour=8, minute=0, tzinfo=KYIV_TZ))
async def morning_news():
    if scheduled_news:
        text = "📰 **Сьогоднішні новини:**\n\n"
        for news in scheduled_news:
            text += f"{news['text']}\n"
        for channel_id in CHANNEL_IDS:
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(text)


@tasks.loop(time=datetime.time(hour=12, minute=0, tzinfo=KYIV_TZ))
async def noon_news():
    if scheduled_news:
        text = "📢 **Нагадування про сьогоднішні новини:**\n\n"
        for news in scheduled_news:
            text += f"{news['text']}\n"
        for channel_id in CHANNEL_IDS:
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(text)


@bot.command(name="testnews")
async def test_news(ctx):
    await parse_news()
    if scheduled_news:
        text = "📰 **Тестові новини:**\n\n"
        for news in scheduled_news:
            text += f"{news['text']}\n"
        await ctx.send(text)
    else:
        await ctx.send("Новини не знайдено або сьогодні немає важливих подій.")


bot.run(TOKEN)
