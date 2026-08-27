#!/usr/bin/env python3
"""高德 Web 服务 API 封装: 地理编码 + POI 搜索, 带本地 JSONL 缓存。

用法(被 build_data.py 调用):
    import amap_geocode as ag
    ag.init(key=os.environ['AMAP_KEY'], cache_path=...)
    hit = ag.query('poi', {'keywords': '永发烧腊', 'city': '东莞市'})
    hit = ag.query('geo', {'address': '广东省东莞市虎门镇', 'city': ''})
    # hit -> {'lng','lat','src','level','name'} 或 None

限流: 个人开发者约 3 QPS, 内部 sleep 控制; 失败自动降级并记录。
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

_KEY = ""
_CACHE_PATH = None
_cache = {}
MIN_INTERVAL = 0.36   # ~2.7 QPS
_last_ts = 0.0


def init(key: str, cache_path):
    global _KEY, _CACHE_PATH, _cache
    _KEY = key.strip()
    _CACHE_PATH = cache_path
    _cache = {}
    try:
        with open(cache_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    _cache[rec["k"]] = rec.get("v")
                except Exception:
                    continue
    except FileNotFoundError:
        pass


def _save(k: str, v):
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({"k": k, "v": v}, ensure_ascii=False) + "\n")


def _throttle():
    global _last_ts
    gap = time.time() - _last_ts
    if gap < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - gap)
    _last_ts = time.time()


def _get(url: str, tries: int = 3) -> dict | None:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "local-foodie-map/0.1"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            time.sleep(1.2 * (i + 1))
    return None


def query(qtype: str, payload: dict):
    """qtype: 'poi' | 'geo'"""
    k = qtype + "|" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if k in _cache:
        return _cache[k]
    params = {"key": _KEY}
    if qtype == "poi":
        url = ("https://restapi.amap.com/v3/place/text?" +
               urllib.parse.urlencode({**params,
                                       "keywords": payload.get("keywords", ""),
                                       "city": payload.get("city", ""),
                                       "citylimit": "true",
                                       "offset": 5}))
    else:
        url = ("https://restapi.amap.com/v3/geocode/geo?" +
               urllib.parse.urlencode({**params,
                                       "address": payload.get("address", ""),
                                       "city": payload.get("city", "")}))

    data = _get(url)
    if not data or str(data.get("status")) != "1":
        _cache[k] = None
        _save(k, None)
        return None
    out = None
    try:
        if qtype == "poi":
            pois = data.get("pois") or []
            if pois:
                p = pois[0]
                loc = p.get("location", "")
                lng, lat = loc.split(",")[:2] if "," in loc else (None, None)
                if lng:
                    out = {"lng": float(lng), "lat": float(lat),
                           "src": "amap_poi", "level": p.get("type", ""), "name": p.get("name", "")}
        else:
            geos = data.get("geocodes") or []
            if geos:
                g = geos[0]
                loc = g.get("location", "")
                lng, lat = loc.split(",")[:2] if "," in loc else (None, None)
                if lng:
                    out = {"lng": float(lng), "lat": float(lat),
                           "src": "amap_geo", "level": g.get("level", "")}
    except Exception:
        out = None
    _cache[k] = out
    _save(k, out)
    return out
