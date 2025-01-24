import requests
from fake_useragent import UserAgent
import time
from tools import *
import json
from bs4 import BeautifulSoup
import re

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

        ground_type="us_m1a1_hc_abrams"
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
        "name": None,
        "nation": None,
        "type": None,
        "rank": None,
        "battle_rating": {
            "AB": None,
            "RB": None,
            "SB": None
        },
        "game_nation": None,
        "role": None,
        "research": {
            "rp": None,
            "currency": "RP"
        },
        "purchase": {
            "sl": None,
            "currency": "SL"
        },
        "images": {
            "country_flag": None,
            "unit_image": None
        }
    }

    header = soup.find('div', class_='game-unit_header')
    if not header:
        return result

    # 解析名称
    name_tag = header.find('div', class_='game-unit_name')
    if name_tag:
        result["name"] = name_tag.get_text(strip=True).replace('&nbsp;', ' ')

    # 解析国家/类型
    nation_tag = header.find('div', class_='game-unit_nation')
    if nation_tag:
        result["nation"] = nation_tag.get_text(strip=True)

    # 解析等级
    rank_tag = header.find('div', class_='game-unit_rank')
    if rank_tag:
        rank_value = rank_tag.find('div', class_='game-unit_card-info_value').get_text(strip=True)
        rank_mapping = {'I':1, 'II':2, 'III':3, 'IV':4, 'V':5, 'VI':6, 'VII':7}
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
        
        if title == "Game nation":
            img_tag = item.find('img')
            if img_tag and 'src' in img_tag.attrs:
                match = re.search(r'country_(\w+)', img_tag['src'])
                if match:
                    result["game_nation"] = match.group(1).upper()
        
        elif title == "Main role":
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
        resolution = {"gunner": None, "commander": None, "driver": None}
        
        # 提取分辨率数据
        specs_rows = popover_soup.find_all(class_="gunit_specs-table_row")
        if len(specs_rows) >= 2:
            values = [div.get_text(strip=True) for div in specs_rows[1].find_all("div")]
            if len(values) == 3:
                resolution = {
                    "gunner": values[0],
                    "commander": values[1],
                    "driver": values[2]
                }
        
        return {
            "resolution": resolution
        }
    soup = BeautifulSoup(html_content, 'html.parser')
    result = {"features": [], "specs": {}}
    
    # 定位Optics模块
    optics_block = soup.find('div', class_='block-header', string='Optics')
    if not optics_block:
        return result
    optics_block = optics_block.find_parent('div', class_='block')
    
    # 解析特性
    features_div = optics_block.find('div', class_='game-unit_features')
    if features_div:
        for btn in features_div.find_all('button'):
            popover_data = parse_popover_data(btn['data-feature-popover'])
            result["features"].append({
                "name": btn.find('span').get_text(strip=True),
                **popover_data
            })
    
    # 解析规格表
    specs_table = optics_block.find('div', class_='gunit_specs-table')
    if specs_table:
        # 光学变焦
        zoom_row = specs_table.find_all(class_='gunit_specs-table_row')[1]
        result["specs"]["optics_zoom"] = {
            "gunner": zoom_row.div.get_text(strip=True),
            "commander": zoom_row.div.find_next_sibling('div').get_text(strip=True),
            "driver": zoom_row.div.find_next_sibling('div').find_next_sibling('div').get_text(strip=True)
        }
        
        # 光学设备
        result["specs"]["optical_devices"] = []
        device_btns = specs_table.find_all('button', class_='gunit_specs-table_btn')
        for btn in device_btns:
            popover_data = parse_popover_data(btn['data-feature-popover'])
            result["specs"]["optical_devices"].append({
                "name": btn.get_text(strip=True),
                **popover_data
            })
    
    return result

