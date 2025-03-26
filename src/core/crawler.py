import json
import os
import sys
import time
import logging
import requests
from typing import List, Dict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from PIL import Image
import io

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.models.game import Game
from src.utils.parser import HtmlParser

CRAWLER_CONFIG = {
    "interval": 5,  # 爬取间隔(秒)
    "concurrency": 1,  # 并发数
    "retries": 3,  # 重试次数
    "timeout": 30,  # 超时时间(秒)
    "urls": [
        "https://www.crazygames.com/",
        "https://www.addictinggames.com/"
    ]
}

class Crawler:
    def __init__(self):
        self.parser = HtmlParser()
        self.logger = logging.getLogger(__name__)
        self.setup_selenium()

    def setup_selenium(self):
        """设置Selenium WebDriver"""
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")  # 启用新版无头模式
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # SSL相关选项
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--ignore-ssl-errors')
        chrome_options.add_argument('--ignore-certificate-errors-spki-list')
        chrome_options.add_argument('--allow-insecure-localhost')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--unsafely-treat-insecure-origin-as-secure')
        
        # 禁用安全特性
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--reduce-security-for-testing')
        
        # 设置日志级别
        chrome_options.add_argument('--log-level=3')  # 仅显示致命错误
        chrome_options.add_argument('--silent')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)

    def crawl(self) -> List[Game]:
        """
        爬取游戏数据
        :return: 游戏列表
        """
        games = []
        for url in CRAWLER_CONFIG["urls"]:
            try:
                self.logger.info(f"开始爬取: {url}")
                self.driver.get(url)
                
                # 等待页面加载
                WebDriverWait(self.driver, CRAWLER_CONFIG["timeout"]).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # 滚动页面以加载更多内容
                self.scroll_page()
                
                # 获取页面内容
                html_content = self.driver.page_source
                print(f"获取到页面内容,长度: {len(html_content)}")
                
                # 解析游戏卡片
                page_games = self.parser.parse_game_cards(html_content)
                games.extend(page_games)
                
                time.sleep(CRAWLER_CONFIG["interval"])
            except Exception as e:
                self.logger.error(f"爬取{url}时出错: {str(e)}")
                continue
        
        return games

    def scroll_page(self):
        """缓慢滚动页面以加载更多内容"""
        print("开始缓慢滚动页面...")
        
        # 获取页面高度
        total_height = self.driver.execute_script("return document.body.scrollHeight")
        
        # 每次滚动的距离(像素)
        scroll_step = 300
        
        # 当前滚动位置
        current_position = 0
        
        while current_position < total_height:
            # 计算下一个滚动位置
            next_position = min(current_position + scroll_step, total_height)
            
            # 滚动到下一个位置
            print(f"滚动到位置: {next_position}/{total_height}")
            self.driver.execute_script(f"window.scrollTo(0, {next_position});")
            
            # 等待内容加载
            time.sleep(2)
            
            # 更新当前位置
            current_position = next_position
            
            # 重新获取页面高度(可能因为加载了新内容而改变)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height > total_height:
                print(f"页面高度更新: {total_height} -> {new_height}")
                total_height = new_height
                
        print("页面滚动完成")

    def __del__(self):
        """清理资源"""
        if hasattr(self, 'driver'):
            self.driver.quit()

