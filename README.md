# Local Foodie Map · 评论区美食地图

把 B站视频 [《当男生吃到好吃的店时》](https://www.bilibili.com/video/BV1D38n6nEy7/) 评论区里的
一万多条"这家店真的好吃"整理成一张可搜索、可浏览、可找附近的中国美食地图。

- **数据源**：B站视频《当男生吃到好吃的店时》(BV1D38n6nEy7) 的评论数据库（本地目录，含
  `locatable_restaurant_comments.csv` 1,293 条可定位餐馆评论与 `comments_tagged_all.csv`
  全量 10,537 条评论标签）。重建数据时把目录路径放进环境变量 `LFM_DATA_DIR` 即可：

  ```bash
  LFM_DATA_DIR=/path/to/BV1D38n6nEy7_评论数据库 python3 scripts/build_data.py --check
  ```

  仓库内 `public/data/*.json` 已是构建产物，前端开箱即用，无需本地评论数据。
- **产物**：纯静态站点（Vite + Vue 3 + Pinia + ECharts），`dist/` 可部署到任意静态托管

## 快速开始

```bash
npm install
npm run dev        # 开发调试 http://localhost:5173
npm run build      # 生产构建 -> dist/
npm run preview    # 本地预览构建产物
```

## 数据重建

```bash
python3 scripts/build_data.py --check     # 重建 restaurants.json / meta.json 并跑锚点自检
```

自检覆盖验收锚点：`永发烧腊`(东莞市虎门镇)、`海椒市`、`落舌冒菜`、`成都`、`烧腊`、`冒菜` 等，
任何一项失败脚本以非零码退出。管线要点：

1. 行政区解析：省→市→区县(含镇/街道)，内置全国三级行政区划词典 + 无后缀城市唯一名识别；
2. 位置精度六档：精确门牌 / 道路或路口 / 明确地标附近 / 区县级 / 城市级 / 暂时无法确认；
3. 同店合并：名称规范化 + 宏观区域一致，两轮保守合并；聚合来源评论、总赞、菜品并集；
4. 疑似停业：正则命中“倒闭/关门/搬走…”标记 `suspectedClosed`（含楼中楼证据）；
5. 境外餐馆剔除（日本/东南亚/欧美…，并豁免“北海道寿司”“美国炸鸡”式菜名误伤）。

### 可选：高德坐标增强

默认使用行政区中心点估算每家店的坐标（`coordSource: "centroid"`）。配置高德 Web 服务 Key 后
可升级为真实地理编码坐标：

```bash
export AMAP_KEY=你的key
python3 scripts/build_data.py            # 结果缓存于 data-cache/geocache_amap.jsonl, 重跑不重复计费
```

## 前端功能地图

| 区域 | 功能 |
| --- | --- |
| Hero | 标题、数据概览、居中大搜索框 + 快捷词 |
| 中国美食地图 | ECharts 省级着色图；hover 显示收录数/热门店；点击省份钻取 |
| 省/市浏览 | 全国 → 省(按城市分组) → 市(按点赞降序卡片)；直辖市特殊处理 |
| 搜索结果 | 分字段加权打分词条卡(名称>地区>菜品>类型>线索>正文)，关键词高亮 |
| 餐馆详情抽屉 | 完整信息网格、原始位置线索、全部来源评论(作者/时间/点赞/图片)、楼中楼、分享链接 |
| 附近馆子 | geolocation 授权定位 / 手动省市区回退 → haversine 最近 1 家 + 备选；自动排除无坐标与疑似停业 |
| 热门 | 点赞榜 / 推荐次数榜 / 各城市 No.1 |
| 随机 | “今天吃什么”，可限定省市/菜品/类型 |
| 筛选 | 省、市、菜品、类型、精度、点赞门槛、推荐次数、有无店名、可靠定位、排除停业 |
| 分享 | hash 深链（#/、#/?q=、#/?p=&c=、#/?r=餐馆id）+ 一键复制 |

主题：浅色玻璃拟态为主，跟随系统深浅色 + 手动切换；移动端导航横滚、面板单列。

## 目录结构

```
scripts/build_data.py     # 评论 → 餐馆 数据管线(--check 自检)
scripts/amap_geocode.py   # 高德编码封装(JSONL 缓存, 可选)
public/data/*.json        # 构建产物(restaurants/meta)
public/geo/china.json     # 中国省级 GeoJSON (DataV Atlas)
src/lib/search.js         # 打分检索
src/lib/nearby.js         # haversine 附近推荐
src/store/app.js          # Pinia 全局状态 + hash 路由
src/components/*           # 页面组件
```

## 免责说明（页面同款）

网友评论整理，非官方商家数据；点赞数为抓取时点数据；部分店没有正式店名（描述性名称）；
地址是评论中的位置线索，可能存在误差；店铺可能已搬迁或停业——出发前请自行核实。
