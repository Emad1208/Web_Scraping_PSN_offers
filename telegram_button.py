from decouple import config
import asyncio
import aiosqlite
import aiohttp
import threading
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler ,filters
from telegram.error import RetryAfter, BadRequest
from datetime import datetime
from pagination_aiohttp_DB import start_scraper , stop_scraper, job


tk = config('token')
channel_id = -1003124060319
admins = [1725178616]
is_sending = False
sending_task = None 
status_ex = None
waiting_for_time = {}
pass_word_admin = '1234'

def is_admin(user):
    return user in admins

async def read_posts_from_db(status_filter=0):
    async with aiosqlite.connect("games.db") as conn:
        async with conn.execute('''
            SELECT title, link, offer_time, platforms, discount, offer_price, original_price, picture, type_post
            FROM games
            WHERE status = ?
        ''', (status_filter,)) as cursor:
            posts = await cursor.fetchall() 
            return posts

async def mark_post_as_sent(link: str):
    async with aiosqlite.connect("games.db") as conn:
        await conn.execute("UPDATE games SET status = 1 WHERE link = ?", (link,))
        await conn.commit()

async def check_image_url(url: str, retries=2, delay=2) -> bool:
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                # try head
                try:
                    async with session.head(url, timeout=10) as resp:
                        if resp.status == 200:
                            content_type = resp.headers.get("Content-Type", "")
                            if "image" in content_type.lower():
                                return True
                except Exception:
                    pass  

                # try get
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get("Content-Type", "")
                        if "image" in content_type.lower():
                            return True
        except Exception as e:
            print(f"⚠️ Error fetching picture (try {attempt+1}/{retries}): {e}")
            await asyncio.sleep(delay)

    return False        

def build_caption(Title, Platform, Original_Price, Discount, Offer_Price, Title_Link, Offer_Time, type_post, today):
    if type_post:
        type_post = type_post.replace(' ', '_')
        type_post = type_post.replace('-','_')

    else:
        type_post = 'Game'
    return (
        f'<b>{Title}</b>\n\n'
        f'<b>{Platform}</b>\n\n'
        f'Original Price : <del>{Original_Price}</del>\n'
        f'Discount : {Discount}\n'
        f'Offer Price : {Offer_Price}\n\n'
        f'<a href="{Title_Link}">Click here to buy</a>\n\n'
        f'<ins>{Offer_Time}</ins>\n'
        f'<b>Today : {today}</b>\n\n'
        f'<b>Tag Post : #{type_post}</b>\n\n'
        '@game'
    )


async def main_inlines():
    keyboards =[
        InlineKeyboardButton('Start sending posts', callback_data= 'Start sending'),
        InlineKeyboardButton('Stop sending posts', callback_data= 'Stop sending')
    ],[
        InlineKeyboardButton('+ Start Exracting data (by timing)', callback_data= 'Extracting_timing'),
        InlineKeyboardButton('- Stop Exracting data (by timing)', callback_data= 'Stop_extracting')
    ],[
        InlineKeyboardButton('Start Exracting data (right now)', callback_data= 'Extracting now')
    ],[
        InlineKeyboardButton('Delete the whole DataBase', callback_data= 'Deleting DataBase')
    ],[
        InlineKeyboardButton('Change your password ', callback_data= 'Change_pass')
    ]
    
    return InlineKeyboardMarkup(keyboards)

# confirm_action
async def confirm_action(query, text, yes_call_back, no_call_back):
    confirm_action = [
            [
            InlineKeyboardButton('Yes', callback_data= yes_call_back),
            InlineKeyboardButton('No', callback_data= no_call_back)
            ],[
                InlineKeyboardButton('Back', callback_data= 'back')
            ]
        ]
    await query.edit_message_text('<b>{}</b>'.format(text),
            reply_markup= InlineKeyboardMarkup(confirm_action), parse_mode='html')
