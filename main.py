import feedparser
import os
import random
import json
import requests
import time
import re
import base64
from bs4 import BeautifulSoup
from google import genai
from nacl import encoding, public
import tweepy

BLOG_RSS_URL = "https://t8ngy.blogspot.com/feeds/posts/default?alt=rss&max-results=500"
HISTORY_FILE = "published.txt"

# --- جلب الأسرار ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
IG_ACCOUNT_ID = os.environ.get("IG_ACCOUNT_ID")
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
THREADS_ACCOUNT_ID = os.environ.get("THREADS_ACCOUNT_ID")
X_API_KEY = os.environ.get("X_API_KEY")
X_API_SECRET = os.environ.get("X_API_SECRET")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.environ.get("X_ACCESS_SECRET")
PINTEREST_ACCESS_TOKEN = os.environ.get("PINTEREST_ACCESS_TOKEN")
PINTEREST_BOARD_ID = os.environ.get("PINTEREST_BOARD_ID")
BSKY_HANDLE = os.environ.get("BSKY_HANDLE")
BSKY_APP_PASSWORD = os.environ.get("BSKY_APP_PASSWORD")

# --- GitHub Secrets (لتحديث توكن ثرادز تلقائياً) ---
# أضف هذين في GitHub Secrets:
# GITHUB_PAT  = Personal Access Token بصلاحية "secrets" (اعمله من Settings > Developer settings > Personal access tokens)
# GITHUB_REPO = اسم الريبو مثل "username/repo-name"
GITHUB_PAT  = os.environ.get("GH_PAT")   # ملاحظة: لا تسميه GITHUB_TOKEN لأنه محجوز
GITHUB_REPO = os.environ.get("GH_REPO")

# --- 1. جلب مفاتيح جيميناي ---
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
    print("❌ خطأ: لم يتم العثور على أي مفاتيح تبدأ بـ GEMINI_API_KEY_ في الـ Secrets!")
    exit()

# اختيار مفتاح عشوائي من القائمة التي تم تجميعها
selected_api_key = random.choice(api_keys_list).strip()

# 2. قائمة النماذج المجانية السريعة واختيار واحد عشوائياً
models_list = ['gemma-4-31b-it', 'gemma-4-26b-a4b-it']
selected_model = random.choice(models_list)

print(f"🔑 تم العثور على ({len(api_keys_list)}) مفاتيح API.")
print(f"🔄 تم اختيار API Key عشوائي.")
print(f"🤖 النموذج المستخدم في هذه العملية: {selected_model}")

# تهيئة جيميناي بالمفتاح المختار
client = genai.Client(api_key=selected_api_key)


# ============================================================
# 🔐 وظيفة تحديث GitHub Secret تلقائياً
# ============================================================
def update_github_secret(secret_name, secret_value):
    """تحدث قيمة Secret في GitHub Actions تلقائياً باستخدام التشفير الصحيح"""
    if not GITHUB_PAT or not GITHUB_REPO:
        print("⚠️ GH_PAT أو GITHUB_REPO غير موجودَين في الـ Secrets، لن يتم حفظ التوكن الجديد.")
        return False

    headers = {
        "Authorization": f"Bearer {GITHUB_PAT}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    # 1. جلب الـ Public Key الخاص بالريبو (مطلوب للتشفير)
    key_url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/public-key"
    key_res = requests.get(key_url, headers=headers)

    if key_res.status_code != 200:
        print(f"⚠️ فشل جلب GitHub Public Key: {key_res.text}")
        return False

    key_data = key_res.json()
    public_key = key_data["key"]
    key_id = key_data["key_id"]

    # 2. تشفير القيمة باستخدام PyNaCl (الطريقة الرسمية التي يطلبها GitHub)
    pk = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder)
    sealed_box = public.SealedBox(pk)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    encrypted_value = base64.b64encode(encrypted).decode("utf-8")

    # 3. رفع القيمة المشفرة
    update_url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/{secret_name}"
    payload = {"encrypted_value": encrypted_value, "key_id": key_id}
    update_res = requests.put(update_url, headers=headers, json=payload)

    if update_res.status_code in [201, 204]:
        print(f"✅ تم تحديث {secret_name} في GitHub Secrets بنجاح!")
        return True
    else:
        print(f"⚠️ فشل تحديث {secret_name}: {update_res.text}")
        return False


