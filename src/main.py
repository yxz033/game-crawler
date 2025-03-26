import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from src.core.crawler import GameCrawler

def main():
    try:
        crawler = GameCrawler()
        crawler.crawl()
    except KeyboardInterrupt:
        print("\n用户中断爬虫运行")
    except Exception as e:
        print(f"\n爬虫运行出错: {str(e)}")
    finally:
        if hasattr(crawler, 'driver'):
            crawler.driver.quit()
        print("爬虫运行完成,程序退出!")
        sys.exit(0)

if __name__ == "__main__":
    main() 