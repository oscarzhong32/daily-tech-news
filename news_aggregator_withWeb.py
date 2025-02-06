import requests
import json
from datetime import datetime
from googletrans import Translator
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import os
from dotenv import load_dotenv
from email.header import Header
import time
import logging

# 載入環境變數
load_dotenv()

# API密鑰設置
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
GLM_API_KEY = os.getenv('GLM_API_KEY')

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_news():
    try:
        url = 'https://newsapi.org/v2/everything'
        
        params = {
            'apiKey': NEWS_API_KEY,
            'language': 'en',
            'pageSize': 20,
            'sortBy': 'publishedAt',
            'q': 'technology OR business',
            'domains': 'techcrunch.com,theverge.com,engadget.com,reuters.com,bloomberg.com'
        }
        
        print("正在獲取新聞...")
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            print(f"API請求失敗，狀態碼：{response.status_code}")
            return []
            
        data = response.json()
        print(f"API響應狀態：{data.get('status')}")
        
        if data.get('status') != 'ok':
            print(f"API返回錯誤：{data.get('message', '未知錯誤')}")
            return []
            
        articles = data.get('articles', [])
        valid_articles = [
            article for article in articles 
            if article.get('title') and article.get('description') 
            and article.get('title') != '[Removed]'
            and len(article.get('description', '')) > 50
        ]
        
        print(f"成功獲取 {len(valid_articles)} 條有效新聞")
        return valid_articles
        
    except Exception as e:
        print(f"獲取新聞時出錯：{str(e)}")
        return []

def translate_text(text):
    if not text:
        return ""
    translator = Translator()
    try:
        return translator.translate(text, dest='zh-tw').text
    except Exception as e:
        print(f"翻譯失敗：{str(e)}")
        return text

