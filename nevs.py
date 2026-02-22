import asyncio
import sqlite3
import feedparser
import logging
import aiohttp
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher
from aiogram.types import URLInputFile

# --- AYARLAR ---
API_TOKEN = '8590087904:AAH7vBNgbYfx9yQ2jDJpvitGfX-erB4IRTE'
CHANNEL_ID = '@azernews_az'
CHECK_INTERVAL = 300  # 5 dəqiqə

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

# --- UNIVERSAL SKREPER (Bütün saytlar üçün şəkil və mətn axtarışı) ---
async def get_full_news(session, url):
    try:
        async with session.get(url, timeout=10) as response:
            if response.status != 200: return None, None
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            img_url, desc = None, ""

            # 1. Şəkil axtarışı (Meta-teqlər vasitəsilə - ən universal yol)
            og_image = soup.find("meta", property="og:image")
            if og_image:
                img_url = og_image["content"]
            
            # 2. Mətn axtarışı (Əsas xəbər blokunu tapmağa çalışırıq)
            # Saytların çoxunda xəbər mətni 'article' və ya 'text' klasında olur
            content_selectors = ['div.text', 'div.news-text', 'div.article-body', 'div.entry-content', 'div.p-text']
            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    # İlk 2 paraqrafı götürürük
                    paragraphs = content_div.find_all('p')
                    desc = " ".join([p.text.strip() for p in paragraphs[:2] if len(p.text.strip()) > 10])
                    break
            
            # Əgər selectorlar işləməsə, description meta-teqinə bax
            if not desc:
                og_desc = soup.find("meta", property="og:description")
                if og_desc: desc = og_desc["content"]

            return (desc[:700] + "..." if len(desc) > 700 else desc), img_url
    except:
        return None, None

# --- ƏSAS PROSES ---
async def auto_post():
    # Azərbaycanın Geniş Xəbər Mənbələri Siyahısı
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
            logging.info("Bütün saytlar üzrə axtarış başladı...")
            for src_url in sources:
                try:
                    feed = feedparser.parse(src_url)
                    # Hər mənbədən son 2 yeni xəbəri yoxlayırıq (kanalı doldurmamaq üçün)
                    for entry in reversed(feed.entries[:2]):
                        if not is_link_shared(entry.link):
                            desc, img = await get_full_news(session, entry.link)
                            
                            # Mətn hazırlığı
                            final_desc = desc if desc and len(desc) > 20 else (entry.summary[:400] if hasattr(entry, 'summary') else "")
                            
                            caption = (f"📢 <b>{entry.title}</b>\n\n"
                                       f"{final_desc}\n\n"
                                       f"🔗 <a href='{entry.link}'>Ətraflı oxu</a>\n\n"
                                       f"🇦🇿 @azernews_az")

                            try:
                                if img and img.startswith('http'):
                                    await bot.send_photo(CHANNEL_ID, photo=URLInputFile(img), caption=caption, parse_mode="HTML")
                                else:
                                    await bot.send_message(CHANNEL_ID, text=caption, parse_mode="HTML", disable_web_page_preview=False)
                                
                                save_new_link(entry.link)
                                logging.info(f"YENİ: {entry.title}")
                                await asyncio.sleep(5) # Telegram limiti üçün
                            except Exception as e:
                                logging.error(f"Paylaşım xətası: {e}")
                except Exception as e:
                    logging.error(f"Mənbə xətası ({src_url}): {e}")
            
            logging.info(f"Dövr tamamlandı. {CHECK_INTERVAL} saniyə gözlənilir...")
            await asyncio.sleep(CHECK_INTERVAL)

async def main():
    init_db()
    await auto_post()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot dayandırıldı.")