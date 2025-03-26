# Game Crawler

这是一个用于爬取在线游戏网站的爬虫程序。目前支持从 Addicting Games 网站爬取游戏信息。

## 功能特点

- 自动爬取游戏列表和详情信息
- 下载并转换游戏缩略图为WebP格式
- 保存游戏元数据(标题、描述、控制说明等)
- 支持游戏在线预览和测试

## 项目结构

```
.
├── src/                    # 源代码目录
│   ├── core/              # 核心功能模块
│   │   └── crawler.py     # 爬虫实现
│   ├── models/            # 数据模型
│   │   └── game.py       # 游戏模型
│   └── utils/            # 工具函数
│       └── parser.py     # HTML解析器
├── games/                 # 游戏数据目录
│   ├── metadata/         # 游戏元数据
│   │   └── index.json    # 游戏索引
│   ├── assets/          # 游戏资源(图片等)
│   └── test.html        # 游戏测试页面
└── requirements.txt      # 项目依赖
```

## 安装说明

1. 克隆仓库:
```bash
git clone https://github.com/YOUR_USERNAME/game-crawler.git
cd game-crawler
```

2. 创建并激活虚拟环境:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. 安装依赖:
```bash
pip install -r requirements.txt
```

## 使用说明

1. 运行爬虫:
```bash
python src/main.py
```

2. 启动测试服务器:
```bash
python -m http.server 8000
```

3. 访问测试页面:
打开浏览器访问 `http://localhost:8000/games/test.html?id=游戏ID`

## 注意事项

- 需要安装Chrome浏览器
- 确保良好的网络连接
- 遵守目标网站的robots.txt规则
- 合理控制爬取频率

## 许可证

MIT License 