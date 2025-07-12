from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from datetime import datetime, timedelta
from fpdf import FPDF
import os, json

# .env dan token va admin ID o‘qish
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# JSON fayllar orqali ma'lumot saqlash
def load_data(file, default):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_data(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

trees = load_data("trees.json", {})
users = load_data("users.json", {})
pending = {}

# Foydalanuvchi va admin uchun tugmalar
user_kb = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("🌳 Daraxt ID kiritish"))
user_full_kb = lambda: ReplyKeyboardMarkup(resize_keyboard=True).add(
    KeyboardButton("🌊 Suv berdim"), KeyboardButton("🧹 Tozaladim")
).add(KeyboardButton("👤 Profilim"), KeyboardButton("🏆 Reyting")).add(KeyboardButton("⬅️ Ortga"))

admin_kb = ReplyKeyboardMarkup(resize_keyboard=True).add(
    KeyboardButton("👤 Bloklanganlar"),
    KeyboardButton("🌳 Daraxtlar"),
    KeyboardButton("🏆 Foydalanuvchilar reytingi"),
    KeyboardButton("➕ Daraxt qo‘shish"),
    KeyboardButton("📄 Hisobot (PDF)"),
    KeyboardButton("♻️ Ballarni nolga tushirish")  # ✅ YANGI TUGMA
)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    uid = message.from_user.id
    username = message.from_user.username or str(uid)
    users.setdefault(username, {"score": 0, "ban": False, "current_tree": None, "id": uid})
    save_data("users.json", users)

    args = message.get_args()
    if args and args.upper() in trees:
        users[username]["current_tree"] = args.upper()
        save_data("users.json", users)
        return await send_tree_info(message, args.upper(), user_full_kb())

    await message.answer("👋 Admin panelga xush kelibsiz" if uid == ADMIN_ID else "👋 Xush kelibsiz! Daraxt tanlang:",
                         reply_markup=admin_kb if uid == ADMIN_ID else user_kb)

@dp.message_handler(lambda m: m.text in ["🌳 Daraxt ID kiritish", "⬅️ Ortga"])
async def ask_tree_id(message: types.Message):
    username = message.from_user.username or str(message.from_user.id)
    users[username]["current_tree"] = None
    save_data("users.json", users)
    await message.answer("Daraxt ID ni kiriting (masalan: ID001):", reply_markup=user_kb)

@dp.message_handler(lambda m: m.text.upper().startswith("ID") and ";" not in m.text)
async def set_tree_by_id(message: types.Message):
    username = message.from_user.username or str(message.from_user.id)
    tree_id = message.text.upper()
    if tree_id not in trees:
        return await message.answer("❌ Bunday daraxt ID topilmadi.")
    users.setdefault(username, {"score": 0, "ban": False, "current_tree": None, "id": message.from_user.id})
    users[username]["current_tree"] = tree_id
    save_data("users.json", users)
    await send_tree_info(message, tree_id, user_full_kb())

async def send_tree_info(message, tree_id, keyboard):
    t = trees[tree_id]
    await message.answer(
        f"""🌳 {t['species']}
{t['desc']}
Ekilgan: {t['date']}
Ekkani: {t['planter']}
Suv har {t['water']} kunda, Tozalash har {t['clean']} kunda
Oxirgi suv: {t.get('last_water', 'yo‘q')}
Oxirgi tozalash: {t.get('last_clean', 'yo‘q')}""",
        reply_markup=keyboard
    )
@dp.message_handler(lambda m: m.text in ["🌊 Suv berdim", "🧹 Tozaladim"])
async def handle_action(message: types.Message):
    username = message.from_user.username or str(message.from_user.id)
    if users[username].get("ban"):
        return await message.answer("⛔ Siz bloklangansiz.")
    tree_id = users[username].get("current_tree")
    if not tree_id:
        return await message.answer("❗ Avval daraxt tanlang.")
    action = "water" if message.text == "🌊 Suv berdim" else "clean"
    key = (tree_id, action)
    tree = trees[tree_id]

    # Amal hali tekshiruvda bo‘lsa
    if key in pending:
        return await message.answer("⏳ Bu amal boshqa foydalanuvchi tomonidan yuborilgan va admin tekshiruvda.")

    # Amal cheklov vaqti tekshiruvi
    last = tree.get(f"last_{action}")
    if last:
        last_date = datetime.strptime(last, "%Y-%m-%d")
        next_date = last_date + timedelta(days=tree[action])
        if datetime.now() < next_date:
            return await message.answer(
                f"ℹ️ Bu daraxtga {last_date.strftime('%d.%m.%Y')} da bu amal bajarilgan.\n"
                f"Keyingi amal sanasi: {next_date.strftime('%d.%m.%Y')}"
            )

    users[username]["pending_action"] = (tree_id, action)
    save_data("users.json", users)
    await message.answer("📷 Iltimos, amalni bajarganingizni tasdiqlovchi rasm yuboring.")

