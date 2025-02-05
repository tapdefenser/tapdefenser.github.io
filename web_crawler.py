import requests
from fake_useragent import UserAgent
import time
from tools import *
import json
from bs4 import BeautifulSoup
import re

base_url = "https://wiki.warthunder.com/"
v_type="germ_leopard_2a4m_can"

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

        ground_type=v_type
        response = s.get(
            f"https://wiki.warthunder.com/unit/{ground_type}",
            headers=get_dynamic_headers(),
            timeout=15
        )
        print("载具详情获取成功！")
        print("Cookies:", s.cookies.get_dict())
        save_text(response.text, f'{ground_type}.html')
        
        # 检查授权状态
        if response.status_code == 403:
            raise Exception("触发反爬机制，需要更新验证策略")
            
        return response.text
    
    finally:
        # 手动关闭Session
        s.close()


from bs4 import BeautifulSoup
import re

def parse_unit_basic_info(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    result = {
        "name": v_type,
        "nation": v_type.split('_')[0],
        "rank": None,
        "battle_rating": {
            "AB": None,
            "RB": None,
            "SB": None
        },
        "role": None,
        "images": {
            "country_flag": None,
            "unit_image": None
        }
    }

    header = soup.find('div', class_='game-unit_header')
    if not header:
        return result

    # 解析等级
    rank_tag = header.find('div', class_='game-unit_rank')
    if rank_tag:
        rank_value = rank_tag.find('div', class_='game-unit_card-info_value').get_text(strip=True)
        rank_mapping = {'I':1, 'II':2, 'III':3, 'IV':4, 'V':5, 'VI':6, 'VII':7, 'VIII':8, 'IX':9, 'X':10}
        result["rank"] = rank_mapping.get(rank_value, None)

    # 解析战斗评级
    br_block = header.find('div', class_='game-unit_br')
    if br_block:
        for item in br_block.find_all('div', class_='game-unit_br-item'):
            mode = item.find('div', class_='mode').get_text(strip=True)
            value = item.find('div', class_='value').get_text(strip=True)
            try:
                if mode in result["battle_rating"]:
                    result["battle_rating"][mode] = float(value)
            except ValueError:
                pass

    # 解析游戏国家和角色
    for item in header.find_all('div', class_='game-unit_card-info_item'):
        title = item.find('div', class_='game-unit_card-info_title').get_text(strip=True)
        value_div = item.find('div', class_='game-unit_card-info_value')
        
        if title == "Main role":
            role_div = item.find('div', class_='text-truncate')
            if role_div:
                result["role"] = role_div.get_text(strip=True)

    # 解析研发和购买成本（修复部分）
    for item in header.find_all('div', class_='game-unit_card-info_item'):
        title = item.find('div', class_='game-unit_card-info_title').get_text(strip=True)
        value_div = item.find('div', class_='game-unit_card-info_value')
        
        if not value_div:
            continue
            
        # 提取数值部分（第一个div）
        value_tag = value_div.find('div')
        if not value_tag:
            continue
            
        # 清理并转换数值
        raw_value = value_tag.get_text(strip=True).replace(',', '')
        if raw_value.isdigit():
            num_value = int(raw_value)
            if title == "Research":
                result["research"]["rp"] = num_value
            elif title == "Purchase":
                result["purchase"]["sl"] = num_value

    # 解析图片信息
    flag_img = header.find('img', class_='game-unit_template-flag')
    if flag_img:
        result["images"]["country_flag"] = flag_img['src']
    
    unit_img = header.find('img', class_='game-unit_template-image')
    if unit_img:
        result["images"]["unit_image"] = unit_img['src']

    return result
def parse_armor_data(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    result = {
        "survivability": {
            "armor": {},
            "features": [],
            "visibility": None,
            "crew": None
        },
        "support_systems": {
            "features": []
        }
    }

    # Step 1: 定位到 Survivability 模块的根元素
    survivability_block = soup.find('div', class_='block-header', string=lambda x: x and 'Survivability and armour' in x)
    if survivability_block:
        survivability_block = survivability_block.find_parent('div', class_='block mb-3')
    else:
        return result  # 如果找不到模块，直接返回

    # Step 2: 解析装甲数据（限定在 Survivability 模块内）
    armor_block = survivability_block.find('div', class_='game-unit_chars')
    if armor_block:
        for line in armor_block.find_all('div', class_='game-unit_chars-subline'):
            armor_type = line.find('span')
            if armor_type:
                armor_type = armor_type.get_text(strip=True)
                values = line.find('span', class_='game-unit_chars-value')
                if values:
                    # 精确提取数值（处理可能的空格和单位）
                    cleaned_values = [
                        v.strip().replace(' mm', '') 
                        for v in values.get_text(strip=True).split('/')
                    ]
                    if len(cleaned_values) == 3:
                        result["survivability"]["armor"][armor_type.lower()] = {
                            "front": int(cleaned_values[0]),
                            "side": int(cleaned_values[1]),
                            "back": int(cleaned_values[2])
                        }

        # Step 3: 解析可见度和乘员（同样限定在模块内）
        for line in armor_block.find_all('div', class_='game-unit_chars-line'):
            header = line.find('span', class_='game-unit_chars-header')
            value = line.find('span', class_='game-unit_chars-value')
            if header and value:
                header_text = header.get_text(strip=True)
                value_text = value.get_text(strip=True)
                if "Visibility" in header_text:
                    result["survivability"]["visibility"] = int(value_text.replace('%', ''))
                elif "Crew" in header_text:
                    result["survivability"]["crew"] = int(value_text.split()[0])

    # Step 4: 解析生存能力特性（限定在模块内）
    features_section = survivability_block.find('div', class_='game-unit_features')
    if features_section:
        for btn in features_section.find_all('button', class_='game-unit_feature'):
            feature_name = btn.find('span')
            if feature_name:
                result["survivability"]["features"].append(feature_name.get_text(strip=True))

    # Step 5: 解析支持系统（限定在模块内）
    support_section = survivability_block.find('div', class_='form-text', string='Support systems')
    if support_section:
        features_div = support_section.find_next_sibling('div', class_='game-unit_features')
        if features_div:
            for btn in features_div.find_all('button', class_='game-unit_feature'):
                feature_name = btn.find('span')
                if feature_name:
                    result["support_systems"]["features"].append(feature_name.get_text(strip=True))

    return result

def parse_mobility_data(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    result = {
        "mobility": {
            "features": [],
            "max_speed": {},
            "power_to_weight_ratio": {},
            "engine_power": {},
            "weight": None
        }
    }

    mobility_block = soup.find('div', class_='block-header', string=lambda x: x and 'Mobility' in x)
    if mobility_block:
        mobility_block = mobility_block.find_parent('div', class_='block mb-3')
    else:
        return result

    # 解析特性（保持不变）
    features_section = mobility_block.find('div', class_='game-unit_features')
    if features_section:
        for btn in features_section.find_all('button', class_='game-unit_feature'):
            feature_name = btn.find('span')
            if feature_name:
                result["mobility"]["features"].append(feature_name.get_text(strip=True))

    chars_block = mobility_block.find('div', class_='game-unit_chars')
    if not chars_block:
        return result

    # 解析最大速度（保持不变）
    max_speed_block = chars_block.find('div', class_='game-unit_chars-block')
    if max_speed_block:
        for line in max_speed_block.find_all('div', class_='game-unit_chars-subline'):
            direction = line.find('span')
            if direction:
                direction = direction.get_text(strip=True).lower()
                value = line.find('span', class_='game-unit_chars-value')
                if value:
                    speed_values = [
                        v.get_text(strip=True) 
                        for v in value.find_all('span', class_=lambda x: x and x.startswith('show-char'))
                    ]
                    if len(speed_values) >= 2:
                        result["mobility"]["max_speed"][direction] = {
                            "rb": float(speed_values[0]),
                            "ab": float(speed_values[1])
                        }

    # 修复后的动力系统解析
    power_blocks = chars_block.find_all('div', class_='game-unit_chars-block')
    if len(power_blocks) > 1:
        power_block = power_blocks[1]

        # 功率重量比（保持不变）
        power_to_weight_line = power_block.find('div', class_='game-unit_chars-line')
        if power_to_weight_line:
            value = power_to_weight_line.find('span', class_='game-unit_chars-value')
            if value:
                power_values = [
                    v.get_text(strip=True) 
                    for v in value.find_all('span', class_=lambda x: x and x.startswith('show-char'))
                ]
                if len(power_values) >= 4:
                    result["mobility"]["power_to_weight_ratio"] = {
                        "rb_ref": float(power_values[0]),
                        "rb_basic": float(power_values[1]),
                        "ab_ref": float(power_values[2]),
                        "ab_basic": float(power_values[3])
                    }

        # 修复发动机功率解析
        engine_power_line = None
        for subline in power_block.find_all('div', class_='game-unit_chars-subline'):
            if subline.find('span', string='Engine power'):
                engine_power_line = subline
                break

        if engine_power_line:
            value = engine_power_line.find('span', class_='game-unit_chars-value')
            if value:
                engine_values = [
                    v.get_text(strip=True).replace(',', '') 
                    for v in value.find_all('span', class_=lambda x: x and x.startswith('show-char'))
                ]
                if len(engine_values) == 4:
                    result["mobility"]["engine_power"] = {
                        "rb_ref": int(engine_values[0]),
                        "rb_basic": int(engine_values[1]),
                        "ab_ref": int(engine_values[2]),
                        "ab_basic": int(engine_values[3])
                    }

        # 修复重量解析
        weight_line = None
        for subline in power_block.find_all('div', class_='game-unit_chars-subline'):
            if subline.find('span', string='Weight'):
                weight_line = subline
                break

        if weight_line:
            value = weight_line.find('span', class_='game-unit_chars-value')
            if value:
                # 直接提取文本内容并清理
                weight_text = ''.join(value.find_all(string=True, recursive=False)).strip()
                if weight_text:
                    try:
                        result["mobility"]["weight"] = float(weight_text.replace(' t', ''))
                    except ValueError:
                        pass

    return result

def parse_optics_data(html_content):
    def parse_popover_data(popover_html):
        popover_soup = BeautifulSoup(popover_html, 'html.parser')
        resolution = {}
        
        specs_rows = popover_soup.find_all(class_="gunit_specs-table_row")
        if len(specs_rows) >= 2:
            values = [div.get_text(strip=True) for div in specs_rows[1].find_all("div")]
            if len(values) == 3:
                resolution = {
                    "gunner": values[0],
                    "commander": values[1],
                    "driver": values[2]
                }
        # 返回解析结果，若没有解析出resolution，则该键不会出现在返回字典中
        return {"resolution": resolution} if resolution else {}

    soup = BeautifulSoup(html_content, 'html.parser')
    result = {"features": [], "specs": {}}
    
    optics_block = soup.find('div', class_='block-header', string='Optics')
    if not optics_block:
        return result
    optics_block = optics_block.find_parent('div', class_='block')
    
    # 初始化光学设备列表
    result["specs"]["optical_devices"] = []
    
    # 解析特性
    features_div = optics_block.find('div', class_='game-unit_features')
    seen_devices = set()
    if features_div:
        for btn in features_div.find_all('button'):
            device_name = btn.find('span').get_text(strip=True)
            if device_name not in seen_devices:  # 避免重复添加相同的设备
                seen_devices.add(device_name)
                popover_data = parse_popover_data(btn['data-feature-popover'])
                feature_entry = {"name": device_name}
                feature_entry.update(popover_data)  # 只有当resolution存在时才会添加该键
                result["features"].append(feature_entry)
    
    # 解析规格表
    specs_table = optics_block.find('div', class_='gunit_specs-table')
    if specs_table:
        zoom_row = specs_table.find_all(class_='gunit_specs-table_row')[1]
        result["specs"]["optics_zoom"] = {
            "gunner": zoom_row.div.get_text(strip=True),
            "commander": zoom_row.div.find_next_sibling('div').get_text(strip=True),
            "driver": zoom_row.div.find_next_sibling('div').find_next_sibling('div').get_text(strip=True)
        }
        
        # 解析光学设备
        device_btns = specs_table.find_all('button', class_='gunit_specs-table_btn')
        for btn in device_btns:
            device_name = btn.get_text(strip=True)
            if device_name not in seen_devices:
                seen_devices.add(device_name)
                popover_data = parse_popover_data(btn['data-feature-popover'])
                optical_device_entry = {"name": device_name}
                optical_device_entry.update(popover_data)  # 只有当resolution存在时才会添加该键
                result["specs"]["optical_devices"].append(optical_device_entry)
    
    return result

def parse_armaments_data(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    result = []
    
    def safe_convert(value):
        try:
            return float(value) if '.' in value else int(value)
        except:
            return value

    armaments_block = soup.find('div', id='weapon')
    if not armaments_block:
        return {"armaments": []}

    for weapon_block in armaments_block.find_all('div', class_='game-unit_weapon'):
        weapon_data = {
            "name": weapon_block.find('span', class_='game-unit_weapon-title').get_text(strip=True),
            "features": [],
            "specs": {},
            "available_ammunition": [],
            "available_belts": []
        }

        # 解析特性
        features_div = weapon_block.find('div', class_='game-unit_features')
        if features_div:
            weapon_data["features"] = [btn.find('span').get_text(strip=True) for btn in features_div.find_all('button')]

        # 解析规格
        for block in weapon_block.find_all('div', class_='game-unit_chars-block'):
            # 特殊处理炮塔旋转速度
            header_line = block.find('div', class_='game-unit_chars-line')
            if header_line:
                header = header_line.find('span', class_='game-unit_chars-header').get_text(strip=True)
                if header == "Turret Rotation Speed":
                    for subline in block.find_all('div', class_='game-unit_chars-subline'):
                        sub_header = subline.find('span').get_text(strip=True)
                        value_span = subline.find('span', class_='game-unit_chars-value')
                        if value_span:
                            value = ' '.join(value_span.stripped_strings)
                            key = f"turret_rotation_speed_{sub_header.lower()}"
                            weapon_data["specs"][key] = value
                    continue

            # 处理Reload特殊结构
            reload_header = block.find('span', class_='game-unit_chars-header', string='Reload')
            if reload_header:
                subline = block.find('div', class_='game-unit_chars-subline')
                if subline:
                    reload_value = subline.find('span', class_='game-unit_chars-value').get_text(strip=True)
                    weapon_data["specs"]["reload"] = reload_value
                continue

            # 常规规格处理
            for line in block.find_all('div', class_='game-unit_chars-line'):
                header = line.find('span', class_='game-unit_chars-header')
                value = line.find('span', class_='game-unit_chars-value')
                if header and value:
                    key = header.get_text(strip=True).lower().replace(' ', '_')
                    weapon_data["specs"][key] = value.get_text(strip=True)

            for subline in block.find_all('div', class_='game-unit_chars-subline'):
                parts = list(subline.stripped_strings)
                if len(parts) >= 2:
                    key = parts[0].lower().replace(' ', '_') if parts[0] else 'unknown'
                    value = parts[-1]
                    weapon_data["specs"][key] = value

        # 解析弹药和弹链
        for accordion in weapon_block.find_all('div', class_='accordion'):
            for item in accordion.find_all('div', class_='accordion-item'):
                if 'ammunition' in item.button.text.lower():
                    # 解析弹药数据
                    for btn in item.find_all('button', {'data-feature-popover': True}):
                        popover_html = btn['data-feature-popover']
                        popover_soup = BeautifulSoup(popover_html, 'html.parser')
                        
                        # 提取基本信息
                        ammo_name = popover_soup.find('span').text.strip()
                        details = {
                            "type": btn.find_next('td').text.strip() if btn.find_next('td') else None
                        }
                        
                        # 提取详细参数
                        for detail_line in popover_soup.find_all('div', class_='game-unit_chars-line'):
                            key = detail_line.find('div', class_='game-unit_chars-header').text.strip().lower().replace(' ', '_')
                            value = detail_line.find('div', class_='game-unit_chars-value').text.strip()
                            details[key] = value
                        
                        # 提取穿深数据
                        armor_pen = {}
                        table = popover_soup.find('table')
                        if table:
                            for row in table.find_all('tr')[1:]:  # 跳过表头
                                cells = [cell.text.strip() for cell in row.find_all(['th', 'td'])]
                                if len(cells) >= 4:
                                    distance = cells[0].replace(' ', '').lower()
                                    armor_pen[distance] = {
                                        "0°": safe_convert(cells[1]),
                                        "30°": safe_convert(cells[2]),
                                        "60°": safe_convert(cells[3])
                                    }
                        
                        weapon_data["available_ammunition"].append({
                            "name": ammo_name,
                            "details": details,
                            "armor_penetration": armor_pen
                        })

                elif 'belts' in item.button.text.lower():
                    # 解析弹链数据
                    for btn in item.find_all('button', {'data-feature-popover': True}):
                        popover_html = btn['data-feature-popover']
                        popover_soup = BeautifulSoup(popover_html, 'html.parser')
                        
                        # 提取基本信息
                        belt_name = popover_soup.find('span').text.strip()
                        belt_type = popover_soup.find('div', style="font-size: .9em").text.split(':')[1].split('<')[0].strip()
                        
                        # 提取穿深数据
                        armor_pen = {}
                        table = popover_soup.find('table')
                        if table:
                            for row in table.find_all('tr')[1:]:  # 跳过表头
                                cells = [cell.text.strip() for cell in row.find_all(['th', 'td'])]
                                if len(cells) >= 4:
                                    distance = cells[0].replace(' ', '').lower()
                                    armor_pen[distance] = {
                                        "0°": safe_convert(cells[1]),
                                        "30°": safe_convert(cells[2]),
                                        "60°": safe_convert(cells[3])
                                    }
                        
                        weapon_data["available_belts"].append({
                            "name": belt_name,
                            "type": belt_type,
                            "armor_penetration": armor_pen
                        })

        result.append(weapon_data)
    
    return {"armaments": result}



def safe_convert(text):
    """将文本转换为整数，如果无法转换则返回0"""
    try:
        return int(text.replace('—', '0'))
    except ValueError:
        return 0

def parse_economy_data(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    result = {
        "repair_cost": {},
        "crew_training": {
            "basic": 0,
            "experts": 0,
            "aces": 0,
            "research_aces": 0
        },
        "rewards": {
            "SL": {"AB": 0, "RB": 0, "SB": 0},
            "RP": 0
        },
        "modifications": {
            "by_tier": {}
        }
    }

    def clean_number(text):
        """清洗数字并移除所有非数字字符"""
        cleaned_text = re.sub(r"[^\d]", "", text) if text else ""
        return int(cleaned_text) if cleaned_text else 0

    # 解析所有维修费用区块
    def parse_repair_costs():
        # 查找所有可能包含维修费用的区块
        blocks = soup.find_all('div', class_='game-unit_chars-block')
        
        for block in blocks:
            header = block.find('span', class_='game-unit_chars-header')
            if not header:
                continue
            
            header_text = header.get_text(strip=True)
            
            # 标准维修费用（AB/RB/SB）
            if "Repair cost" in header_text:
                for subline in block.find_all('div', class_='game-unit_chars-subline'):
                    mode = subline.find('span').get_text(strip=True)
                    values = subline.find('span', class_='game-unit_chars-value')
                    if values:
                        numbers = [clean_number(v) for v in re.split(r"[→/]", values.get_text())]
                        if len(numbers) >= 2:
                            result["repair_cost"][mode] = {
                                "basic": numbers[0],
                                "reference": numbers[1]
                            }
            
            # 装甲部件维修费用（Hull/Turret）
            elif "Armor repair" in header_text:
                for subline in block.find_all('div', class_='game-unit_chars-subline'):
                    parts = subline.find_all('span')
                    if len(parts) < 2:
                        continue
                    
                    part_type = parts[0].get_text(strip=True)
                    values = re.findall(r'\d+', parts[1].get_text())
                    
                    if len(values) >= 2:
                        result["repair_cost"][part_type] = {
                            "basic": int(values[0]),
                            "reference": int(values[1])
                        }

    # 解析乘员训练
    def parse_crew_training():
        crew_block = soup.find('span', string='Crew training')
        if crew_block:
            crew_block = crew_block.find_parent('div', class_='game-unit_chars-block')
            # 基础训练费用
            base_cost = crew_block.find('span', class_='game-unit_chars-value')
            if base_cost:
                result["crew_training"]["basic"] = clean_number(base_cost.get_text())
            
            # 其他训练类型
            for item in crew_block.find_all('div', class_='game-unit_chars-subline'):
                key = item.find('span').get_text(strip=True).lower().replace(' ', '_')
                value = item.find('span', class_='game-unit_chars-value')
                if value:
                    result["crew_training"][key] = clean_number(value.get_text())

    # 解析奖励系统
    def parse_rewards():
        reward_block = soup.find('span', class_='game-unit_chars-header', string='Reward multiplier')
        if reward_block:
            block = reward_block.find_parent('div', class_='game-unit_chars-block')
            lines = block.find_all('div', class_='game-unit_chars-line')

            # 解析SL奖励
            if len(lines) >= 2:
                sl_values = lines[1].find('span', class_='game-unit_chars-value')
                if sl_values:
                    values = [clean_number(v) for v in re.split(r'/', sl_values.get_text())]
                    if len(values) >= 3:
                        result["rewards"]["SL"] = {
                            "AB": values[0],
                            "RB": values[1],
                            "SB": values[2]
                        }

            # 解析RP奖励
            if len(lines) >= 3:
                rp_value = lines[2].find('span', class_='game-unit_chars-value')
                if rp_value:
                    result["rewards"]["RP"] = clean_number(rp_value.get_text())

    # 解析改装件系统
    def parse_modifications():
        mods_container = soup.find('div', class_='game-unit_mods-container')
        if mods_container:
            for table in mods_container.find_all('table'):
                rows = table.find_all('tr')[1:]  # 跳过表头
                for tier, row in enumerate(rows, start=1):
                    for cell in row.find_all('td'):
                        btn = cell.find('button', class_='game-unit_mod')
                        if not btn:
                            continue

                        mod_data = {
                            "id": btn.get('data-mod-id', ''),
                            "name": btn.find('span').get_text(strip=True),
                            "tier": tier,
                            "requirements": list(filter(None, [btn.get('data-mod-req-id')])),
                            "costs": {
                                "research": 0,
                                "purchase": {"SL": 0, "GE": 0}
                            }
                        }

                        popover = BeautifulSoup(btn.get('data-feature-popover', ''), 'html.parser')
                        for line in popover.find_all('div', class_='game-unit_mod-char-line'):
                            spans = line.find_all('span')
                            if len(spans) < 2:
                                continue

                            img = spans[1].find('img')
                            currency = img.get('alt') if img else ''
                            value = clean_number(spans[1].get_text())

                            if "Research" in spans[0].get_text():
                                mod_data["costs"]["research"] = value
                            elif currency == "SL":
                                mod_data["costs"]["purchase"]["SL"] = value
                            elif currency == "GE":
                                mod_data["costs"]["purchase"]["GE"] = value

                        if tier not in result["modifications"]["by_tier"]:
                            result["modifications"]["by_tier"][tier] = []
                        result["modifications"]["by_tier"][tier].append(mod_data)

    # 执行所有解析流程
    parse_repair_costs()
    parse_crew_training()
    parse_rewards()
    parse_modifications()

    return result

# 执行示例
if __name__ == "__main__":
    start = time.time()
    #html_data = get_ground_data()
    #print(html_data)
    #print(f"成功获取数据，耗时：{time.time()-start:.2f}s")
    # 此处添加数据处理逻辑...
    # 使用示例
    html = str_read(f"{v_type}.html")
    data = {"unit_basic_info":parse_unit_basic_info(html),"survivability":parse_armor_data(html),"mobility":parse_mobility_data(html),"optics":parse_optics_data(html),"armaments":parse_armaments_data(html)}
    save_text(json.dumps(data, indent=4), f'{v_type}.json')
    
