import feedparser
import os
import random
import json
import requests
import time # ⏱️ مكتبة جديدة للانتظار العشوائي
import re
from bs4 import BeautifulSoup
from google import genai

BLOG_RSS_URL = "https://t8ngy.blogspot.com/feeds/posts/default?alt=rss&max-results=500"
HISTORY_FILE = "published.txt"

# --- جلب الأسرار ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
IG_ACCOUNT_ID = os.environ.get("IG_ACCOUNT_ID")

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

# التأكد من العثور على مفاتيح
if not api_keys_list:
    print("❌ خطأ: لم يتم العثور على أي مفاتيح تبدأ بـ GEMINI_API_KEY_ في الـ Secrets!")
    exit()

# اختيار مفتاح عشوائي من القائمة التي تم تجميعها
selected_api_key = random.choice(api_keys_list).strip()

# 2. قائمة النماذج المجانية السريعة واختيار واحد عشوائياً
models_list = ['gemma-3-27b-it', 'gemma-3-12b-it']
selected_model = random.choice(models_list)

print(f"🔑 تم العثور على ({len(api_keys_list)}) مفاتيح API.")
print(f"🔄 تم اختيار API Key عشوائي.")
print(f"🤖 النموذج المستخدم في هذه العملية: {selected_model}")

# تهيئة جيميناي بالمفتاح المختار
client = genai.Client(api_key=selected_api_key)

# --- (نفس وظائف الذاكرة وجلب المقالات) ---
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
    # البحث عن كل وسوم h2 و h3
    for tag in soup.find_all(['h2', 'h3']):
        text = tag.get_text(strip=True)
        if text: # التأكد أن العنوان ليس فارغاً
            headings.append(text)
    return headings

