import feedparser
import os
import random
import json
import requests
import time
import re
from bs4 import BeautifulSoup
from google import genai

# --- المصادر ---
RSS_SOURCES = [
    {"url": "https://techcrunch.com/feed/", "name": "TechCrunch", "all": True},
    {"url": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml", "name": "TheVerge-AI", "all": False},
    {"url": "https://www.theverge.com/tech/rss/index.xml", "name": "TheVerge-Tech", "all": False},
]

HISTORY_FILE = "tech_published.txt"

# --- الأسرار ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
IG_ACCOUNT_ID = os.environ.get("IG_ACCOUNT_ID")
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
THREADS_ACCOUNT_ID = os.environ.get("THREADS_ACCOUNT_ID")
BSKY_HANDLE = os.environ.get("BSKY_HANDLE")
BSKY_APP_PASSWORD = os.environ.get("BSKY_APP_PASSWORD")
GH_PAT = os.environ.get("GH_PAT")
GH_REPO = os.environ.get("GH_REPO")

# --- جيميناي ---
api_keys_list = []
secrets_json = os.environ.get("ALL_SECRETS")
if secrets_json:
    try:
        secrets_dict = json.loads(secrets_json)
        for key_name, key_value in secrets_dict.items():
            if key_name.startswith("GEMINI_API_KEY_"):
                api_keys_list.append(key_value)
    except json.JSONDecodeError:
        print("❌ خطأ في قراءة الـ Secrets.")

if not api_keys_list:
    print("❌ لم يتم العثور على مفاتيح Gemini!")
    exit()

selected_api_key = random.choice(api_keys_list).strip()
models_list = ['gemma-4-31b-it', 'gemma-4-26b-a4b-it']
selected_model = random.choice(models_list)
client = genai.Client(api_key=selected_api_key)

print(f"🔑 تم العثور على ({len(api_keys_list)}) مفاتيح API.")
print(f"🤖 النموذج: {selected_model}")


# ============================================================
# وظائف الذاكرة
# ============================================================
def get_published_data():
    data = {}
    if not os.path.exists(HISTORY_FILE):
        return data
    with open(HISTORY_FILE, "r") as f:
        for line in f.readlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) == 3:
                link = parts[0].strip()
                title = parts[1].strip()
                platforms = set(p.strip() for p in parts[2].split(","))
                data[link] = {"title": title, "platforms": platforms}
            elif len(parts) == 2:
                link = parts[0].strip()
                platforms = set(p.strip() for p in parts[1].split(","))
                data[link] = {"title": "", "platforms": platforms}
            else:
                data[line.strip()] = {"title": "", "platforms": set()}
    return data

def save_published_data(data):
    with open(HISTORY_FILE, "w") as f:
        for link, info in data.items():
            title = info.get("title", "")
            platforms_str = ",".join(sorted(info.get("platforms", set())))
            f.write(f"{link} | {title} | {platforms_str}\n")


# ============================================================
# سحب المقالات من RSS
# ============================================================
def get_new_articles(published_data):
    articles_per_source = {}
    for source in RSS_SOURCES:
        feed = feedparser.parse(source["url"])
        for entry in feed.entries[:20]:
            link = entry.link
            if link not in published_data:
                name = source["name"]
                if name not in articles_per_source:
                    articles_per_source[name] = []
                articles_per_source[name].append({
                    "link": link,
                    "title": entry.title,
                    "source": name,
                    "summary": entry.get("summary", "")
                })

    # اختيار مصدر عشوائي من المصادر اللي عندها مقالات جديدة
    available_sources = [articles for articles in articles_per_source.values() if articles]
    if not available_sources:
        return []
    
    chosen_source = random.choice(available_sources)
    return [chosen_source[0]]


# ============================================================
# سحب نص المقالة الكاملة
# ============================================================
def fetch_article_text(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        # إزالة السكريبتات والستايلات
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text(strip=True) for p in paragraphs)
        return text[:8000]  # أول 8000 حرف كافي لجيميناي
    except Exception as e:
        print(f"⚠️ فشل سحب المقالة: {e}")
        return ""