# ============================================================
# 🔄 وظيفة تجديد توكن ثرادز (Long-Lived Token - 60 يوم)
# ============================================================
def refresh_threads_token():
    """تجدد الـ Long-Lived Token وتحفظه في GitHub Secrets تلقائياً"""
    global THREADS_ACCESS_TOKEN

    if not THREADS_ACCESS_TOKEN:
        print("⚠️ THREADS_ACCESS_TOKEN غير موجود.")
        return

    print("\n🔄 جاري تجديد توكن ثرادز...")
    refresh_url = (
        f"https://graph.threads.net/refresh_access_token"
        f"?grant_type=th_refresh_token"
        f"&access_token={THREADS_ACCESS_TOKEN}"
    )

    try:
        res = requests.get(refresh_url)
        data = res.json()

        if "access_token" in data:
            new_token = data["access_token"]
            expires_in_days = data.get("expires_in", 0) // 86400

            # تحديث المتغير في الذاكرة للاستخدام الفوري
            THREADS_ACCESS_TOKEN = new_token

            print(f"✅ تم تجديد توكن ثرادز! (صالح لـ {expires_in_days} يوماً)")

            # حفظ التوكن الجديد في GitHub Secrets تلقائياً
            update_github_secret("THREADS_ACCESS_TOKEN", new_token)
        else:
            print(f"⚠️ لم يتم تجديد التوكن: {data}")

    except Exception as e:
        print(f"⚠️ خطأ أثناء تجديد توكن ثرادز: {e}")


# ============================================================
# وظائف الذاكرة وجلب المقالات
# ============================================================
def get_published_links():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r") as file:
        return [line.strip() for line in file.readlines()]

def save_published_link(link):
    with open(HISTORY_FILE, "a") as file:
        file.write(link + "\n")

def get_all_posts():
    all_entries = []
    current_url = BLOG_RSS_URL
    while current_url:
        feed = feedparser.parse(current_url)
        all_entries.extend(feed.entries)
        next_link = None
        if 'links' in feed.feed:
            for link in feed.feed.links:
                if link.rel == 'next':
                    next_link = link.href
                    break
        current_url = next_link
    return all_entries

