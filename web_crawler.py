import requests
from fake_useragent import UserAgent
import time
from tools import *
import json
from bs4 import BeautifulSoup
import re
from parse_data import *

base_url = "https://wiki.warthunder.com/"

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

def check_now_unit():
    try:
        now = eval(str_read('now_unit.txt'))
        return now
    except:
        save_text('0', 'now_unit.txt')
        return 0

def init_session(get_ground_list=False):
    s = requests.Session()
    ground_url = "/ground"
        # 自动携带更新的cookies发起请求
    response = s.get(
        base_url + ground_url,
        headers=get_dynamic_headers(),
        timeout=15
    )
    print("session获取成功！")
    print("Cookies:", s.cookies.get_dict())
    if get_ground_list:
        html_content = response.text
        save_text(html_content, 'ground.txt')
        soup = BeautifulSoup(html_content, 'html.parser')
        # 查找所有 <a> 标签
        links = soup.find_all('a', class_='wt-tree_item-link')
        # 提取 href 属性中包含 /unit/ 的链接
        unit_links = [link['href'] for link in links if link['href'].startswith('/unit/')]
        unit_list = [s[6:] for s in unit_links if len(s) > 6]
        save_text(json.dumps(unit_list), 'ground_unit_links.json')
        return s, unit_list
    return s

def auto_get_ground_data(now_unit):
    s,unit_list = init_session(get_ground_list=True)
    start = time.time()
    for i in range(now_unit, len(unit_list)):
        ground_type = unit_list[i]
        response = s.get(
            f"https://wiki.warthunder.com/unit/{ground_type}",
            headers=get_dynamic_headers(),
            timeout=15
        )
        print("载具详情获取成功！")
        print("Cookies:", s.cookies.get_dict())
        html = response.text
        save_text(html, f'html/{ground_type}.html')
        #解码
        data = parse_ground_data(html,ground_type)
        
        save_text(json.dumps(data, indent=4), f'json/{ground_type}.json')
        # 检查授权状态
        if response.status_code != 200:
            print(f"授权有效时长：{time.time()-start:.2f}s")
            print("授权已过期")
            start = time.time()
            tries =3
            s = init_session()
            i-=1
            tries -= 1
            if tries == 0:
                print("授权已过期，程序退出")
                break
            continue

        save_text(str(i), 'now_unit.txt')

# 执行示例
if __name__ == "__main__":
    start = time.time()
    html_data = init_session(get_ground_list=True)
    auto_get_ground_data(check_now_unit())
    
