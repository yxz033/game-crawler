# Game Portal Development TODO

## 1. 爬虫系统开发

### 技术栈选择
- Python 3.8+
- Playwright (用于浏览器自动化)
- aiohttp (用于异步请求)
- pillow (用于图片处理)

### 功能实现
1. 主页游戏信息爬取
   - 游戏名称
   - 静态预览图
   - GIF动态图
   - 游戏链接
   - 基础信息(分类、评分等)

2. 游戏详情页爬取
   - iframe嵌入代码
   - 评分和评分人数
   - 评论内容
   - 标签(Tags)
   - 分类(Category)
   - 游戏描述
   - 游戏说明
   - 内容分级
   - 发布日期
   - 开发者信息

3. 文件管理系统
   ```
   games/
   ├── metadata/
   │   ├── game1/
   │   │   ├── info.json      # 游戏基本信息
   │   │   ├── comments.json  # 评论数据
   │   │   └── stats.json     # 统计数据
   │   └── game2/
   ├── images/
   │   ├── game1/
   │   │   ├── preview.jpg    # 静态预览图
   │   │   ├── preview.gif    # 动态预览图
   │   │   └── screenshots/   # 游戏截图
   │   └── game2/
   └── cache/                 # 爬虫缓存数据
   ```

4. 错误处理和重试机制
   - 请求失败重试
   - 数据验证
   - 错误日志记录
   - 断点续传

## 2. 自动更新系统

### 技术栈选择
- Node.js
- chokidar (文件监控)
- Playwright (iframe测试)

### 功能实现
1. 文件监控系统
   - 监控games目录变化
   - 检测新增/删除/修改
   - 触发相应处理流程

2. 数据处理流程
   - 解析新增游戏数据
   - 验证数据完整性
   - 更新数据库/状态
   - 生成必要的页面

3. iframe测试系统
   ```typescript
   interface IframeTest {
     url: string;
     timeout: number;
     retries: number;
     checks: {
       loading: boolean;
       interaction: boolean;
       performance: boolean;
     }
   }
   ```

4. 自动化流程
   - 检测新游戏
   - 测试iframe可用性
   - 自动生成游戏页面
   - 更新分类页面
   - 更新主页展示

## 3. 系统集成

### 配置管理
1. 爬虫配置
   ```yaml
   crawler:
     interval: 24h
     concurrency: 5
     retries: 3
     timeout: 30s
   ```

2. 监控配置
   ```yaml
   watcher:
     paths:
       - games/metadata
       - games/images
     ignored: ['*.tmp', '.git']
     interval: 1000
   ```

3. 测试配置
   ```yaml
   iframe_test:
     timeout: 10s
     retries: 2
     checks:
       - load_time
       - interaction
       - performance
   ```

### 日志系统
- 爬虫运行日志
- 文件变更日志
- 测试结果日志
- 错误追踪日志

### 监控告警
- 爬虫异常告警
- 测试失败告警
- 系统资源告警
- 数据异常告警

## 4. 开发计划

### Phase 1: 爬虫系统
- [ ] 基础爬虫框架搭建
- [ ] 主页游戏信息爬取
- [ ] 详情页数据爬取
- [ ] 图片和资源下载
- [ ] 数据存储格式设计
- [ ] 错误处理机制实现

### Phase 2: 自动更新系统
- [ ] 文件监控系统实现
- [ ] 数据处理流程开发
- [ ] iframe测试系统开发
- [ ] 页面自动生成功能
- [ ] 增量更新机制

### Phase 3: 系统集成
- [ ] 配置系统开发
- [ ] 日志系统实现
- [ ] 监控告警集成
- [ ] 系统测试和优化
- [ ] 文档编写

## 5. 注意事项

### 性能考虑
- 使用异步编程提高爬虫效率
- 实现合理的缓存机制
- 优化文件监控性能
- 控制资源占用

### 安全考虑
- 遵守网站robots.txt
- 控制请求频率
- 保护敏感信息
- 数据备份机制

### 可维护性
- 模块化设计
- 完善的错误处理
- 详细的日志记录
- 清晰的代码文档

### 扩展性
- 支持多数据源
- 插件化设计
- 配置驱动
- API接口预留

## 6. 爬虫系统数据规格 (基于实际网页分析调整)