# start command
async def start(update : Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id
    if is_admin(user):
        mark_up = await main_inlines()
        await update.message.reply_text('Please choose one:', reply_markup = mark_up)

# Start sending posts ---------- function button
async def start_sending(query, update, context):
    await confirm_action(query,'Do you want to start the sending posts?','Yes','No')

async def start_yes_sending(query, update, context):
    global is_sending, sending_task

    user = update.effective_user.id
    if is_admin(user):
        if is_sending:  # task is running
            await query.edit_message_text("<b>⚠️ Already running!</b>", parse_mode='html')
            return
        
        await query.edit_message_text("<b>The start sending posts is active! ✅</b>", parse_mode='html')
        is_sending = True
        # create a task
        sending_task = asyncio.create_task(send_posts_loop(update, context))

async def send_posts_loop(update, context):
    default_image = 'https://gmedia.playstation.com/is/image/SIEPDC/ps-store-evergreen-image-block-01-en-09aug22?$1600px$'
    global is_sending
    while is_sending:
            today = datetime.now().strftime("%m/%d/%Y")
            
            posts = await read_posts_from_db(status_filter=0)  
            if not posts:
                print("⏳ No new posts, checking again in 10s...")
                await context.bot.send_message(chat_id = update.effective_chat.id,
                    text = '💯💯 All of the posts in Data Base is sent \n Date: {}'.format(today))
                # timing for re-scan the DataBase
                await asyncio.sleep(100)   #            await asyncio.sleep(3 * 3600 + 30 * 60)  3 hours and 30 minutes
                continue
            
            for idx, post in enumerate(posts, start=1):
                Title, Title_Link, Offer_Time, Platform, Discount, Offer_Price, Original_Price, Pictur, Type_Post = post
    
                try:
                
                    image_url = Pictur if await check_image_url(Pictur) else default_image
                    
                    await context.bot.send_photo(
                        chat_id = channel_id,
                        photo=image_url,
                        caption=build_caption(
                            Title, Platform, Original_Price, Discount,
                            Offer_Price, Title_Link, Offer_Time, Type_Post, today
                        ),
                        parse_mode='HTML'
                    )
                    
                    
                    await mark_post_as_sent(Title_Link)
                    print(f"✅ Post {idx} sent: {Title}")
                    # timing for sending posts
                    await asyncio.sleep(10)  
                    
                except RetryAfter as e:
                    wait_time = int(e.retry_after)
                    print(f"💥 Flood control, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time + 1)
                except BadRequest as e:
                        print(f"❌ BadRequest at post {idx}: {e}")
                        await context.bot.send_message(chat_id= update.effective_chat.id,text= f"❌ BadRequest at post {idx}: {e}\n<a href='{Title_Link}'>{Title}</a>", parse_mode= 'html')
                        await mark_post_as_sent(Title_Link)
            
            
    await asyncio.sleep(10)

    

async def start_no_sending(query, update, context):
    await query.edit_message_text('<b>The start sending posts is canceled! ❌</b>', parse_mode= 'html')

# Stop sending posts ------------- function button
async def stop_sending(query, update, context):
    await confirm_action(query, 'Do you want to stop the sending posts?','Yes_stop','No_stop')
    
async def stop_yes_sending(query, update, context):
    global is_sending, sending_task
    if is_sending:
        is_sending = False
        if sending_task:
            sending_task.cancel()
            sending_task = None
        await query.edit_message_text("<b>❌ Sending stopped!</b>", parse_mode='html')
    else:
        await query.edit_message_text("<b>⚠️ Nothing is running!</b>", parse_mode='html')

async def stop_no_sending(query, update, context):
    await query.edit_message_text('<b>The sending posts is not stopped! ❌</b>',parse_mode='html')

# Extracting Data by clicking (right now) --------- function button
async def extracting_now(query, update, context):
    await confirm_action(query,'Do you want to Extracte data at this moment?\nThis order canceled the Data Extracting automatic porcess! ⚠️','Yes_extract','No_extract' )

async def extracting_yes_now(query, update, context):
    user = update.effective_user.id
    await query.edit_message_text('<b>Enter the password :</b>',parse_mode='html')
    waiting_for_time.pop(user, None)
    waiting_for_time[user] = "waiting_for_password"


async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):   
    global pass_word_admin
    user = update.effective_user.id
    
    if user in waiting_for_time and waiting_for_time[user] == "waiting_for_password":
        
        try:
            if not update.message or not update.message.text:
                await context.bot.send_message(
                    chat_id=user,
                    text='<b>Please send a text message (not a photo or sticker).</b>',
                    parse_mode='html'
                )
                return
            
            pass_word = update.message.text.strip()

            
            if pass_word == pass_word_admin:
                waiting_for_time.pop(user)

                await context.bot.send_message(
                    chat_id=user,
                    text='<b>✅ Password correct!\nStarting data extraction...</b>',
                    parse_mode='html'
                )
                stop_scraper()
                await asyncio.to_thread(job)

            else:
                await context.bot.send_message(
                    chat_id=user,
                    text='<b>❌ Wrong password! Try again.</b>',
                    parse_mode='html'
                )

        except Exception as e:
            await context.bot.send_message(
                chat_id=user,
                text=f'<b>An unexpected error occurred:</b>\n<code>{e}</code>',
                parse_mode='html'
            )            
async def extracting_no_now(query, update, context):
    await query.edit_message_text('<b>The Extracting data is canceled! ❌</b>',parse_mode='html')

# Extracting Data by giving time (deponds on admins) ---------- function button
async def extracting_timing(query, update, context):
    await confirm_action(query,'Do you want the data Extraction to be repeated automaticly?','Yes_extract_time','No_extract_time' )
    
async def extracting_yes_timing(query, update, context):
    global status_ex
    user = update.effective_user.id
    if not status_ex:
        waiting_for_time.pop(user, None)
        waiting_for_time[user] = True
        await query.edit_message_text('<b>How often do you want the data Extraction to be repeated?</b>\nPleace inter a number (In hours):',
                    parse_mode='html')
    else:
        await query.edit_message_text('<b>Data Extracting is running! ⚠️</b>',
                parse_mode='html')
    
async def get_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global status_ex
    user = update.effective_user.id
    if user in waiting_for_time and waiting_for_time[user] == True:
        if not status_ex:
            try:
                hours = int(update.message.text)
                if hours < 1 or hours > 24:
                    await context.bot.send_message(chat_id= user, text= '<b>Your number must be between 1 and 24</b>',parse_mode='html')
                else:
                    waiting_for_time[user] = False
                    await context.bot.send_message(chat_id= user, text='<b>Your data extracting will be repeated evry {} hours</b>'.format(hours),
                        parse_mode='html')
                    status_ex = asyncio.create_task(start_scraper(hours))
            except ValueError:
                await context.bot.send_message(chat_id= user , text='<b>Please just enter a number</b>',
                    parse_mode='html')    
        else:
            pass

async def extracting_no_timing(query, update, context):
    await query.edit_message_text('<b>The data Extracting is canceled! ❌</b>',
                parse_mode='html')
    
# Stop data extracting -------- function button    
async def stop_extracting(query, update, context):
    await confirm_action(query, 'Do you want to Stop Data Extracting ? ⚠️', 'yes_stop_ex','no_stop_ex')

async def yes_stop_ex(query, update, context):
    global status_ex
    if not status_ex:
        await query.edit_message_text("<b>⚠️ Nothing is running!</b>", parse_mode='html')
        return
    stop_scraper()
    status_ex = None
    waiting_for_time.clear()
    await query.edit_message_text('<b>Stopping Data Extracting is successful! ✅</b>', parse_mode='html')

async def no_stop_ex(query, update, context):
    await query.edit_message_text('<b>Stopping Data Extracting is canceled! ❌</b>', parse_mode='html')

# Deleting DataBase ----------- function button
async def deleting_database(query, update, context):
    await confirm_action(query, 'Are sure about deleting the whole DataBase? ⚠️','Yes_delete','No_delete')
    
async def deleting_yes_database(query, update, context):
    await query.edit_message_text('<b>The whole DataBase is deleted! ✅</b>', parse_mode='html')

async def deleting_no_database(query, update, context):
    await query.edit_message_text('<b>Deleting DataBase is canceled! ❌</b>', parse_mode='html')

# back --------- function button
async def back(query, update, context):
    mark_up = await(main_inlines())
    await query.edit_message_text('Please choose one:', reply_markup = mark_up)
# change password ---------- function button
async def change_pass(query, update, context):
    await confirm_action(query,'Do you want to Change your password? ⚠️','Yes_pass','No_pass' )

async def yes_pass_change(query, update, context):
    user = update.effective_user.id
    waiting_for_time.pop(user, None)
    waiting_for_time[user] = 'waiting_old_password'
    await query.edit_message_text('<b>Enter your current password: </b>', parse_mode='html')
    
async def changing_pass( update, context):
    global pass_word_admin
    user = update.effective_user.id
    if user in waiting_for_time and waiting_for_time[user] == 'waiting_old_password':
        try:
            if not update.message or not update.message.text:
                await context.bot.send_message(
                    chat_id=user,
                    text='<b>Please send a text message (not a photo or sticker).</b>',
                    parse_mode='html'
                )
                return
            text = update.message.text.strip()

            if waiting_for_time.get(user) == 'waiting_old_password':
                if text != pass_word_admin:
                    await context.bot.send_message(chat_id = user, text = '<b>Your Password is wrong! </b>⚠️\nPlease enter your current password: ',parse_mode = 'html')
            
                else:
                    waiting_for_time[user] = 'waiting_new_password'
                    await context.bot.send_message(chat_id = user, text = '<b>Enter your new password: </b>',parse_mode = 'html')
        except Exception as e:
            await context.bot.send_message(
                chat_id=user,
                text=f'<b>An unexpected error occurred:</b>\n<code>{e}</code>',
                parse_mode='html'
            )
async def set_new_password(update, context):
    global pass_word_admin
    user = update.effective_user.id
    if user in waiting_for_time and waiting_for_time[user] == 'waiting_new_password':
        try:
            if not update.message or not update.message.text:
                await context.bot.send_message(
                    chat_id=user,
                    text='<b>Please send a text message (not a photo or sticker).</b>',
                    parse_mode='html'
                )
                return

            new_pass = update.message.text.strip()
            pass_word_admin = new_pass
            waiting_for_time.pop(user, None)

            await context.bot.send_message(
                chat_id=user,
                text=f'<b>Password changed successfully ✅</b>\nYour new password: <code>{new_pass}</code>',
                parse_mode='html'
            )

        except Exception as e:
            await context.bot.send_message(
                chat_id=user,
                text=f'<b>An unexpected error occurred:</b>\n<code>{e}</code>',
                parse_mode='html'
            )

async def no_pass_change(query, update, context):
    await query.edit_message_text('<b>Changing password is canceled! ❌</b>', parse_mode='html')

async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id

    if user in waiting_for_time and waiting_for_time[user] == "waiting_for_password":
        await get_password(update, context)

 
    elif user in waiting_for_time and waiting_for_time[user] == True:
        await get_user_input(update, context)

    elif user in waiting_for_time and waiting_for_time[user] == 'waiting_old_password':
        await changing_pass(update, context)

    elif user in waiting_for_time and waiting_for_time[user] == 'waiting_new_password':
        await set_new_password(update, context)

    else:
        await context.bot.send_message(
            chat_id=user,
            text="Unexpected type of data⚠️",
            parse_mode="html"
        )

dictionary_query = {
    # Sending Posts
    'Start sending': start_sending,
    'Yes': start_yes_sending,
    'No': start_no_sending,
    'Stop sending':stop_sending,
    'Yes_stop': stop_yes_sending,
    'No_stop': stop_no_sending,
    # Extracting Data
    #### Now
    'Extracting now': extracting_now,
    'Yes_extract': extracting_yes_now,
    'No_extract': extracting_no_now,
    #### By Timing Start
    'Extracting_timing': extracting_timing,
    'Yes_extract_time': extracting_yes_timing,
    'No_extract_time': extracting_no_timing,
    #### By Timing Stop
    'Stop_extracting': stop_extracting,
    'yes_stop_ex': yes_stop_ex,
    'no_stop_ex' : no_stop_ex,
    # Deleting Data Base
    'Deleting DataBase': deleting_database,
    'Yes_delete': deleting_yes_database,
    'No_delete': deleting_no_database,
    # Back
    'back': back,
    # Setting Password
    'Change_pass': change_pass,
    'Yes_pass': yes_pass_change,
    'No_pass': no_pass_change
}
# button function -----------    
async def button(update : Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = dictionary_query.get(query.data)
    if action:
        await action(query, update, context)

def main():
    app = Application.builder().token(tk).build()
    app.add_handler(CommandHandler('start',start, block= False))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_input))
    app.run_polling(allowed_updates= Update.ALL_TYPES)


if __name__ == '__main__':
    main()    