def parse_armaments_data(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    result = []

    # 定位Armaments模块
    armaments_block = soup.find('div', id='weapon')
    if not armaments_block:
        return result

    # 解析每个武器
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
            weapon_data["features"] = [
                btn.find('span').get_text(strip=True)
                for btn in features_div.find_all('button')
            ]

        # 解析规格
        specs_blocks = weapon_block.find_all('div', class_='game-unit_chars-block')
        for block in specs_blocks:
            for line in block.find_all('div', class_='game-unit_chars-line'):
                header = line.find('span', class_='game-unit_chars-header')
                value = line.find('span', class_='game-unit_chars-value')
                
                # 检查header和value是否存在
                if header and value:
                    header_text = header.get_text(strip=True)
                    value_text = value.get_text(strip=True)
                    weapon_data["specs"][header_text.lower().replace(' ', '_')] = value_text

        # 解析可用弹药
        ammo_accordion = weapon_block.find('div', class_='accordion')
        if ammo_accordion:
            for item in ammo_accordion.find_all('div', class_='accordion-item'):
                table = item.find('table', class_='game-unit_belt-list')
                if table:
                    for row in table.find_all('tr')[1:]:  # 跳过表头
                        cells = row.find_all('td')
                        if len(cells) >= 7:
                            ammo_data = {
                                "name": cells[0].get_text(strip=True),
                                "type": cells[1].get_text(strip=True),
                                "armor_penetration": {
                                    "10m": int(cells[2].get_text(strip=True)),
                                    "100m": int(cells[3].get_text(strip=True)),
                                    "500m": int(cells[4].get_text(strip=True)),
                                    "1000m": int(cells[5].get_text(strip=True)),
                                    "1500m": int(cells[6].get_text(strip=True)),
                                    "2000m": int(cells[7].get_text(strip=True))
                                }
                            }
                            weapon_data["available_ammunition"].append(ammo_data)

        result.append(weapon_data)

    return {"armaments": result}

def parse_economy_data(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    result = {
        "repair_cost": {
            "AB": {"basic": 0, "reference": 0},
            "RB": {"basic": 0, "reference": 0},
            "SB": {"basic": 0, "reference": 0}
        },
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

    # 解析维修费用
    def parse_repair_cost():
        repair_block = soup.find('span', class_='game-unit_chars-header', string='Repair cost')
        if not repair_block:
            return

        block = repair_block.find_parent('div', class_='game-unit_chars-block')
        for subline in block.find_all('div', class_='game-unit_chars-subline'):
            mode_tag = subline.find('span')
            if not mode_tag:
                continue

            mode = mode_tag.get_text(strip=True)
            value_tag = subline.find('span', class_='game-unit_chars-value')
            if not value_tag:
                continue

            values = re.findall(r'[\d,]+', value_tag.get_text())
            if len(values) == 2:
                result["repair_cost"][mode] = {
                    "basic": int(values[0].replace(',', '')),
                    "reference": int(values[1].replace(',', ''))
                }

    # 解析乘员训练
    def parse_crew_training():
        crew_block = soup.find('span', class_='game-unit_chars-header', string='Crew training')
        if not crew_block:
            return

        block = crew_block.find_parent('div', class_='game-unit_chars-block')
        main_cost = block.find('span', class_='game-unit_chars-value')
        if main_cost:
            result["crew_training"]["basic"] = int(re.sub(r'\D', '', main_cost.get_text()))

        for subline in block.find_all('div', class_='game-unit_chars-subline'):
            key_tag = subline.find('span')
            value_tag = subline.find('span', class_='game-unit_chars-value')
            if not key_tag or not value_tag:
                continue

            key = key_tag.get_text(strip=True).lower().replace(' ', '_')
            value = re.sub(r'\D', '', value_tag.get_text())
            if value:
                result["crew_training"][key] = int(value)

    # 解析改装件系统
    def parse_modifications():
        mods_container = soup.find('div', class_='game-unit_mods-container')
        if not mods_container:
            return

        for table in mods_container.find_all('table'):
            # 每个表格内的行号即为层级（从1开始）
            for tier, row in enumerate(table.find_all('tr')[1:], start=1):  # 跳过表头
                for cell in row.find_all('td'):
                    btn = cell.find('button', class_='game-unit_mod')
                    if not btn:
                        continue

                    # 解析基础信息
                    mod_id = btn.get('data-mod-id', '')
                    req_id = btn.get('data-mod-req-id', '')
                    name = btn.find('span').get_text(strip=True)

                    # 解析详细信息
                    popover = BeautifulSoup(
                        btn['data-feature-popover'], 
                        'html.parser'
                    )
                    
                    # 初始化成本值
                    research_cost = 0
                    purchase_sl = 0
                    purchase_ge = 0

                    # 解析研究成本
                    for cost_line in popover.find_all('div', class_='game-unit_mod-char-line'):
                        parts = cost_line.find_all('span')
                        if len(parts) < 2:
                            continue

                        label = parts[0].get_text(strip=True)
                        value = re.sub(r'\D', '', parts[1].get_text())

                        if 'Research' in label:
                            research_cost = int(value) if value else 0
                        elif 'Purchase' in label:
                            if 'SL' in parts[1].get_text():
                                purchase_sl = int(value) if value else 0
                            elif 'GE' in parts[1].get_text():
                                purchase_ge = int(value) if value else 0

                    # 构建数据对象
                    mod_data = {
                        "id": mod_id,
                        "name": name,
                        "tier": tier,
                        "requirements": [req_id] if req_id else [],
                        "costs": {
                            "research": research_cost,
                            "purchase": {
                                "SL": purchase_sl,
                                "GE": purchase_ge
                            }
                        }
                    }

                    # 按层级存储
                    if tier not in result["modifications"]["by_tier"]:
                        result["modifications"]["by_tier"][tier] = []
                    result["modifications"]["by_tier"][tier].append(mod_data)

    # 执行解析流程
    parse_repair_cost()
    parse_crew_training()
    parse_modifications()

    return result

# 执行示例
if __name__ == "__main__":
    start = time.time()
    #html_data = get_ground_data()
    #print(html_data)
    print(f"成功获取数据，耗时：{time.time()-start:.2f}s")
    # 此处添加数据处理逻辑...
    # 使用示例
    html = str_read("us_m1a1_hc_abrams.html")
    data = {"unit_basic_info":parse_unit_basic_info(html),"survivability":parse_armor_data(html),"mobility":parse_mobility_data(html),"optics":parse_optics_data(html),"armaments":parse_armaments_data(html),"economy":parse_economy_data(html)}
    save_text(json.dumps(data, indent=4), 'us_m1a1_hc_abrams.json')

    
