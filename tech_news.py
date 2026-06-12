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
            if "|" in line:
                link, platforms = line.split("|", 1)
                data[link.strip()] = set(p.strip() for p in platforms.split(","))
            else:
                data[line.strip()] = set()
    return data

def save_published_data(data):
    with open(HISTORY_FILE, "w") as f:
        for link, platforms in data.items():
            platforms_str = ",".join(sorted(platforms))
            f.write(f"{link} | {platforms_str}\n")


# ============================================================
# سحب المقالات من RSS
# ============================================================
def get_new_articles(published_data):
    new_articles = []
    for source in RSS_SOURCES:
        feed = feedparser.parse(source["url"])
        for entry in feed.entries[:20]:
            link = entry.link
            if link not in published_data:
                new_articles.append({
                    "link": link,
                    "title": entry.title,
                    "source": source["name"],
                    "summary": entry.get("summary", "")
                })
    return new_articles


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
    عندك مقالة جديدة عنوانها: "{new_title}"
    وعندك قائمة مقالات تم نشرها مسبقاً:
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
    أنت مترجم ومحرر محتوى عربي محترف متخصص في التكنولوجيا والذكاء الاصطناعي.
    
    مهمتك:
    1. اقرأ المقالة الإنجليزية التالية وافهمها جيداً
    2. اكتب ملخصاً عربياً بأسلوب بشري طبيعي 100% بالعربية الفصحى البيضاء
    3. الملخص يكون منشور جذاب لوسائل التواصل الاجتماعي
    
    عنوان المقالة: "{title}"
    
    نص المقالة:
    {article_text[:5000]}
    
    شروط صارمة:
    1. اكتب بأسلوب بشري طبيعي مش روبوتي
    2. لا تتجاوز 250 حرفاً في المنشور كله بما فيه الهاشتاجات
    3. ابدأ بجملة تشد الانتباه مباشرة
    4. اختم بـ Call to Action + 👇
    5. في السطر الأخير اكتب 4 هاشتاجات عربية وإنجليزية متعلقة بالموضوع
    6. لا تكتب [رابط] أو (Link) أو أي إشارة للرابط
    7. لا تستخدم --- أو *** أو ** أو HTML
    8. لا تكتب أي مقدمات، أعطني المنشور النهائي مباشرة
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

def send_to_telegram(ai_text, link):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        return False
    hashtags = re.findall(r'#\w+', ai_text)
    text_without_hashtags = re.sub(r'#\w+', '', ai_text).strip()
    all_hashtags = " ".join(hashtags)
    final_text = f"{text_without_hashtags}\n\n🔗 المصدر:\n{link}\n\n{all_hashtags}"
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
            post_id = res["id"]
            print("✅ فيسبوك!")
            wait = random.randint(30, 60)
            print(f"⏱️ ننتظر {wait} ثانية...")
            time.sleep(wait)
            comment_url = f"https://graph.facebook.com/v19.0/{post_id}/comments"
            requests.post(comment_url, data={"message": f"🔗 المصدر:\n{link}", "access_token": META_ACCESS_TOKEN})
            print("💬 تعليق فيسبوك!")
            return True
        print(f"❌ فيسبوك: {res}")
        return False
    except Exception as e:
        print(f"❌ خطأ فيسبوك: {e}")
        return False

def send_to_instagram(ai_text, link):
    if not META_ACCESS_TOKEN or not IG_ACCOUNT_ID:
        return False
    clean_text, all_hashtags = clean_text_for_platforms(ai_text)
    ig_caption = f"{clean_text}\n\n{all_hashtags}"
    try:
        print("\n🟣 جاري النشر على إنستجرام...")
        # إنستجرام محتاج صورة للنشر العادي - هنستخدم carousel بصورة واحدة بيضاء
        # أوننشر كـ caption only عن طريق reels - الأبسط نتخطاه لو مفيش صورة
        print("⚠️ إنستجرام يحتاج صورة - تم التخطي للمقالات بدون صورة.")
        return False
    except Exception as e:
        print(f"❌ خطأ إنستجرام: {e}")
        return False

def send_to_threads(ai_text, link):
    if not THREADS_ACCESS_TOKEN or not THREADS_ACCOUNT_ID:
        return False
    clean_text, all_hashtags = clean_text_for_platforms(ai_text)
    threads_text = f"{clean_text}\n\n{all_hashtags}"
    try:
        print("\n🧵 جاري النشر على ثرادز...")
        url = f"https://graph.threads.net/v1.0/{THREADS_ACCOUNT_ID}/threads"
        payload = {"media_type": "TEXT", "text": threads_text[:500], "access_token": THREADS_ACCESS_TOKEN}
        res = requests.post(url, data=payload).json()
        if "id" in res:
            creation_id = res["id"]
            time.sleep(5)
            pub_url = f"https://graph.threads.net/v1.0/{THREADS_ACCOUNT_ID}/threads_publish"
            pub_res = requests.post(pub_url, data={"creation_id": creation_id, "access_token": THREADS_ACCESS_TOKEN}).json()
            if "id" in pub_res:
                thread_id = pub_res["id"]
                print("✅ ثرادز!")
                wait = random.randint(90, 120)
                print(f"⏱️ ننتظر {wait} ثانية للرد...")
                time.sleep(wait)
                rep_payload = {"media_type": "TEXT", "text": f"🔗 المصدر:\n{link}", "reply_to_id": thread_id, "access_token": THREADS_ACCESS_TOKEN}
                rep_create = requests.post(url, data=rep_payload).json()
                if "id" in rep_create:
                    requests.post(pub_url, data={"creation_id": rep_create["id"], "access_token": THREADS_ACCESS_TOKEN})
                    print("💬 رد ثرادز!")
                return True
        print(f"❌ ثرادز: {res}")
        return False
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

        post_text_limited = post_text[:300]
        post_payload = {
            "repo": did,
            "collection": "app.bsky.feed.post",
            "record": {
                "$type": "app.bsky.feed.post",
                "text": post_text_limited,
                "facets": find_facets(post_text_limited),
                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        }
        post_res = requests.post("https://bsky.social/xrpc/com.atproto.repo.createRecord", headers=headers, json=post_payload).json()
        if "uri" in post_res:
            post_uri = post_res["uri"]
            post_cid = post_res["cid"]
            print("✅ Bluesky!")
            wait = random.randint(30, 60)
            time.sleep(wait)
            reply_text = f"🔗 المصدر:\n{link}"
            reply_payload = {
                "repo": did,
                "collection": "app.bsky.feed.post",
                "record": {
                    "$type": "app.bsky.feed.post",
                    "text": reply_text,
                    "facets": find_facets(reply_text),
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "reply": {"root": {"uri": post_uri, "cid": post_cid}, "parent": {"uri": post_uri, "cid": post_cid}}
                }
            }
            reply_res = requests.post("https://bsky.social/xrpc/com.atproto.repo.createRecord", headers=headers, json=reply_payload).json()
            if "uri" in reply_res:
                print("💬 رد Bluesky!")
            return True
        print(f"❌ Bluesky: {post_res}")
        return False
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
    published_titles = [link.split("/")[-1].replace("-", " ").replace(".html", "") for link in published_data.keys()]

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
        published_data[link] = {"telegram", "facebook", "instagram", "threads", "bluesky"}
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
        published_data[link] = set()

    missing_platforms = ALL_PLATFORMS - published_data[link]
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
            published_data[link].add(platform)

    save_published_data(published_data)
    print(f"\n✅ تم الحفظ! المنصات: {published_data[link]}")


if __name__ == "__main__":
    process_tech_news()