# --- الوظيفة الجديدة: استخراج الصورة من المقالة ---
def extract_image_url(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    img_tag = soup.find('img') # يبحث عن أول صورة في المقالة
    if img_tag and 'src' in img_tag.attrs:
        return img_tag['src']
    return None

# --- وظيفة توليد المحتوى (المحدثة والذكية جداً) ---
def generate_social_media_post(title, category, headings):
    headings_text = "\n- ".join(headings) if headings else "لا توجد عناوين فرعية، اعتمد على العنوان الرئيسي فقط."
    
    # الـ Prompt الاحترافي الجديد
    prompt = f"""
    أنت لست مجرد ذكاء اصطناعي، أنت "Copywriter" خبير وداهية في التسويق النفسي وعلم الأعصاب.
    مهمتك كتابة "Hook" (خطاف) يخطف انتباه القارئ من أول ثانية لمقالة جديدة، ويجعله يشعر بفضول قاتل لدرجة أنه لا يستطيع التوقف عن التفكير في الموضوع.

    معلومات المقالة (اقرأها للتحليل والفهم فقط، إياك أن تنسخها أو تسردها):
    - العنوان: "{title}"
    - القسم: "{category}"
    - النقاط المذكورة (للفهم فقط):
    {headings_text}
    
    شروط الكتابة الصارمة:
    1. إياك أن تنسخ العناوين الفرعية كما هي، حللها وافهم "نية البحث" (Search Intent) والحلول التي تقدمها المقالة، ثم صُغ منها فكرة تسويقية واحدة قوية.
    2. استخدم أسلوباً يخاطب اللاوعي (مثل إثارة الفضول، الخوف من تفويت الفرصة FOMO، أو تحقيق حلم وطموح).
    3. لا تستخدم أكواد HTML أبداً مثل <br>. للنزول لسطر جديد، استخدم النزول العادي (Enter).
    4. اجعل النص سلساً، ذكياً، وقصيراً إلى متوسط الطول (لا تكتب مقالاً داخل منشور).
    5. استخدم إيموجي (1 إلى 3 كحد أقصى) لتزيين النص دون إزعاج العين.
    6. 💡 الشرط الأهم (الحافز): في نهاية النص التسويقي، اكتب جملة تحفيزية ذكية جداً (Call to Action) تدفع القارئ للبحث عن التفاصيل، واختمها بإيموجي يشير للأسفل (👇). 
       (مثال للأسلوب: "اكتشف السر والتفاصيل الكاملة الآن 👇" أو "خطوات التنفيذ بانتظارك هنا 👇").
    7. لا تكتب مطلقاً كلمات مثل [رابط] أو (Link) أو "اضغط على الرابط" أو "اقرأ المقالة" أو "[رابط المقالة]" أو "إليك الرابط" ولا تضع أقواساً، فقط الجملة التحفيزية والسهم 👇.
    8. في نهاية النص، انزل سطرين واكتب 4 هاشتاجات (#) شائعة وقوية متعلقة بالموضوع.
    9. لا تضف هاشتاج القسم "{category}"، أنا سأضيفه بنفسي.
    10. لا تكتب أي مقدمات، أعطني المنشور النهائي جاهزاً.
    """
    
    try:
        print("🧠 جاري كتابة محتوى تسويقي احترافي ...")
        response = client.models.generate_content(
            model=selected_model,
            contents=prompt,
        )
        
        # استلام النص من جيميناي
        raw_text = response.text.strip()
        
        # --- تنظيف النص باحترافية ---
        clean_text = raw_text.replace("**", "") # مسح النجمتين
        clean_text = clean_text.replace("!", "") # مسح علامة التعجب
        clean_text = clean_text.replace("！", "") 
        clean_text = clean_text.replace("<br>", "\n") # تحويل br إلى نزول سطر سليم
        clean_text = clean_text.replace("<br/>", "\n") 
        clean_text = clean_text.replace("</br>", "")
        
        # إزالة الكلمات الوهمية إذا عاند وكتبها
        clean_text = clean_text.replace("[رابط المقالة]", "") 
        clean_text = clean_text.replace("[الرابط]", "")
        
        return clean_text.strip()
        
    except Exception as e:
        print(f"❌ حدث خطأ أثناء الاتصال بـ Gemini: {e}")
        return None

# --- وظيفة تليجرام المحدثة لترتيب العناصر بشكل مثالي ---
def send_to_telegram(image_url, ai_text, link, main_hashtag):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("❌ بيانات تليجرام غير مكتملة في الـ Secrets.")
        return False        
    
    # 1. استخراج الهاشتاجات التي كتبها جيميناي من النص
    ai_hashtags = re.findall(r'#\w+', ai_text)
    
    # 2. مسح هذه الهاشتاجات من النص ليكون النص صافياً تماماً
    text_without_hashtags = re.sub(r'#\w+', '', ai_text).strip()
    
    # 3. تجميع كل الهاشتاجات (هاشتاج القسم الأساسي + هاشتاجات جيميناي)
    all_hashtags = f"{main_hashtag} " + " ".join(ai_hashtags)
    
    # 4. الترتيب المثالي الذي طلبته: النص الصافي -> الرابط -> كل الهاشتاجات تحت خالص
    final_caption = f"{text_without_hashtags}\n\n🔗 الرابط:\n{link}\n\n{all_hashtags}"
    
    try:
        print("🚀 جاري النشر على تليجرام بالترتيب الجديد...")
        if image_url:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            payload = {
                "chat_id": TELEGRAM_CHANNEL_ID,
                "photo": image_url,
                "caption": final_caption
            }
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHANNEL_ID,
                "text": final_caption,
                "disable_web_page_preview": False
            }
            
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

# --- 🔵 وظيفة فيسبوك (المنشور + الرابط في التعليق) ---
def send_to_facebook(image_url, ai_text, link, main_hashtag):
    if not META_ACCESS_TOKEN or not FB_PAGE_ID:
        return False
        
    ai_hashtags = re.findall(r'#\w+', ai_text)
    text_without_hashtags = re.sub(r'#\w+', '', ai_text).strip()
    all_hashtags = f"{main_hashtag} " + " ".join(ai_hashtags)
    
    # النص الأساسي بدون الرابط
    fb_caption = f"{text_without_hashtags}\n\n{all_hashtags}"
    
    try:
        print("\n🔵 جاري النشر على فيسبوك...")
        if image_url:
            # 1. نشر الصورة مع النص
            url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
            payload = {"url": image_url, "message": fb_caption, "access_token": META_ACCESS_TOKEN}
            response = requests.post(url, data=payload).json()
            
            if "id" in response:
                post_id = response["id"] # معرف المنشور
                print("✅ تم نشر المنشور على فيسبوك بنجاح!")
                
                # 2. الانتظار العشوائي قبل التعليق (من 30 إلى 60 ثانية)
                wait_time = random.randint(30, 60)
                print(f"⏱️ ننتظر {wait_time} ثانية كالمحترفين للهروب من الخوارزميات...")
                time.sleep(wait_time)
                
                # 3. وضع الرابط في التعليقات
                comment_url = f"https://graph.facebook.com/v19.0/{post_id}/comments"
                comment_payload = {"message": f"🔗 الموضوع كامل:\n{link}", "access_token": META_ACCESS_TOKEN}
                comment_response = requests.post(comment_url, data=comment_payload)
                
                if comment_response.status_code == 200:
                    print("💬 تم وضع الرابط في تعليق فيسبوك بنجاح!")
                else:
                    print("⚠️ فشل إضافة التعليق.")
                return True
            else:
                print(f"❌ فشل النشر على فيسبوك: {response}")
                return False
    except Exception as e:
        print(f"❌ خطأ في فيسبوك: {e}")
        return False

