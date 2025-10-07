import aiohttp
import asyncio
import re
from bs4 import BeautifulSoup
import requests
import sqlite3
import schedule
import time
from threading import Thread


stop_ex = False

def execute(cursor, cursor_1):
    cursor.execute("SELECT * FROM games")
    cursor_1.execute("SELECT * FROM games")
    rows = cursor.fetchall()
    rows1 = cursor_1.fetchall()
    return rows, rows1


def rows_different(old_row, new_row, mode="all"):
   
    if mode == "all":
        # all of culonm
        return any(old_row[i] != new_row[i] for i in range(0, 9))
    elif mode == "important":
        #  title(0), offer_time(2), discount(4), offer_price(5)
        important_indices = [0, 2, 4, 5]
        return any(old_row[i] != new_row[i] for i in important_indices)
    else:
        raise ValueError("mode must be 'all' or 'important'")
   

def updating_data(cursor, conn, rows, rows1):
    for new_row in rows1:
        link1 = new_row[1]

        # to find old culomn with new link
        old_matches = [row for row in rows if row[1] == link1]

        if old_matches:
            old_row = old_matches[0]
            if rows_different(old_row, new_row) and new_row[2] != "Not defined":
                cursor.execute('''
                    UPDATE games SET
                        title=?, link=?, offer_time=?, platforms=?, discount=?, 
                        offer_price=?, original_price=?, picture=?, type_post=?, status=0
                    WHERE link=?
                ''', (*new_row[:9], link1))
                conn.commit()
                print("updated:", new_row[0])
            elif rows_different(old_row, new_row) == False and old_row[-1] == 1:
                print("This post was deleted:", old_row[0])
                cursor.execute('DELETE FROM games WHERE link = ?', (old_row[1],))
                conn.commit()
            
                
        else:
            # if not exists add it
            cursor.execute('''
                INSERT INTO games 
                (title, link, offer_time, platforms, discount, offer_price, original_price, picture, type_post, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            ''', new_row[:9])
            conn.commit()
            print("new post added:", new_row[0])  




url = 'https://store.playstation.com/en-tr/category/3f772501-f6f8-49b7-abac-874a88ca4897/1'
respons = requests.get(url, timeout=10)
bs = BeautifulSoup(respons.content, 'html.parser')
latest = bs.find('ol', attrs={'class': "psw-l-space-x-1 psw-l-line-center psw-list-style-none"}).find_all('span', attrs={'class': "psw-fill-x"})
number_page = int(latest[-1].get_text())
print("Pages:", number_page)

def safe_get_text(tag, default="Not defined"):
    return tag.get_text().strip() if tag else default

# getting offer time
async def get_offer_time(session, url_offer, old_value="Not defined", retries=3, delay=2):

    for attempt in range(retries):
        try:
            async with session.get(url_offer, timeout=10) as resp:
                if resp.status != 200:
                    await asyncio.sleep(delay)
                    continue
                html = await resp.text()

            bs_offer = BeautifulSoup(html, 'html.parser')
            tag = bs_offer.find(
                'span',
                attrs={'data-qa': re.compile(r"mfeCtaMain#offer\d+#discountDescriptor")}
            )

            if tag:
                return safe_get_text(tag)  
            else:
                await asyncio.sleep(delay)

        except Exception as e:
            print(f"⚠️ Error fetching offer time (try {attempt+1}/{retries}): {e}")
            await asyncio.sleep(delay)

    return old_value