# ============================================================
# فحص التكرار بجيميناي
# ============================================================
def is_duplicate(new_title, published_titles):
    if not published_titles:
        return False
    if len(published_titles) > 30:
        published_titles = published_titles[-30:]

    titles_text = "\n".join(f"- {t}" for t in published_titles)
    prompt = f"""
    لديك مقالة جديدة عنوانها: "{new_title}"
    ولديك قائمة مقالات تم نشرها مسبقاً:
    {titles_text}
    
    هل الموضوع الرئيسي للمقالة الجديدة مطابق أو متشابه جداً لأي مقالة في القائمة؟
    أجب بكلمة واحدة فقط: نعم أو لا
    """
    try:
        response = client.models.generate_content(model=selected_model, contents=prompt)
        answer = response.text.strip()
        return "نعم" in answer
    except Exception as e:
        print(f"⚠️ خطأ في فحص التكرار: {e}")
        return False


# ============================================================
# توليد المحتوى العربي بجيميناي
# ============================================================
def generate_arabic_post(title, article_text):
    prompt = f"""
    أنت خبير صناعة محتوى تقني ومترجم رقمي محترف، متخصص في صياغة منشورات جذابة وفيرال (Viral) لمنصات التواصل الاجتماعي (Telegram, Facebook, Instagram, Threads, Bluesky).
    مهمتك هي تلخيص وتحويل المقال الإنجليزي المرفق إلى منشور اجتماعي مكتوب بـ "العربية الفصحى البيضاء" بأسلوب سردي بشري انسيابي وطبيعي 100%.

    [سياق المدخلات]
    - عنوان المقال: {title}
    - نص المقال: {article_text[:1000000]}

    [استراتيجية التنفيذ والتوجيه اللغوي]
    1. التعامل مع المصطلحات: حافظ على المصطلحات التقنية المتقدمة والمتخصصة باللغة الإنجليزية (English) كما هي دون ترجمة إذا كانت تفتقر لمرادف عربي دقيق ودارج، وذلك لضمان احترافية المحتوى ومصداقيته لدى الجمهور التقني.
    2. الخطاف الديناميكي الذكي (The Hook): قم بتحليل المقال المرفق واكتشف العنصر الأكثر إثارة فيه. اختر بحرية وبناءً على المحتوى نوع الخطاف الأقوى لجذب الانتباه في السطر الأول مباشرة (سواء كان: سؤالاً تفاعلياً يثير الفضول، إحصائية/رقماً صادماً من النص، أو مفارقة تكنولوجية غريبة، وبالمثل...). الهدف الأساسي هو دفع القارئ للنقر على "قراءة المزيد" وتوليد رغبة عارمة لديه للتعليق أو المشاركة لرفع الريتش (Reach).
    3. صياغة جسم المنشور: رتب النقاط والفوائد الأساسية المستخلصة بشكل متسلسل، واستخدم مسافات برمجية (أسطر فارغة) بين الفقرات لسهولة القراءة السريعة (Scannability).
    4. الختام والتفاعل (CTA): أنهِ المنشور بدعوة صريحة ومحفزة للجمهور للتفاعل (مثل فتح نقاش أو طلب مشاركة آرائهم)، وألحقها مباشرة بالإيموجي (👇) في نفس السطر أو سطر منفصل.
    5. الوسوم (Hashtags): في السطر الأخير تماماً، أضف 5 هاشتاغات ذات صلة وثيقة بالمحتوى (مزيج بين العربي والإنجليزي).

    [محددات وقيود صارمة]
    - يُمنع تماماً استخدام أي تنسيقات ماردوان (Markdown) مثل النجوم (* أو ** أو *** لتغليظ الكلمات أو " أو "")، أو الخطوط الفاصلة (---)، أو علامة !، أو وسوم HTML. يجب أن يظهر النص كاملاً ككتلة نصية خام ونقية (Plain Text) لتناسب اللصق المباشر على كافة المنصات المستهدفة دون تشويه لغوي.
    - يُمنع إدراج أي روابط أو استخدام كلمات نائبة مثل [رابط] أو (Link) أو أي إشارة نصية توحي بوجود رابط خارجي.
    - ابدأ بكتابة المنشور مباشرة؛ يُمنع تماماً كتابة أي مقدمات تفاعلية أو هوامش تفسيرية من النموذج (مثل: "إليك المنشور المطلوبة"). السطر الأول في ردك هو أول سطر في المنشور مباشرة.
    """
    try:
        print("🧠 جاري ترجمة وتلخيص المقالة...")
        response = client.models.generate_content(model=selected_model, contents=prompt)
        text = response.text.strip()
        text = text.replace("**", "").replace("---", "").replace("***", "")
        text = text.replace("<br>", "\n").replace("[رابط]", "").replace("(Link)", "")
        return text.strip()
    except Exception as e:
        print(f"❌ خطأ في جيميناي: {e}")
        return None