def summarize_with_glm(articles):
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GLM_API_KEY}",
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    summaries = []
    for article in articles:
        try:
            data = {
                "model": "glm-4",
                "messages": [{
                    "role": "system",
                    "content": """你是一個專業的科技新聞分析師和編輯，擅長將英文科技新聞翻譯成繁體中文並進行深入分析。
請注意以下幾點：
1. 準確翻譯原文的關鍵信息
2. 分析新聞背後的影響和意義
3. 結合行業趨勢給出見解
4. 使用專業但易懂的語言"""
                }, {
                    "role": "user",
                    "content": f"""請對以下英文新聞進行翻譯和深入分析（200-300字）：

標題：{article.get('title', '')}

內容：{article.get('description', '')}

請按照以下結構輸出：
1. 新聞要點：簡要概述主要事件和關鍵信息
2. 背景分析：說明事件的背景和原因
3. 影響評估：分析這個新聞可能帶來的影響
4. 專業見解：從行業趨勢角度提供你的觀點"""
                }],
                "temperature": 0.5,
                "top_p": 0.8,
                "max_tokens": 800,
                "do_sample": True,
                "stream": False
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                summary = result['choices'][0]['message']['content'].strip()
                print(f"成功生成摘要：{summary[:50]}...")
            else:
                raise Exception("API 返回格式異常")
            
        except Exception as e:
            print(f"生成摘要失敗：{str(e)}")
            try:
                description = article.get('description', '')
                if description:
                    summary = translate_text(description)
                    print(f"使用翻譯內容作為摘要：{summary[:50]}...")
                else:
                    summary = "無法獲取新聞內容"
            except Exception as e:
                print(f"翻譯也失敗了：{str(e)}")
                summary = "無法生成摘要"
        
        try:
            title = translate_text(article.get('title', ''))
            if not title:
                title = article.get('title', '無標題')
        except Exception as e:
            title = article.get('title', '無標題')
        
        summaries.append({
            'title': title,
            'summary': summary,
            'url': article.get('url', '#'),
            'published_at': article.get('publishedAt', '')
        })
        
        time.sleep(5)
    
    return summaries

def send_email(content):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = EMAIL_ADDRESS
        msg['Subject'] = Header(f'每日新聞摘要 - {datetime.now().strftime("%Y-%m-%d")}', 'utf-8').encode()
        
        msg.attach(MIMEText(content, 'html', 'utf-8'))
        
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            print("連接到 SMTP 服務器...")
            server.starttls()
            print("開始登錄...")
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            print("登錄成功，開始發送郵件...")
            server.sendmail(EMAIL_ADDRESS, EMAIL_ADDRESS, msg.as_string())
            print("郵件發送成功！")
            
    except Exception as e:
        print(f"發送郵件失敗：{str(e)}")

def save_to_html(summaries):
    html_content = '''
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>每日科技新聞摘要 - {}</title>
        <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .news-container { 
            max-width: 900px; 
            margin: 20px auto; 
            font-family: Arial, sans-serif;
        }
        .news-item { 
            margin-bottom: 35px; 
            padding: 25px; 
            border: 1px solid #eee;
            border-radius: 8px;
            background-color: #fff;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .news-header {
            background-color: #f8f9fa;
            padding: 20px 25px;
            border-bottom: 1px solid #eee;
        }
        .news-title {
            color: #2c3e50;
            margin: 0;
            font-size: 1.5em;
            line-height: 1.4;
        }
        .news-meta {
            color: #666;
            font-size: 0.9em;
            margin-top: 8px;
        }
        .news-content {
            padding: 25px;
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
        }
        .news-section {
            padding: 20px;
            background-color: #fff;
            border-radius: 8px;
            border: 1px solid #e1e8ed;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .news-section:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .section-title {
            color: #2980b9;
            font-size: 1.2em;
            margin-bottom: 12px;
            font-weight: bold;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .section-content {
            color: #333;
            line-height: 1.8;
            font-size: 1.1em;
            text-align: justify;
        }
        .news-footer {
            padding: 15px 25px;
            background-color: #f8f9fa;
            border-top: 1px solid #eee;
            text-align: right;
        }
        .news-link {
            color: #3498db;
            text-decoration: none;
            font-weight: bold;
            display: inline-block;
            padding: 8px 20px;
            background-color: #fff;
            border: 2px solid #3498db;
            border-radius: 6px;
            transition: all 0.3s ease;
        }
        .news-link:hover {
            background-color: #3498db;
            color: white;
        }
        .last-update {
            text-align: center;
            color: #666;
            margin-bottom: 20px;
        }
        @media (max-width: 768px) {
            .news-content {
                grid-template-columns: 1fr;
            }
        }
        </style>
    </head>
    <body>
    '''.format(datetime.now().strftime("%Y-%m-%d"))

    html_content += '''
    <div class="news-container">
        <h1 style="text-align: center; color: #2c3e50;">每日科技新聞深度分析</h1>
        <p class="last-update">最後更新時間：{}</p>
    '''.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    for summary in summaries:
        try:
            published_time = datetime.fromisoformat(summary['published_at'].replace('Z', '+00:00'))
            formatted_time = published_time.strftime('%Y-%m-%d %H:%M')
        except:
            formatted_time = "發布時間未知"
        
        content = summary['summary']
        sections = {
            '新聞要點': '',
            '背景分析': '',
            '影響評估': '',
            '專業見解': ''
        }
        
        parts = content.split('\n')
        current_section = None
        for part in parts:
            if '1. 新聞要點' in part:
                current_section = '新聞要點'
                continue
            elif '2. 背景分析' in part:
                current_section = '背景分析'
                continue
            elif '3. 影響評估' in part:
                current_section = '影響評估'
                continue
            elif '4. 專業見解' in part:
                current_section = '專業見解'
                continue
            
            if current_section and part.strip():
                sections[current_section] += part.strip() + ' '
        
        html_content += f'''
        <div class="news-item">
            <div class="news-header">
                <h3 class="news-title">{summary['title']}</h3>
                <div class="news-meta">📅 發布時間：{formatted_time}</div>
            </div>
            
            <div class="news-content">
                <div class="news-section">
                    <div class="section-title">
                        <span class="section-icon">📌</span>
                        <span>新聞要點</span>
                    </div>
                    <div class="section-content">{sections['新聞要點']}</div>
                </div>
                
                <div class="news-section">
                    <div class="section-title">
                        <span class="section-icon">🔍</span>
                        <span>背景分析</span>
                    </div>
                    <div class="section-content">{sections['背景分析']}</div>
                </div>
                
                <div class="news-section">
                    <div class="section-title">
                        <span class="section-icon">💡</span>
                        <span>影響評估</span>
                    </div>
                    <div class="section-content">{sections['影響評估']}</div>
                </div>
                
                <div class="news-section">
                    <div class="section-title">
                        <span class="section-icon">🎯</span>
                        <span>專業見解</span>
                    </div>
                    <div class="section-content">{sections['專業見解']}</div>
                </div>
            </div>
            
            <div class="news-footer">
                <a href="{summary['url']}" class="news-link" target="_blank">閱讀原文 →</a>
            </div>
        </div>
        '''
    
    html_content += '''
    </div>
    </body>
    </html>
    '''
    
    # 保存到index.html文件
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

def main():
    articles = get_news()
    if not articles:
        print("未獲取到任何新聞，程序退出")
        return
    
    print("開始處理新聞...")
    summaries = summarize_with_glm(articles)
    
    if not summaries:
        print("沒有可用的新聞摘要，程序退出")
        return
    
    save_to_html(summaries)  # 替换原来的send_email

if __name__ == '__main__':
    main() 