### 文件系统结构
```
public/
└── games/
    ├── metadata/                 # 游戏元数据
    │   ├── [game-id]/           # 使用游戏ID作为文件夹名
    │   │   ├── info.json        # 基本信息
    │   │   └── stats.json       # 统计数据
    │   └── index.json           # 所有游戏的索引
    └── assets/                  # 游戏相关资源
        └── [game-id]/          # 使用相同的游戏ID
            ├── thumbnail.webp   # 静态预览图 (16:9)
            ├── preview.webp     # 动态预览图 (可选)
            └── screenshots/     # 游戏截图文件夹
                ├── 1.webp      # 截图1
                ├── 2.webp      # 截图2
                └── ...         # 更多截图
```

### 数据格式规范 (基于实际可获取数据)

1. info.json 格式
```json
{
  "id": "string",              // 游戏唯一标识符 (URL slug)
  "title": "string",           // 游戏标题
  "description": "string",     // 游戏描述
  "url": "string",            // iframe URL (以@开头表示外部链接)
  "developer": "string",       // 开发者名称
  "category": "string",        // 主分类
  "tags": ["string"],         // 标签数组
  "controls": {               // 控制说明
    "keyboard": ["string"],    // 键盘控制
    "mouse": ["string"],      // 鼠标控制
    "touch": ["string"]       // 触摸控制
  },
  "thumbnailUrl": "string",   // 相对路径: /games/assets/[game-id]/thumbnail.webp
  "previewUrl": "string",     // 相对路径: /games/assets/[game-id]/preview.webp
  "screenshots": ["string"],  // 截图相对路径数组
  "features": ["string"],     // 游戏特性
  "device": {                 // 设备支持
    "mobile": boolean,        // 移动设备支持
    "desktop": boolean        // 桌面设备支持
  },
  "addedDate": "string",      // 添加日期 (YYYY-MM-DD)
  "lastUpdated": "string"     // 最后更新日期 (YYYY-MM-DD)
}
```

2. stats.json 格式
```json
{
  "id": "string",           // 游戏ID
  "plays": number,          // 游玩次数
  "rating": number,         // 评分 (0-5)
  "ratingCount": number,    // 评分人数
  "lastUpdated": "string"   // 统计更新时间
}
```

3. index.json 格式
```json
{
  "lastUpdated": "string",  // 索引更新时间
  "games": [
    {
      "id": "string",      // 游戏ID
      "title": "string",   // 游戏标题
      "category": "string", // 主分类
      "rating": number,    // 评分
      "plays": number,     // 游玩次数
      "thumbnailUrl": "string", // 缩略图路径
      "added": "string"    // 添加日期
    }
  ],
  "categories": [          // 分类信息
    {
      "id": "string",     // 分类ID
      "name": "string",   // 分类名称
      "count": number    // 游戏数量
    }
  ]
}
```

### 图片规格要求 (基于实际网页分析)

1. 缩略图 (thumbnail.webp)
- 格式: WebP (更好的压缩比)
- 尺寸: 保持原始比例，宽度不超过800px
- 质量: 85%
- 最大文件大小: 150KB

2. 预览图 (preview.webp)
- 格式: WebP
- 尺寸: 与缩略图相同
- 质量: 85%
- 最大文件大小: 300KB
- 注意: 不是所有游戏都有动态预览

3. 截图 (screenshots/*.webp)
- 格式: WebP
- 尺寸: 保持原始比例，宽度不超过1920px
- 质量: 90%
- 最大文件大小: 500KB
- 数量: 实际可获取数量（通常1-4张）

### 数据采集重点

1. 游戏嵌入
- iframe URL格式和参数
- 必要的API调用
- 跨域处理方案

2. 游戏信息
- 基础信息从游戏卡片获取
- 详细信息从详情页获取
- 控制说明从游戏说明获取

3. 统计数据
- 实时评分和游玩次数
- 定期更新机制
- 数据验证机制

### 错误处理策略

1. 必需数据缺失
- title: 使用ID生成临时标题
- description: 使用简短的默认描述
- thumbnail: 使用默认图片
- category: 归类为"Others"

2. 可选数据缺失
- preview: 跳过不处理
- screenshots: 使用缩略图代替
- controls: 使用通用说明
- features: 留空数组

3. 数据格式问题
- URL: 添加必要的前缀
- 日期: 使用采集时间
- 评分: 默认为0
- 计数: 默认为0

### 数据更新策略

1. 增量更新
- 每小时检查新游戏
- 每天更新统计数据
- 每周更新游戏信息
- 每月更新所有数据

2. 数据验证
- 检查URL可访问性
- 验证图片完整性
- 确认数据格式
- 检查必需字段

3. 备份策略
- 每日增量备份
- 每周完整备份
- 保留30天历史
- 记录更新日志