# ============================================================
# وظائف النشر (نص بس بدون صورة)
# ============================================================
def clean_text_for_platforms(ai_text):
    hashtags = re.findall(r'#\w+', ai_text)
    clean_text = re.sub(r'#\w+', '', ai_text).strip()
    return clean_text, " ".join(hashtags)

def split_text_at_word(text, limit):
    """يقطع النص عند آخر كلمة كاملة قبل الحد"""
    if len(text) <= limit:
        return text, None
    cut = text[:limit]
    last_space = cut.rfind(" ")
    if last_space == -1:
        return cut, text[limit:]
    return text[:last_space], text[last_space:].strip()

def send_to_telegram(ai_text, link):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        return False
    hashtags = re.findall(r'#\w+', ai_text)
    text_without_hashtags = re.sub(r'#\w+', '', ai_text).strip()
    all_hashtags = " ".join(hashtags)
    final_text = f"{text_without_hashtags}\n\n{all_hashtags}"
    try:
        print("🚀 جاري النشر على تليجرام...")
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHANNEL_ID, "text": final_text}
        res = requests.post(url, data=payload)
        if res.status_code == 200:
            print("✅ تليجرام!")
            return True
        print(f"❌ تليجرام: {res.text}")
        return False
    except Exception as e:
        print(f"❌ خطأ تليجرام: {e}")
        return False

def send_to_facebook(ai_text, link):
    if not META_ACCESS_TOKEN or not FB_PAGE_ID:
        return False
    clean_text, all_hashtags = clean_text_for_platforms(ai_text)
    fb_caption = f"{clean_text}\n\n{all_hashtags}"
    try:
        print("\n🔵 جاري النشر على فيسبوك...")
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
        payload = {"message": fb_caption, "access_token": META_ACCESS_TOKEN}
        res = requests.post(url, data=payload).json()
        if "id" in res:
            print("✅ فيسبوك!")
            return True
        print(f"❌ فيسبوك: {res}")
        return False
    except Exception as e:
        print(f"❌ خطأ فيسبوك: {e}")
        return False

