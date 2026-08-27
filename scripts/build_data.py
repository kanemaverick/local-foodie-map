#!/usr/bin/env python3
"""
Local Foodie Map 数据构建管线。

输入: BV1D38n6nEy7 评论数据库 CSV
输出: public/data/restaurants.json + public/data/meta.json

流程:
  1. 读取可定位餐馆评论 locatable_restaurant_comments.csv
  2. 解析行政区(省/市/区县)、位置精度、菜品、餐馆类型、疑似停业
  3. 同店合并 -> 餐馆(聚合评论/点赞/菜品)
  4. (可选) 高德地理编码增强(AMAP_KEY), 回退行政区中心点
  5. 输出静态 JSON 与元信息索引 (--check 执行锚点自检)
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 评论数据库目录, 可用环境变量 LFM_DATA_DIR 覆盖
DATA_DIR = Path(os.environ.get(
    "LFM_DATA_DIR",
    "/Users/a1-6/Documents/mac相关/BV1D38n6nEy7_评论数据库"))
CACHE_DIR = ROOT / "data-cache"
OUT_DIR = ROOT / "public" / "data"

VIDEO_URL = "https://www.bilibili.com/video/BV1D38n6nEy7/"

# ---------------------------------------------------------------------------
# 正则资产（大部分复用自数据目录的 tag_restaurant_comments.py）
# ---------------------------------------------------------------------------

SHORT_TO_FULL_PROV = {
    "北京": "北京市", "天津": "天津市", "上海": "上海市", "重庆": "重庆市",
    "河北": "河北省", "山西": "山西省", "辽宁": "辽宁省", "吉林": "吉林省",
    "黑龙江": "黑龙江省", "江苏": "江苏省", "浙江": "浙江省", "安徽": "安徽省",
    "福建": "福建省", "江西": "江西省", "山东": "山东省", "河南": "河南省",
    "湖北": "湖北省", "湖南": "湖南省", "广东": "广东省", "广西": "广西壮族自治区",
    "海南": "海南省", "四川": "四川省", "贵州": "贵州省", "云南": "云南省",
    "西藏": "西藏自治区", "陕西": "陕西省", "甘肃": "甘肃省", "青海": "青海省",
    "宁夏": "宁夏回族自治区", "新疆": "新疆维吾尔自治区", "内蒙古": "内蒙古自治区",
    "香港": "香港特别行政区", "澳门": "澳门特别行政区", "台湾": "台湾省",
}
MUNICIPAL = {"北京市", "天津市", "上海市", "重庆市"}
# 全称在前，避免短形式抢先匹配
PROVINCE_FORMS = sorted(SHORT_TO_FULL_PROV.keys(), key=len, reverse=True)

CITY_ABBRS = (
    "广州深圳成都武汉西安南京杭州苏州长沙郑州济南青岛厦门福州泉州合肥昆明贵阳南宁海口"
    "兰州银川乌鲁木齐哈尔滨长春沈阳大连石家庄太原南昌无锡常州徐州温州宁波佛山东莞珠海"
    "中山惠州洛阳芜湖六盘水信阳台州柳州桂林遵义绵阳乐山宜宾南充达州自贡泸州内江眉山德阳遂宁雅安"
)
ABBR_CITY_RE = re.compile("(?:%s)" % "|".join(
    a for a in ["广州", "深圳", "成都", "武汉", "西安", "南京", "杭州", "苏州", "长沙", "郑州",
                "济南", "青岛", "厦门", "福州", "泉州", "合肥", "昆明", "贵阳", "南宁", "海口",
                "兰州", "银川", "乌鲁木齐", "哈尔滨", "长春", "沈阳", "大连", "石家庄", "太原",
                "南昌", "无锡", "常州", "徐州", "温州", "宁波", "佛山", "东莞", "珠海", "中山",
                "惠州", "洛阳", "芜湖", "六盘水", "信阳", "台州", "柳州", "桂林", "遵义", "绵阳",
                "乐山", "宜宾", "南充", "达州", "自贡", "泸州", "内江", "眉山", "德阳", "遂宁",
                "雅安"]))

ADMIN_CAND_RE = re.compile(r"[一-鿿]{1,9}?(?:区|县|旗|镇|乡|街道)")
TOWN_SUFFIXES = ("镇", "乡", "街道")
GENERIC_SPANS = {"上面", "下面", "里面", "外面", "左边", "右边", "旁边", "附近",
                 "这边", "那边", "哪里", "周边", "各区"}

ROAD_RE = re.compile(r"[一-鿿A-Za-z0-9]{1,14}(?:大道|大街|街道|胡同|路|街|巷|弄)")
# "路"前若是这些字/词, 多为普通叙述而非道路名
BAD_ROAD_PREFIX = set("的在去从往沿到过和与就都也很这那有一条每走绕同对忘说过")
FOREIGN_RE = re.compile(
    "(?:日本|京都|东京|大阪|名古屋|札幌|福冈|冲绳|奈良|神户|横滨|北海道|鎌倉|镰仓|"
    "首尔|首尔|釜山|济州岛|"
    "曼谷|清迈|普吉|芭提雅|新加坡|吉隆坡|槟城|沙巴|柔佛|新山|麻坡|越南芽庄|河内|胡志明市|"
    "岘港|金边|万象|仰光|加德满都|迪拜|阿布扎比|"
    "美国|洛杉矶|旧金山|湾区|西雅图|纽约|波士顿|芝加哥|休斯顿|德克萨斯|夏威夷|bellevue|"
    "加拿大|温哥华|多伦多|蒙特利尔|英国|伦敦|曼城|爱丁堡|巴黎|凯旋门|卢浮宫|马赛|"
    "德国|意大利|西班牙|荷兰|瑞士|瑞典|挪威|芬兰|丹麦|冰岛|捷克|奥地利|希腊|土耳其|"
    "法国|俄罗斯|印度尼西亚|印尼|菲律宾|柬埔寨|缅甸|老挝|尼泊尔|斯里兰卡|马尔代夫|"
    "东京|大阪城|柏林慕尼黑|法兰克福|米兰|罗马|巴塞罗那|阿姆斯特丹|苏黎世|维也纳|奥斯陆|"
    "斯德哥尔摩|哥本哈根|赫尔辛基|都柏林|里斯本|雅典|华沙|布拉格|布达佩斯|"
    "开罗|约翰内斯堡|开普敦|圣保罗|里约热内卢|布宜诺斯艾利斯|墨西哥城|利马|圣地亚哥|"
    "法兰克福|意大利|米兰|罗马|西班牙|巴塞罗那|葡萄牙|里斯本|荷兰|阿姆斯特丹|瑞士|苏黎世|"
    "奥地利维也纳|瑞典斯德哥尔摩|挪威奥斯陆|芬兰赫尔辛基|丹麦哥本哈根|澳洲|悉尼|墨尔本|布里斯班|"
    "新西兰奥克兰|埃及开罗|南非约翰内斯堡|巴西圣保罗|阿根廷布宜诺斯|墨西哥城)")
# 这些后缀说明前面提到的外国词是"菜式/风格", 不是实际在国外
FOREIGN_STYLE_GUARD_RE = re.compile(
    "(?:寿司|料理|烤肉|炸鸡|肉饼|风味|风情|风格|主题|进口|代购|零食|超市|面包|奶茶|"
    "咖啡|汉堡|披萨|牛排|拉面|便当|炒面|汤|馆|店|楼|街|路|味|菜|餐)")


def is_foreign(text_sq: str) -> bool:
    """命中外国地名且后面紧跟的不是 菜式/风格 词 -> 视为境外内容"""
    for m in FOREIGN_RE.finditer(text_sq):
        tail = text_sq[m.end(): m.end() + 6]
        if not FOREIGN_STYLE_GUARD_RE.match(tail):
            return True
    return False

# ---------------------------------------------------------------------------
# 唯一地名词典: 从行政区划表自动生成无后缀可识别词 (如 济宁/嘉祥/顺德)
# 仅保留全国唯一且不与常见口语冲突的词条, 匹配时前后不接中文判断降低误伤
# ---------------------------------------------------------------------------

NOUN_BLOCKLIST = {
    "市场", "东西", "上学", "大学", "中文", "天水", "光滑", "大方", "大方", "开平",
    "南方", "北方", "东城", "西城", "城区", "江南", "江北", "新华", "前进", "幸福",
}


class UniquePlaces:
    def __init__(self):
        self.city_stem = {}
        self.dist_stem = {}
        self.stem_to_kind = {}

    def build(self, rg: "Regions"):
        counter = Counter()
        entries = []
        for item in rg.raw:
            nm = squash(item["name"])
            if item["level"] == "city":
                stem = nm[:-1] if nm.endswith("市") else nm
                entries.append(("city", stem, item))
                counter[stem] += 1
            elif item["level"] == "district":
                stem = nm.rstrip("区县市旗") or nm
                entries.append(("dist", stem, item))
                counter[stem] += 1
        for kind, stem, item in entries:
            if len(stem) < 2 or stem in NOUN_BLOCKLIST:
                continue
            if counter[stem] != 1:          # 全国重名 -> 歧义, 不做后缀省略匹配
                continue
            if stem.endswith("省"):
                continue
            self.stem_to_kind.setdefault(stem, (kind, item))
        self.STEM_RE = re.compile("(" + "|".join(
            s for s in sorted(self.stem_to_kind.keys(), key=len, reverse=True)) + ")")

    def find(self, text_sq: str):
        out = []
        for m in self.STEM_RE.finditer(text_sq):
            prev_ok = m.start() == 0 or text_sq[m.start() - 1] not in (
                "的在去从往沿到过和与就都也很这那里有到边近")
            if prev_ok:
                kind, item = self.stem_to_kind[m.group()]
                out.append((m.start(), kind, item))
        return out


UNIQ = None
JUNCTION_RE = re.compile(r"(?:交叉口|十字路口|丁字路口|红绿灯(?:路口)?|路口)")
LANDMARK_RE = re.compile(
    "[一-鿿A-Za-z0-9]{1,18}?(?:广场|商场|市场|购物中心|万象城|万达广场|银泰城|大悦城|吾悦广场|"
    "小区|公馆|花园|公寓|家属院|家属区|宿舍|学校|大学|学院|中学|小学|幼儿园|医院|"
    "地铁站|火车站|高铁站|车站|客运站|公交站|公交车站|公园|大厦|大楼|写字楼|"
    "教堂|消防站|青少年宫|体育馆|博物馆|图书馆|景区|古镇|古城|码头|机场|菜市场|步行街)")
REL_RE = re.compile(
    "(?:斜对面|正对面|对面|旁边|隔壁|边上|附近|后边|背后|前面|门前|门口|左手边|右手边|楼上|楼下|巷子里)")
HOUSE_RE = re.compile(r"\d+\s*号(?:楼|院|栋|幢)?|\d+\s*弄|[A-H]\s*口")
PRECISE_HINT_RE = re.compile(
    r"(?:\d+\s*号|(?:东|西|南|北)(?:门|侧)[^。.，,]{0,10}(?:对面|旁边|附近)|正门(?:口?)|斜对面)")

FOOD_ALTS = [
    "羊肉粉", "牛肉粉", "螺蛳粉", "酸辣粉", "肥肠粉", "桂林米粉", "过桥米线", "砂锅米线",
    "土豆粉", "老友粉", "猪脚粉", "卷粉", "卤粉", "肠粉", "河粉", "粿条", "饵丝", "米干",
    "牛肉面", "羊肉面", "刀削面", "板面", "热干面", "担担面", "重庆小面", "兰州拉面",
    "油泼面", "臊子面", "杂酱面", "肥肠面", "排骨面", "爆肚面", "焖面", "拌面", "烩面",
    "饸饹面", "擀面皮", "凉皮", "秦镇米皮", "米皮",
    "煲仔饭", "叉烧饭", "黄焖鸡米饭", "猪脚饭", "隆江猪脚", "盖浇饭", "盖码饭", "木桶饭",
    "竹筒饭", "炒饭", "扬州炒饭",
    "肉夹馍", "烧饼", "火烧", "锅盔", "煎饼果子", "鸡蛋饼", "手抓饼", "酱香饼", "千层饼",
    "煎饼", "葱花饼",
    "小笼包", "灌汤包", "汤包", "生煎包", "生煎", "烧麦", "蒸饺", "水饺", "饺子", "馄饨",
    "扁食", "抄手", "云吞", "包子", "馒头", "花卷", "油条", "麻团", "糍粑", "锅贴", "春卷",
    "馅饼", "肉饼", "汤圆", "元宵", "粽子",
    "火锅", "串串香", "钵钵鸡", "冷锅串串", "冒菜", "麻辣烫", "麻辣香锅", "麻辣拌", "干锅",
    "砂锅", "烧烤", "烤串", "烤肉", "烤鱼", "铁板烧", "石板烤肉", "新疆炒米粉", "炒米粉",
    "小龙虾", "生蚝", "扇贝", "鲍鱼", "螃蟹", "大闸蟹", "虾滑", "海鲜", "河鲜", "剁椒鱼头",
    "酸菜鱼", "水煮鱼", "烤全羊", "大盘鸡", "椒麻鸡",
    "羊肉", "牛肉", "驴肉", "兔头", "牛杂", "羊杂", "猪脚", "猪蹄", "肥肠", "脑花", "鸭血",
    "毛肚", "酥肉", "烧腊", "叉烧", "烧鹅", "白切鸡", "盐焗鸡", "手撕鸡", "口水鸡",
    "卤味", "卤鹅", "鸭脖", "无骨鸡爪", "凤爪", "把子肉", "锅包肉", "溜肉段", "地三鲜",
    "铁锅炖", "酱骨头",
    "洋芋", "豆腐脑", "臭豆腐", "豆汁儿", "豆浆", "凉粉", "冰粉", "凉糕", "甜水面",
    "糖油果子", "蛋烘糕", "狼牙土豆", "锅巴土豆", "豆腐", "土豆", "豆花",
    "胡辣汤", "羊汤", "羊肉汤", "牛肉汤", "羊杂汤", "瓦罐汤", "筒骨汤",
    "糖水", "双皮奶", "姜撞奶", "杨枝甘露", "奶茶", "咖啡", "蛋糕", "甜品", "豆花",
    "豆腐花", "凉茶", "龟苓膏", "清补凉", "柠檬茶",
    "抓饭", "炒面", "黄面", "烤包子", "馕", "架子肉", "马肠子", "纳仁",
    "砂锅粥", "艇仔粥", "及第粥", "猪杂粥", "皮蛋瘦肉粥", "八宝粥", "瘦肉粥",
    "米豆腐", "绿豆粉", "花溪牛肉粉", "烙锅", "丝娃娃", "夺夺粉", "恋爱豆腐果", "豆腐圆子",
    "青岩豆腐", "脆哨", "肠旺面", "豆花面",
    "炸鸡", "汉堡", "披萨", "意面", "牛排", "寿司", "石锅拌饭", "紫菜包饭", "部队火锅",
    "年糕", "炒酸奶", "冰淇淋", "沙冰", "雪糕",
    "口味虾", "口味蛇", "嗦螺", "糖油粑粑", "捆鸡", "米粉肉",
    "自助餐", "盒饭", "盖饭", "早茶", "宵夜", "夜市小吃", "小吃",
]
FOOD_RE = re.compile("(" + "|".join(sorted(set(FOOD_ALTS), key=lambda s: -len(s))) + ")")

CLOSED_RE = re.compile(
    r"(?:关门了|关了门|倒闭了|倒闭|不开了|不干了|不做了|改做了|停业|歇业|结业|闭店|拆了|"
    r"搬走了|已经没了|再也没吃到|再也没喝到|再没吃到|再没喝到|找不到了|已经不在|关张|"
    r"宝藏店铺关了|店铺关了|转让了)")

STORE_TYPE_TOKENS = [
    "火锅店", "串串香店", "串串香", "冒菜店", "麻辣烫店", "麻辣烫", "烧烤摊", "烧烤店",
    "烤肉店", "烤鱼店", "面馆", "粉店", "米粉店", "米线店", "拉面馆", "牛肉面馆", "汤包店",
    "包子铺", "包子店", "饺子馆", "馄饨店", "烧腊店", "卤味店", "螺蛳粉店", "肠粉店",
    "粥铺", "粥店", "快餐店", "大排档", "小吃店", "早餐店", "早点铺", "奶茶店", "甜品店",
    "咖啡店", "羊汤馆", "羊肉馆", "牛肉馆", "菜馆", "饭店", "餐厅", "食堂", "烧饼铺",
    "凉皮店", "肉夹馍店", "炸鸡店", "汉堡店", "汤锅店", "豆花店", "糖水铺", "苍蝇馆子",
]
TYPE_TOKEN_RE = re.compile("(%s)" % "|".join(re.escape(t) for t in STORE_TYPE_TOKENS))
PLACE_SUFFIX_RE = re.compile("[一-鿿A-Za-z0-9]{2,10}?(?:店|馆|铺|摊|档)(?![:：，,。])")

TYPE_RULES = [
    ("火锅串串", ["火锅", "串串", "钵钵鸡", "冷锅"]),
    ("冒菜麻辣烫", ["冒菜", "麻辣烫", "麻辣拌", "麻辣香锅"]),
    ("烧烤烤肉", ["烧烤", "烤串", "烤肉", "铁板烧", "烙锅"]),
    ("粉面", ["面馆", "拉面", "板面", "米线", "米粉", "螺蛳粉", "肥肠粉", "热干面",
              "刀削面", "饸饹", "烩面", "臊子面", "小面", "汤面", "拌面"]),
    ("粤式茶点", ["烧腊", "叉烧", "烧鹅", "白切鸡", "盐焗鸡", "肠粉", "早茶", "茶楼",
                  "糖水", "双皮奶", "艇仔粥", "砂锅粥", "云吞面", "竹升面", "粿条"]),
    ("海鲜河鲜", ["海鲜", "河鲜", "小龙虾", "生蚝", "扇贝", "蟹", "鱼庄", "烤鱼", "鱼头"]),
    ("甜品饮品", ["甜品", "奶茶", "咖啡", "蛋糕", "烘焙", "冰室", "豆腐花", "凉茶",
                  "龟苓膏", "清补凉"]),
    ("牛羊肉汤锅", ["羊汤", "羊肉汤", "牛肉汤", "羊杂", "涮羊肉", "羊蝎子", "全羊", "驴肉"]),
    ("地方菜馆", ["川菜", "湘菜", "东北菜", "西北菜", "新疆菜", "云南菜", "贵州菜", "粤菜",
                  "客家菜", "潮汕菜", "农家菜", "家常菜", "菜馆", "饭店", "酒楼", "餐厅",
                  "炒菜", "私房菜", "土菜", "柴火鸡", "大盘鸡", "椒麻鸡"]),
    ("小吃快餐", ["小吃", "煎饼", "鸡蛋饼", "包子", "馒头", "烧饼", "火烧", "锅盔", "饺子",
                  "馄饨", "肉夹馍", "凉皮", "卷饼", "手抓饼", "灌汤包", "生煎", "锅贴",
                  "油条", "豆浆", "早餐", "早点", "夜宵", "夜市", "炸串", "卤味", "鸭脖",
                  "猪脚饭", "快餐", "食堂", "大排档", "炒饭", "炒粉", "炒面", "煲仔饭",
                  "黄焖鸡", "沙县"]),
]

DESCRIPTIVE_LANDMARK_RE = LANDMARK_RE


def clean_text(s: str) -> str:
    s = re.sub(r"\[[^\]]{1,12}\]", " ", s or "")          # [doge] 等表情占位
    s = re.sub(r"(?:回复\s*)?@[一-鿿\w\-]+\s*[:：]?", " ", s)
    s = re.sub(r"[\u200b\u3000]+", "", s)
    return s.strip()


def squash(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


# ---------------------------------------------------------------------------
# 行政区数据与解析
# ---------------------------------------------------------------------------

class Regions:
    def __init__(self):
        raw = json.load(open(CACHE_DIR / "regions_all.json", encoding="utf-8"))
        self.raw = raw
        self.prov_by_adcode = {}
        self.city_by_adcode = {}
        self.provinces = {}
        self.cities = defaultdict(list)          # 名称(含/不含'市') -> [item]
        self.districts = defaultdict(list)       # 名称/去后缀基名 -> [item]
        self.abbr_map = {}                       # 成都 -> 成都市item
        self.name_to_adcode = {}
        for it in raw:
            lv = it["level"]
            nm = squash(it["name"])
            it["_base"] = nm
            if lv == "province":
                self.prov_by_adcode[it["adcode"]] = it
                self.provinces[nm] = it
                self.name_to_adcode[nm] = it["adcode"]
            elif lv == "city":
                self.city_by_adcode[it["adcode"]] = it
                stem = nm[:-1] if nm.endswith("市") else nm
                self.cities[nm].append(it)
                self.cities[stem].append(it)
                self.abbr_map.setdefault(stem, it)
                self.abbr_map.setdefault(nm, it)
                self.name_to_adcode.setdefault(nm, it["adcode"])
            elif lv == "district":
                stem = nm.rstrip("区县市旗") or nm
                self.districts[nm].append(it)
                if stem != nm:
                    self.districts[stem].append(it)

    def parent_province(self, item):
        p = self.prov_by_adcode.get(item.get("parent"))
        if p:
            return p
        c = self.city_by_adcode.get(item.get("parent"))
        if c:
            return self.prov_by_adcode.get(c.get("parent"))
        return None

    def hierarchy(self, item):
        """returns (prov_full, city_full_or '', item_name)"""
        if item["level"] == "province":
            return item["name"], "", item["name"]
        if item["level"] == "city":
            p = self.parent_province(item)
            return (p["name"] if p else ""), item["name"], item["name"]
        c = self.city_by_adcode.get(item.get("parent"))
        p = self.parent_province(item)
        return ((p["name"] if p else "")), (c["name"] if c else ""), item["name"]

    def centroid(self, prov="", city="", dist=""):
        for pool, key in [(self.districts, dist), (self.cities, city),
                          ({}, prov)]:
            if not key:
                continue
            infos = pool.get(squash(key))
            if pool is self.cities and not infos:
                continue
            if infos:
                want_city = squash(city)
                best = None
                for inf in infos:
                    hz = self.hierarchy(inf)
                    if not want_city or hz[1] == want_city or not hz[1]:
                        best = inf
                        break
                cand = best or infos[0]
                if cand.get("lat"):
                    return float(cand["lat"]), float(cand["lng"])
        if prov:
            pv = self.provinces.get(SHORT_TO_FULL_PROV.get(prov, prov)) or \
                self.provinces.get(squash(prov))
            if pv:
                return float(pv["lat"]), float(pv["lng"])
        return None


RG = None  # 全局 Regions 实例


def resolve_admin_span(span: str):
    """匹配到的行政名片段可能带省市前缀(如 深圳市南山区); 尝试逐级截短后在字典中查找"""
    info = None
    n = len(span)
    for cut in range(0, max(1, n - 1)):
        sub = span[cut:]
        if len(sub) < 3:
            continue
        hits = RG.districts.get(sub)
        if hits:
            info = hits
            break
    return info


def parse_region(text_sq: str) -> dict:
    t = squash(text_sq)
    res = {"prov": "", "city": "", "dist": "", "town": ""}

    # --- 省份 ---
    prov_pos = []
    for form in RG.provinces.keys():
        idx = t.find(form)
        if idx >= 0:
            prov_pos.append((idx, form))
    for short in sorted(SHORT_TO_FULL_PROV.keys(), key=len, reverse=True):
        idx = t.find(short)
        if idx >= 0 and (idx, SHORT_TO_FULL_PROV[short]) not in prov_pos:
            overlapped = any(i <= idx < i + len(f) for i, f in prov_pos)
            if not overlapped:
                prov_pos.append((idx, SHORT_TO_FULL_PROV[short]))
    prov = ""
    if prov_pos:
        prov_pos.sort()
        prov = prov_pos[0][1]

    # --- 城市 ---
    city_hits = []
    for it in RG.raw:
        if it["level"] != "city":
            continue
        nm = it["_base"]
        idx = t.find(nm)
        if idx >= 0:
            city_hits.append((idx, it))
    for m in ABBR_CITY_RE.finditer(t):
        ab = m.group()
        it = RG.abbr_map.get(ab)
        if not it:
            continue
        if any(existing[1]["adcode"] == it["adcode"] for existing in city_hits):
            continue
        city_hits.append((m.start(), it))

    # --- 区县候选 ---
    dist_hits = []
    town_spans = []
    for m in ADMIN_CAND_RE.finditer(t):
        name = m.group()
        if name in GENERIC_SPANS or len(name) <= 2:
            continue
        base = name.rstrip("区县市旗街道乡镇") or name
        infos = RG.districts.get(name) or RG.districts.get(base) or resolve_admin_span(name)
        if infos:
            dist_hits.append((m.start(), name, infos))
        elif name.endswith(TOWN_SUFFIXES) and len(name) >= 4:
            cleaned = strip_admin_prefix(name)
            if len(cleaned) >= 3 and re.search(r"(?:镇|乡|街道)$", cleaned):
                town_spans.append((m.start(), cleaned))

    city = None
    # --- 唯一地名词典补充 (无后缀城市/区县名, 如 济宁、嘉祥、顺德) ---
    if UNIQ is not None:
        known_city_ads = {c[1]["adcode"] for c in city_hits}
        known_dist_ads = {inf["adcode"] for _, _, ii in dist_hits for inf in ii}
        for pos, kind, item in UNIQ.find(t):
            if kind == "city":
                if item["adcode"] not in known_city_ads:
                    city_hits.append((pos, item))
                    known_city_ads.add(item["adcode"])
            else:
                if item["adcode"] not in known_dist_ads:
                    dist_hits.append((pos, item["_base"], [item]))
                    known_dist_ads.add(item["adcode"])

    # 选择城市: 优先属于已定省份的
    if prov:
        in_prov = [(i, c) for i, c in city_hits
                   if _prov_of(c)["name"] == prov]
        pool = in_prov or city_hits
    else:
        pool = city_hits
    if pool:
        pool.sort(key=lambda x: x[0])
        city = pool[0][1]
        hp = _prov_of(city)
        if hp and hp["name"] != prov:
            prov = hp["name"]

    # --- 区县选择 ---
    dist_item = None
    if dist_hits:
        def dscore(entry):
            _, _, infos = entry
            sc = -min(len(infos) * 5, 30)
            best_local = -999
            for inf in infos:
                hz = RG.hierarchy(inf)
                s = 0
                if city and hz[1] == city["name"]:
                    s = 100
                elif prov and hz[0] == prov:
                    s = 60
                elif not city and not prov and len(infos) > 0:
                    s = -10 * len(infos)
                best_local = max(best_local, s)
            return sc + best_local
        dist_hits.sort(key=lambda e: (-dscore(e), e[0]))
        if dscore(dist_hits[0]) >= 40 or (not city and not prov and len(dist_hits[0][2]) == 1):
            dist_item = dist_hits[0]

    if dist_item is not None:
        infos = dist_item[2]
        disp = None
        for inf in infos:
            hz = RG.hierarchy(inf)
            if city and hz[1] == city["name"]:
                disp, chosen_hz = inf["name"], hz
                break
        if disp is None and prov:
            for inf in infos:
                hz = RG.hierarchy(inf)
                if hz[0] == prov:
                    disp, chosen_hz = inf["name"], hz
                    break
        if disp is None:
            disp, chosen_hz = infos[0]["_base"], RG.hierarchy(infos[0])
        res["dist"] = disp
        hz = chosen_hz
        if hz[0]:
            prov = hz[0]
        if hz[1]:
            res["city"] = hz[1]
            city = RG.cities[hz[1]][0] if hz[1] in RG.cities else city

    if city is not None and not res["city"]:
        res["city"] = city["name"]
    res["prov"] = prov or ""

    # --- 镇/乡/街道 补充（区县级信息，但不在 gazetteer） ---
    if town_spans and (res["city"] or res["dist"]):
        pos, name = town_spans[0]
        if not res["dist"]:
            res["dist"] = name
        else:
            res["town"] = name
    return res


def _prov_of(item) -> dict:
    return RG.parent_province(item) or {}


# ---------------------------------------------------------------------------
# 字段提取
# ---------------------------------------------------------------------------

def classify_type(text_sq: str) -> str:
    t = squash(text_sq)
    for cat, kws in TYPE_RULES:
        for kw in kws:
            if kw in t:
                return cat
    return ""


def extract_dishes(msg: str) -> list:
    t = squash(msg)
    cnt = Counter(m.group() for m in FOOD_RE.finditer(t))
    names = [n for n, _ in cnt.most_common()]
    dishes = []
    for n in names:
        covered = any(n != o and n in o for o in names)
        if not covered:
            dishes.append(n)
    return dishes[:10]


def strip_admin_prefix(name: str) -> str:
    """去掉省市前缀, 如 '广东省东莞市虎门镇' -> '虎门镇'"""
    changed = True
    prefixes = sorted(SHORT_TO_FULL_PROV.values()) + sorted(SHORT_TO_FULL_PROV.keys())
    prefixes += [n[:-1] for n in RG.provinces.keys()] + list(RG.provinces.keys())
    prefixes += [c["_base"] for c in RG.raw if c["level"] == "city"]
    prefixes += [c["_base"][:-1] for c in RG.raw if c["level"] == "city" and c["_base"].endswith("市")]
    prefixes += ["北京市", "天津市", "上海市", "重庆市"]
    prefixes = sorted(set(prefixes), key=len, reverse=True)
    while changed:
        changed = False
        for pfx in prefixes:
            if len(pfx) >= 2 and name.startswith(pfx) and len(name) > len(pfx) + 1:
                name = name[len(pfx):]
                changed = True
                break
    return name


def find_road(text_sq: str) -> str:
    t = squash(text_sq)
    best = ""
    for m in ROAD_RE.finditer(t):
        seg = m.group()
        if len(seg) <= 2:
            continue
        if m.start() > 0 and t[m.start() - 1] in BAD_ROAD_PREFIX:
            continue
        if seg[:2] in {"路上", "沿着", "中途", "半路", "哪条", "什么", "一条", "这条", "那条",
                       "哪里的", "一路"}:
            continue
        if len(seg) > len(best):
            best = seg
    if best:
        return strip_admin_prefix(best)[:20]
    m = JUNCTION_RE.search(t)
    if m:
        s = max(0, m.start() - 10)
        return squash(t[s:m.end()])[:24]
    return ""


def find_landmark(text_sq: str) -> str:
    t = squash(text_sq)
    best = ""
    for m in DESCRIPTIVE_LANDMARK_RE.finditer(t):
        seg = m.group()
        if len(seg) > len(best):
            best = seg
    return best[:22]


BAD_HINT_START_RE = re.compile(
    "^(?:里面|外边|外面|快到|路口|红灯|旁边|对面|附近|隔壁|楼下|楼上|有个|有一个|那块|"
    "以前|曾经|当时|然后|还有|就是|好像|感觉|记得|读书|上学|小时候|初中|高中|大学|夜里|"
    "晚上|早上|中午|每次|经常|偶尔|终于|他们|老板|味道|口味|推荐|必点|人均|老板娘|门头)")
GOOD_HINT_SUFFIX_RE = re.compile(
    "(?:饭馆|餐馆|食府|食堂|大排档|快餐|小吃|早餐|宵夜|粉店|米粉|米线|面馆|拉面|板面|"
    "香锅|麻辣烫|冒菜|串串|火锅|烧烤|烤肉|烤鱼|烧腊|叉烧|卤味|卤鹅|煲仔|炒饭|盖码|盖浇|"
    "猪脚饭|肠粉|糖水|甜品|奶茶|咖啡|饺子|馄饨|汤包|包子|烧饼|羊肉|牛肉|驴肉|羊汤|汤锅|"
    "鱼庄|菜馆|酒楼|餐厅|饭店|店|馆|铺|档|摊|坊|阁|苑|轩|灶)$")
STORE_NAME_RE = re.compile(
    "[一-鿿A-Za-z0-9·]{2,14}(?:饭馆|餐馆|食府|大排档|螺蛳粉|小米线|火锅鸡|串串香|烤肉拌饭|"
    "凉皮|肉夹馍|酸辣粉|过桥米线|牛肉粉|羊肉粉|螺狮粉|煲仔饭|猪脚饭|烧腊|隆江猪脚|"
    "火锅|串串|冒菜|麻辣烫|烤肉|烤鱼|烧烤|米粉|米线|面馆|拉面|板面|包子|饺子|馄饨|汤包|"
    "卤味|奶茶|甜品|糖水|炸鸡|汉堡|披萨|寿司|烘焙|糕点|咖啡馆|茶餐厅|小馆|苍蝇馆子|土鸭馆|"
    "菜市场熟食|私房菜|农家菜|家常菜)"
)


def hint_looks_like_name(h: str, msg_sq: str) -> bool:
    """校验上游打标给出的 restaurant_name_hint 是否像一个真店名"""
    if not h or len(h) < 2:
        return False
    if len(h) > 18:
        return False
    if BAD_HINT_START_RE.match(h):
        return False
    if GOOD_HINT_SUFFIX_RE.search(h[-4:] if len(h) >= 4 else h):
        pass
    elif re.search(r"[A-Za-z]", h):      # 字母品牌名(如 M+咖啡)
        pass
    else:
        # 无店铺类后缀的纯中文片段: 仅当其在原文里前后都是标点时才可信(如被引号强调)
        idx = msg_sq.find(h)
        if idx < 0:
            return False
        prev_ok = idx == 0 or msg_sq[idx - 1] in "，。！？、：；,.!?:" \
            or msg_sq[idx - 1] in "」』）)”\"'"
        nxt_pos = idx + len(h)
        next_ok = nxt_pos >= len(msg_sq) or msg_sq[nxt_pos] in "，。！？、：；,.!?:" \
            or msg_sq[nxt_pos] in "（(「『“\"'"
        if not (prev_ok and next_ok):
            return False
    return True


# 店名候选里若混入这些词 -> 只是位置/叙述描述, 不是店名
CAND_BAD_RE = re.compile(
    "(?:对面|旁边|附近|隔壁|背后|前面|后面|门口|楼下|楼上|巷子|路口|公交站|地铁站|车站|"
    "火车站|机场|小区|广场|商场|市场|学校|大学|中学|小学|医院|教堂|公园|大厦|写字楼|夜市|"
    "步行街|菜市场|一家|一口|一家家|有名|美食|小吃街|路口)")

def extract_store_name(msg_sq: str):
    """从正文提取形态像店名的短语, 取最早出现且干净者"""
    best = ""
    best_pos = 10 ** 9
    for m in STORE_NAME_RE.finditer(msg_sq):
        seg = m.group()
        if seg.startswith(("的", "有", "这", "那", "个")):
            continue
        if len(seg) < 3 or len(seg) > 12:
            continue
        if CAND_BAD_RE.search(seg):
            continue
        if RG is not None and RG.cities.get(squash(seg)) is not None:
            continue                      # 撞城市名的不是店名
        pos = m.start()
        if pos < best_pos:
            best, best_pos = seg, pos
    return best


def store_name_strong(seg: str) -> bool:
    return bool(seg) and 3 <= len(seg) <= 12 and \
        GOOD_HINT_SUFFIX_RE.search(seg[-4:] if len(seg) >= 4 else seg) and \
        not CAND_BAD_RE.search(seg)


SEARCHY_PREFIX_RE = re.compile(r"^(?:图|高德|百度|腾讯)?(?:地图)?(?:直接|可以)?(?:搜索|搜)")
NARRATION_PREFIX_RE = re.compile(
    r"^(?:吃完了|吃完|还能|再去|再去看看|可以去|然后|接着|顺便|记得|去了|路过时?)+")


def tidy_descriptive(nm: str) -> str:
    """描述性名称收尾清理: 去掉省市前缀与搜索词、叙述词开头"""
    changed = True
    while changed and nm:
        changed = False
        m = SEARCHY_PREFIX_RE.match(nm)
        if m:
            nm = nm[m.end():]
            changed = True
        m = NARRATION_PREFIX_RE.match(nm)
        if m:
            nm = nm[m.end():]
            changed = True
        stripped = strip_admin_prefix(nm)
        if stripped != nm:
            nm = stripped
            changed = True
    return nm or "评论区推荐的小馆子"


def descriptive_name(msg_sq: str, hint: str, region: dict, road: str,
                     landmark: str, dishes: list, dtype: str):
    """返回 (display_name, has_real_name)"""
    h_valid = hint_looks_like_name(hint, msg_sq)

    # 从正文提取形态像店名的短语, 修复上游截断错误或补全缺失店名
    extracted = extract_store_name(msg_sq)
    if h_valid:
        if extracted and (extracted in hint or hint in extracted):
            return (hint if len(hint) >= len(extracted) else extracted, True)
        return (hint, True)
    if store_name_strong(extracted):
        return (extracted, True)
    t = squash(msg_sq)
    # 尝试 “地标+相对词 的 店型/菜品” 描述性命名
    lm_re = DESCRIPTIVE_LANDMARK_RE
    for m in lm_re.finditer(t):
        lm = m.group()
        tail = t[m.end(): m.end() + 12]
        rm = REL_RE.match(tail) or REL_RE.search(tail[:8])
        if not rm:
            continue
        rest = tail[rm.end():]
        kind = ""
        tm = TYPE_TOKEN_RE.search(rest[:8]) or PLACE_SUFFIX_RE.search(rest[:8])
        if tm:
            kind = tm.group().rstrip("的一家")
        else:
            dm = re.search(r"[一-鿿]{2,6}", rest[:8])
            probe = rest
            dish_hit = None
            fm = FOOD_RE.search(probe[:6])
            if fm:
                dish_hit = fm.group()
            if dish_hit:
                kind = dish_hit if dish_hit.endswith(("店", "馆", "铺")) else dish_hit + "店"
            elif dtype:
                cat_map = {"火锅串串": "火锅店", "冒菜麻辣烫": "冒菜店", "烧烤烤肉": "烧烤摊",
                           "粤式茶点": "糖水铺", "牛羊肉汤锅": "羊汤馆"}
                kind = cat_map.get(dtype, dtype.replace("地方菜馆", "家常菜馆")
                                   .replace("粉面", "粉面小店").replace("小吃快餐", "小吃店"))
        if kind and len(kind) >= 2:
            return tidy_descriptive(f"{lm}{rm.group()}的{kind}"), False
        return tidy_descriptive(f"{lm}{rm.group()}的小馆子"), False
    base_lm = landmark or road
    if base_lm:
        if TYPE_TOKEN_RE.search(t):
            return tidy_descriptive(f"{base_lm}旁的{TYPE_TOKEN_RE.search(t).group()}"), False
        if dishes:
            d0 = dishes[0]
            suffix = d0 if d0.endswith(("店", "馆", "铺")) else d0 + "店"
            return tidy_descriptive(f"{base_lm}旁的{suffix}"), False
        return tidy_descriptive(f"{base_lm}旁的小馆子"), False
    area = region.get("dist") or region.get("city") or region.get("prov") or ""
    kw = ""
    if dishes:
        kw = dishes[0]
    elif dtype:
        kw = {"火锅串串": "火锅", "冒菜麻辣烫": "冒菜", "烧烤烤肉": "烧烤", "粉面": "粉面",
              "粤式茶点": "茶点", "地方菜馆": "家常菜"}.get(dtype, dtype)
    if area and kw:
        return tidy_descriptive(f"{area}的{kw}小店"), False
    if area:
        return tidy_descriptive(f"{area}的一家宝藏小馆"), False
    return "评论区网友推荐的宝藏小馆", False


PRECI_ORDER = {"精确门牌": 6, "道路或路口": 5, "明确地标附近": 4,
               "区县级位置": 3, "城市级位置": 2, "暂时无法确认": 1}


def precision_of(region: dict, msg_sq: str, road: str, landmark: str) -> str:
    if PRECISE_HINT_RE.search(msg_sq):
        return "精确门牌"
    if road:
        return "道路或路口"
    if landmark or REL_RE.search(msg_sq):
        return "明确地标附近"
    if region.get("dist"):
        return "区县级位置"
    if region.get("city") or region.get("prov"):
        return "城市级位置"
    return "暂时无法确认"


def closed_evidence(msg_sq: str) -> str:
    m = CLOSED_RE.search(msg_sq)
    if not m:
        return ""
    s = max(0, m.start() - 10)
    return msg_sq[s: m.end() + 8]


# ---------------------------------------------------------------------------
# 构建餐馆对象
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    n = squash(name)
    n = re.sub(r"[（）()\[\]【】「」『']", "", n)
    n = re.sub(r"(总店|旗舰店|分店|二店|三店|一号店)$", "", n)
    return n.lower()


def region_key(rg: dict) -> str:
    return "|".join([rg.get("prov") or "", rg.get("city") or "", rg.get("dist") or ""])


def same_macro_area(k_a: str, k_b: str) -> bool:
    pa, ca, da = k_a.split("|")
    pb, cb, db = k_b.split("|")
    if pa and pb:
        if pa != pb:
            return False
        if ca and cb:
            return ca == cb
        return True
    # 一方只有市/区
    return (ca and cb and ca == cb) or (da and db and da == db)


def build_restaurants(rows):
    # 境外餐馆不属于中国美食地图, 剔除并统计
    usable = []
    foreign_skipped = 0
    for row in rows:
        sq = squash(clean_text(row["message"]))
        if is_foreign(sq):
            foreign_skipped += 1
        else:
            usable.append(row)
    if foreign_skipped:
        print(f"      剔除境外餐馆评论 {foreign_skipped} 条")

    mentions = []
    for row in usable:
        msg = clean_text(row["message"])
        msq = squash(msg)
        region = parse_region(msq)
        hint = squash(row.get("restaurant_name_hint") or "").strip("。，,!")
        road = find_road(msq)
        landmark = find_landmark(msq)
        dishes = extract_dishes(msg)
        dtype = classify_type((hint or "") + msq[:48])
        prec = precision_of(region, msq, road, landmark)
        name, has_real = descriptive_name(msq, hint, region, road, landmark, dishes, dtype)
        mentions.append({
            "row": row, "msg": msg, "msq": msq, "region": region, "hint": hint,
            "road": road, "landmark": landmark, "dishes": dishes, "dtype": dtype,
            "precision": prec, "closedEv": closed_evidence(msq),
            "name": name, "hasReal": has_real,
        })
    print(f"[1/5] 解析完成: {len(mentions)} 条可定位评论; 精度分布:",
          dict(Counter(m["precision"] for m in mentions)))
    prov_missing = sum(1 for m in mentions if not m["region"]["prov"] and not m["region"]["city"])
    print(f"      未识别到省市线索: {prov_missing} 条")

    # ---- 合并 ----
    groups = []          # 保持插入顺序
    by_key = {}
    for m in mentions:
        rk = region_key(m["region"])
        nm = normalize_name(m["name"])
        key = ("N" if m["hint"] else "D") + ":" + nm
        target = None
        if key in by_key:
            for idx in by_key[key]:
                g = groups[idx]
                if same_macro_area(g["rkey"], rk):
                    target = g
                    break
        if target is None:
            target = {
                "key": key, "rkey": rk, "mentions": [], "comments": [],
                "replies": {}, "dishCounter": Counter(), "types": Counter(),
                "precisions": [], "hasRealName": False, "closedEvs": [],
            }
            by_key.setdefault(key, []).append(len(groups))
            groups.append(target)
        add_mention(target, m, THREAD_REPLIES)
    print(f"[2/5] 合并完成: {len(groups)} 家餐馆 (来自 {len(mentions)} 条提及)")

    # 第二遍保守合并: 同一大区域 + 店名互为包含 (长度>=4) 的组视为同店
    merged_flag = True
    while merged_flag:
        merged_flag = False
        for i in range(len(groups)):
            gi = groups[i]
            if not gi["hasRealName"]:
                continue
            ni = normalize_name(gi["mentions"][0]["name"])
            if len(ni) < 4:
                continue
            for j in range(i + 1, len(groups)):
                gj = groups[j]
                if not gj["hasRealName"]:
                    continue
                nj = normalize_name(gj["mentions"][0]["name"])
                if len(nj) < 4:
                    continue
                if not same_macro_area(gi["rkey"], gj["rkey"]):
                    continue
                long_n, short_n = (ni, nj) if len(ni) >= len(nj) else (nj, ni)
                if short_n in long_n:
                    big, small = (gi, gj) if len(ni) >= len(nj) else (gj, gi)
                    for m2 in small["mentions"]:
                        add_mention(big, m2, THREAD_REPLIES)
                    big["closedEvs"].extend(small["closedEvs"])
                    # 数据已并入 big; 删除 small 所在槽位后 break 由外层 while 重启扫描
                    groups.pop(groups.index(small))
                    merged_flag = True
                    break
            if merged_flag:
                break

    restaurants = [finalize_group(g) for g in groups]
    return restaurants


THREAD_REPLIES = None


def add_mention(g, m, thread_replies):
    row = m["row"]
    pics = []
    try:
        pic_raw = json.loads(row.get("pictures_json") or "[]")
        if isinstance(pic_raw, list):
            for p in pic_raw[:4]:
                url = p if isinstance(p, str) else (p.get("url") or p.get("img_src"))
                if url:
                    pics.append(url)
    except Exception:
        pass
    cobj = {
        "id": row["rpid"],
        "root": row.get("root_rpid") or row["rpid"],
        "user": row.get("uname", ""),
        "time": row.get("created_at", ""),
        "likes": int(float(row.get("like_count") or 0)),
        "msg": m["msg"],
        "pics": pics,
        "isReply": row.get("level") == "1",
    }
    g["mentions"].append(m)
    g["comments"].append(cobj)
    for rep in thread_replies.get(cobj["root"], []):
        g["replies"][rep["id"]] = rep
    for d in m["dishes"]:
        g["dishCounter"][d] += 1
    if m["dtype"]:
        g["types"][m["dtype"]] += 1
    g["precisions"].append(m["precision"])
    g["hasRealName"] = g["hasRealName"] or m["hasReal"]
    if m["closedEv"]:
        g["closedEvs"].append({"text": m["closedEv"], "src": "comment"})
    for rep in g["replies"].values():
        if rep.get("flag") == "closed_hint":
            g["closedEvs"].append({"text": rep["ev"], "src": "reply"})


def finalize_group(g):
    mentions = g["mentions"]
    first = mentions[0]
    rg = best_region(g)
    dishes = [d for d, _ in g["dishCounter"].most_common(10)]
    dtype = g["types"].most_common(1)[0][0] if g["types"] else ""
    prec = max(g["precisions"], key=lambda p: PRECI_ORDER[p])
    comments = sorted(g["comments"], key=lambda c: (-c["likes"], c["time"]))
    likes_sum = sum(c["likes"] for c in g["comments"])
    reply_likes = sum(r["likes"] for r in g["replies"].values())
    top = comments[0] if comments else None
    clues = list(dict.fromkeys([m["road"] for m in mentions if m["road"]] +
                               [m["landmark"] for m in mentions if m["landmark"]]))
    score = PRECI_ORDER[prec] * 12
    score += min(len(comments) * 6, 14)
    score += 8 if g["hasRealName"] else 0
    score += min(math.log10(max(likes_sum, 1)) * 4, 14)
    if rg.get("dist"):
        score += 8
    cred = "高" if score >= 82 else ("中" if score >= 58 else "低")

    area_full = " ".join(x for x in [rg.get("prov"), rg.get("city"), rg.get("dist")] if x)
    stable_id = "R" + hashlib.md5(g["key"].encode("utf-8")).hexdigest()[:12]
    return {
        "id": stable_id,
        "name": first["name"],
        "hasRealName": g["hasRealName"],
        "descriptiveOnly": not g["hasRealName"],
        "type": dtype,
        "province": rg.get("prov", ""),
        "city": rg.get("city", ""),
        "district": rg.get("dist", ""),
        "areaFull": area_full,
        "addressHint": "; ".join(clues[:2]),
        "locationClues": clues,
        "rawLocationText": first["row"].get("location_hint") or first["msg"][:140],
        "dishes": dishes,
        "precision": prec,
        "credibility": cred,
        "credScore": round(score, 1),
        "suspectedClosed": bool(g["closedEvs"]),
        "closedEvidence": list(dict.fromkeys(e["text"] for e in g["closedEvs"]))[:3],
        "mentionCount": len(mentions),
        "totalLikes": likes_sum,
        "replyLikes": reply_likes,
        "topComment": top,
        "lat": None, "lng": None, "coordSource": "",
        "videoUrl": VIDEO_URL,
        "comments": g["comments"],
        "threadReplies": list(g["replies"].values())[:14],
    }


def best_region(g):
    rg = {"prov": "", "city": "", "dist": ""}
    for m in g["mentions"]:
        r = m["region"]
        if not rg["prov"]:
            rg["prov"] = r["prov"]
        if not rg["city"]:
            rg["city"] = r["city"]
        if not rg["dist"]:
            rg["dist"] = r["dist"] or r.get("town") or ""
    # 若某条提及给出更完整区域则替换
    fullest = max(g["mentions"], key=lambda m: sum(bool(m["region"][k]) for k in ("prov", "city", "dist")))
    rf = fullest["region"]
    for k in ("prov", "city", "dist"):
        if rf.get(k):
            rg[k] = rf[k]
    return rg


# ---------------------------------------------------------------------------
# 地理坐标
# ---------------------------------------------------------------------------

def attach_coords(restaurants):
    key = os.environ.get("AMAP_KEY", "").strip()
    mod = None
    if key:
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import amap_geocode as ag
            ag.init(key=key, cache_path=CACHE_DIR / "geocache_amap.jsonl")
            mod = ag
            print("[4/5] 使用高德 API 增强 (Key 已配置)")
        except Exception as e:
            print("!! 高德模块不可用:", e)
    else:
        print("[4/5] 未配置 AMAP_KEY -> 行政区中心点估算")

    miss = 0
    amap_cnt = 0
    for r in restaurants:
        lat, lng, src = None, None, ""
        if mod:
            hit = _amap_one(mod, r)
            if hit:
                lng, lat, src = hit["lng"], hit["lat"], hit["src"]
                amap_cnt += 1
        if lat is None:
            pt = RG.centroid(r["province"], r["city"], r["district"])
            if pt:
                lat, lng = pt
                src = "centroid"
            else:
                miss += 1
        r["lat"], r["lng"], r["coordSource"] = lat, lng, src
    print(f"      高德命中 {amap_cnt}, 中心点回退 {sum(1 for r in restaurants if r['coordSource']=='centroid')}, 缺失 {miss}")


def _amap_one(mod, r):
    queries = []
    city = r["city"] or r["province"]
    if r["hasRealName"] and city:
        queries.append(("poi", {"keywords": re.sub(r"\s", "", r["name"])[:28], "city": squash(city)}))
    area = "".join(x for x in [r["province"], r["city"], r["district"]] if x)
    if area and (r["locationClues"] or r["rawLocationText"]):
        addr = squash(area + (r["locationClues"][0] if r["locationClues"] else ""))[:60]
        queries.append(("geo", {"address": addr, "city": squash(city)}))
    for qtype, payload in queries:
        try:
            hit = mod.query(qtype, payload)
        except Exception:
            return None
        if hit and hit.get("lat"):
            return hit
    return None


# ---------------------------------------------------------------------------
# meta 与自检
# ---------------------------------------------------------------------------

def gen_meta(restaurants, total_comments):
    prov_agg = defaultdict(lambda: {"count": 0, "cities": defaultdict(int), "likes": 0})
    for r in restaurants:
        p = r["province"]
        agg = prov_agg[p or "未识别省份"]
        agg["count"] += 1
        if r["city"]:
            agg["cities"][r["city"]] += 1
        agg["likes"] += r["totalLikes"]
    prov_list = []
    for pname, agg in prov_agg.items():
        tops = sorted((r for r in restaurants if (r["province"] or "未识别省份") == pname),
                      key=lambda r: -r["totalLikes"])[:3]
        prov_list.append({
            "name": pname,
            "count": agg["count"],
            "cityCount": len(agg["cities"]),
            "cities": [{"name": cn, "count": ct} for cn, ct in
                       sorted(agg["cities"].items(), key=lambda kv: (-kv[1], kv[0]))],
            "top": [{"id": t["id"], "name": t["name"], "likes": t["totalLikes"]} for t in tops],
        })
    prov_list.sort(key=lambda x: -x["count"])
    cities_set = {f'{r["province"]}|{r["city"]}' for r in restaurants if r["city"]}
    meta = {
        "generatedAt": time.strftime("%Y-%m-%d %H:%M"),
        "videoUrl": VIDEO_URL,
        "source": "B站视频《当男生吃到好吃的店时》评论区 (BV1D38n6nEy7)",
        "overview": {
            "totalComments": total_comments,
            "locatableComments": sum(r["mentionCount"] for r in restaurants),
            "restaurantCount": len(restaurants),
            "provinceCount": sum(1 for p in prov_list if p["name"] != "未识别省份"),
            "cityCount": len(cities_set),
            "totalLikes": sum(r["totalLikes"] for r in restaurants),
            "suspectedClosed": sum(1 for r in restaurants if r["suspectedClosed"]),
        },
        "provinces": prov_list,
        "types": [t for t, _ in Counter(r["type"] for r in restaurants if r["type"]).most_common()],
        "topDishes": [d for d, _ in Counter(d for r in restaurants for d in r["dishes"]).most_common(64)],
    }
    # 行政区中心点索引用于前端手动模式距离估算 (n=官方全名)
    meta["regions"] = [{
        "a": it["adcode"], "n": it["name"], "l": it["level"][0],
        "p": it.get("parent"), "x": round(float(it["lng"]), 4), "y": round(float(it["lat"]), 4),
    } for it in RG.raw if it["level"] != "country"]
    return meta


def run_check(restaurants, meta):
    print("\n===== 锚点自检 =====")
    hay = {}
    for r in restaurants:
        parts = [r["name"], r["areaFull"], r["type"], "".join(r["dishes"])]
        parts.extend(r["locationClues"])
        parts.extend(c["msg"] for c in r["comments"])
        hay[r["id"]] = squash(" ".join(parts))

    def search(kw):
        kq = squash(kw)
        return [r for r in restaurants if kq in hay[r["id"]]]

    def fmt(rs):
        if not rs:
            return ""
        r = rs[0]
        return f" 例:{r['name']} @ {r['areaFull'] or '?'} 👍{r['totalLikes']}"

    checks = [
        ("永发烧腊 -> 命中且属东莞市", lambda rs: bool(rs) and any(r["city"] == "东莞市" for r in rs), search("永发烧腊")),
        ("海椒市 -> 命中", lambda rs: bool(rs), search("海椒市")),
        ("落舌冒菜 -> 命中", lambda rs: bool(rs), search("落舌冒菜")),
        ("虎门 -> 命中", lambda rs: bool(rs), search("虎门")),
        ("成都 -> 有结果", lambda rs: len(rs) >= 5, search("成都")),
        ("东莞 -> 命中含虎门结果", lambda rs: any("虎门" in squash(r["areaFull"]) for r in rs), search("东莞")),
        ("烧腊 -> 有结果", lambda rs: bool(rs), search("烧腊")),
        ("冒菜 -> 有结果", lambda rs: bool(rs), search("冒菜")),
        ("市辖区/城市聚合数", lambda _: True, [meta["overview"]]),
    ]
    ok_all = True
    for label, judge, got in checks:
        good = judge(got)
        ok_all &= good
        extra = fmt(got) if got and isinstance(got[0], dict) and "name" in (got[0] or {}) else ""
        print(("PASS " if good else "FAIL ") + label + extra)
    ov = meta["overview"]
    print(f"概览: {ov['restaurantCount']} 家店 | {ov['provinceCount']} 省 | "
          f"{ov['cityCount']} 城 | 疑似停业 {ov['suspectedClosed']} | 总赞 {ov['totalLikes']}")
    unassigned = [r for r in restaurants if not r["province"]]
    if unassigned:
        print(f"!! {len(unassigned)} 家省份为空, 示例:",
              [(r["name"], r["comments"][0]["msg"][:40]) for r in unassigned[:5]])
    print("自检整体:", "OK ✅" if ok_all else "FAIL ❌")
    return ok_all


def dedupe_names(restaurants):
    seen = Counter(r["name"] for r in restaurants)
    for r in restaurants:
        if seen[r["name"]] > 1:
            area = r["district"] or r["city"]
            if area:
                r["name"] = f"{r['name']}({area})"


def main():
    global RG, THREAD_REPLIES, UNIQ
    RG = Regions()
    UNIQ = UniquePlaces()
    UNIQ.build(RG)

    rows = []
    with open(DATA_DIR / "locatable_restaurant_comments.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    with open(DATA_DIR / "comments_tagged_all.csv", encoding="utf-8-sig") as f:
        tagged_all = list(csv.DictReader(f))

    root_ids = {r["rpid"] for r in rows}
    THREAD_REPLIES = defaultdict(list)
    for r in tagged_all:
        rt = r.get("root_rpid") or ""
        if rt in root_ids and r["rpid"] not in root_ids and r.get("level") == "1" \
                and r.get("category") in ("locatable_restaurant", "restaurant_not_locatable"):
            msq = squash(clean_text(r.get("message", "")))
            ev = closed_evidence(msq)
            THREAD_REPLIES[rt].append({
                "id": r["rpid"], "user": r.get("uname", ""), "time": r.get("created_at", ""),
                "likes": int(float(r.get("like_count") or 0)), "msg": clean_text(r.get("message", ""))[:400],
                "flag": "closed_hint" if ev else "",
                "ev": ev or "",
            })
    n_close_thread = sum(any(rep["flag"] for rep in v) for v in THREAD_REPLIES.values())
    print(f"载入 {len(rows)} 条可定位评论 / {len(tagged_all)} 全量; 含停业线索楼中楼主题 {n_close_thread}")

    restaurants = build_restaurants(rows)
    attach_coords(restaurants)
    dedupe_names(restaurants)
    meta = gen_meta(restaurants, len(tagged_all))
    print("[5/5] meta:", meta["overview"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "restaurants.json", "w", encoding="utf-8") as f:
        json.dump({"restaurants": restaurants}, f, ensure_ascii=False, separators=(",", ":"))
    with open(OUT_DIR / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"输出: restaurants.json {(OUT_DIR/'restaurants.json').stat().st_size//1024} KB + meta.json")

    if "--check" in sys.argv:
        sys.exit(0 if run_check(restaurants, meta) else 1)


if __name__ == "__main__":
    main()