class GameCrawler:
    def __init__(self):
        self.base_url = "https://www.addictinggames.com/all-games"
        self.driver = None
        self.setup_selenium()
        
    def setup_selenium(self):
        """设置Selenium WebDriver"""
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")  # 启用新版无头模式
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--ignore-ssl-errors')
        chrome_options.add_argument('--log-level=3')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
    def download_and_convert_image(self, url: str, save_path: str, max_width: int = None, quality: int = 85):
        """下载图片并转换为WebP格式"""
        try:
            # 创建保存目录
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 下载图片
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # 打开图片
            img = Image.open(io.BytesIO(response.content))
            
            # 调整大小
            if max_width and img.width > max_width:
                ratio = max_width / img.width
                new_size = (max_width, int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # 保存为WebP格式
            img.save(save_path, 'WEBP', quality=quality)
            print(f"图片已保存到: {save_path}")
            return True
        except Exception as e:
            print(f"处理图片时出错: {str(e)}")
            return False
            
    def download_file(self, url: str, save_path: str):
        """下载文件到指定路径"""
        try:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"文件已保存到: {save_path}")
            return True
        except Exception as e:
            print(f"下载文件时出错: {str(e)}")
            return False
            
    def crawl_game_detail(self, game_url: str, game_title: str):
        """爬取游戏详情页"""
        print(f"\n开始爬取游戏详情: {game_title}")
        
        try:
            # 访问游戏详情页
            print(f"访问URL: {game_url}")
            self.driver.get(game_url)
            
            # 等待页面加载
            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # 等待游戏iframe加载
            print("等待游戏iframe加载...")
            time.sleep(5)  # 给页面一些时间加载JavaScript
            
            # 获取页面源代码
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # 尝试从JavaScript数据中提取游戏URL
            game_url = None
            next_data = soup.find('script', {'id': '__NEXT_DATA__'})
            if next_data:
                try:
                    data = json.loads(next_data.string)
                    game_data = data.get('props', {}).get('pageProps', {}).get('game', {})
                    embed_url = game_data.get('embedUrl', '')
                    if embed_url:
                        if embed_url.startswith('//'):
                            game_url = 'https:' + embed_url
                        elif embed_url.startswith('/'):
                            game_url = 'https://www.addictinggames.com' + embed_url
                        else:
                            game_url = embed_url
                        print(f"从JavaScript数据中找到游戏URL: {game_url}")
                    else:
                        print("JavaScript数据中没有找到游戏URL")
                        print("游戏数据:", json.dumps(game_data, indent=2))
                except Exception as e:
                    print(f"解析JavaScript数据时出错: {str(e)}")
            
            # 查找游戏iframe
            if not game_url:
                game_iframe = soup.select_one('iframe#game-iframe, iframe.GamePlayer__Game')
                if game_iframe:
                    iframe_url = game_iframe.get('src', '')
                    if iframe_url:
                        if iframe_url.startswith('//'):
                            game_url = 'https:' + iframe_url
                        elif iframe_url.startswith('/'):
                            game_url = 'https://www.addictinggames.com' + iframe_url
                        else:
                            game_url = iframe_url
                        print(f"找到游戏iframe URL: {game_url}")
            
            # 如果还是没有找到游戏URL，尝试从其他脚本中查找
            if not game_url:
                print("尝试从其他脚本中查找游戏URL...")
                scripts = soup.find_all('script')
                for script in scripts:
                    script_text = str(script)
                    if 'gameUrl' in script_text or 'game_url' in script_text:
                        print("找到可能包含游戏URL的脚本:", script_text[:200])
            
            # 创建游戏专属目录
            game_id = game_title.replace(" ", "_").lower()
            metadata_dir = os.path.join("games/metadata", game_id)
            assets_dir = os.path.join("games/assets", game_id)
            os.makedirs(metadata_dir, exist_ok=True)
            os.makedirs(os.path.join(assets_dir, "screenshots"), exist_ok=True)
            
            # 获取游戏信息
            info = {
                "id": game_id,
                "title": game_title,
                "url": game_url,
                "description": "",
                "developer": "",
                "category": "",
                "tags": [],
                "controls": "",  # 修改为字符串类型
                "thumbnailUrl": f"/games/assets/{game_id}/thumbnail.webp",
                "previewUrl": f"/games/assets/{game_id}/preview.webp",
                "screenshots": [],
                "features": [],
                "device": {
                    "mobile": True,
                    "desktop": True
                },
                "addedDate": "",
                "lastUpdated": time.strftime("%Y-%m-%d"),
                "gameUrl": game_url
            }
            
            # 获取描述
            description = soup.select_one('.Content h4:-soup-contains("Game Description") + div p')
            if description:
                info["description"] = description.text.strip()
            
            # 获取分类和标签
            category = soup.select_one('.CategoryTag__Label span')
            if category:
                info["category"] = category.text.strip()
            
            tags = soup.select('.GamePage__Tags a .CategoryTag__Label span')
            info["tags"] = [tag.text.strip() for tag in tags if tag.text.strip()]
            
            # 获取开发者和发布日期
            meta_items = soup.select('.GPDescription__GameMeta div')
            for item in meta_items:
                label = item.find('strong')
                if not label:
                    continue
                    
                label_text = label.text.strip()
                value = item.text.replace(label_text, '').strip()
                
                if 'Developer' in label_text:
                    info["developer"] = value
                elif 'Release Date' in label_text:
                    info["addedDate"] = value
            
            # 获取游戏说明作为控制说明
            instructions = soup.select_one('.Content h4:-soup-contains("Instructions") + p')
            if instructions:
                info["controls"] = instructions.text.strip()
            
            # 保存游戏信息
            with open(os.path.join(metadata_dir, "info.json"), "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)
            
            # 获取统计数据
            stats = {
                "id": game_id,
                "plays": 0,
                "rating": 0,
                "ratingCount": 0,
                "lastUpdated": time.strftime("%Y-%m-%d")
            }
            
            rating_elem = soup.select_one('.GPRatingUi__Rating button span span')
            if rating_elem:
                stats["rating"] = float(rating_elem.text.strip())
            
            rating_stats = soup.select_one('.GamePage__Game__RatingStats')
            if rating_stats:
                count = rating_stats.text.strip().split('\n')[0]
                stats["ratingCount"] = int(count.replace("Ratings", "").strip())
            
            # 保存统计数据
            with open(os.path.join(metadata_dir, "stats.json"), "w", encoding="utf-8") as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            
            # 获取评论
            comments = {
                "id": game_id,
                "comments": [],
                "lastUpdated": time.strftime("%Y-%m-%d")
            }
            
            for review in soup.select('.GameReview'):
                try:
                    author = review.select_one('.GameReview__Author a')
                    date = review.select_one('.GameReview__Subject')
                    content = review.select_one('p:not(.GameReview__Subject)')
                    rating = 5 if 'GameReview--positive' in review.get('class', []) else 1
                    
                    if author and date and content:
                        comments["comments"].append({
                            "id": f"{game_id}_{len(comments['comments'])}",
                            "user": author.text.strip(),
                            "content": content.text.strip(),
                            "rating": rating,
                            "date": date.text.strip()
                        })
                except Exception as e:
                    print(f"解析评论时出错: {str(e)}")
                    continue
            
            # 保存评论数据
            with open(os.path.join(metadata_dir, "comments.json"), "w", encoding="utf-8") as f:
                json.dump(comments, f, ensure_ascii=False, indent=2)
            
            # 下载并处理图片
            thumbnail = soup.select_one('img[alt$="Thumbnail"]')
            if thumbnail:
                src = thumbnail.get('src', '')
                if src:
                    if src.startswith('/_next/image'):
                        srcset = thumbnail.get('srcset', '').split(',')
                        if srcset:
                            src = srcset[-1].strip().split(' ')[0]
                    
                    if src.startswith('/'):
                        src = 'https://www.addictinggames.com' + src
                        
                    # 下载并转换缩略图
                    thumbnail_path = os.path.join(assets_dir, "thumbnail.webp")
                    self.download_and_convert_image(src, thumbnail_path, max_width=800)
                    
                    # 同时保存为预览图
                    preview_path = os.path.join(assets_dir, "preview.webp")
                    self.download_and_convert_image(src, preview_path, max_width=800)
            
            print(f"游戏详情已保存到: {metadata_dir}")
            return info
            
        except Exception as e:
            print(f"爬取游戏详情时出错: {str(e)}")
            return None
        
    def crawl(self):
        print("爬虫系统启动...")
        try:
            print("正在访问游戏列表页面...")
            self.driver.get(self.base_url)
            
            # 等待页面加载
            print("等待页面加载...")
            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "Listed__Game")))
            
            # 解析游戏列表
            print("开始解析游戏列表...")
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            game_elements = soup.select('div.Listed__Game a.Listed__Game__Inner')
            
            # 只处理第一个游戏
            if game_elements:
                element = game_elements[0]
                try:
                    game = {
                        "title": element.text.strip(),
                        "url": element.get('href', '')
                    }
                    if game["url"] and not game["url"].startswith("http"):
                        game["url"] = "https://www.addictinggames.com" + game["url"]
                    print(f"找到游戏: {game['title']} - {game['url']}")
                    
                    # 爬取游戏详情
                    game_info = self.crawl_game_detail(game["url"], game["title"])
                    if game_info:
                        # 更新索引文件
                        self.update_index([game_info])
                    
                except Exception as e:
                    print(f"解析游戏元素时出错: {str(e)}")
            else:
                print("未找到任何游戏")
            
            print("\n爬虫运行完成!")
            print("浏览器窗口将保持打开状态,请手动关闭浏览器窗口...")
            input("按回车键退出程序...")
            
        except Exception as e:
            print(f"爬取过程中出现错误: {str(e)}")
            print("\n爬虫运行完成!")
            print("浏览器窗口将保持打开状态,请手动关闭浏览器窗口...")
            input("按回车键退出程序...")
                
    def update_index(self, games: List[Dict]):
        """更新游戏索引文件"""
        index_file = "games/metadata/index.json"
        
        # 读取现有索引
        if os.path.exists(index_file):
            with open(index_file, "r", encoding="utf-8") as f:
                index = json.load(f)
        else:
            index = {
                "lastUpdated": "",
                "games": [],
                "categories": []
            }
        
        # 更新游戏列表
        for game in games:
            # 读取统计数据
            stats_file = f"games/metadata/{game['id']}/stats.json"
            if os.path.exists(stats_file):
                with open(stats_file, "r", encoding="utf-8") as f:
                    stats = json.load(f)
            else:
                stats = {"rating": 0, "plays": 0}
            
            # 添加或更新游戏信息
            game_index = {
                "id": game["id"],
                "title": game["title"],
                "category": game["category"],
                "rating": stats["rating"],
                "plays": stats["plays"],
                "thumbnailUrl": game["thumbnailUrl"],
                "added": game["addedDate"]
            }
            
            # 检查是否已存在
            existing = next((g for g in index["games"] if g["id"] == game["id"]), None)
            if existing:
                existing.update(game_index)
            else:
                index["games"].append(game_index)
        
        # 更新分类信息
        categories = {}
        for game in index["games"]:
            cat = game["category"]
            if cat:
                if cat not in categories:
                    categories[cat] = {
                        "id": cat.lower().replace(" ", "_"),
                        "name": cat,
                        "count": 0
                    }
                categories[cat]["count"] += 1
        
        index["categories"] = list(categories.values())
        index["lastUpdated"] = time.strftime("%Y-%m-%d")
        
        # 保存索引
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
            
        print(f"索引已更新: {index_file}")
        
if __name__ == "__main__":
    crawler = GameCrawler()
    crawler.crawl() 