def send_to_threads(ai_text, link):
    if not THREADS_ACCESS_TOKEN or not THREADS_ACCOUNT_ID:
        return False
    clean_text, all_hashtags = clean_text_for_platforms(ai_text)
    threads_text = f"{clean_text}\n\n{all_hashtags}"

    try:
        print("\n🧵 جاري النشر على ثرادز...")
        url = f"https://graph.threads.net/v1.0/{THREADS_ACCOUNT_ID}/threads"
        pub_url = f"https://graph.threads.net/v1.0/{THREADS_ACCOUNT_ID}/threads_publish"

        # تقسيم النص لأجزاء غير محدودة
        parts = []
        remaining = threads_text
        while remaining:
            part, remaining = split_text_at_word(remaining, 495)
            parts.append(part)
            if not remaining:
                break

        # نشر الجزء الأول
        payload = {"media_type": "TEXT", "text": parts[0], "access_token": THREADS_ACCESS_TOKEN}
        res = requests.post(url, data=payload).json()
        if "id" not in res:
            print(f"❌ ثرادز: {res}")
            return False

        time.sleep(15)
        pub_res = requests.post(pub_url, data={"creation_id": res["id"], "access_token": THREADS_ACCESS_TOKEN}).json()
        if "id" not in pub_res:
            print(f"❌ ثرادز: {pub_res}")
            return False

        last_thread_id = pub_res["id"]
        print("✅ ثرادز!")

        # نشر باقي الأجزاء كردود
        for i, part in enumerate(parts[1:], start=2):
            time.sleep(100)
            rep_payload = {"media_type": "TEXT", "text": part, "reply_to_id": last_thread_id, "access_token": THREADS_ACCESS_TOKEN}
            rep_create = requests.post(url, data=rep_payload).json()
            if "id" not in rep_create:
                print(f"⚠️ فشل الجزء {i}: {rep_create}")
                continue
            time.sleep(100)
            rep_pub = requests.post(pub_url, data={"creation_id": rep_create["id"], "access_token": THREADS_ACCESS_TOKEN}).json()
            if "id" in rep_pub:
                last_thread_id = rep_pub["id"]
                print(f"📝 الجزء {i} على ثرادز!")
            else:
                print(f"⚠️ فشل نشر الجزء {i}: {rep_pub}")

        return True

    except Exception as e:
        print(f"❌ خطأ ثرادز: {e}")
        return False

def send_to_bluesky(ai_text, link):
    if not BSKY_HANDLE or not BSKY_APP_PASSWORD:
        return False

    clean_text, all_hashtags = clean_text_for_platforms(ai_text)
    post_text = f"{clean_text}\n\n{all_hashtags}"

    def find_facets(text):
        facets = []
        for match in re.finditer(r'#\w+', text):
            start = len(text[:match.start()].encode("utf-8"))
            end = len(text[:match.end()].encode("utf-8"))
            facets.append({
                "index": {"byteStart": start, "byteEnd": end},
                "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": match.group()[1:]}]
            })
        for match in re.finditer(r'https?://[^\s]+', text):
            start = len(text[:match.start()].encode("utf-8"))
            end = len(text[:match.end()].encode("utf-8"))
            facets.append({
                "index": {"byteStart": start, "byteEnd": end},
                "features": [{"$type": "app.bsky.richtext.facet#link", "uri": match.group()}]
            })
        return facets

    try:
        print("\n🦋 جاري النشر على Bluesky...")
        session_res = requests.post(
            "https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier": BSKY_HANDLE, "password": BSKY_APP_PASSWORD}
        ).json()
        if "accessJwt" not in session_res:
            print(f"❌ فشل تسجيل الدخول Bluesky: {session_res}")
            return False

        access_token = session_res["accessJwt"]
        did = session_res["did"]
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        # تقسيم النص لأجزاء غير محدودة
        parts = []
        remaining = post_text
        while remaining:
            part, remaining = split_text_at_word(remaining, 300)
            parts.append(part)
            if not remaining:
                break

        # نشر الجزء الأول
        first_payload = {
            "repo": did,
            "collection": "app.bsky.feed.post",
            "record": {
                "$type": "app.bsky.feed.post",
                "text": parts[0],
                "facets": find_facets(parts[0]),
                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        }
        post_res = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            headers=headers,
            json=first_payload
        ).json()

        if "uri" not in post_res:
            print(f"❌ Bluesky: {post_res}")
            return False

        root_uri = post_res["uri"]
        root_cid = post_res["cid"]
        last_uri = root_uri
        last_cid = root_cid
        print("✅ Bluesky!")

        # نشر باقي الأجزاء كردود
        for i, part in enumerate(parts[1:], start=2):
            time.sleep(10)
            part_payload = {
                "repo": did,
                "collection": "app.bsky.feed.post",
                "record": {
                    "$type": "app.bsky.feed.post",
                    "text": part,
                    "facets": find_facets(part),
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "reply": {
                        "root": {"uri": root_uri, "cid": root_cid},
                        "parent": {"uri": last_uri, "cid": last_cid}
                    }
                }
            }
            part_res = requests.post(
                "https://bsky.social/xrpc/com.atproto.repo.createRecord",
                headers=headers,
                json=part_payload
            ).json()
            if "uri" in part_res:
                last_uri = part_res["uri"]
                last_cid = part_res["cid"]
                print(f"📝 الجزء {i} على Bluesky!")
            else:
                print(f"⚠️ فشل الجزء {i}: {part_res}")
                break

        return True

    except Exception as e:
        print(f"❌ خطأ Bluesky: {e}")
        return False

