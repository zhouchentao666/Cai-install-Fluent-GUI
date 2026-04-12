# -*- coding: utf-8 -*-
"""
修改器后端 - 支持 FLiNG 等多数据源。

数据来源:
  FLiNG: https://archive.flingtrainer.com/  (完整 A-Z 列表)

本地缓存: APP_ROOT/config/trainer_cache.json  (24h 有效)
"""

import os
import re
import sys
import json
import shutil
import stat
import string
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Optional, Callable, Dict, List
from urllib.parse import urljoin, urlparse, unquote, urlencode

import requests
import cloudscraper
import ssl
from bs4 import BeautifulSoup
import warnings
from urllib3.exceptions import InsecureRequestWarning

warnings.simplefilter("ignore", InsecureRequestWarning)

# ── 代理配置 ──────────────────────────────────────────────────
# 默认不使用代理，只有在直连失败时才使用
_USE_PROXY_GLOBAL = False

def _get_proxies() -> Optional[Dict[str, str]]:
    """获取系统代理设置（仅在开启时返回）"""
    if not _USE_PROXY_GLOBAL:
        return None
    
    try:
        proxies = {}
        http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
        https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
        socks_proxy = os.environ.get('SOCKS_PROXY') or os.environ.get('socks_proxy')
        
        if socks_proxy:
            proxies['http'] = socks_proxy
            proxies['https'] = socks_proxy
        elif https_proxy:
            proxies['https'] = https_proxy
        elif http_proxy:
            proxies['http'] = http_proxy
            proxies['https'] = http_proxy
        
        return proxies if proxies else None
    except Exception:
        return None


def _http_get_with_fallback(url: str, headers: Optional[Dict] = None, timeout: int = 15, **kwargs) -> requests.Response:
    """发送 HTTP GET 请求，优先直连，失败后尝试代理"""
    default_headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0"
    }
    if headers:
        default_headers.update(headers)
    
    # 先尝试直连
    try:
        resp = requests.get(url, headers=default_headers, timeout=timeout, **kwargs)
        return resp
    except Exception:
        pass
    
    # 直连失败，尝试代理
    proxies = _get_proxies()
    if proxies:
        try:
            resp = requests.get(url, headers=default_headers, timeout=timeout, proxies=proxies, **kwargs)
            return resp
        except Exception:
            pass
    
    # 仍然失败，抛出异常
    return requests.get(url, headers=default_headers, timeout=timeout, **kwargs)


