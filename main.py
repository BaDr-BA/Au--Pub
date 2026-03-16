import feedparser
import os
import random
import json # مكتبة جديدة لقراءة الـ Secrets المجمعة
from bs4 import BeautifulSoup
from google import genai

BLOG_RSS_URL = "https://t8ngy.blogspot.com/feeds/posts/default?alt=rss&max-results=500"
HISTORY_FILE = "published.txt"

# --- 1. الطريقة الجديدة والذكية لجلب المفاتيح المنفصلة ---
api_keys_list = []

# محاولة قراءة كل الـ Secrets التي مررها GitHub
secrets_json = os.environ.get("ALL_SECRETS")

if secrets_json:
    try:
        # تحويل النص إلى قاموس (Dictionary)
        secrets_dict = json.loads(secrets_json)
        
        # البحث عن أي مفتاح يبدأ بـ GEMINI_API_KEY_
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
    3. اجعل النص سلساً، ذكياً، وقصيراً إلى متوسط الطول (لا تكتب مقالاً داخل منشور).
    4. استخدم إيموجي (1 إلى 3 كحد أقصى) لتزيين النص دون إزعاج العين.
    5. لا تكتب أي دعوة لاتخاذ إجراء (Call to Action) مثل "اضغط على الرابط" أو "اقرأ المقالة" أو "[رابط المقالة]" أو "إليك الرابط". اترك هذه النهاية مفتوحة.
    6. في نهاية النص، انزل سطرين واكتب 4 هاشتاجات (#) شائعة وقوية متعلقة بالموضوع.
    7. لا تضف هاشتاج القسم "{category}"، أنا سأضيفه بنفسي.
    8. لا تكتب أي مقدمات، أعطني المنشور النهائي جاهزاً.
    """
    
    try:
        print("🧠 جاري كتابة محتوى تسويقي احترافي يعتمد على علم النفس...")
        response = client.models.generate_content(
            model=selected_model,
            contents=prompt,
        )
        
        # استلام النص من جيميناي
        raw_text = response.text.strip()
        
        # --- تنظيف النص (إزالة النجمتين وعلامات التعجب) ---
        clean_text = raw_text.replace("**", "") # مسح النجمتين
        clean_text = clean_text.replace("!", " ") # استبدال علامة التعجب بمسافة
        clean_text = clean_text.replace("！", " ") # للتعجب باللغة الصينية أحياناً
        clean_text = clean_text.replace("[رابط المقالة]", "") # زيادة أمان لو كتبها
        
        # إزالة أي مسافات زائدة نتجت عن التنظيف
        clean_text = " ".join(clean_text.split())
        
        return clean_text
        
    except Exception as e:
        print(f"❌ حدث خطأ أثناء الاتصال بـ Gemini: {e}")
        return None

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
        
        print("🎯 تم تحديد المقالة:")
        print(f"العنوان: {title}")
        print(f"القسم: {category}")
        print(f"📑 عدد العناوين الفرعية المستخرجة: {len(extracted_headings)}")
        
        # إرسال البيانات لجيميناي
        ai_content = generate_social_media_post(title, category, extracted_headings)
        
        if ai_content:
            main_hashtag = f"#{category.replace(' ', '_')}" 
            final_post = f"{ai_content}\n\n{main_hashtag}"
            
            print("\n📌 الشكل النهائي للبوست:\n")
            print("========================================")
            print(final_post)
            print("========================================\n")
            
            save_published_link(link)
            print("✅ تم الحفظ في الذاكرة بنجاح.")
        else:
            print("❌ فشل توليد المحتوى.")
            
    else:
        print("🎉 لا يوجد مقالات جديدة لنشرها.")

if __name__ == "__main__":
    process_oldest_unpublished_post()