# ============================================================
# وظيفة إعادة المحاولة
# ============================================================
def run_with_retry(platform_func, *args):
    platform_name = platform_func.__name__.replace("send_to_", "").capitalize()
    for attempt in range(1, 3):
        success = platform_func(*args)
        if success:
            return True
        if attempt == 1:
            print(f"⚠️ فشلت المحاولة الأولى لـ {platform_name}، ننتظر 15 ثانية...")
            time.sleep(15)
        else:
            print(f"❌ فشلت المحاولة الثانية لـ {platform_name}.")
    return False

# ============================================================
# الوظيفة الرئيسية
# ============================================================
def process_tech_news():
    published_data = get_published_data()
    published_titles = [info.get("title", "") for info in published_data.values() if info.get("title")]

    new_articles = get_new_articles(published_data)

    if not new_articles:
        print("🎉 لا توجد مقالات جديدة.")
        return

    print(f"📰 تم العثور على {len(new_articles)} مقالة جديدة.")

    # نأخذ أول مقالة جديدة بس في كل تشغيل
    article = new_articles[0]
    link = article["link"]
    title = article["title"]
    source = article["source"]

    print(f"\n📌 المقالة: {title}")
    print(f"🌐 المصدر: {source}")

    # فحص التكرار
    if is_duplicate(title, published_titles):
        print(f"⚠️ موضوع مكرر — تم التخطي وحفظه في الذاكرة.")
        published_data[link] = {"title": title, "platforms": {"telegram", "facebook", "instagram", "threads", "bluesky"}}
        save_published_data(published_data)
        return

    # سحب نص المقالة
    article_text = fetch_article_text(link)
    if not article_text:
        print("❌ فشل سحب المقالة.")
        return

    # توليد المحتوى العربي
    ai_content = generate_arabic_post(title, article_text)
    if not ai_content:
        return

    # النشر
    ALL_PLATFORMS = {"telegram", "facebook", "threads", "bluesky"}
    # ملاحظة: إنستجرام مش في القائمة لأنه يحتاج صورة

    if link not in published_data:
        published_data[link] = {"title": title, "platforms": set()}
    
    missing_platforms = ALL_PLATFORMS - published_data[link]["platforms"]
    results = {}

    if "telegram" in missing_platforms:
        results["telegram"] = run_with_retry(send_to_telegram, ai_content, link)

    if "facebook" in missing_platforms:
        results["facebook"] = run_with_retry(send_to_facebook, ai_content, link)

    if "threads" in missing_platforms:
        results["threads"] = run_with_retry(send_to_threads, ai_content, link)

    if "bluesky" in missing_platforms:
        results["bluesky"] = run_with_retry(send_to_bluesky, ai_content, link)

    for platform, success in results.items():
        if success:
            published_data[link]["platforms"].add(platform)

    save_published_data(published_data)
    print(f"\n✅ تم الحفظ! المنصات: {published_data[link]['platforms']}")


if __name__ == "__main__":
    process_tech_news()
