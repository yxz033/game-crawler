from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

class Game:
    def __init__(self, title: str, url: str, thumbnail: str = None, video: str = None):
        self.title = title
        self.url = url
        self.thumbnail = thumbnail
        self.video = video
        
    def __str__(self):
        return f"Game(title='{self.title}', url='{self.url}')"
        
    def __repr__(self):
        return self.__str__()

@dataclass
class Game:
    id: str                     # 游戏唯一标识符
    title: str                  # 游戏标题
    url: str                    # 游戏链接
    thumbnail_url: str          # 缩略图URL
    category: str               # 主分类
    tags: List[str] = None      # 标签列表
    description: str = ""       # 游戏描述
    rating: float = 0.0         # 评分
    plays: int = 0             # 游玩次数
    added_date: str = None     # 添加日期
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "thumbnailUrl": self.thumbnail_url,
            "category": self.category,
            "tags": self.tags or [],
            "description": self.description,
            "rating": self.rating,
            "plays": self.plays,
            "addedDate": self.added_date or datetime.now().strftime("%Y-%m-%d")
        } 