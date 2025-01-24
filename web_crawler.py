import requests
from fake_useragent import UserAgent
import time
from tools import *
base_url = "https://wiki.warthunder.com/"

import json
from bs4 import BeautifulSoup
def get_dynamic_headers():
    """生成动态请求头，包含随机UA和时效性参数"""
    ua = UserAgent(browsers=['edge', 'chrome'])
    return {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'priority': 'u=0, i',
        'sec-ch-ua': f'"Microsoft Edge";v="131", "Chromium";v="131", "Not A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',  # 可动态修改平台
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': ua.random  # 动态生成UA
    }

def get_ground_data():
    # 手动创建Session对象
    s = requests.Session()
    
    try:
        
        ground_url = "/ground"
        # 自动携带更新的cookies发起请求
        response = s.get(
            base_url + ground_url,
            headers=get_dynamic_headers(),
            timeout=15
        )
        print("载具页获取成功！")
        print("Cookies:", s.cookies.get_dict())
        html_content = response.text
        save_text(html_content, 'ground.txt')

        soup = BeautifulSoup(html_content, 'html.parser')
    
        # 查找所有 <a> 标签
        links = soup.find_all('a', class_='wt-tree_item-link')
        
        # 提取 href 属性中包含 /unit/ 的链接
        unit_links = [link['href'] for link in links if link['href'].startswith('/unit/')]

        save_text(json.dumps(unit_links), 'ground_unit_links.json')
        
        response = s.get(
            "https://wiki.warthunder.com/unit/us_t29",
            headers=get_dynamic_headers(),
            timeout=15
        )
        print("载具详情获取成功！")
        print("Cookies:", s.cookies.get_dict())
        
        save_text(response.text, 'us_t29.txt')
        
        # 检查授权状态
        if response.status_code == 403:
            raise Exception("触发反爬机制，需要更新验证策略")
            
        return response.text
    
    finally:
        # 手动关闭Session
        s.close()

# 执行示例
if __name__ == "__main__":
    try:
        start = time.time()
        html_data = get_ground_data()
        #print(html_data)
        print(f"成功获取数据，耗时：{time.time()-start:.2f}s")
        # 此处添加数据处理逻辑...
        
    except Exception as e:
        print(f"请求失败: {str(e)}")