# --- 🟣 وظيفة إنستجرام (المنشور + الرابط في التعليق) ---
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
        # 1. تجهيز الصورة والنص (Container)
        create_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media"
        create_payload = {"image_url": image_url, "caption": ig_caption, "access_token": META_ACCESS_TOKEN}
        create_response = requests.post(create_url, data=create_payload).json()
        
        if "id" in create_response:
            creation_id = create_response["id"]
            
            # 2. النشر الفعلي للمنشور
            publish_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media_publish"
            publish_payload = {"creation_id": creation_id, "access_token": META_ACCESS_TOKEN}
            publish_response = requests.post(publish_url, data=publish_payload).json()
            
            if "id" in publish_response:
                ig_media_id = publish_response["id"]
                print("✅ تم نشر المنشور على إنستجرام بنجاح!")
                
                # 3. الانتظار العشوائي للتعليق
                wait_time = random.randint(30, 60)
                print(f"⏱️ ننتظر {wait_time} ثانية لوضع التعليق في إنستجرام...")
                time.sleep(wait_time)
                
                # 4. وضع التعليق
                comment_url = f"https://graph.facebook.com/v19.0/{ig_media_id}/comments"
                comment_payload = {"message": f"🔗 انسخ الرابط:\n{link}", "access_token": META_ACCESS_TOKEN}
                requests.post(comment_url, data=comment_payload)
                print("💬 تم وضع التعليق في إنستجرام بنجاح!")
                return True
        else:
            print(f"❌ فشل النشر على إنستجرام: {create_response}")
            return False
    except Exception as e:
        print(f"❌ خطأ في إنستجرام: {e}")
        return False

# --- الوظيفة الرئيسية المحدثة ---
def process_oldest_unpublished_post():
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
        
        # استخراج محتوى المقالة (HTML)
        html_content = ""
        if 'content' in target_post:
            html_content = target_post.content[0].value
        elif 'summary' in target_post:
            html_content = target_post.summary
            
        # سحب عناوين H2 و H3
        extracted_headings = extract_headings(html_content)
        image_url = extract_image_url(html_content) # سحبنا الصورة هنا
        
        print("🎯 تم تحديد المقالة:")
        print(f"العنوان: {title}")
        print(f"القسم: {category}")
        print(f"📑 عدد العناوين الفرعية المستخرجة: {len(extracted_headings)}")
        print(f"الصورة المستخرجة: {'نعم' if image_url else 'لا'}")
        
        # إرسال البيانات لجيميناي
        ai_content = generate_social_media_post(title, category, extracted_headings)
        
        if ai_content:
            main_hashtag = f"#{category.replace(' ', '_')}" 
            
            # 1. النشر على تليجرام
            send_to_telegram(image_url, ai_content, link, main_hashtag)
            
            # 2. النشر على فيسبوك
            send_to_facebook(image_url, ai_content, link, main_hashtag)
            
            # 3. النشر على إنستجرام
            send_to_instagram(image_url, ai_content, link, main_hashtag)
            
            # حفظ في الذاكرة بعد الانتهاء
            save_published_link(link)
            print("\n✅ تم الحفظ في الذاكرة بنجاح. المهمة تمت!")
            
    else:
        print("🎉 لا يوجد مقالات جديدة لنشرها.")

if __name__ == "__main__":
    process_oldest_unpublished_post()