def _create_scraper():
    """创建禁用SSL验证的cloudscraper（兼容check_hostname）"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return cloudscraper.create_scraper(ssl_context=ctx)


def _http_get(url: str, headers: Optional[Dict] = None, timeout: int = 15, **kwargs) -> requests.Response:
    """发送 HTTP GET 请求"""
    default_headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0"
    }
    if headers:
        default_headers.update(headers)
    
    return requests.get(url, headers=default_headers, timeout=timeout, **kwargs)


def _setup_rarfile_path():
    """设置 rarfile 能找到的解压工具路径"""
    try:
        import rarfile
        import os
        
        # 添加 7-Zip 和 WinRAR 到 PATH
        extra_paths = [
            r"C:\Program Files\7-Zip",
            r"C:\Program Files (x86)\7-Zip",
            r"C:\Program Files\WinRAR",
            r"C:\Program Files (x86)\WinRAR",
        ]
        
        current_path = os.environ.get('PATH', '')
        for p in extra_paths:
            if os.path.isdir(p) and p not in current_path:
                os.environ['PATH'] = p + os.pathsep + current_path
        
        # 让 rarfile 优先使用 7z
        rarfile.USE_SYSTEM_UNRAR = False
    except ImportError:
        pass

# ── 项目根目录 ──────────────────────────────────────────────
def _get_app_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

APP_ROOT = _get_app_root()

# ── 常量 ────────────────────────────────────────────────────
_ARCHIVE_URL  = "https://archive.flingtrainer.com/"
_MAIN_AZ_URL  = "https://flingtrainer.com/all-trainers-a-z/"
_CACHE_FILE   = APP_ROOT / "config" / "trainer_cache.json"
_CACHE_TTL    = 86400          # 24 小时
_TRAINER_DIR  = APP_ROOT / "trainers"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://archive.flingtrainer.com/",
}

# ── 工具函数 ─────────────────────────────────────────────────

def get_trainer_dir() -> Path:
    _TRAINER_DIR.mkdir(parents=True, exist_ok=True)
    return _TRAINER_DIR


def _sanitize(text: str) -> str:
    """去除标点/空格/大小写，用于模糊匹配"""
    try:
        import zhon.hanzi
        all_punct = string.punctuation + zhon.hanzi.punctuation
    except ImportError:
        all_punct = string.punctuation
    # 把数字转罗马数字（与 GCM 保持一致）
    text = re.sub(r'\d+', lambda m: _to_roman(int(m.group())), text)
    return ''.join(c for c in text if c not in all_punct and not c.isspace()).lower()


def _to_roman(n: int) -> str:
    if n == 0:
        return '0'
    vals = [(1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),
            (50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]
    r = ''
    for v, s in vals:
        while n >= v:
            r += s; n -= v
    return r


def _fuzzy_match(keyword: str, target: str, threshold: int = 72) -> bool:
    try:
        from fuzzywuzzy import fuzz
        return fuzz.partial_ratio(_sanitize(keyword), _sanitize(target)) >= threshold
    except ImportError:
        return keyword.lower() in target.lower()


def _is_chinese(text: str) -> bool:
    """检测文本是否包含中文"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def _translate_keyword(keyword: str) -> str:
    """
    使用 Bing 翻译 API 翻译关键词。
    - 中文 -> 英文
    - 英文 -> 中文
    """
    if not keyword or not keyword.strip():
        return keyword
    
    keyword = keyword.strip()
    
    # 判断输入语言
    if _is_chinese(keyword):
        lfrom, lto = "中文", "English"
    else:
        lfrom, lto = "English", "中文"
    
    langfrom = {"自动检测": "auto-detect", "中文": "zh-Hans", "English": "en"}
    langto = {"中文": "zh-Hans", "English": "en"}
    
    url = "https://cn.bing.com/translator?ref=TThis&text=&from=zh-Hans&to=en"
    header = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0"
    }
    
    try:
        # 获取 token 和 ig
        response = _http_get(url, headers=header, timeout=10)
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        dev_element = soup.find("div", id="tta_outGDCont")
        if not dev_element:
            return keyword
        data_iid = dev_element.attrs.get("data-iid", "")
        ig = re.search(r'IG:"(\w+)"', html)
        if not ig:
            return keyword
        ig = ig.group(1)
        
        pattern = r'var params_AbusePreventionHelper = \[(\d+),"([^"]+)",\d+\];'
        token = re.findall(pattern, html)
        if not token:
            return keyword
        
        # 执行翻译
        url = "https://cn.bing.com/ttranslatev3?isVertical=1&&IG=" + ig + "&IID=" + data_iid
        data = {
            "fromLang": langfrom[lfrom],
            "to": langto[lto],
            "token": token[0][1],
            "key": token[0][0],
            "text": keyword,
            "tryFetchingGenderDebiasedTranslations": "true"
        }
        
        from urllib.request import urlopen, Request
        req = Request(
            url,
            data=urlencode(data).encode("utf-8"),
            headers=header
        )
        response = urlopen(req, timeout=10)
        html = response.read().decode("utf-8")
        target = json.loads(html)
        return target[0]['translations'][0]['text']
    except Exception:
        return keyword



def _parse_game_name(raw: str) -> str:
    """从 FLiNG 文件名中提取游戏名"""
    name = re.sub(
        r'\s+v[\d.]+.*'
        r'|\.v[\d].*'
        r'|\s+\d+\.\d+\.\d+.*'
        r'|\s+Plus\s+\d+.*'
        r'|Build\s+\d+.*'
        r'|\d+\.\d+-Update.*'
        r'|Update\s+\d+.*'
        r'|\(Update\s.*'
        r'|\s+Early\s+Access.*'
        r'|\.Early\.Access.*'
        r'|-FLiNG$'
        r'|\s+Fixed$'
        r'|\s+Updated.*',
        '', raw, flags=re.IGNORECASE
    )
    name = name.replace('_', ': ').strip()
    if name == "Bright.Memory.Episode.1":
        name = "Bright Memory: Episode 1"
    return name