async def fetch_page(session, page_num):
    url = 'https://store.playstation.com/en-tr/category/3f772501-f6f8-49b7-abac-874a88ca4897/{}'.format(page_num)
    print(f"📥 Fetching page {page_num}...")

    try:
        async with session.get(url, timeout=15) as resp:
            if resp.status != 200:
                print(f"⚠️ Error {resp.status} on page {page_num}")
                return []
            html = await resp.text()
    except Exception as e:
        print(f"❌ Failed page {page_num}: {e}")
        return []

    bs = BeautifulSoup(html, 'html.parser')
    offers_post = bs.find('div', attrs={'class': 'psw-l-w-1/1'}).find('ul', attrs={'class': 'psw-grid-list psw-l-grid'})
    if not offers_post:
        print("Structure {} not find".format(offers_post))
        return []
    else:
        # extracting data
        title_all = offers_post.find_all('span', attrs={'id':'product-name'})
        title_link_all = offers_post.find_all('div', attrs={'class':'psw-product-tile psw-interactive-root'})
        platform_names = offers_post.find_all('div', attrs={'class':'psw-l-cluster psw-l-gap-2'})
        discount_all = offers_post.find_all('div', attrs={'class':'psw-m-t-3 psw-m-b-2 psw-badge psw-l-anchor psw-l-inline psw-r-1'})
        offer_price_all = offers_post.find_all('div', attrs={'class':'psw-l-line-left-top psw-l-line-wrap psw-clip psw-t-h-body-1 psw-l-anchor psw-l-line-no-wrap'})
        original_price_all = offers_post.find_all('div', attrs={'class':'psw-l-line-left-top psw-l-line-wrap psw-clip psw-t-h-body-1 psw-l-anchor psw-l-line-no-wrap'})
        pictur_all = offers_post.find_all('span', attrs={'class':'psw-media-frame psw-fill-x psw-image psw-media psw-media-interactive psw-aspect-1-1'})
        type_post_all = bs.find('div', attrs={'class': "psw-l-w-1/1"}).find_all('div', attrs={'class': "psw-product-tile psw-interactive-root"})
    
        results = []
        https = "https://store.playstation.com"
    
        for i in range(len(title_link_all)):
            # game link
            game_link = https + title_link_all[i].find('a')['href']
    
            # offer time (async)
            offer_time = await get_offer_time(session, game_link)
    
            # platform
            plats = platform_names[i].find_all('span')
            plats = [p.get_text() for p in plats]
    
            # picture
            img = pictur_all[i].find_all('img')
            if len(img) > 1:
                picture = img[1].get('src')
            elif img:
                picture = img[0].get('src') or img[0].get('data-src', "No image")
            else:
                picture = "No image"
    
            # type post
            type_tag = type_post_all[i].find('span', attrs={'class': "psw-product-tile__product-type psw-t-bold psw-t-size-1 psw-c-t-2 psw-t-uppercase psw-m-b-1 psw-m-t-2"})
            type_post = type_tag.get_text() if type_tag else None
    
            results.append({
                "title": safe_get_text(title_all[i]),
                "link": game_link,
                "offer_time": offer_time,
                "platforms": " ".join(plats),
                "discount": safe_get_text(discount_all[i]),
                "offer_price": safe_get_text(offer_price_all[i].find('span')),
                "original_price": safe_get_text(original_price_all[i].find('s')),
                "picture": picture,
                "type_post": type_post
            })
    
        print(f"✅ Page {page_num} done, {len(results)} items")
        return results

def save_to_db(flat):
    conn_1 = sqlite3.connect('games_1.db')
    cursor_1 = conn_1.cursor()
    cursor_1.execute("DELETE FROM games")
    for game in flat:
        cursor_1.execute('''
        INSERT INTO games (title, link, offer_time, platforms, discount, offer_price, original_price, picture, type_post, status)
        VALUES (:title, :link, :offer_time, :platforms, :discount, :offer_price, :original_price, :picture, :type_post, NULL)
        ''', game)
    conn_1.commit()
    conn_1.close()
    print("💾 Data saved to games_1.db")


max_pages = min(number_page, 25)
async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_page(session, i) for i in range(1, max_pages + 1)]  #number page
        all_results = await asyncio.gather(*tasks)

    # unique list
    flat = [item for sublist in all_results for item in sublist]
    print(f"\n📊 Total items collected: {len(flat)}")

    # print
    for row in flat[:3]:
        print(row)   
    save_to_db(flat)


def job():
    conn_1 = sqlite3.connect('games_1.db')
    cursor_1 = conn_1.cursor()

    conn = sqlite3.connect('games.db')
    cursor = conn.cursor()

    cursor_1.execute('''
    CREATE TABLE IF NOT EXISTS games(
        title TEXT,
        link TEXT,
        offer_time TEXT,
        platforms TEXT,
        discount TEXT,
        offer_price TEXT,
        original_price TEXT,
        picture TEXT,
        type_post TEXT,
        status INT DEFAULT 0
    )
    ''')
    conn_1.commit()
    print("Job started...")
    # run main code
    asyncio.run(main())  
    rows, rows1 = execute(cursor, cursor_1)
    updating_data(cursor, conn, rows, rows1)
    print("Job finished...\n")
    conn.close()
    conn_1.close()



async def start_scraper(hours: int):
    global stop_ex
    stop_ex = False
    # bedore the changing timer all of the task is cleared
    schedule.clear()

    # deponding on job function extract by timing 
    schedule.every(hours).minutes.do(job)
    print(f"⏳ Scraper scheduled every {hours} hours.")

    while not stop_ex:
        await asyncio.sleep(1) 

    print('The Data Extracting is stopped by user')
    

def stop_scraper():
    global stop_ex
    stop_ex = True
    schedule.clear() 
    print('The Stop function is called and schedule cleared!!')

def run_schedule():
    while True:
            schedule.run_pending()
            time.sleep(1)

    # running at the different tiime
t = Thread(target=run_schedule, daemon=True)
t.start()



# def start_scraper(nu_time):
#     # job()
#     schedule.every(nu_time).hours.do(job)
#     while True:
#         schedule.run_pending()
#         time.sleep(1)
# # start_scraper(24)



