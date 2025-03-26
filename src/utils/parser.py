from bs4 import BeautifulSoup
import re
from typing import List, Dict
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.models.game import Game
import logging

class HtmlParser:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.base_url = "https://www.addictinggames.com"

    def parse_game_cards(self, html_content: str) -> List[Game]:
        """
        解析游戏卡片
        :param html_content: HTML内容
        :return: 游戏列表
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            print(f"开始解析HTML内容,长度: {len(html_content)}")
            
            # 使用更精确的选择器
            selector = 'div.Flex.Flex--fit > a.GameTile.AgGameTile'
            game_elements = soup.select(selector)
            print(f"\n使用选择器 '{selector}' 找到 {len(game_elements)} 个元素")
            
            if game_elements:
                # 打印第一个元素的HTML结构
                print(f"\n第一个游戏卡片的HTML结构:")
                print(game_elements[0].prettify())
            
            games = []
            for element in game_elements:
                try:
                    # 获取游戏标题
                    title_element = element.select_one('.GameTile__Description')
                    if title_element:
                        title = title_element.text.strip()
                        print(f"\n找到游戏: {title}")
                    else:
                        print("未找到标题元素")
                        continue
                        
                    # 获取游戏URL
                    url = element.get('href')
                    if url:
                        url = url if url.startswith('http') else self.base_url + url
                        print(f"URL: {url}")
                    else:
                        print("未找到URL")
                        continue
                        
                    # 获取缩略图
                    thumbnail_element = element.select_one('img.GameTileVideoThumbnail__Poster')
                    thumbnail = thumbnail_element.get('src') if thumbnail_element else None
                    if thumbnail:
                        print(f"缩略图: {thumbnail}")
                    else:
                        print("未找到缩略图")
                    
                    # 获取视频源
                    video_element = element.select_one('video.GameTileVideoThumbnail__Video source')
                    video = video_element.get('src') if video_element else None
                    if video:
                        print(f"视频源: {video}")
                    else:
                        print("未找到视频源")
                    
                    # 创建游戏对象
                    game = Game(
                        title=title,
                        url=url,
                        thumbnail=thumbnail,
                        video=video
                    )
                    games.append(game)
                    
                except Exception as e:
                    print(f"解析游戏卡片时出错: {str(e)}")
                    continue
            
            print(f"\n总共找到 {len(games)} 个游戏")
            return games
            
        except Exception as e:
            print(f"解析HTML时出错: {str(e)}")
            return []

    def parse_game_list(self, html_content: str) -> List[Game]:
        """
        解析游戏列表
        :param html_content: HTML内容
        :return: 游戏列表
        """
        return self.parse_game_cards(html_content)

    def parse_game_cards(self, html_content: str) -> List[Dict]:
        """
        解析游戏卡片数据
        :param html_content: HTML内容
        :return: 游戏卡片列表
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        games = []

        # 打印HTML内容的一部分用于调试
        print("HTML content preview:", html_content[:1000])

        # 尝试不同的选择器
        game_cards = soup.find_all('a', class_='GameThumbLinkDesktop') or \
                    soup.find_all('a', class_='GameThumbLinkMobile') or \
                    soup.find_all('div', class_='GameThumb') or \
                    soup.find_all('div', class_='game-thumb')

        print(f"找到{len(game_cards)}个游戏卡片")

        for card in game_cards:
            try:
                # 尝试不同的选择器组合来获取游戏信息
                title_elem = card.find('div', class_='GameThumbTitleContainer') or \
                           card.find('div', class_='title') or \
                           card.find('h2') or \
                           card.find('h3')
                
                img_elem = card.find('img', class_='GameThumbImage') or \
                          card.find('img')
                
                video_elem = card.find('video')

                game = {
                    'title': title_elem.text.strip() if title_elem else "未知游戏",
                    'url': card.get('href', '') if card.name == 'a' else card.find('a').get('href', '') if card.find('a') else "",
                    'thumbnail': img_elem['src'] if img_elem and 'src' in img_elem.attrs else "",
                    'video': video_elem.find('source')['src'] if video_elem and video_elem.find('source') else ""
                }
                games.append(game)
                print(f"解析到游戏: {game['title']}")
            except Exception as e:
                self.logger.error(f"解析游戏卡片时出错: {str(e)}")
                continue

        return games 