# ── 缓存管理 ─────────────────────────────────────────────────

def _load_cache() -> Optional[list]:
    try:
        if _CACHE_FILE.exists():
            data = json.loads(_CACHE_FILE.read_text(encoding='utf-8'))
            if time.time() - data.get('ts', 0) < _CACHE_TTL:
                return data.get('trainers', [])
    except Exception:
        pass
    return None


def _save_cache(trainers: list):
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(
            json.dumps({'ts': time.time(), 'trainers': trainers}, ensure_ascii=False),
            encoding='utf-8'
        )
    except Exception as e:
        print(f"[TrainerBackend] 缓存写入失败: {e}")


# ── 爬取 FLiNG 列表 ──────────────────────────────────────────

def _fetch_archive_list() -> list:
    """
    爬取 archive.flingtrainer.com，返回
    [{"game_name": str, "trainer_name": str, "url": str, "source": "archive"}, ...]
    """
    try:
        scraper = _create_scraper()
        resp = scraper.get(_ARCHIVE_URL, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        print(f"[TrainerBackend] 爬取 archive 失败: {e}")
        return []

    results = []
    ignored = {"Dying Light The Following Enhanced Edition",
               "Monster Hunter World", "Street Fighter V", "World War Z"}

    for link in soup.find_all('a', target='_self'):
        raw = link.get_text(strip=True)
        if not raw:
            continue
        game_name = _parse_game_name(raw)
        if not game_name or game_name in ignored:
            continue
        href = link.get('href', '')
        url = urljoin(_ARCHIVE_URL, href) if href else ''
        results.append({
            "game_name":    game_name,
            "trainer_name": f"[FLiNG] {game_name} Trainer",
            "url":          url,
            "source":       "archive",
            "version":      "",
            "author":       "FLiNG",
        })
    return results


def _fetch_main_list() -> list:
    """
    爬取 flingtrainer.com/all-trainers-a-z/，返回
    [{"game_name", "trainer_name", "url", "source": "main"}, ...]
    """
    try:
        scraper = _create_scraper()
        resp = scraper.get(_MAIN_AZ_URL, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        print(f"[TrainerBackend] 爬取主站 A-Z 失败: {e}")
        return []

    results = []
    for section in soup.find_all(class_='letter-section'):
        for li in section.find_all('li'):
            for a in li.find_all('a'):
                raw = a.get_text(strip=True)
                game_name = raw.rsplit(' Trainer', 1)[0].strip()
                if not game_name:
                    continue
                url = a.get('href', '')
                results.append({
                    "game_name":    game_name,
                    "trainer_name": f"[FLiNG] {game_name} Trainer",
                    "url":          url,
                    "source":       "main",
                    "version":      "",
                    "author":       "FLiNG",
                })
    return results


def refresh_trainer_list(force: bool = False) -> list:
    """
    获取完整修改器列表（优先读缓存）。
    force=True 强制重新爬取。
    """
    if not force:
        cached = _load_cache()
        if cached:
            return cached

    # 先爬 archive（有直接下载链接），再爬主站（较新，但需要进详情页）
    archive = _fetch_archive_list()
    main    = _fetch_main_list()

    # 主站优先：用 game_name 去重，main 覆盖 archive
    merged: dict[str, dict] = {}
    for t in archive:
        merged[t['game_name'].lower()] = t
    for t in main:
        merged[t['game_name'].lower()] = t   # 主站覆盖

    trainers = list(merged.values())
    if trainers:
        _save_cache(trainers)
    return trainers


# ── 搜索 ─────────────────────────────────────────────────────

def search_trainers(keyword: str) -> list:
    """
    在本地缓存中模糊搜索修改器。
    首次调用会爬取 FLiNG 网站（约 2-5 秒），之后 24h 内走缓存。
    支持中英文互译搜索。
    """
    all_trainers = refresh_trainer_list()
    if not all_trainers:
        raise RuntimeError("无法获取修改器列表，请检查网络连接")

    def _do_search(kw: str, trainers_list: list) -> list:
        results = []
        for t in trainers_list:
            if _fuzzy_match(kw, t['game_name']):
                results.append(t)
        return results

    def _score(t, kw_lower):
        name = t['game_name'].lower()
        if name == kw_lower:
            return 0
        if kw_lower in name:
            return 1
        return 2

    results = []
    
    # 搜索 FLiNG 数据源
    fling_results = _do_search(keyword, all_trainers)
    
    # 如果 FLiNG 没找到，尝试翻译后搜索
    if not fling_results:
        translated = _translate_keyword(keyword)
        if translated != keyword:
            fling_results = _do_search(translated, all_trainers)
    
    results.extend(fling_results)
    
    # 按相关度排序（完全包含 > 模糊匹配）
    kw_lower = keyword.lower()
    results.sort(key=lambda t: _score(t, kw_lower))
    return results[:50]   # 最多返回 50 条


# ── 下载 ─────────────────────────────────────────────────────

def _get_direct_download_url(trainer: dict) -> Optional[str]:
    """
    获取直接下载链接。
    - archive/main 来源：需要进详情页找下载链接
    """
    url = trainer.get('url', '')
    source = trainer.get('source', '')
    game_name = trainer.get('game_name', '')
    
    if source == 'archive' and url:
        # archive 链接可能是直接的下载链接，也可能是 HTML 页面
        # 先检查是否是直接的下载链接（包含文件扩展名或 files 目录）
        if url.endswith(('.zip', '.rar', '.exe', '.7z')) or '/files/' in url:
            return url
        
        # 如果不是直接链接，尝试解析 HTML 页面找下载链接
        try:
            scraper = _create_scraper()
            resp = scraper.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 方法1：找 target="_self" 的链接（与 GCM 一致）
            for a in soup.find_all('a', target='_self'):
                href = a.get('href', '')
                if href:
                    # 确保是完整的 URL
                    if href.startswith('http'):
                        return href
                    elif href.startswith('/'):
                        return urljoin('https://archive.flingtrainer.com/', href)
            
            # 方法2：找所有压缩包链接
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.endswith(('.zip', '.rar', '.exe', '.7z')):
                    if href.startswith('http'):
                        return href
                    else:
                        return urljoin('https://archive.flingtrainer.com/', href)
            
            # 方法3：找包含 files 目录的链接
            for a in soup.find_all('a', href=True):
                href = a['href']
                if '/files/' in href or 'download' in href.lower():
                    if href.startswith('http'):
                        return href
                    elif href.startswith('/'):
                        return urljoin('https://archive.flingtrainer.com/', href)
        except Exception as e:
            print(f"[TrainerBackend] 解析 archive 页面失败: {e}")

    if source == 'main' and url:
        try:
            scraper = _create_scraper()
            resp = scraper.get(url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 方法1：找 download 按钮或链接 (target="_self") - 参考GCM实现
            # 关键：只要href中包含flingtrainer.com即可，不要求特定后缀
            for a in soup.find_all('a', target='_self'):
                href = a.get('href', '')
                if 'flingtrainer.com' in href:
                    return href
            
            # 方法2：找所有压缩包链接
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.endswith(('.zip', '.rar', '.exe', '.7z')):
                    return href
            
            # 方法3：找 form post 提交
            form = soup.find('form', action=re.compile(r'flingtrainer', re.I))
            if form:
                action = form.get('action', '')
                if action:
                    return urljoin(url, action)
            
            # 方法4：找 meta refresh 重定向
            meta = soup.find('meta', attrs={'http-equiv': 'refresh'})
            if meta and meta.get('content'):
                match = re.search(r'url=([^\s"]+)', meta['content'], re.I)
                if match:
                    return urljoin(url, match.group(1))
            
            # 方法5：找 data-url 或 data-href 属性
            for elem in soup.find_all(attrs={'data-url': True}):
                href = elem.get('data-url', '')
                if href:
                    return urljoin(url, href)
            for elem in soup.find_all(attrs={'data-href': True}):
                href = elem.get('data-href', '')
                if href:
                    return urljoin(url, href)
            
            # 方法6：找 JavaScript 中的下载链接
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    # 匹配各种 JS 下载模式
                    patterns = [
                        r'["\']([^"\']*flingtrainer[^"\']*\.(zip|rar|7z)[^"\']*)["\']',
                        r'["\']([^"\']*download[^"\']*\.(zip|rar|7z)[^"\']*)["\']',
                        r'window\.location\s*=\s*["\']([^"\']+)["\']',
                        r'document\.location\s*=\s*["\']([^"\']+)["\']',
                        r'location\.href\s*=\s*["\']([^"\']+)["\']',
                        r'url:\s*["\']([^"\']+)["\']',
                        r'["\']https?://[^"\']*\.zip["\']',
                    ]
                    for pattern in patterns:
                        matches = re.findall(pattern, script.string, re.I)
                        for m in matches:
                            if isinstance(m, str) and (m.startswith('http') or '.zip' in m.lower() or '.rar' in m.lower()):
                                if m.startswith('http'):
                                    return m
                                else:
                                    return urljoin(url, m)
            
            # 方法7：查找包含 "download" 文字的链接
            for a in soup.find_all('a', href=True):
                text = a.get_text(strip=True).lower()
                if 'download' in text or '下载' in text:
                    href = a['href']
                    if href.startswith('http'):
                        return href
            
            # 方法8：查找按钮中的链接
            for btn in soup.find_all('button'):
                onclick = btn.get('onclick', '')
                if onclick:
                    matches = re.findall(r'["\']([^"\']+\.(zip|rar|7z)[^"\']*)["\']', onclick, re.I)
                    if matches:
                        return urljoin(url, matches[0][0])
                href = btn.get('href')
                if href:
                    if href.endswith(('.zip', '.rar', '.exe')):
                        return href
            
            # 方法9：从 archive 搜索获取
            archive_search_url = f"https://archive.flingtrainer.com/search?q={game_name.replace(' ', '+')}"
            try:
                resp2 = scraper.get(archive_search_url, timeout=10)
                if resp2.status_code == 200:
                    soup2 = BeautifulSoup(resp2.text, 'html.parser')
                    for a in soup2.find_all('a', href=True):
                        href = a['href']
                        if href.endswith(('.zip', '.rar', '.exe')):
                            return urljoin('https://archive.flingtrainer.com/', href)
            except:
                pass
                
        except Exception as e:
            print(f"[TrainerBackend] 获取详情页失败: {e}")
    
    return None


def _find_fname(response) -> str:
    cd = response.headers.get('content-disposition', '')
    if 'filename*=' in cd:
        enc = cd.split('filename*=')[-1].strip('";')
        if enc.upper().startswith("UTF-8''"):
            enc = enc[7:]
        return unquote(enc)
    if 'filename=' in cd:
        return cd.split('filename=')[-1].strip('";')
    name = urlparse(response.url).path.split('/')[-1]
    return unquote(name) or 'trainer.zip'


def download_trainer(
    trainer: dict,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    log_cb: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    下载并安装修改器。
    返回: {"success": bool, "path": str, "message": str}
    """
    def log(msg: str):
        if log_cb:
            log_cb(msg)
        print(f"[TrainerBackend] {msg}")

    trainer_name = re.sub(r'[\\/:*?"<>|]', '_',
                          trainer.get('trainer_name') or trainer.get('game_name', 'Unknown'))
    source = trainer.get('source', '')

    log("正在获取下载链接...")
    dl_url = _get_direct_download_url(trainer)
    if not dl_url:
        return {"success": False, "path": "", "message": "无法获取下载链接，请检查网络或稍后重试"}
    
    log(f"正在下载: {trainer_name}")
    tmp_dir = Path(tempfile.gettempdir()) / "FluentInstallTrainer"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 根据来源决定使用哪种下载方式
        # GCM 数据源使用签名 URL，直接下载不需要 cloudscraper
        if source in ('xiaoxing', 'ct', 'gcm'):
            # 签名 URL 通常是 S3 或类似的直接下载链接
            log(f"使用签名URL下载: {dl_url[:80]}...")
            resp = requests.get(dl_url, stream=True, timeout=120, 
                               headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            resp.raise_for_status()
        else:
            # archive/main 来源使用 cloudscraper（可能需要绕过 Cloudflare）
            scraper = _create_scraper()
            resp = scraper.get(dl_url, stream=True, timeout=120)
            resp.raise_for_status()
            
            # 检测是否是 HTML 页面（而非实际文件）
            content_type = resp.headers.get('content-type', '').lower()
            if 'text/html' in content_type or resp.text.strip().startswith('<!DOCTYPE') or resp.text.strip().startswith('<html'):
                # 是 HTML 页面，尝试解析下载链接
                log("下载的是页面，尝试解析下载链接...")
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # 尝试找下载链接
                download_url = None
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if href.endswith(('.zip', '.rar', '.7z')) or 'download' in href.lower():
                        if href.startswith('http'):
                            download_url = href
                            break
                        elif href.startswith('/'):
                            download_url = urljoin(dl_url, href)
                            break
                
                # 尝试找 meta refresh 或 JavaScript 重定向
                if not download_url:
                    meta = soup.find('meta', attrs={'http-equiv': 'refresh'})
                    if meta and meta.get('content'):
                        import re as re_module
                        match = re_module.search(r'url=([^\s"]+)', meta['content'], re.I)
                        if match:
                            download_url = urljoin(dl_url, match.group(1))
                
                if download_url:
                    log(f"找到实际下载链接: {download_url}")
                    resp = scraper.get(download_url, stream=True, timeout=120)
                    resp.raise_for_status()
                else:
                    return {"success": False, "path": "", "message": "无法解析下载链接，网站结构可能已更改"}
        
        fname = _find_fname(resp)
        tmp_file = tmp_dir / fname
        
        # 如果文件没有扩展名但实际是压缩文件，修正扩展名
        if not tmp_file.suffix.lower() in ('.zip', '.rar', '.7z', '.exe', '.ct', '.cetrainer'):
            # 检测实际文件类型
            first_bytes = resp.content[:4]
            if first_bytes == b'PK\x03\x04':  # ZIP 文件签名
                tmp_file = tmp_dir / (fname + '.zip')
            elif first_bytes == b'Rar!':  # RAR 文件签名
                tmp_file = tmp_dir / (fname + '.rar')
        
        total = int(resp.headers.get('content-length', 0))
        downloaded = 0
        with open(tmp_file, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)
    except Exception as e:
        return {"success": False, "path": "", "message": f"下载失败: {e}"}

    # 目标目录
    dest_dir = get_trainer_dir() / trainer_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    ext = tmp_file.suffix.lower()
    
    # 如果扩展名不对，检测实际文件类型
    if ext not in ('.zip', '.rar', '.7z'):
        try:
            with open(tmp_file, 'rb') as f:
                header = f.read(4)
            if header == b'PK\x03\x04':
                ext = '.zip'
                tmp_file = Path(str(tmp_file) + '.zip')
        except:
            pass
    
    # 解压到临时目录
    extracted_dir = tmp_dir / "extracted"
    if extracted_dir.exists():
        shutil.rmtree(extracted_dir)
    extracted_dir.mkdir(parents=True)
    
    if ext == '.zip':
        log("正在解压...")
        try:
            try:
                with zipfile.ZipFile(tmp_file, 'r') as zf:
                    zf.extractall(extracted_dir)
            except zipfile.BadZipFile:
                z7, tool = _find_unrar_tool()
                if z7:
                    log(f"正在解压 ({tool})...")
                    subprocess.run(
                        [z7, 'x', '-y', '-o' + str(extracted_dir), str(tmp_file)],
                        check=True, creationflags=subprocess.CREATE_NO_WINDOW,
                        timeout=60
                    )
                else:
                    raise Exception("ZIP 文件无效且未安装解压工具")
            tmp_file.unlink(missing_ok=True)
        except Exception as e:
            return {"success": False, "path": "", "message": f"解压失败: {e}"}
    elif ext == '.rar':
        # 优先使用 7z 解压 RAR（更可靠）
        z7, tool = _find_unrar_tool()
        if z7:
            log(f"正在解压 RAR ({tool})...")
            try:
                # 使用 shell=True 确保路径特殊字符被正确处理
                cmd = f'"{z7}" x -y "{tmp_file}" -o"{extracted_dir}"'
                result = subprocess.run(
                    cmd,
                    shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=60,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    tmp_file.unlink(missing_ok=True)
                else:
                    # 尝试回退
                    if tool == 'winrar':
                        # WinRAR UnRAR.exe 可能不支持，用 rarfile 库
                        raise Exception("UnRAR failed, trying rarfile...")
                    raise Exception(f"Extraction failed: {result.stderr or 'Unknown error'}")
            except Exception as fallback_err:
                if 'rarfile' not in str(fallback_err):
                    log(f"命令行解压失败，尝试 rarfile 库: {fallback_err}")
                
                try:
                    import rarfile
                    # 设置 7z
                    if z7:
                        rarfile.UNRAR_TOOL = z7
                    
                    log("正在解压 RAR (rarfile)...")
                    with rarfile.RarFile(tmp_file, 'r') as rf:
                        rf.extractall(extracted_dir)
                    tmp_file.unlink(missing_ok=True)
                except ImportError:
                    # 移动原始文件而不是解压
                    shutil.move(str(tmp_file), str(extracted_dir / tmp_file.name))
                    return {"success": False, "path": "", "message": f"解压失败，请安装 7-Zip: {fallback_err}"}
                except Exception as e:
                    return {"success": False, "path": "", "message": f"解压失败: {e}"}
        else:
            # 没有找到解压工具，尝试 rarfile
            try:
                import rarfile
                log("正在解压 RAR (rarfile)...")
                with rarfile.RarFile(tmp_file, 'r') as rf:
                    rf.extractall(extracted_dir)
                tmp_file.unlink(missing_ok=True)
            except ImportError:
                shutil.move(str(tmp_file), str(extracted_dir / tmp_file.name))
                return {"success": False, "path": "", "message": "请安装 7-Zip 来解压 RAR 文件"}
            except Exception as e:
                return {"success": False, "path": "", "message": f"解压失败: {e}"}
    elif ext == '.7z':
        tool_path, tool = _find_unrar_tool()
        if tool_path:
            log(f"正在解压 ({tool})...")
            try:
                subprocess.run(
                    [tool_path, 'x', '-y', str(tmp_file), f'-o{extracted_dir}'],
                    check=True, creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=60
                )
                tmp_file.unlink(missing_ok=True)
            except Exception as e:
                return {"success": False, "path": "", "message": f"解压失败: {e}"}
        else:
            shutil.move(str(tmp_file), str(extracted_dir / tmp_file.name))
            return {"success": False, "path": "", "message": "请安装 7-Zip 来解压 7z 文件"}
    else:
        # 非压缩文件（如 .ct, .exe），直接移动
        shutil.move(str(tmp_file), str(extracted_dir / tmp_file.name))
    
    # 处理解压后的文件结构（参考 GCM 的 handle_multi_version_archive 逻辑）
    temp_contents = os.listdir(extracted_dir)
    has_executable_in_root = any(
        file.lower().endswith((".exe", ".ct", ".cetrainer", ".png"))
        for file in temp_contents
        if os.path.isfile(os.path.join(extracted_dir, file))
    )
    folders = [item for item in temp_contents if os.path.isdir(os.path.join(extracted_dir, item)) and item != "gcm-instructions"]
    
    # 检查是否有 gcm-instructions 文件夹（单文件训练器的说明文件夹）
    instructions_folder = extracted_dir / "gcm-instructions"
    if instructions_folder.exists() and instructions_folder.is_dir():
        # 移动 gcm-instructions 到目标目录
        instructions_dest = dest_dir / "gcm-instructions"
        if instructions_dest.exists():
            shutil.rmtree(instructions_dest)
        shutil.move(str(instructions_folder), str(instructions_dest))
        log("检测到说明文件夹，将一起移动")
    
    # 处理多版本文件夹
    if not has_executable_in_root and len(folders) > 0:
        # 解压后是多个版本文件夹，每个版本移动到单独的目录
        for folder_name in folders:
            source_path = extracted_dir / folder_name
            safe_folder_name = re.sub(r'[\\/:*?"<>|]', '_', folder_name.strip())
            version_dest = dest_dir.parent / f"{trainer_name} {safe_folder_name}"
            version_dest.mkdir(parents=True, exist_ok=True)
            
            # 移动文件夹内容
            for item in os.listdir(source_path):
                src = source_path / item
                dst = version_dest / item
                if dst.exists():
                    if dst.is_file():
                        dst.chmod(stat.S_IWRITE)
                        dst.unlink()
                shutil.move(str(src), str(dst))
        
        # 删除空的源文件夹
        shutil.rmtree(extracted_dir)
        
        # 如果 dest_dir 为空，删除它
        if dest_dir.exists() and not any(dest_dir.iterdir()):
            dest_dir.rmdir()
        
        log(f"✅ 下载完成（多版本）: {dest_dir.parent / trainer_name}")
        return {"success": True, "path": str(dest_dir.parent / trainer_name), "message": "下载成功"}
    else:
        # 单个训练器，直接移动解压内容到目标目录
        for item in os.listdir(extracted_dir):
            src = extracted_dir / item
            dst = dest_dir / item
            if dst.exists():
                if dst.is_dir():
                    shutil.rmtree(dst)
                else:
                    dst.chmod(stat.S_IWRITE)
                    dst.unlink()
            shutil.move(str(src), str(dst))
        
        # 删除临时解压目录
        if extracted_dir.exists():
            shutil.rmtree(extracted_dir)

    # 写元信息
    info = {
        "game_name": trainer.get('game_name', ''),
        "source":    trainer.get('source', ''),
        "version":   trainer.get('version', ''),
        "author":    trainer.get('author', ''),
    }
    try:
        (dest_dir / 'gcm_info.json').write_text(
            json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8'
        )
    except Exception:
        pass

    log(f"✅ 下载完成: {dest_dir}")
    return {"success": True, "path": str(dest_dir), "message": "下载成功"}


def _find_unrar_tool():
    """查找可用的解压工具（优先7-Zip，其次WinRAR）"""
    # 7-Zip 路径
    for p in [r"C:\Program Files\7-Zip\7z.exe",
              r"C:\Program Files (x86)\7-Zip\7z.exe"]:
        if os.path.isfile(p):
            return p, '7z'
    
    # WinRAR 路径
    for p in [r"C:\Program Files\WinRAR\UnRAR.exe",
              r"C:\Program Files (x86)\WinRAR\UnRAR.exe"]:
        if os.path.isfile(p):
            return p, 'winrar'
    
    return None, None


# ── 已安装修改器管理 ──────────────────────────────────────────

def list_installed_trainers() -> list:
    base = get_trainer_dir()
    trainers = []
    default_exts = {'.exe', '.ct', '.cetrainer'}

    for entry in base.iterdir():
        if entry.is_file():
            if entry.suffix.lower() in default_exts and entry.stat().st_size > 0:
                trainers.append({
                    "name": entry.stem, "path": str(entry),
                    "exe": str(entry), "source": "", "version": "",
                })
        elif entry.is_dir():
            info: dict = {}
            info_file = entry / 'gcm_info.json'
            if info_file.exists():
                try:
                    info = json.loads(info_file.read_text(encoding='utf-8'))
                except Exception:
                    pass

            custom_ext = info.get('extension')
            target_exts = ['.' + custom_ext] if custom_ext and custom_ext != 'none' else list(default_exts)
            exe_path: Optional[str] = None
            for ext in target_exts:
                for f in entry.iterdir():
                    if f.is_file() and f.suffix.lower() == ext:
                        exe_path = str(f)
                        break
                if exe_path:
                    break

            if exe_path or custom_ext == 'none':
                trainers.append({
                    "name":    entry.name,
                    "path":    str(entry),
                    "exe":     exe_path or str(entry),
                    "source":  info.get('source', ''),
                    "version": info.get('version', ''),
                })

    trainers.sort(key=lambda x: x['name'].lower())
    return trainers


def launch_trainer(exe_path: str) -> bool:
    import ctypes
    try:
        if os.path.isdir(exe_path):
            os.startfile(exe_path)
            return True
        ext = os.path.splitext(exe_path)[1].lower()
        verb = 'runas' if ext == '.exe' else 'open'
        ctypes.windll.shell32.ShellExecuteW(
            None, verb, exe_path, None, os.path.dirname(exe_path), 1
        )
        return True
    except Exception as e:
        print(f"[TrainerBackend] 启动失败: {e}")
        return False


def delete_trainer(trainer_path: str) -> bool:
    try:
        p = Path(trainer_path)
        if p.is_dir():
            shutil.rmtree(p)
        else:
            parent = p.parent
            if parent.name == p.stem:
                shutil.rmtree(parent)
            else:
                p.chmod(stat.S_IWRITE)
                p.unlink()
        return True
    except Exception as e:
        print(f"[TrainerBackend] 删除失败: {e}")
        return False


# 模块初始化：设置 rarfile 路径
_setup_rarfile_path()
