import http.client
import json
import os
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

# ================= 配置说明 =================
# 建议用户在一个名为 config.json 的文件中填入以下内容：
# {
#   "apikey": "你的_APIDANCE_KEY",
#   "authtoken": "你的_TWITTER_AUTH_TOKEN"
# }
# 或者直接修改下方的 DEFAULT_CONFIG
# ===========================================

CONFIG_FILE = "config.json"
OUTPUT_FILE = f"crypto_daily_report_{datetime.now().strftime('%Y%m%d')}.txt"
MAX_PAGES = 30
TIME_LIMIT_HOURS = 24

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    
    # 如果没有配置文件，提示用户输入
    print("⚠️ 未检测到 config.json，请输入配置信息：")
    api_key = input("请输入 APIDance API Key: ").strip()
    auth_token = input("请输入 Twitter AuthToken: ").strip()
    
    # 保存配置方便下次使用
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump({"apikey": api_key, "authtoken": auth_token}, f, indent=4)
    
    return {"apikey": api_key, "authtoken": auth_token}

def parse_twitter_date(date_str):
    try:
        return datetime.strptime(date_str, '%a %b %d %H:%M:%S %z %Y')
    except:
        return datetime.now(timezone.utc)

def fetch_page(api_key, auth_token, cursor=None):
    conn = http.client.HTTPSConnection("api.apidance.pro")
    headers = {
        'apikey': api_key,
        'AuthToken': auth_token,
        'Content-Type': 'application/json'
    }
    
    variables = {
        "count": 40,
        "includePromotedContent": False,
        "latestControlAvailable": True,
        "requestContext": "launch"
    }
    if cursor:
        variables["cursor"] = cursor

    encoded_vars = urllib.parse.quote(json.dumps(variables))
    url = f"/graphql/HomeLatestTimeline?variables={encoded_vars}"

    try:
        conn.request("GET", url, '', headers)
        res = conn.getresponse()
        return json.loads(res.read().decode("utf-8"))
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

def run_task():
    config = load_config()
    api_key = config.get('apikey')
    auth_token = config.get('authtoken')

    if not api_key or not auth_token:
        print("❌ 配置缺失，无法运行。")
        return

    all_tweets = []
    next_cursor = None
    now = datetime.now(timezone.utc)
    time_limit = now - timedelta(hours=TIME_LIMIT_HOURS)

    print(f"\n🚀 开始抓取过去 {TIME_LIMIT_HOURS} 小时的推文...")
    print(f"📅 截止时间: {time_limit.strftime('%Y-%m-%d %H:%M:%S')}")

    for page in range(1, MAX_PAGES + 1):
        print(f"📄 第 {page} 页...", end="", flush=True)
        data = fetch_page(api_key, auth_token, next_cursor)
        
        if not data:
            print(" (请求失败或无数据)")
            break

        instructions = data.get('data', {}).get('home', {}).get('home_timeline_urt', {}).get('instructions', [])
        page_tweets = []
        page_cursor = None
        reached_limit = False

        for instr in instructions:
            if instr.get('type') == 'TimelineAddEntries':
                for entry in instr.get('entries', []):
                    entry_id = entry.get('entryId', '')
                    content = entry.get('content', {})
                    
                    # 获取游标
                    if content.get('cursorType') == 'Bottom':
                        page_cursor = content.get('value')

                    # 解析推文
                    if entry_id.startswith('tweet-') or entry_id.startswith('home-conversation-'):
                        item_content = content.get('itemContent') or content.get('items', [{}])[0].get('item', {}).get('itemContent', {})
                        tweet_res = item_content.get('tweet_results', {}).get('result', {})
                        
                        if tweet_res and 'legacy' in tweet_res:
                            legacy = tweet_res['legacy']
                            created_at = parse_twitter_date(legacy.get('created_at'))
                            
                            if created_at < time_limit:
                                reached_limit = True
                            else:
                                author = tweet_res['core']['user_results']['result']['legacy']['name']
                                screen_name = tweet_res['core']['user_results']['result']['legacy']['screen_name']
                                text = legacy['full_text'].replace('\n', ' ')
                                tid = tweet_res['rest_id']
                                url = f"https://x.com/{screen_name}/status/{tid}"
                                
                                page_tweets.append(f"⏰ {created_at.strftime('%m-%d %H:%M')} | 👤 {author} (@{screen_name})\n📄 {text}\n🔗 {url}\n{'-'*50}")

        all_tweets.extend(page_tweets)
        print(f" ✅ 获取 {len(page_tweets)} 条")

        if reached_limit:
            print("🛑 已触达时间限制，停止抓取。")
            break
        
        if not page_cursor:
            print("⚠️ 无更多页面。")
            break
            
        next_cursor = page_cursor
        time.sleep(1.5)

    if all_tweets:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(f"=== 每日 Crypto 全景推文 (共 {len(all_tweets)} 条) ===\n\n")
            f.write("\n".join(all_tweets))
        print(f"\n🎉 抓取完成！结果已保存至: {OUTPUT_FILE}")
        print("👉 下一步：请将该文件内容复制给 ChatGPT/Claude，并使用配套提示词生成研报。")
    else:
        print("\n❌ 未获取到数据，请检查 Token 是否过期。")

if __name__ == "__main__":
    run_task()
