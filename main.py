import feedparser
import os

# رابط مدونتك
BLOG_RSS_URL = "https://t8ngy.blogspot.com/feeds/posts/default?alt=rss&max-results=500"
HISTORY_FILE = "published.txt"

def get_published_links():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r") as file:
        return [line.strip() for line in file.readlines()]

def save_published_link(link):
    with open(HISTORY_FILE, "a") as file:
        file.write(link + "\n")

# هذه الوظيفة الجديدة السحرية التي ستجلب كل المقالات مهما كان عددها
def get_all_posts():
    all_entries = []
    current_url = BLOG_RSS_URL
    
    # الحلقة التكرارية: طالما هناك صفحة تالية، استمر في جلب المقالات
    while current_url:
        feed = feedparser.parse(current_url)
        all_entries.extend(feed.entries)
        
        # البحث عن رابط "الصفحة التالية" في بلوجر
        next_link = None
        if 'links' in feed.feed:
            for link in feed.feed.links:
                if link.rel == 'next':
                    next_link = link.href
                    break
                    
        # تحديث الرابط للانتقال للصفحة التالية، أو التوقف إذا انتهت المقالات
        current_url = next_link
        
    return all_entries

def process_oldest_unpublished_post():
    # 1. جلب كل المقالات من المدونة باستخدام الوظيفة الجديدة
    all_entries = get_all_posts()
    
    if len(all_entries) == 0:
        print("المدونة فارغة أو هناك خطأ في الرابط.")
        return
    
    # 2. قلب القائمة لتصبح الأقدم أولاً
    all_posts = reversed(all_entries)
    
    # 3. جلب الذاكرة
    published_links = get_published_links()
    
    target_post = None
    
    # 4. البحث عن أول مقالة غير منشورة
    for post in all_posts:
        if post.link not in published_links:
            target_post = post
            break
            
    if target_post:
        title = target_post.title
        link = target_post.link
        category = target_post.tags[0].term if 'tags' in target_post else "عام"
        
        print("🎯 تم تحديد المقالة التي سيتم نشرها اليوم:")
        print(f"العنوان: {title}")
        print(f"الرابط: {link}")
        print(f"القسم: {category}")
        
        # حفظ الرابط في الذاكرة
        save_published_link(link)
        print("✅ تم حفظ المقالة في الذاكرة بنجاح.")
        
    else:
        print("🎉 لقد تم نشر جميع مقالات المدونة مسبقاً! لا يوجد مقالات جديدة لنشرها.")

# تشغيل السكريبت
process_oldest_unpublished_post()
