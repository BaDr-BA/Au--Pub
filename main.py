import feedparser
import os

# أضفنا &max-results=500 لنجلب أكبر عدد ممكن من المقالات دفعة واحدة
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

def process_oldest_unpublished_post():
    # 1. جلب كل المقالات من المدونة
    feed = feedparser.parse(BLOG_RSS_URL)
    
    if len(feed.entries) == 0:
        print("المدونة فارغة أو هناك خطأ في الرابط.")
        return
    
    # 2. قلب القائمة! بلوجر يعطينا الأحدث أولاً، نحن نعكسها لتصبح الأقدم أولاً
    all_posts = reversed(feed.entries)
    
    # 3. جلب الذاكرة (الروابط التي نُشرت سابقاً)
    published_links = get_published_links()
    
    # 4. البحث عن أول مقالة غير منشورة
    target_post = None
    
    for post in all_posts:
        if post.link not in published_links:
            target_post = post
            break # وجدنا المقالة المطلوبة، نوقف البحث فوراً
            
    # 5. التعامل مع المقالة التي وجدناها
    if target_post:
        title = target_post.title
        link = target_post.link
        category = target_post.tags[0].term if 'tags' in target_post else "عام"
        
        print("🎯 تم تحديد المقالة التي سيتم نشرها اليوم:")
        print(f"العنوان: {title}")
        print(f"الرابط: {link}")
        print(f"القسم: {category}")
        
        # ... (هنا سنضع كود الذكاء الاصطناعي والنشر لاحقاً) ...
        
        # حفظ الرابط في الذاكرة لكي لا ينشر غداً
        save_published_link(link)
        print("✅ تم حفظ المقالة في الذاكرة بنجاح.")
        
    else:
        print("🎉 لقد تم نشر جميع مقالات المدونة مسبقاً! لا يوجد مقالات جديدة لنشرها.")

# تشغيل السكريبت
process_oldest_unpublished_post()
