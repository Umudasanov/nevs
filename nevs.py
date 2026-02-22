import asyncio
import sqlite3
import feedparser
import logging
import aiohttp
import os
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher
from aiogram.types import URLInputFile

# --- AYARLAR ---
# Render panelində 'BOT_TOKEN' olaraq əlavə etdiyin tokeni oxuyur
API_TOKEN = os.getenv('BOT_TOKEN', '8590087904:AAH7vBNgbYfx9yQ2jDJpvitGfX-erB4IRTE')
CHANNEL_ID = '@azernews_az'
CHECK_INTERVAL = 300 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- VERİLƏNLƏR BAZASI ---
def init_db():
    conn = sqlite3.connect('news_storage.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS shared_links (link TEXT PRIMARY KEY)')
    conn.commit()
    conn.close()

def is_link_shared(link):
    conn = sqlite3.connect('news_storage.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM shared_links WHERE link = ?', (link,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def save_new_link(link):
    conn = sqlite3.connect('news_storage.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO shared_links VALUES (?)', (link,))
    conn.commit()
    conn.close()

# --- UNIVERSAL SKREPER (Şəkil və Mətn üçün) ---
async def get_full_news(session, url):
    try:
        async with session.get(url, timeout=15) as response:
            if response.status != 200: return None, None
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            img_url, desc = None, ""

            # Şəkil üçün meta teqi
            og_image = soup.find("meta", property="og:image")
            if og_image:
                img_url = og_image["content"]
            
            # Mətn üçün əsas bloklar
            content_selectors = ['div.text', 'div.news-text', 'div.article-body', 'article']
            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    paragraphs = content_div.find_all('p')
                    desc = " ".join([p.text.strip() for p in paragraphs[:2] if len(p.text.strip()) > 20])
                    break
            
            if not desc:
                og_desc = soup.find("meta", property="og:description")
                if og_desc: desc = og_desc["content"]

            return (desc[:700] + "..." if len(desc) > 700 else desc), img_url
    except:
        return None, None

# --- ƏSAS AVTOMATİK PAYLAŞIM ---
async def auto_post():
    sources = [
        "https://oxu.az/rss",
"https://report.az/rss",
"https://apa.az/az/rss",
"https://qafqazinfo.az/rss",
"https://www.trend.az/rss",
"https://news.day.az/rss",
"https://milli.az/rss",
"https://axar.az/rss",
"https://modern.az/rss",
"https://sonxeber.az/rss",
"https://unikal.az/rss",
"https://olke.az/rss",
"https://lent.az/rss",
"https://musavat.com/rss"
    ]
    
    async with aiohttp.ClientSession() as session:
        while True:
            logging.info("Xəbər axtarışı başladı...")
            for src_url in sources:
                try:
                    feed = feedparser.parse(src_url)
                    for entry in reversed(feed.entries[:2]):
                        if not is_link_shared(entry.link):
                            desc, img = await get_full_news(session, entry.link)
                            
                            final_desc = desc if desc else (entry.summary[:400] if hasattr(entry, 'summary') else "")
                            
                            caption = (f"📢 <b>{entry.title}</b>\n\n"
                                       f"{final_desc}\n\n"
                                       f"🔗 <a href='{entry.link}'>Ətraflı oxu</a>\n\n"
                                       f"🇦🇿 @azernews_az")

                            try:
                                if img and img.startswith('http'):
                                    await bot.send_photo(CHANNEL_ID, photo=URLInputFile(img), caption=caption, parse_mode="HTML")
                                else:
                                    await bot.send_message(CHANNEL_ID, text=caption, parse_mode="HTML")
                                
                                save_new_link(entry.link)
                                logging.info(f"Paylaşıldı: {entry.title}")
                                await asyncio.sleep(5)
                            except Exception as e:
                                logging.error(f"Göndərmə xətası: {e}")
                except Exception as e:
                    logging.error(f"Mənbə xətası: {e}")
            
            await asyncio.sleep(CHECK_INTERVAL)

async def main():
    init_db()
    # Python 3.14-də taskın idarə olunması
    asyncio.create_task(auto_post())
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
