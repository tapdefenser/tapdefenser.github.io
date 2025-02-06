from tools import *
from parse_data import *
import json

if __name__ == "__main__":
    v_list = str_read("ground_unit_links.json")
    v_list = json.loads(v_list)
    for v_type in v_list:
        v_html = str_read(f"./html/{v_type}.html")
        data = parse_ground_data(v_html, v_type)
        save_text(json.dumps(data, indent=4), f"json/{v_type}.json")