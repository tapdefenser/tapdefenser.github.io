import requests
from fake_useragent import UserAgent
import time
from tools import *
import json
from bs4 import BeautifulSoup
import re
from parse_data import *
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import threading
from threading import Lock

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
            tries =4
            s = init_session()
            i-=1
            tries -= 1
            if tries == 0:
                print("授权已过期，程序退出")
                break
            continue

        save_text(str(i), 'now_unit.txt') #更新now_unit

# 用于任务状态跟踪和互斥访问
condition = threading.Condition()
task_status = {}  # {task_index: (success, future)}
lock = threading.Lock()

def auto_get_ground_data_async(now_unit,max_worker = 5):
    def process_unit(i, unit_list, session):
        ground_type = unit_list[i]
        try:
            response = session.get(
                f"https://wiki.warthunder.com/unit/{ground_type}",
                headers=get_dynamic_headers(),
                timeout=15
            )
            if response.status_code != 200:
                print(f"获取{ground_type}详情失败，状态码：{response.status_code}")
                return i, False
            
            html = response.text
            save_text(html, f'html/{ground_type}.html')
            data = parse_ground_data(html, ground_type)
            save_text(json.dumps(data, indent=4), f'json/{ground_type}.json')
            
            return i, True
        except Exception as e:
            print(f"处理单元{i}时出错: {e}")
            return i, False

    # 初始化
    s, unit_list = init_session(get_ground_list=True)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_worker)  # 调整线程数以适应你的需求
    futures = []
    tries_map = {}
    global task_status

    # 提交任务
    for i in range(now_unit, len(unit_list)):
        future = executor.submit(process_unit, i, unit_list, s)
        futures.append((future, i))
        tries_map[i] = 4  # 初始化重试次数

    # 等待任务完成
    for future, index in futures:
        try:
            result_i, success = future.result()
            with condition:
                # 更新任务状态
                task_status[result_i] = (success, future)

                # 检查是否按顺序完成
                current_running_index = now_unit
                while current_running_index <= result_i:
                    if current_running_index not in task_status or not task_status[current_running_index][0]:
                        print(f"任务{result_i}需等待任务{current_running_index}完成")
                        condition.wait()  # 阻塞，等待任务current_running_index完成
                    else:
                        current_running_index += 1

                # 更新 now_unit
                if success:
                    save_text(str(result_i + 1), 'now_unit.txt')  # 更新now_unit为下一个
                    print(f"{result_i + 1} done")
                    condition.notify_all()  # 通知其他等待的任务

                elif tries_map[result_i] > 0:
                    # 重试任务
                    tries_map[result_i] -= 1
                    new_future = executor.submit(process_unit, result_i, unit_list, init_session())
                    futures.append((new_future, result_i))
                    print(f"任务{result_i}重试次数剩余: {tries_map[result_i]}")
                else:
                    print(f"任务{result_i}多次尝试失败，程序退出")
                    executor.shutdown(wait=False)
                    exit(1)
        except Exception as e:
            print(f"任务{index}处理异常: {e}")

    executor.shutdown()

# 执行示例
if __name__ == "__main__":
    start = time.time()
    html_data = init_session(get_ground_list=True)
    auto_get_ground_data_async(check_now_unit(),max_worker=10)
    