@dp.message_handler(lambda m: m.text == "♻️ Ballarni nolga tushirish")
async def reset_scores(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    for u in users:
        users[u]["score"] = 0
        users[u]["water_done"] = 0
        users[u]["clean_done"] = 0
    save_data("users.json", users)

    # Sana va vaqtni faylga yozish
    with open("reset_log.txt", "w", encoding="utf-8") as f:
        f.write(datetime.now().strftime('%d.%m.%Y %H:%M'))

    await message.answer("✅ Barcha foydalanuvchilarning ballari nolga tushirildi.")

@dp.message_handler(content_types=types.ContentType.PHOTO)
async def receive_photo(message: types.Message):
    username = message.from_user.username or str(message.from_user.id)
    info = users[username].get("pending_action")
    if not info:
        return await message.answer("❗ Avval amalni tanlang.")
    tree_id, action = info
    key = (tree_id, action)
    file_id = message.photo[-1].file_id
    pending[key] = {
        "user": username,
        "time": datetime.now().strftime("%Y-%m-%d"),
        "file_id": file_id
    }

    # ✅ Bu yerda noto‘g‘ri bo‘sh joy xatosi bo‘lishi mumkin edi. Endi to‘g‘ri:
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{tree_id}_{action}"),
        InlineKeyboardButton("⚠️ Rad – Ogohlantirish", callback_data=f"warn_{tree_id}_{action}"),
        InlineKeyboardButton("⛔ Rad – Bloklash", callback_data=f"block_{tree_id}_{action}")
    )

    await bot.send_photo(ADMIN_ID, photo=file_id,
                         caption=f"👤 @{username}\n🌳 {tree_id}\n🔧 {action.upper()}",
                         reply_markup=markup)
    await message.answer("✅ Amal yuborildi. Admin tekshiruvda.")
    users[username]["pending_action"] = None
    save_data("users.json", users)

@dp.callback_query_handler(lambda c: any(c.data.startswith(p) for p in ["approve_", "warn_", "block_"]))
async def admin_decision(call: types.CallbackQuery):
    action_type, tid, action = call.data.split("_")
    key = (tid, action)
    data = pending.get(key)
    if not data:
        return await call.message.edit_text("❌ Amal topilmadi.")

    username = data["user"]
    user_id = users[username]["id"]

    if action_type == "approve":
        # ✅ Amalni tasdiqlash
        trees[tid][f"last_{action}"] = data["time"]
        trees.setdefault(tid, {}).setdefault(f"{action}_count", 0)
        trees[tid][f"{action}_count"] += 1
        users.setdefault(username, {}).setdefault(f"{action}_done", 0)
        users[username][f"{action}_done"] += 1
        users[username]["score"] += 10
        save_data("trees.json", trees)
        save_data("users.json", users)
        try:
            await bot.send_message(user_id, f"✅ {action.upper()} amal tasdiqlandi. +10 ball.")
        except:
            pass

    elif action_type == "warn":
        # ⚠️ Ogohlantirish yuborish
        users.setdefault(username, {}).setdefault("warnings", 0)
        users[username]["warnings"] += 1
        save_data("users.json", users)
        try:
            await bot.send_message(user_id, "⚠️ Amal rad qilindi. Ogohlantirish berildi. Yana xato bo‘lsa bloklanasiz.")
        except:
            pass

    elif action_type == "block":
        # ⛔ Bloklash
        users.setdefault(username, {})
        users[username]["ban"] = True
        save_data("users.json", users)
        try:
            await bot.send_message(user_id, "⛔ Amal rad qilindi. Siz bloklandingiz va botdan foydalana olmaysiz.")
        except:
            pass

    # ✅ Har qanday holatda ham tekshiruvdan olib tashlash
    del pending[key]
    await call.message.edit_reply_markup()

@dp.message_handler(lambda m: m.text == "👤 Profilim")
async def profile(message: types.Message):
    username = message.from_user.username or str(message.from_user.id)
    u = users[username]
    score = u["score"]
    water = u.get("water_done", 0)
    clean = u.get("clean_done", 0)
    await message.answer(f"👤 @{username}\n🎯 Ball: {score}\n💧 Suv bergan: {water} marta\n🧹 Tozalagan: {clean} marta")

@dp.message_handler(lambda m: m.text in ["🏆 Reyting", "🏆 Foydalanuvchilar reytingi"])
async def leaderboard(message: types.Message):
    sorted_users = sorted(users.items(), key=lambda x: x[1]["score"], reverse=True)
    text = "\n".join([f"{i+1}. @{u} – {d['score']} ball" for i, (u, d) in enumerate(sorted_users)])
    await message.answer("🏆 Reyting:\n" + text)