# --- الوظيفة الجديدة: استخراج عناوين H2 و H3 من داخل المقالة ---
def extract_headings(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    headings = []
    for tag in soup.find_all(['h2', 'h3']):
        text = tag.get_text(strip=True)
        if text:
            headings.append(text)
    return headings

# --- الوظيفة الجديدة: استخراج الصورة من المقالة ---
def extract_image_url(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    img_tag = soup.find('img') # يبحث عن أول صورة في المقالة
    if img_tag and 'src' in img_tag.attrs:
        return img_tag['src']
    return None


# ============================================================
# وظيفة توليد المحتوى بجيميناي
# ============================================================
def generate_social_media_post(title, category, headings):
    headings_text = "\n- ".join(headings) if headings else "لا توجد عناوين فرعية، اعتمد على العنوان الرئيسي فقط."

    prompt = f"""
    أنت لست مجرد ذكاء اصطناعي، أنت "Copywriter" تكتب باللغة العربية البيضاء وخبير وداهية في التسويق النفسي وعلم الأعصاب.
    مهمتك كتابة "Hook" (خطاف) يخطف انتباه القارئ من أول ثانية لمقالة جديدة، ويجعله يشعر بفضول قاتل لدرجة أنه لا يستطيع التوقف عن التفكير في الموضوع.

    معلومات المقالة (اقرأها للتحليل والفهم فقط، إياك أن تنسخها أو تسردها):
    - العنوان: "{title}"
    - القسم: "{category}"
    - النقاط المذكورة (للفهم فقط):
    {headings_text}
    
    شروط الكتابة الصارمة:
    1. ⚠️ طول النص: يجب ألا يتجاوز المنشور بأكمله (بما فيه الهاشتاجات) 270 حرفاً كحد أقصى! كن مختصراً، ذكياً، سلساً، ومكثفاً.
    2. إياك أن تنسخ العناوين الفرعية كما هي، حللها وافهم "نية البحث" (Search Intent) والحلول التي تقدمها المقالة، ثم صُغ منها فكرة تسويقية واحدة قوية.
    3. استخدم أسلوباً يخاطب اللاوعي (مثل إثارة الفضول، الخوف من تفويت الفرصة FOMO، أو تحقيق حلم وطموح).
    4. لا تستخدم أكواد HTML أبداً مثل <br>. للنزول لسطر جديد، استخدم النزول العادي (Enter).
    5. لا تستخدم أي فواصل مثل --- أو ***.
    6. استخدم إيموجي (1 إلى 5 كحد أقصى) لتزيين النص دون إزعاج العين.
    7. 💡 الشرط الأهم (الحافز): في نهاية النص التسويقي، اكتب جملة تحفيزية ذكية جداً (Call to Action) تدفع القارئ للبحث عن التفاصيل، واختمها بإيموجي يشير للأسفل (👇).
    8. لا تكتب مطلقاً كلمات مثل [رابط] أو (Link) أو "اضغط على الرابط" أو "اقرأ المقالة" أو "[رابط المقالة]" أو "إليك الرابط" ولا تضع أقواساً، فقط الجملة التحفيزية والسهم 👇.
    9. في نهاية النص، انزل سطرين واكتب 4 هاشتاجات (#) شائعة وقوية متعلقة بالموضوع.
    10. لا تضف هاشتاج القسم "{category}"، أنا سأضيفه بنفسي.
    11. لا تكتب أي مقدمات، أعطني المنشور النهائي جاهزاً.
    """

    try:
        print("🧠 جاري كتابة محتوى تسويقي احترافي وقصير ...")
        response = client.models.generate_content(
            model=selected_model,
            contents=prompt,
        )

        # استلام النص من جيميناي
        raw_text = response.text.strip()

        # --- تنظيف النص باحترافية ---
        clean_text = raw_text.replace("**", "")
        clean_text = clean_text.replace("!", "")
        clean_text = clean_text.replace("！", "")
        clean_text = clean_text.replace("<br>", "\n")
        clean_text = clean_text.replace("<br/>", "\n")
        clean_text = clean_text.replace("</br>", "")
        clean_text = clean_text.replace("---", "")
        clean_text = clean_text.replace("***", "")
        clean_text = clean_text.replace("[رابط المقالة]", "")
        clean_text = clean_text.replace("[الرابط]", "")

        return clean_text.strip()

    except Exception as e:
        print(f"❌ حدث خطأ أثناء الاتصال بـ Gemini: {e}")
        return None


# ============================================================
# وظائف النشر
# ============================================================
def clean_text_for_platforms(ai_text, main_hashtag):
    hashtags = re.findall(r'#\w+', ai_text)
    clean_text = re.sub(r'#\w+', '', ai_text).strip()
    return clean_text, f"{main_hashtag} " + " ".join(hashtags)


def send_to_telegram(image_url, ai_text, link, main_hashtag):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("❌ بيانات تليجرام غير مكتملة في الـ Secrets.")
        return False

    # 1. استخراج الهاشتاجات التي كتبها جيميناي من النص
    ai_hashtags = re.findall(r'#\w+', ai_text)

    # 2. مسح هذه الهاشتاجات من النص ليكون النص صافياً تماماً
    text_without_hashtags = re.sub(r'#\w+', '', ai_text).strip()

    # 3. الترتيب لتليجرام: النص الصافي -> الرابط -> هاشتاج القسم فقط!
    final_caption = f"{text_without_hashtags}\n\n🔗 الرابط:\n{link}\n\n{main_hashtag}"

    try:
        print("🚀 جاري النشر على تليجرام...")
        if image_url:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            payload = {"chat_id": TELEGRAM_CHANNEL_ID, "photo": image_url, "caption": final_caption}
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHANNEL_ID, "text": final_caption, "disable_web_page_preview": False}

        response = requests.post(url, data=payload)

        if response.status_code == 200:
            print("✅ تم النشر على تليجرام بنجاح!")
            return True
        else:
            print(f"❌ فشل النشر على تليجرام: {response.text}")
            return False

    except Exception as e:
        print(f"❌ خطأ برمجي أثناء التواصل مع تليجرام: {e}")
        return False


def send_to_facebook(image_url, ai_text, link, main_hashtag):
    if not META_ACCESS_TOKEN or not FB_PAGE_ID:
        return False

    ai_hashtags = re.findall(r'#\w+', ai_text)
    text_without_hashtags = re.sub(r'#\w+', '', ai_text).strip()
    all_hashtags = f"{main_hashtag} " + " ".join(ai_hashtags)
    fb_caption = f"{text_without_hashtags}\n\n{all_hashtags}"

    try:
        print("\n🔵 جاري النشر على فيسبوك...")
        if image_url:
            url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
            payload = {"url": image_url, "message": fb_caption, "access_token": META_ACCESS_TOKEN}
            response = requests.post(url, data=payload).json()

            if "id" in response:
                post_id = response.get("post_id", response.get("id"))
                print("✅ تم نشر المنشور على فيسبوك بنجاح!")

                wait_time = random.randint(30, 60)
                print(f"⏱️ ننتظر {wait_time} ثانية للهروب من الخوارزميات...")
                time.sleep(wait_time)

                comment_url = f"https://graph.facebook.com/v19.0/{post_id}/comments"
                comment_payload = {"message": f"🔗 الموضوع:\n{link}", "access_token": META_ACCESS_TOKEN}
                comment_response = requests.post(comment_url, data=comment_payload)

                if comment_response.status_code == 200:
                    print("💬 تم وضع الرابط في تعليق فيسبوك بنجاح!")
                else:
                    print(f"⚠️ فشل إضافة تعليق فيسبوك: {comment_response.text}")
                return True
            else:
                print(f"❌ فشل النشر على فيسبوك: {response}")
                return False
    except Exception as e:
        print(f"❌ خطأ في فيسبوك: {e}")
        return False


def send_to_instagram(image_url, ai_text, link, main_hashtag):
    if not META_ACCESS_TOKEN or not IG_ACCOUNT_ID:
        return False

    if not image_url:
        print("⚠️ إنستجرام يرفض النشر بدون صورة. تم التخطي.")
        return False

    ai_hashtags = re.findall(r'#\w+', ai_text)
    text_without_hashtags = re.sub(r'#\w+', '', ai_text).strip()
    all_hashtags = f"{main_hashtag} " + " ".join(ai_hashtags)
    ig_caption = f"{text_without_hashtags}\n\n{all_hashtags}"

    try:
        print("\n🟣 جاري النشر على إنستجرام...")
        create_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media"
        create_payload = {"image_url": image_url, "caption": ig_caption, "access_token": META_ACCESS_TOKEN}
        create_response = requests.post(create_url, data=create_payload).json()

        if "id" in create_response:
            creation_id = create_response["id"]
            print("⏳ ننتظر 15 ثانية حتى يقوم إنستجرام بمعالجة الصورة في سيرفراته...")
            time.sleep(15)

            publish_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media_publish"
            publish_payload = {"creation_id": creation_id, "access_token": META_ACCESS_TOKEN}
            publish_response = requests.post(publish_url, data=publish_payload).json()

            if "id" in publish_response:
                ig_media_id = publish_response["id"]
                print("✅ تم نشر المنشور على إنستجرام بنجاح!")

                wait_time = random.randint(30, 60)
                print(f"⏱️ ننتظر {wait_time} ثانية لوضع التعليق في إنستجرام...")
                time.sleep(wait_time)

                comment_url = f"https://graph.facebook.com/v19.0/{ig_media_id}/comments"
                comment_payload = {"message": f"🔗 انسخ الرابط:\n{link}", "access_token": META_ACCESS_TOKEN}
                comment_response = requests.post(comment_url, data=comment_payload)

                if comment_response.status_code == 200:
                    print("💬 تم وضع التعليق في إنستجرام بنجاح!")
                else:
                    print(f"⚠️ فشل إضافة تعليق إنستجرام: {comment_response.text}")
                return True
            else:
                print(f"❌ فشل النشر النهائي على إنستجرام: {publish_response}")
                return False
        else:
            print(f"❌ فشل رفع الصورة على إنستجرام: {create_response}")
            return False
    except Exception as e:
        print(f"❌ خطأ في إنستجرام: {e}")
        return False


def send_to_threads(image_url, ai_text, link, main_hashtag):
    if not THREADS_ACCESS_TOKEN or not THREADS_ACCOUNT_ID:
        return False
    if not image_url:
        print("⚠️ ثرادز يحتاج صورة. تم التخطي.")
        return False

    # تنظيف النص وأخذ النص الصافي فقط بدون هاشتاجات نهائياً لثرادز
    clean_text, _ = clean_text_for_platforms(ai_text, main_hashtag)
    threads_caption = clean_text

    try:
        print("\n🧵 جاري النشر على ثرادز...")
        url = f"https://graph.threads.net/v1.0/{THREADS_ACCOUNT_ID}/threads"
        payload = {
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": threads_caption,
            "access_token": THREADS_ACCESS_TOKEN
        }
        res = requests.post(url, data=payload).json()
        print(f"📋 رد ثرادز (رفع الصورة): {res}")

        if "id" in res:
            creation_id = res["id"]
            print("⏳ ننتظر 15 ثانية لمعالجة الصورة في ثرادز...")
            time.sleep(15)

            pub_url = f"https://graph.threads.net/v1.0/{THREADS_ACCOUNT_ID}/threads_publish"
            pub_res = requests.post(pub_url, data={"creation_id": creation_id, "access_token": THREADS_ACCESS_TOKEN}).json()
            print(f"📋 رد ثرادز (النشر): {pub_res}")

            if "id" in pub_res:
                thread_id = pub_res["id"]
                print("✅ تم النشر على ثرادز!")

                wait = random.randint(30, 60)
                print(f"⏱️ ننتظر {wait} ثانية للرد...")
                time.sleep(wait)

                rep_url = f"https://graph.threads.net/v1.0/{THREADS_ACCOUNT_ID}/threads"
                rep_payload = {
                    "media_type": "TEXT",
                    "text": f"🔗 الموضوع كامل:\n{link}",
                    "reply_to_id": thread_id,
                    "access_token": THREADS_ACCESS_TOKEN
                }
                rep_create = requests.post(rep_url, data=rep_payload).json()

                if "id" in rep_create:
                    final_pub = requests.post(pub_url, data={"creation_id": rep_create["id"], "access_token": THREADS_ACCESS_TOKEN}).json()
                    print(f"💬 رد ثرادز (التعليق): {final_pub}")
                    print("💬 تم وضع الرابط في رد ثرادز!")
                else:
                    print(f"⚠️ فشل إنشاء الرد في ثرادز: {rep_create}")
                return True
            else:
                print(f"❌ فشل النشر النهائي على ثرادز: {pub_res}")
                return False
        else:
            print(f"❌ فشل رفع الصورة على ثرادز: {res}")
            return False
    except Exception as e:
        print(f"❌ خطأ ثرادز: {e}")
        return False


def send_to_twitter(image_url, ai_text, link, main_hashtag):
    if not X_API_KEY:
        return False

    clean_text, all_hashtags = clean_text_for_platforms(ai_text, main_hashtag)
    x_caption = f"{clean_text}\n\n{all_hashtags}"

    print("\n🐦 جاري النشر على X (تويتر)...")
    auth = tweepy.OAuth1UserHandler(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)
    api = tweepy.API(auth)
    client_x = tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_SECRET
    )

    tweet = None

    if image_url:
        for attempt in range(1, 3):
            try:
                img_data = requests.get(image_url).content
                with open("temp.jpg", "wb") as f:
                    f.write(img_data)
                media = api.media_upload("temp.jpg")
                tweet = client_x.create_tweet(text=x_caption[:250], media_ids=[media.media_id])
                os.remove("temp.jpg")
                print("✅ تم النشر على تويتر مع الصورة بنجاح!")
                break
            except Exception as img_err:
                print(f"⚠️ فشلت محاولة الصورة رقم {attempt} في تويتر. الخطأ: {img_err}")
                if os.path.exists("temp.jpg"):
                    os.remove("temp.jpg")
                if attempt == 1:
                    time.sleep(10)

    if not tweet:
        print("🔄 تويتر رفض الصورة نهائياً، ننتقل لمحاولة النشر بالنص فقط...")
        for attempt in range(1, 3):
            try:
                tweet = client_x.create_tweet(text=x_caption[:250])
                print("✅ تم النشر على تويتر بالنص فقط بنجاح!")
                break
            except Exception as txt_err:
                print(f"❌ فشلت محاولة النص رقم {attempt} في تويتر. الخطأ: {txt_err}")
                if attempt == 1:
                    time.sleep(10)

    if tweet:
        tweet_id = tweet.data['id']
        wait = random.randint(30, 60)
        print(f"⏱️ ننتظر {wait} ثانية لوضع الرابط في تعليق تويتر...")
        time.sleep(wait)
        try:
            client_x.create_tweet(text=f"🔗 الموضوع كامل:\n{link}", in_reply_to_tweet_id=tweet_id)
            print("💬 تم وضع الرابط في رد تويتر بنجاح!")
            return True
        except Exception as reply_err:
            print(f"⚠️ فشل وضع التعليق في تويتر: {reply_err}")
            return True
    else:
        print("❌ فشل النشر على تويتر تماماً (صورة ونص).")
        return False


