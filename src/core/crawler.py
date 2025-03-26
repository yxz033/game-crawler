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
        self.game_cache = {}  # 游戏数据缓存
        self.game_buffer = []  # 游戏信息缓冲区，用于批量更新索引
        
        # 并发控制
        self.max_workers = 5  # 最大线程数
        self.thread_pool = None  # 线程池在实际使用前初始化
        
        # 线程安全锁
        self.cache_lock = threading.Lock()  # 缓存访问锁
        self.buffer_lock = threading.Lock()  # 缓冲区访问锁
        self.progress_lock = threading.Lock()  # 进度信息锁
        self.stats_lock = threading.Lock()  # 统计信息锁
        
        # 线程本地存储WebDriver
        self.local_drivers = {}  # 存储线程ID到WebDriver的映射
        self.driver_lock = threading.Lock()  # WebDriver访问锁
        
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
        if not url:
            return None
            
        # 创建目录
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        try:
            # 设置请求超时和重试
            session = requests.Session()
            retry = 0
            max_retries = 3
            timeout = 10  # 设置超时为10秒
            
            while retry < max_retries:
                try:
                    # 使用超时机制防止请求卡住
                    response = session.get(url, timeout=timeout)
                    response.raise_for_status()  # 如果状态码不是200，将引发HTTPError异常
                    break
                except (requests.RequestException, IOError) as e:
                    retry += 1
                    if retry >= max_retries:
                        self.logger.error(f"下载图片失败(已重试{retry}次): {url} - {str(e)}")
                        return None
                    # 使用指数退避算法增加重试间隔
                    wait_time = 0.5 * (2 ** retry)
                    self.logger.warning(f"下载图片重试({retry}/{max_retries})，等待{wait_time}秒: {url}")
                    time.sleep(wait_time)
            
            # 图片处理和转换
            image_data = io.BytesIO(response.content)
            img = Image.open(image_data)
            
            # 如果指定了最大宽度，则按比例缩放
            if max_width and img.width > max_width:
                ratio = max_width / img.width
                new_width = max_width
                new_height = int(img.height * ratio)
                img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # 确保图片模式为RGB
            if img.mode != 'RGB':
                img = img.convert('RGB')
                
            # 保存为WebP格式
            img.save(save_path, 'WEBP', quality=quality)
            self.logger.debug(f"图片已保存: {save_path}")
            
            return save_path
        except Exception as e:
            self.logger.error(f"处理图片时出错: {url} - {str(e)}")
            return None
            
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
        """爬取所有游戏，使用多线程并发处理"""
        print("\n=== 游戏爬虫启动 ===")
        progress = self.load_progress()
        
        # 批量处理大小
        batch_size = 10
        
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
            
            # 初始化线程池
            self.thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)
            self.logger.info(f"初始化线程池，并发线程数: {self.max_workers}")
            
            # 使用tqdm创建进度条
            pbar = tqdm(total=total_games, desc="爬取进度")
            
            # 收集需要处理的游戏
            games_to_process = []
            
            # 第一步：过滤已处理的游戏
            for element in game_elements:
                try:
                    game = {
                        "title": element.text.strip(),
                        "url": element.get('href', '')
                    }
                    
                    if game["url"] and not game["url"].startswith("http"):
                        game["url"] = "https://www.addictinggames.com" + game["url"]
                    
                    # 生成游戏ID
                    game_id = self.sanitize_id(game["title"])
                    
                    # 快速过滤：检查缓存和已处理列表
                    if game_id in self.game_cache or game["url"] in progress["processed_games"]:
                        pbar.update(1)
                        continue
                    
                    # 收集需要处理的游戏
                    games_to_process.append(game)
                    
                except Exception as e:
                    self.logger.error(f"解析游戏元素时出错: {str(e)}")
                    with self.stats_lock:
                        self.stats["failed"] += 1
                    pbar.update(1)
            
            self.logger.info(f"需要处理的游戏数量: {len(games_to_process)}")
            
            # 第二步：批量处理游戏
            if games_to_process:
                # 创建Future到游戏的映射
                futures = {}
                
                # 提交所有任务到线程池
                for game in games_to_process:
                    future = self.thread_pool.submit(self.process_game_task, game, progress)
                    futures[future] = game
                
                # 处理完成的任务
                self._process_completed_futures(futures, pbar, progress, batch_size)
            
            # 确保最后的缓冲区也被处理
            if self.game_buffer:
                with self.buffer_lock:
                    buffer_copy = self.game_buffer.copy()
                    self.game_buffer = []
                
                self.update_index(buffer_copy)
                self.logger.info(f"已更新剩余 {len(buffer_copy)} 个游戏到索引")
            
            # 最后保存一次进度
            self.save_progress(progress)
                
            pbar.close()
            print(f"\n=== 爬虫运行完成 ===")
            print(f"成功: {self.stats['success']} | 失败: {self.stats['failed']}")
            print(f"缓存游戏数量: {len(self.game_cache)}")
            
        except Exception as e:
            self.logger.error(f"爬取过程中出现错误: {str(e)}")
            
            # 确保发生异常时也保存已处理的游戏
            if self.game_buffer:
                try:
                    with self.buffer_lock:
                        buffer_copy = self.game_buffer.copy()
                        self.game_buffer = []
                    
                    self.update_index(buffer_copy)
                    self.logger.info(f"异常退出前保存 {len(buffer_copy)} 个游戏到索引")
                except Exception as save_error:
                    self.logger.error(f"异常退出时保存索引失败: {str(save_error)}")
                
            self.save_progress(progress)
        finally:
            # 关闭所有线程的WebDriver实例
            self.close_thread_drivers()
            
            # 关闭线程池
            if self.thread_pool:
                self.thread_pool.shutdown(wait=True)
                self.logger.info("线程池已关闭")
            
            # 关闭主WebDriver
            if hasattr(self, 'driver'):
                self.driver.quit()
                
    def _process_completed_futures(self, futures, pbar, progress, batch_size):
        """处理已完成的Future任务"""
        completed_count = 0
        buffer_update_threshold = batch_size
        progress_save_threshold = batch_size * 2
        
        # 等待任务完成并处理结果
        for future in as_completed(futures):
            game = futures[future]
            try:
                result = future.result()
                completed_count += 1
                
                if result["success"] and result["game_info"]:
                    self.logger.debug(f"任务成功完成: {game['title']}")
                else:
                    self.logger.debug(f"任务跳过或失败: {game['title']} - {result.get('error', '未知错误')}")
                
                # 更新进度条
                pbar.update(1)
                
                # 每处理一定数量的任务，批量保存进度和更新索引
                if completed_count % progress_save_threshold == 0:
                    self.save_progress(progress)
                    self.logger.info(f"已处理 {completed_count}/{len(futures)} 个任务，保存进度")
                
                # 批量更新索引
                if completed_count % buffer_update_threshold == 0:
                    with self.buffer_lock:
                        if len(self.game_buffer) >= buffer_update_threshold:
                            buffer_copy = self.game_buffer.copy()
                            self.game_buffer = []
                            
                            # 释放锁后更新索引
                            self.update_index(buffer_copy)
                            self.logger.info(f"已批量更新索引，游戏数：{len(buffer_copy)}")
                
            except Exception as e:
                self.logger.error(f"处理任务结果出错: {game['title']} - {str(e)}")
                pbar.update(1)
                with self.stats_lock:
                    self.stats["failed"] += 1
        
        # 确保最后的进度也保存
        self.save_progress(progress)
        self.logger.info(f"所有 {completed_count} 个任务已完成处理")
        
        # 短暂延迟，避免请求过于频繁
        time.sleep(random.uniform(0.2, 0.5))

    def sanitize_id(self, text: str) -> str:
        """生成安全的ID，去除特殊字符"""
        # 将标题转换为小写并替换空格为下划线
        id_text = text.lower().replace(" ", "_")
        
        # 移除所有不适合作为文件夹名的字符
        import re
        id_text = re.sub(r'[^\w\-]', '_', id_text)
        
        # 确保没有连续的下划线
        id_text = re.sub(r'_+', '_', id_text)
        
        # 去除首尾的下划线
        id_text = id_text.strip('_')
        
        return id_text

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

    def crawl_game_detail(self, game_url: str, game_title: str, use_thread_driver=False):
        """爬取游戏详情页"""
        self.logger.debug(f"开始爬取游戏详情: {game_title}")
        
        try:
            # 先检查缓存中是否已存在该游戏
            game_id = self.sanitize_id(game_title)
            with self.cache_lock:
                if game_id in self.game_cache:
                    self.logger.info(f"使用缓存中的游戏数据: {game_title}")
                    return self.game_cache[game_id]
            
            # 以下是原有的爬取逻辑
            # 获取合适的WebDriver，根据是否并发使用不同的实例
            driver = self.get_thread_driver() if use_thread_driver else self.driver
            
            # 访问游戏详情页
            self.logger.debug(f"访问URL: {game_url}")
            driver.get(game_url)
            
            # 等待页面基本元素加载
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # 等待游戏内容加载 - 使用具体元素而不是固定等待
            try:
                # 尝试等待游戏描述或游戏图片等关键元素
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".Content h4, .GamePage__Tags, iframe.PlayFrame")))
                self.logger.debug("游戏详情页面关键元素已加载")
            except Exception as e:
                self.logger.warning(f"等待游戏详情元素超时: {str(e)}")
            
            # 获取页面源代码
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # 创建游戏专属目录
            game_id = self.sanitize_id(game_title)
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
            info_path = os.path.join(metadata_dir, "info.json")
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)

            # 保存游戏数据到game.json以方便缓存
            game_path = os.path.join(metadata_dir, "game.json")
            with open(game_path, "w", encoding="utf-8") as f:
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
            
            # 线程安全地更新缓存
            with self.cache_lock:
                self.game_cache[game_id] = info
                
            return info
            
        except Exception as e:
            self.logger.error(f"爬取游戏详情时出错: {str(e)}")
            return None
        
    def load_progress(self):
        """加载爬取进度和已下载的游戏数据"""
        progress = {"last_game": None, "processed_games": []}
        
        # 加载进度文件
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)
            except Exception as e:
                self.logger.error(f"加载进度文件失败: {str(e)}")
        
        # 加载已下载的游戏数据到缓存
        metadata_dir = "games/metadata"
        if os.path.exists(metadata_dir):
            for game_dir in os.listdir(metadata_dir):
                if game_dir == 'index.json':
                    continue
                    
                # 优先读取game.json，如果不存在则读取info.json
                game_json = os.path.join(metadata_dir, game_dir, "game.json")
                info_json = os.path.join(metadata_dir, game_dir, "info.json")
                
                json_file = game_json if os.path.exists(game_json) else info_json
                
                if os.path.exists(json_file):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            game_data = json.load(f)
                            # 确保游戏ID是安全的
                            game_id = self.sanitize_id(game_data.get("title", game_dir))
                            game_data["id"] = game_id
                            
                            # 保存到缓存
                            self.game_cache[game_id] = game_data
                            
                            # 如果游戏URL不在进度中，添加到进度
                            game_url = game_data.get("url", "")
                            if game_url and game_url not in progress["processed_games"]:
                                progress["processed_games"].append(game_url)
                                
                            # 如果是从info.json加载的，创建game.json以便后续使用
                            if json_file == info_json and not os.path.exists(game_json):
                                with open(game_json, 'w', encoding='utf-8') as gf:
                                    json.dump(game_data, gf, ensure_ascii=False, indent=2)
                                    
                    except Exception as e:
                        self.logger.error(f"加载游戏数据失败 {game_dir}: {str(e)}")
        
        self.logger.info(f"已加载 {len(self.game_cache)} 个游戏数据到缓存")
        return progress

    def save_progress(self, progress):
        """保存爬取进度"""
        try:
            # 添加缓存统计信息到进度数据
            progress["cache_stats"] = {
                "total_games": len(self.game_cache),
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress, f, ensure_ascii=False, indent=2)
            self.logger.debug(f"已保存进度和缓存统计信息，当前缓存游戏数：{len(self.game_cache)}")
        except Exception as e:
            self.logger.error(f"保存进度失败: {str(e)}")

    def scroll_to_load_all_games(self):
        """滚动页面加载所有游戏"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        games_count = 0
        no_change_count = 0
        max_no_change = 3  # 连续3次没有新内容就认为加载完成
        
        # 创建进度条
        pbar = tqdm(desc="加载游戏列表", unit="个")
        
        # 创建WebDriverWait对象
        wait = WebDriverWait(self.driver, 10)
        
        while True:
            # 滚动到页面底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # 使用显式等待，等待新游戏加载
            try:
                # 记录当前游戏数量
                current_count = len(self.driver.find_elements(By.CSS_SELECTOR, '.Listed__Game'))
                
                # 如果游戏数量没有变化，尝试通过等待DOM变化来检测新内容
                if current_count == games_count:
                    # 等待新游戏加载或超时
                    start_time = time.time()
                    while time.time() - start_time < 3:  # 最多等待3秒
                        new_count = len(self.driver.find_elements(By.CSS_SELECTOR, '.Listed__Game'))
                        if new_count > current_count:
                            current_count = new_count
                            break
                        # 短暂等待，避免过度消耗CPU
                        time.sleep(0.2)
                
            except Exception as e:
                self.logger.debug(f"等待新游戏加载时出错: {str(e)}")
            
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
        self.logger.info(f"页面滚动完成，共加载 {games_count} 个游戏")

    def update_index(self, games: List[Dict]):
        """批量更新游戏索引文件"""
        if not games:
            return
            
        self.logger.debug(f"正在批量更新索引，游戏数量: {len(games)}")
        index_file = "games/metadata/index.json"
        
        # 读取现有索引
        if os.path.exists(index_file):
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    index = json.load(f)
            except Exception as e:
                self.logger.error(f"读取索引文件失败: {str(e)}")
                index = {
                    "lastUpdated": "",
                    "games": [],
                    "categories": []
                }
        else:
            index = {
                "lastUpdated": "",
                "games": [],
                "categories": []
            }
        
        # 创建ID到索引的映射，加速查找
        game_map = {game["id"]: i for i, game in enumerate(index["games"])}
        
        # 批量更新游戏列表
        updated_count = 0
        added_count = 0
        
        for game in games:
            # 读取统计数据
            stats_file = f"games/metadata/{game['id']}/stats.json"
            if os.path.exists(stats_file):
                try:
                    with open(stats_file, "r", encoding="utf-8") as f:
                        stats = json.load(f)
                except Exception as e:
                    self.logger.warning(f"读取游戏统计数据失败: {game['id']} - {str(e)}")
                    stats = {"rating": 0, "plays": 0}
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
            
            # 检查是否已存在并更新
            if game["id"] in game_map:
                index_pos = game_map[game["id"]]
                index["games"][index_pos].update(game_index)
                updated_count += 1
            else:
                index["games"].append(game_index)
                game_map[game["id"]] = len(index["games"]) - 1
                added_count += 1
        
        # 更新分类信息
        category_map = {}
        for game in index["games"]:
            cat = game.get("category", "")
            if cat:
                if cat not in category_map:
                    category_map[cat] = {
                        "id": self.sanitize_id(cat),
                        "name": cat,
                        "count": 0
                    }
                category_map[cat]["count"] += 1
        
        index["categories"] = list(category_map.values())
        index["lastUpdated"] = time.strftime("%Y-%m-%d")
        
        # 保存索引
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        try:
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
            self.logger.info(f"索引已更新: 添加 {added_count} 个新游戏, 更新 {updated_count} 个现有游戏")
        except Exception as e:
            self.logger.error(f"保存索引文件失败: {str(e)}")
            
    def get_thread_driver(self):
        """获取当前线程的WebDriver实例"""
        thread_id = threading.get_ident()
        
        with self.driver_lock:
            if thread_id not in self.local_drivers:
                self.logger.debug(f"为线程 {thread_id} 创建新的WebDriver实例")
                # 创建新的WebDriver实例
                chrome_options = Options()
                chrome_options.add_argument("--headless=new")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument('--ignore-certificate-errors')
                chrome_options.add_argument('--ignore-ssl-errors')
                chrome_options.add_argument('--log-level=3')
                chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
                
                service = Service(ChromeDriverManager().install())
                self.local_drivers[thread_id] = webdriver.Chrome(service=service, options=chrome_options)
            
            return self.local_drivers[thread_id]
            
    def close_thread_drivers(self):
        """关闭所有线程的WebDriver实例"""
        with self.driver_lock:
            for thread_id, driver in self.local_drivers.items():
                try:
                    driver.quit()
                    self.logger.debug(f"已关闭线程 {thread_id} 的WebDriver实例")
                except Exception as e:
                    self.logger.error(f"关闭线程 {thread_id} 的WebDriver实例时出错: {str(e)}")
            
            # 清空驱动程序字典
            self.local_drivers.clear()

    def process_game_task(self, game, progress):
        """处理单个游戏爬取任务，用于并发执行"""
        game_id = self.sanitize_id(game["title"])
        result = {
            "success": False,
            "game_info": None,
            "error": None
        }
        
        try:
            # 检查游戏是否在缓存中（再次检查是为了避免任务提交后缓存更新的情况）
            with self.cache_lock:
                if game_id in self.game_cache:
                    self.logger.debug(f"[线程任务] 使用缓存数据: {game['title']}")
                    result["success"] = True
                    result["game_info"] = self.game_cache[game_id]
                    return result
            
            # 检查是否已处理过该游戏
            with self.progress_lock:
                if game["url"] in progress["processed_games"]:
                    self.logger.debug(f"[线程任务] 跳过已处理的游戏: {game['title']}")
                    result["success"] = True
                    return result
            
            self.logger.info(f"[线程任务] 处理游戏: {game['title']}")
            
            # 爬取游戏详情，使用线程专用WebDriver
            retry_count = 0
            while retry_count < self.max_retries:
                try:
                    game_info = self.crawl_game_detail(game["url"], game["title"], use_thread_driver=True)
                    if game_info:
                        result["success"] = True
                        result["game_info"] = game_info
                        
                        # 线程安全地更新进度
                        with self.progress_lock:
                            if game["url"] not in progress["processed_games"]:
                                progress["processed_games"].append(game["url"])
                                progress["last_game"] = game["url"]
                        
                        # 线程安全地添加到缓冲区
                        with self.buffer_lock:
                            self.game_buffer.append(game_info)
                        
                        # 线程安全地更新统计信息
                        with self.stats_lock:
                            self.stats["success"] += 1
                    else:
                        with self.stats_lock:
                            self.stats["failed"] += 1
                    break
                except Exception as e:
                    retry_count += 1
                    error_msg = f"处理游戏失败 (尝试 {retry_count}/{self.max_retries}): {str(e)}"
                    self.logger.error(error_msg)
                    result["error"] = error_msg
                    
                    if retry_count >= self.max_retries:
                        with self.stats_lock:
                            self.stats["failed"] += 1
            
            return result
            
        except Exception as e:
            error_msg = f"游戏任务处理异常: {str(e)}"
            self.logger.error(error_msg)
            result["error"] = error_msg
            
            with self.stats_lock:
                self.stats["failed"] += 1
            
            return result

if __name__ == "__main__":
    crawler = GameCrawler()
    crawler.crawl() 