@dp.message_handler(lambda m: m.text == "👤 Bloklanganlar")
async def show_blocked(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    markup = InlineKeyboardMarkup()
    for u, d in users.items():
        if d["ban"]:
            markup.add(InlineKeyboardButton(f"{u}", callback_data=f"unblock_{u}"))
    if markup.inline_keyboard:
        await message.answer("🚫 Bloklangan foydalanuvchilar:", reply_markup=markup)
    else:
        await message.answer("🚫 Bloklangan foydalanuvchi yo‘q.")

@dp.callback_query_handler(lambda c: c.data.startswith("unblock_"))
async def unblock_user(call: types.CallbackQuery):
    username = call.data.split("_")[1]
    if username in users:
        users[username]["ban"] = False
        save_data("users.json", users)
        await call.answer("✅ Blokdan chiqarildi", show_alert=True)
        await call.message.edit_reply_markup()

@dp.message_handler(lambda m: m.text == "➕ Daraxt qo‘shish")
async def prompt_add_tree(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Yozing: ID;Turi;Sana;Ekkani;Lavozimi;Tavsif;SuvKuni;TozalashKuni")

@dp.message_handler(lambda m: ";" in m.text and m.from_user.id == ADMIN_ID)
async def add_tree(message: types.Message):
    try:
        tid, typ, date, name, pos, desc, water, clean = message.text.split(";")
        tid = tid.upper()
        if tid in trees:
            return await message.answer("❗ Bu ID allaqachon mavjud.")
        trees[tid] = {
            "species": typ, "date": date, "planter": f"{name} ({pos})",
            "desc": desc, "water": int(water), "clean": int(clean)
        }
        save_data("trees.json", trees)
        await message.answer(f"✅ {tid} daraxti saqlandi.")
    except:
        await message.answer("❌ Xatolik. Format to‘g‘ri emas.")

@dp.message_handler(lambda m: m.text == "🌳 Daraxtlar")
async def list_trees(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    for tid, t in trees.items():
        text = f"ID: {tid}\nTuri: {t['species']}\nSuv: {t.get('last_water', 'yo‘q')} ({t.get('water_count', 0)} marta)\n" \
               f"Tozalash: {t.get('last_clean', 'yo‘q')} ({t.get('clean_count', 0)} marta)"
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton(f"🗑 O‘chirish {tid}", callback_data=f"delete_{tid}")
        )
        await message.answer(text, reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith("delete_"))
async def delete_tree(call: types.CallbackQuery):
    tid = call.data.split("_")[1]
    if tid in trees:
        del trees[tid]
        save_data("trees.json", trees)
        await call.message.edit_text(f"🗑 {tid} daraxti o‘chirildi.")

from fpdf import FPDF

@dp.message_handler(lambda m: m.text == "📄 Hisobot (PDF)")
async def generate_pdf_report(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Yuklangan vaqt
    now_str = datetime.now().strftime('%d.%m.%Y %H:%M')

    # Ballar nolga tushirilgan so‘nggi vaqtni o‘qish
    try:
        with open("reset_log.txt", "r", encoding="utf-8") as f:
            reset_time = f.read().strip()
    except FileNotFoundError:
        reset_time = "Ma’lumot yo‘q"

    # Hisobot bosh qismi
    pdf.cell(200, 10, txt="Aqlli Kochat Hisobot", ln=True, align="C")
    pdf.cell(200, 10, txt=f"Yuklangan sana: {now_str}", ln=True, align="C")
    pdf.cell(200, 10, txt=f"Ballar nolga tushirilgan: {reset_time}", ln=True, align="C")
    pdf.ln(10)

    # Daraxtlar statistikasi
    pdf.cell(200, 10, txt="Daraxtlar statistikasi:", ln=True)
    for tid, t in trees.items():
        line = f"{tid} - {t['species']} | Suv: {t.get('water_count', 0)} | Tozalash: {t.get('clean_count', 0)}"
        pdf.cell(200, 10, txt=line, ln=True)

    # Foydalanuvchilar statistikasi
    pdf.ln(10)
    pdf.cell(200, 10, txt="Foydalanuvchilar statistikasi:", ln=True)
    for u, d in users.items():
        line = f"{u} | Ball: {d['score']} | Suv: {d.get('water_done', 0)} | Tozalash: {d.get('clean_done', 0)}"
        pdf.cell(200, 10, txt=line, ln=True)

    file_path = "hisobot.pdf"
    pdf.output(file_path)
    await bot.send_document(chat_id=message.chat.id, document=types.InputFile(file_path))

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