def send_to_pinterest(image_url, title, ai_text, link, category):
    pinterest_token = os.environ.get("PINTEREST_ACCESS_TOKEN")
    pinterest_board = os.environ.get("PINTEREST_BOARD_ID")

    if not pinterest_token:
        return False
    if not image_url:
        print("⚠️ بينتريست يرفض النشر بدون صورة. تم التخطي.")
        return False

    print("\n📌 جاري النشر على بينتريست...")

    headers = {
        "Authorization": f"Bearer {pinterest_token}",
        "Content-Type": "application/json"
    }

    pin_description = ai_text[:490] + "..." if len(ai_text) > 490 else ai_text
    pin_payload = {
        "title": title[:100],
        "description": pin_description,
        "link": link,
        "media_source": {"source_type": "image_url", "url": image_url}
    }

    success = False

    if pinterest_board:
        pin_payload["board_id"] = pinterest_board
        try:
            print(f"📍 جاري النشر في اللوحة العامة ({pinterest_board})...")
            res = requests.post("https://api.pinterest.com/v5/pins", headers=headers, json=pin_payload).json()
            if "id" in res:
                print("✅ تم النشر في اللوحة العامة لبينتريست بنجاح!")
                success = True
            else:
                print(f"⚠️ فشل النشر في اللوحة العامة: {res}")
        except Exception as e:
            print(f"❌ خطأ أثناء النشر في اللوحة العامة: {e}")

    print(f"🔍 جاري البحث عن لوحة باسم القسم '{category}'...")
    category_board_id = None

    try:
        boards_res = requests.get("https://api.pinterest.com/v5/boards", headers=headers).json()
        if "items" in boards_res:
            for board in boards_res["items"]:
                if board["name"].lower() == category.lower():
                    category_board_id = board["id"]
                    print(f"✅ تم العثور على لوحة القسم موجودة مسبقاً ({category_board_id}).")
                    break

        if not category_board_id:
            print(f"🛠️ جاري إنشاء لوحة جديدة باسم '{category}'...")
            create_board_payload = {"name": category, "description": f"مقالات قسم {category}"}
            create_res = requests.post("https://api.pinterest.com/v5/boards", headers=headers, json=create_board_payload).json()
            if "id" in create_res:
                category_board_id = create_res["id"]
                print(f"✅ تم إنشاء اللوحة الجديدة بنجاح ({category_board_id})!")
            else:
                print(f"⚠️ فشل إنشاء اللوحة الجديدة: {create_res}")

    except Exception as e:
        print(f"❌ خطأ أثناء البحث/إنشاء اللوحة: {e}")

    if category_board_id:
        print(f"⏱️ ننتظر 20 ثانية قبل النشر في لوحة القسم...")
        time.sleep(20)

        pin_payload["board_id"] = category_board_id
        try:
            print(f"📍 جاري النشر في لوحة القسم '{category}'...")
            res2 = requests.post("https://api.pinterest.com/v5/pins", headers=headers, json=pin_payload).json()
            if "id" in res2:
                print(f"✅ تم النشر في لوحة القسم '{category}' بنجاح!")
                success = True
            else:
                print(f"⚠️ فشل النشر في لوحة القسم: {res2}")
        except Exception as e:
            print(f"❌ خطأ أثناء النشر في لوحة القسم: {e}")

    return success

