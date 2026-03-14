import feedparser
import os
import google.generativeai as genai # مكتبة جيميناي الجديدة

# إعدادات المدونة والذاكرة
BLOG_RSS_URL = "https://t8ngy.blogspot.com/feeds/posts/default?alt=rss&max-results=500"
HISTORY_FILE = "published.txt"

# إعداد مفتاح جيميناي من الخزنة السرية (Secrets)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # استخدام أحدث وأسرع نموذج مجاني
    model = genai.GenerativeModel('gemma-3-27b-it')
else:
    print("❌ خطأ: لم يتم العثور على مفتاح GEMINI_API_KEY!")

# --- (نفس وظائف الذاكرة وجلب المقالات التي كتبناها سابقاً) ---

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

# --- الوظيفة الجديدة: توليد المحتوى التسويقي باستخدام Gemini ---

def generate_social_media_post(title, category):
    # هذا هو الطلب (Prompt) الذي سيرسل لجيميناي، قمت بصياغته بناءً على طلبك
    prompt = f"""
    أنت خبير تسويق إلكتروني محترف. أريدك أن تكتب لي منشوراً (Post) جذاباً واحترافياً لمواقع التواصل الاجتماعي للترويج لمقالة جديدة.
    
    معلومات المقالة:
    - عنوان المقالة: "{title}"
    - قسم المقالة: "{category}"
    
    شروط كتابة المنشور:
    1. اكتب نصاً تسويقياً مشوقاً يجعل القارئ يرغب بشدة في قراءة المقالة (لا تكتب الرابط، أنا سأضيفه لاحقاً).
    2. استخدم الإيموجي المناسبة للموضوع بشكل احترافي وغير مبالغ فيه.
    3. في نهاية المنشور، اكتب 4 هاشتاجات شائعة وقوية متعلقة بموضوع "{title}".
    4. لا تضف هاشتاج القسم "{category}"، أنا سأضيفه بنفسي.
    5. لا تكتب أي مقدمات مثل "إليك المنشور" أو "بالتأكيد"، اكتب المنشور النهائي مباشرة جاهزاً للنسخ.
    """
    
    try:
        print("🤖 جاري طلب المحتوى من Gemini...")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"❌ حدث خطأ أثناء الاتصال بـ Gemini: {e}")
        return None

# --- الوظيفة الرئيسية المحدثة ---

def process_oldest_unpublished_post():
    all_entries = get_all_posts()
    if len(all_entries) == 0:
        print("المدونة فارغة أو هناك خطأ في الرابط.")
        return
    
    all_posts = reversed(all_entries)
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
        
        print("🎯 تم تحديد المقالة:")
        print(f"العنوان: {title}")
        print(f"القسم: {category}")
        
        # --- السحر هنا: نرسل العنوان والقسم لجيميناي ---
        ai_content = generate_social_media_post(title, category)
        
        if ai_content:
            print("\n✨ المحتوى الذي ولده الذكاء الاصطناعي:\n")
            print("========================================")
            print(ai_content)
            
            # تجهيز الهاشتاج الأساسي (القسم) كما طلبت ليكون الأول
            main_hashtag = f"#{category.replace(' ', '_')}" 
            
            # الشكل النهائي للبوست الذي سيُنشر (باستثناء الرابط الذي سيضاف لاحقاً حسب المنصة)
            final_post = f"{ai_content}\n\n{main_hashtag}"
            print("\n📌 الشكل النهائي للبوست مع هاشتاج القسم:\n")
            print(final_post)
            print("========================================\n")
            
            # حفظ الرابط في الذاكرة
            save_published_link(link)
            print("✅ تم الحفظ في الذاكرة.")
        else:
            print("❌ فشل توليد المحتوى، لن يتم حفظ المقالة في الذاكرة لتجربتها مرة أخرى لاحقاً.")
            
    else:
        print("🎉 لا يوجد مقالات جديدة لنشرها.")

if __name__ == "__main__":
    process_oldest_unpublished_post()
