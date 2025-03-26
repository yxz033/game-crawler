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
import random
import mimetypes
from urllib.parse import urlparse
from pathlib import Path
from tqdm import tqdm

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
        self.retry_count = 3
        self.scroll_pause_time = 2
        self.max_retries = 3
        self.progress_file = "crawl_progress.json"
        self.stats = {"success": 0, "failed": 0}
        self.setup_logging()

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
        
    def setup_logging(self):
        """设置日志系统"""
        # 创建logs目录
        os.makedirs("logs", exist_ok=True)
        
        # 设置日志格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # 文件处理器 - 详细日志
        file_handler = logging.FileHandler("logs/crawler.log", encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        
        # 控制台处理器 - 只显示关键信息
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        
        # 配置根日志器
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
            
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
        """下载文件到指定路径，保留原始格式"""
        try:
            # 创建保存目录
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 下载文件
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # 获取文件扩展名
            content_type = response.headers.get('content-type', '')
            ext = mimetypes.guess_extension(content_type) or os.path.splitext(urlparse(url).path)[1]
            if not ext:
                ext = '.jpg'  # 默认使用jpg
            
            # 更新保存路径使用原始扩展名
            save_path = str(Path(save_path).with_suffix(ext))
            
            # 保存文件
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            self.logger.debug(f"文件已保存到: {save_path}")
            return save_path
        except Exception as e:
            self.logger.error(f"下载文件时出错: {str(e)}")
            return None
            
    def crawl(self):
        """爬取所有游戏"""
        print("\n=== 游戏爬虫启动 ===")
        progress = self.load_progress()
        
        try:
            self.driver.get(self.base_url)
            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "Listed__Game")))
            
            # 滚动加载所有游戏
            self.scroll_to_load_all_games()
            
            # 解析游戏列表
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            game_elements = soup.select('div.Listed__Game a.Listed__Game__Inner')
            total_games = len(game_elements)
            
            print(f"\n总共找到 {total_games} 个游戏")
            
            # 使用tqdm创建进度条,total设为游戏总数
            pbar = tqdm(total=total_games, desc="爬取进度")
            
            # 处理所有游戏
            for element in game_elements:
                try:
                    game = {
                        "title": element.text.strip(),
                        "url": element.get('href', '')
                    }
                    
                    if game["url"] and not game["url"].startswith("http"):
                        game["url"] = "https://www.addictinggames.com" + game["url"]
                    
                    # 检查是否已处理过该游戏
                    if game["url"] in progress["processed_games"]:
                        self.logger.debug(f"跳过已处理的游戏: {game['title']}")
                        pbar.update(1)
                        continue
                    
                    print(f"\n正在处理: {game['title']}")
                    
                    # 爬取游戏详情
                    retry_count = 0
                    while retry_count < self.max_retries:
                        try:
                            game_info = self.crawl_game_detail(game["url"], game["title"])
                            if game_info:
                                self.update_index([game_info])
                                progress["last_game"] = game["url"]
                                progress["processed_games"].append(game["url"])
                                self.save_progress(progress)
                                self.stats["success"] += 1
                            else:
                                self.stats["failed"] += 1
                            break
                        except Exception as e:
                            retry_count += 1
                            self.logger.error(f"处理游戏失败 (尝试 {retry_count}/{self.max_retries}): {str(e)}")
                            if retry_count >= self.max_retries:
                                self.stats["failed"] += 1
                    
                    # 更新进度条
                    pbar.update(1)
                    
                    # 随机延迟1-3秒,避免请求过快
                    time.sleep(random.uniform(1, 3))
                    
                except Exception as e:
                    self.logger.error(f"解析游戏元素时出错: {str(e)}")
                    self.stats["failed"] += 1
                    pbar.update(1)
            
            pbar.close()
            print(f"\n=== 爬虫运行完成 ===")
            print(f"成功: {self.stats['success']} | 失败: {self.stats['failed']}")
            
        except Exception as e:
            self.logger.error(f"爬取过程中出现错误: {str(e)}")
        finally:
            if hasattr(self, 'driver'):
                self.driver.quit()

    def get_video_url(self, game_data=None, soup=None):
        """获取视频URL"""
        try:
            # 首先尝试从JavaScript数据中获取
            if game_data and 'videoThumbnailUrl' in game_data:
                video_url = game_data.get('videoThumbnailUrl')
                if video_url:
                    self.logger.debug(f"从JavaScript数据中找到视频URL: {video_url}")
                    return video_url
            
            # 尝试从video标签获取URL
            if soup:
                try:
                    # 找到Gameplay标题下的video标签
                    gameplay_header = soup.find('h4', text='10 Mahjong Gameplay')
                    if gameplay_header:
                        video_div = gameplay_header.find_next('div')
                        if video_div:
                            video_source = video_div.find('video').find('source')
                            if video_source:
                                video_url = video_source.get('src')
                                if video_url:
                                    self.logger.debug(f"从video标签找到视频URL: {video_url}")
                                    return video_url
                except Exception as e:
                    self.logger.debug(f"从video标签获取视频URL失败: {str(e)}")
            
            return None
        except Exception as e:
            self.logger.error(f"获取视频URL时出错: {str(e)}")
            return None

    def crawl_game_detail(self, game_url: str, game_title: str):
        """爬取游戏详情页"""
        self.logger.debug(f"开始爬取游戏详情: {game_title}")
        
        try:
            # 访问游戏详情页
            self.logger.debug(f"访问URL: {game_url}")
            self.driver.get(game_url)
            
            # 等待页面加载
            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # 等待游戏iframe加载
            time.sleep(5)  # 给页面一些时间加载JavaScript
            
            # 获取页面源代码
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # 创建游戏专属目录
            game_id = game_title.replace(" ", "_").lower()
            metadata_dir = os.path.join("games/metadata", game_id)
            assets_dir = os.path.join("games/assets", game_id)
            os.makedirs(metadata_dir, exist_ok=True)
            os.makedirs(os.path.join(assets_dir, "screenshots"), exist_ok=True)
            
            # 获取游戏URL和游戏数据
            game_url = None
            game_data = None
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
                        self.logger.debug(f"从JavaScript数据中找到游戏URL: {game_url}")
                except Exception as e:
                    self.logger.error(f"解析JavaScript数据时出错: {str(e)}")
            
            # 获取视频URL
            video_url = self.get_video_url(game_data, soup)
            
            # 获取游戏信息
            info = {
                "id": game_id,
                "title": game_title,
                "url": game_url,
                "description": "",
                "developer": "",
                "category": "",
                "tags": [],
                "controls": "",
                "thumbnailUrl": "",  # 稍后更新
                "previewUrl": "",    # 稍后更新
                "previewVideoUrl": "",  # 稍后更新
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
            
            # 下载并处理图片和视频
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
                        
                    # 下载缩略图
                    thumbnail_path = os.path.join(assets_dir, "thumbnail")  # 不指定扩展名
                    saved_path = self.download_file(src, thumbnail_path)
                    if saved_path:
                        # 更新路径，使用相对路径
                        info["thumbnailUrl"] = f"/games/assets/{game_id}/{os.path.basename(saved_path)}"
                        info["previewUrl"] = info["thumbnailUrl"]  # 使用相同的图片作为预览
            
            # 下载预览视频
            if video_url:
                video_path = os.path.join(assets_dir, "preview")  # 不指定扩展名
                saved_path = self.download_file(video_url, video_path)
                if saved_path:
                    info["previewVideoUrl"] = f"/games/assets/{game_id}/{os.path.basename(saved_path)}"
            
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
                    self.logger.error(f"解析评论时出错: {str(e)}")
                    continue
            
            # 保存评论数据
            with open(os.path.join(metadata_dir, "comments.json"), "w", encoding="utf-8") as f:
                json.dump(comments, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"游戏详情已保存到: {metadata_dir}")
            return info
            
        except Exception as e:
            self.logger.error(f"爬取游戏详情时出错: {str(e)}")
            return None
        
    def load_progress(self):
        """加载爬取进度"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载进度文件失败: {str(e)}")
        return {"last_game": None, "processed_games": []}

    def save_progress(self, progress):
        """保存爬取进度"""
        try:
            with open(self.progress_file, 'w') as f:
                json.dump(progress, f)
        except Exception as e:
            print(f"保存进度失败: {str(e)}")

    def scroll_to_load_all_games(self):
        """滚动页面加载所有游戏"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        games_count = 0
        no_change_count = 0
        max_no_change = 3  # 连续3次没有新内容就认为加载完成
        
        # 创建进度条
        pbar = tqdm(desc="加载游戏列表", unit="个")
        
        while True:
            # 滚动到页面底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(self.scroll_pause_time)
            
            # 获取当前游戏数量
            current_games = len(self.driver.find_elements(By.CSS_SELECTOR, '.Listed__Game'))
            
            if current_games > games_count:
                pbar.update(current_games - games_count)
                games_count = current_games
                no_change_count = 0
            else:
                no_change_count += 1
                
            if no_change_count >= max_no_change:
                break
                
            # 检查新的页面高度
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                no_change_count += 1
            else:
                last_height = new_height
                no_change_count = 0
        
        pbar.close()

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