def send_to_bluesky(image_url, ai_text, link, main_hashtag):
    if not BSKY_HANDLE or not BSKY_APP_PASSWORD:
        print("⚠️ بيانات Bluesky غير مكتملة.")
        return False

    clean_text, all_hashtags = clean_text_for_platforms(ai_text, main_hashtag)
    post_text = f"{clean_text}\n\n{all_hashtags}"

    try:
        print("\n🦋 جاري النشر على Bluesky...")

        # 1. تسجيل الدخول وجلب التوكن
        session_res = requests.post(
            "https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier": BSKY_HANDLE, "password": BSKY_APP_PASSWORD}
        ).json()

        if "accessJwt" not in session_res:
            print(f"❌ فشل تسجيل الدخول على Bluesky: {session_res}")
            return False

        access_token = session_res["accessJwt"]
        did = session_res["did"]

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        # 2. رفع الصورة لو موجودة
        image_blob = None
        if image_url:
            try:
                img_data = requests.get(image_url).content
                upload_res = requests.post(
                    "https://bsky.social/xrpc/com.atproto.repo.uploadBlob",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "image/jpeg"
                    },
                    data=img_data
                ).json()
                if "blob" in upload_res:
                    image_blob = upload_res["blob"]
                    print("✅ تم رفع الصورة على Bluesky!")
            except Exception as e:
                print(f"⚠️ فشل رفع الصورة: {e}")

        # 3. إنشاء المنشور
        post_payload = {
            "repo": did,
            "collection": "app.bsky.feed.post",
            "record": {
                "$type": "app.bsky.feed.post",
                "text": post_text[:300],
                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                **({"embed": {
                    "$type": "app.bsky.embed.images",
                    "images": [{"image": image_blob, "alt": ""}]
                }} if image_blob else {})
            }
        }

        post_res = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            headers=headers,
            json=post_payload
        ).json()

        if "uri" in post_res:
            post_uri = post_res["uri"]
            post_cid = post_res["cid"]
            print("✅ تم النشر على Bluesky بنجاح!")

            # 4. وضع الرابط في رد
            wait = random.randint(30, 60)
            print(f"⏱️ ننتظر {wait} ثانية لوضع الرابط في رد...")
            time.sleep(wait)

            reply_payload = {
                "repo": did,
                "collection": "app.bsky.feed.post",
                "record": {
                    "$type": "app.bsky.feed.post",
                    "text": f"🔗 الموضوع كامل:\n{link}",
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "reply": {
                        "root": {"uri": post_uri, "cid": post_cid},
                        "parent": {"uri": post_uri, "cid": post_cid}
                    }
                }
            }

            reply_res = requests.post(
                "https://bsky.social/xrpc/com.atproto.repo.createRecord",
                headers=headers,
                json=reply_payload
            ).json()

            if "uri" in reply_res:
                print("💬 تم وضع الرابط في رد Bluesky!")
            else:
                print(f"⚠️ فشل الرد: {reply_res}")

            return True
        else:
            print(f"❌ فشل النشر على Bluesky: {post_res}")
            return False

    except Exception as e:
        print(f"❌ خطأ في Bluesky: {e}")
        return False

# ============================================================
# وظيفة إعادة المحاولة الذكية
# ============================================================
def run_with_retry(platform_func, *args):
    platform_name = platform_func.__name__.replace("send_to_", "").capitalize()

    for attempt in range(1, 3):
        success = platform_func(*args)
        if success:
            return True
        else:
            if attempt == 1:
                print(f"⚠️ فشلت المحاولة الأولى لـ {platform_name}، ننتظر 15 ثانية ونجرب المحاولة الثانية...")
                time.sleep(15)
            else:
                print(f"❌ فشلت المحاولة الثانية والأخيرة لـ {platform_name}. نتجاوزها.")
    return False


# ============================================================
# الوظيفة الرئيسية
# ============================================================
def process_oldest_unpublished_post():
    # ✅ تجديد توكن ثرادز في بداية كل تشغيل
    refresh_threads_token()

    all_entries = get_all_posts()
    if len(all_entries) == 0:
        print("المدونة فارغة أو هناك خطأ في الرابط.")
        return

    all_posts = list(reversed(all_entries))
    published_links = get_published_links()
    target_post = None

    for post in all_posts:
        if post.link not in published_links:
            target_post = post
            break

    if target_post:
        title = target_post.title
        link = target_post.link
        category = target_post.tags[0].term if 'tags' in target_post else "عام"

        html_content = ""
        if 'content' in target_post:
            html_content = target_post.content[0].value
        elif 'summary' in target_post:
            html_content = target_post.summary

        extracted_headings = extract_headings(html_content)
        image_url = extract_image_url(html_content)

        print("🎯 تم تحديد المقالة:")
        print(f"العنوان: {title}")
        print(f"القسم: {category}")
        print(f"📑 عدد العناوين الفرعية المستخرجة: {len(extracted_headings)}")
        print(f"الصورة المستخرجة: {'نعم' if image_url else 'لا'}")

        ai_content = generate_social_media_post(title, category, extracted_headings)

        if ai_content:
            main_hashtag = f"#{category.replace(' ', '_')}"

            # 1. تليجرام
            run_with_retry(send_to_telegram, image_url, ai_content, link, main_hashtag)

            # 2. فيسبوك
            run_with_retry(send_to_facebook, image_url, ai_content, link, main_hashtag)

            # 3. إنستجرام
            run_with_retry(send_to_instagram, image_url, ai_content, link, main_hashtag)

            # 4. ثرادز
            run_with_retry(send_to_threads, image_url, ai_content, link, main_hashtag)

            # 5. Bluesky
            run_with_retry(send_to_bluesky, image_url, ai_content, link, main_hashtag)

            # 6. تويتر (فعّله لو عندك API)
            # run_with_retry(send_to_twitter, image_url, ai_content, link, main_hashtag)

            # 7. بينتريست (فعّله لو اتقبل الـ app)
            # run_with_retry(send_to_pinterest, image_url, title, ai_content, link, category)

            save_published_link(link)
            print("\n✅ تم الحفظ في الذاكرة بنجاح. المهمة تمت!")

    else:
        print("🎉 لا يوجد مقالات جديدة لنشرها.")


if __name__ == "__main__":
    process_oldest_unpublished_post()
