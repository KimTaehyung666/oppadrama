from flask import Flask, request, render_template, Response
import requests, math
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import base64
from flask_caching import Cache
import re

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple', 'CACHE_DEFAULT_TIMEOUT': 300})
BASE_URL = "http://45.11.57.125/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# KONFIGURASI FILTER
COUNTRIES = {
    'south-korea': 'Korea',
    'china': 'China', 
    'thailand': 'Thailand',
    'japan': 'Jepang',
    'taiwan': 'Taiwan',
    'philippines': 'Filipina',
    'hong-kong': 'Hong Kong',
    'india': 'India',
    'united-states': 'Barat',
    'usa': 'Series Barat'
}

CATEGORIES = {
    'drama': 'Drama',
    'movie': 'Film',
    'tv-show': 'Variety Show',
    'animation': 'Animasi'
}


@cache.memoize(timeout=300)
def get_drama_list_all():
    dramas = []
    for page_num in range(1, 6):
        url = f"{BASE_URL}/page/{page_num}/"
        r = requests.get(url, headers=HEADERS)
        if r.status_code != 200: break
        soup = BeautifulSoup(r.text, "html.parser")
        new_count = 0
        for a in soup.find_all("a", href=True):
            title = a.get("title")
            eps = a.find("span", class_="epx")
            jam = a.find("div", class_="timeago")
            thumb = a.find("img")
            if title and eps and jam:
                slug = urlparse(a["href"]).path.lstrip("/")
                is_movie = is_movie_content(slug)
                dramas.append({
                    "title": title.strip(),
                    "eps": eps.text.strip(),
                    "jam": jam.text.strip(),
                    "thumb": thumb["src"] if thumb else "",
                    "link": slug,
                    "type": "movie" if is_movie else "series"
                })
                new_count += 1
        if new_count == 0: break
    return dramas

@cache.memoize(timeout=300)
def search_drama(query):
    url = f"{BASE_URL}/?s={query}"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    for article in soup.select("article.bs"):
        a = article.select_one("a.tip")
        if not a: continue
        title = a.get("title") or a.text.strip()
        thumb = article.select_one("img")
        eps = article.select_one(".epx")
        slug = urlparse(a["href"]).path.lstrip("/")
        is_movie = is_movie_content(slug)
        results.append({
            "title": title.strip(),
            "eps": eps.text.strip() if eps else "",
            "jam": "",
            "thumb": thumb["src"] if thumb else "",
            "link": slug,
            "type": "movie" if is_movie else "series"
        })
    return results

@cache.memoize(timeout=300)
def get_dramas_by_filter(country=None, category=None, page=1):
    """Mendapatkan drama berdasarkan filter negara dan kategori"""
    params = {}
    
    if country and category:
        url = f"{BASE_URL}/series/"
        params = {
            'country[]': country,
            'type': category.capitalize() if category != 'tv-show' else 'TV Show',
            'order': 'update'
        }
    elif country:
        url = f"{BASE_URL}/country/{country}/"
    elif category:
        if category == 'animation':
            url = f"{BASE_URL}/series/"
            params = {'genre[0]': 'animation', 'type': '', 'order': 'update'}
        elif category == 'tv-show':
            url = f"{BASE_URL}/series/"
            params = {'type': 'TV Show', 'order': 'update'}
        else:
            url = f"{BASE_URL}/series/"
            params = {'type': category.capitalize(), 'order': 'update'}
    else:
        return []
    
    if page > 1:
        if '/country/' in url:
            url = f"{url.rstrip('/')}/page/{page}/"
        else:
            params['page'] = page
    
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        if r.status_code != 200: return []
    except:
        return []
    
    soup = BeautifulSoup(r.text, "html.parser")
    dramas = []
    
    for article in soup.select("article.bs"):
        a = article.select_one("a.tip")
        if not a: continue
        title = a.get("title") or a.text.strip()
        thumb = article.select_one("img")
        eps = article.select_one(".epx")
        jam = article.select_one(".timeago")
        slug = urlparse(a["href"]).path.lstrip("/")
        is_movie = is_movie_content(slug)
        dramas.append({
            "title": title.strip(),
            "eps": eps.text.strip() if eps else "",
            "jam": jam.text.strip() if jam else "",
            "thumb": thumb["src"] if thumb else "",
            "link": slug,
            "type": "movie" if is_movie else "series"
        })
    
    return dramas

@cache.memoize(timeout=300)
def is_movie_content(slug):
    slug_lower = slug.lower()
    if 'movie' in slug_lower and 'episode' not in slug_lower: return True
    movie_pattern = re.search(r'-\d{4}($|-)', slug_lower)
    if movie_pattern and 'episode' not in slug_lower: return True
    if 'bluray' in slug_lower and 'episode' not in slug_lower: return True
    return False

@cache.memoize(timeout=300)
def get_all_episodes_from_series(slug):
    url = urljoin(BASE_URL + "/", slug)
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200: return []
    except: return []
    
    soup = BeautifulSoup(r.text, "html.parser")
    episodes = []
    
    eplister = soup.select_one(".eplister")
    if eplister:
        for li in eplister.select("ul li"):
            a = li.find("a", href=True)
            if not a: continue
            num_elem = li.select_one(".epl-num")
            title_elem = li.select_one(".epl-title")
            episode_slug = urlparse(a["href"]).path.lstrip("/")
            episode_num = ""
            if num_elem:
                episode_num_match = re.search(r'(\d+)', num_elem.text)
                if episode_num_match: episode_num = episode_num_match.group(1)
            if not episode_num and title_elem:
                episode_num_match = re.search(r'(\d+)', title_elem.text)
                if episode_num_match: episode_num = episode_num_match.group(1)
            if not episode_num:
                episode_num_match = re.search(r'episode-(\d+)', episode_slug)
                if episode_num_match: episode_num = episode_num_match.group(1)
            
            episode_data = {
                "num": episode_num if episode_num else f"Episode {len(episodes) + 1}",
                "title": title_elem.text.strip() if title_elem else f"Episode {episode_num}" if episode_num else f"Episode {len(episodes) + 1}",
                "date": "",
                "link": episode_slug
            }
            if not any(ep['link'] == episode_slug for ep in episodes):
                episodes.append(episode_data)
    
    try: episodes.sort(key=lambda x: int(x['num']) if x['num'].isdigit() else 0)
    except: pass
    return episodes

@cache.memoize(timeout=300)
def get_drama_detail(slug):
    url = urljoin(BASE_URL + "/", slug)
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            fallback_url = f"{BASE_URL}/{slug}"
            r = requests.get(fallback_url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                return {"title": "Error - Content Not Found", "videos": [], "downloads": [], "all_episodes": [], "sinopsis": ""}
    except:
        return {"title": "Error - Connection Failed", "videos": [], "downloads": [], "all_episodes": [], "sinopsis": ""}
    
    soup = BeautifulSoup(r.text, "html.parser")
    title_tag = soup.find("h1", class_="entry-title")
    title = title_tag.text.strip() if title_tag else "Tanpa Judul"

    sinopsis = ""
    sinopsis_selectors = [".desc.mindes", ".entry-content p", ".bixbox.infx p", ".wp-block-paragraph", ".sinopsis"]
    for selector in sinopsis_selectors:
        if sinopsis: break
        elements = soup.select(selector)
        for element in elements:
            text = element.get_text().strip()
            if (len(text) > 50 and 
                not text.startswith(('Download', 'Nonton', 'Episode', 'Season')) and
                'sinopsis' not in text.lower() and
                'description' not in text.lower()):
                sinopsis = text
                break

    if not sinopsis:
        all_divs = soup.find_all('div')
        for div in all_divs:
            text = div.get_text().strip()
            if (100 < len(text) < 2000 and 
                not any(keyword in text.lower() for keyword in ['download', 'nonton', 'episode', 'season', 'status:', 'network:', 'dirilis:'])):
                sinopsis = text
                break

    videos = []
    video_content = soup.select_one(".video-content")
    if video_content:
        iframe = video_content.find("iframe")
        if iframe and iframe.get("src"):
            videos.append({"provider": "Default", "url": iframe["src"]})
    
    mirror_select = soup.find("select", class_="mirror")
    if mirror_select:
        for opt in mirror_select.find_all("option"):
            provider = opt.text.strip()
            encoded = opt.get("value")
            if encoded and provider != "Pilih Server Video":
                try:
                    decoded = base64.b64decode(encoded).decode("utf-8", errors="ignore")
                    iframe_soup = BeautifulSoup(decoded, "html.parser")
                    iframe2 = iframe_soup.find("iframe")
                    if iframe2 and iframe2.get("src"):
                        videos.append({"provider": provider, "url": iframe2["src"]})
                except: pass

    downloads = []
    dl_section = soup.find("div", class_="dlbox")
    if dl_section:
        for li in dl_section.find_all("li"):
            if "head" in li.get("class", []): continue
            link = li.find("a", href=True)
            if link:
                server = li.select_one(".q b")
                quality = li.select_one(".w")
                download_text = f"{server.text.strip() if server else ''} {quality.text.strip() if quality else ''}".strip()
                downloads.append({"text": download_text, "url": link["href"]})

    is_movie = is_movie_content(slug)
    has_video_or_download = len(videos) > 0 or len(downloads) > 0
    has_eplister = soup.select_one(".eplister") is not None
    
    if is_movie:
        is_episode = False
        is_series_overview = False
    elif has_video_or_download and has_eplister:
        is_episode = False
        is_series_overview = True
    elif has_video_or_download:
        is_episode = True
        is_series_overview = False
    elif has_eplister:
        is_episode = False
        is_series_overview = True
    else:
        is_episode = False
        is_series_overview = False
        is_movie = True

    series_link = None
    if not is_movie:
        nav = soup.select_one(".naveps .nvsc a")
        if nav and nav.get("href"):
            series_link = urlparse(nav["href"]).path.lstrip("/")
        if not series_link:
            series_info = soup.select_one(".single-info .infox h2 a")
            if series_info and series_info.get("href"):
                series_link = urlparse(series_info["href"]).path.lstrip("/")
    
    episodes = []
    all_series_episodes = []
    if is_series_overview:
        episodes = get_all_episodes_from_series(slug)
        all_series_episodes = episodes
    elif is_episode:
        if series_link:
            all_series_episodes = get_all_episodes_from_series(series_link)
        else:
            series_slug_guess = re.sub(r'-episode-\d+.*$', '', slug).rstrip('/')
            all_series_episodes = get_all_episodes_from_series(series_slug_guess)

    normalized_slug = slug.rstrip('/')
    current_index = -1
    if is_episode:
        for i, ep in enumerate(all_series_episodes):
            normalized_ep_slug = ep['link'].rstrip('/')
            if normalized_slug == normalized_ep_slug:
                current_index = i
                break

    return {
        "title": title, 
        "sinopsis": sinopsis,
        "videos": videos, 
        "downloads": downloads, 
        "series_link": series_link, 
        "episodes": episodes,
        "all_episodes": all_series_episodes,
        "is_movie": is_movie,
        "is_episode": is_episode,
        "is_series_overview": is_series_overview,
        "current_slug": slug,
        "current_index": current_index
    }

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    filter_type = request.args.get("type", "all")
    country = request.args.get("country", "")
    category = request.args.get("category", "")
    per_page = 12

    if country or category:
        dramas_all = get_dramas_by_filter(country=country, category=category, page=page)
        total = len(dramas_all)
        pages = math.ceil(total / per_page) if total > 0 else 1
        dramas_paginated = dramas_all
    elif q:
        dramas_all = search_drama(q)
        total = len(dramas_all)
        pages = math.ceil(total / per_page) if total > 0 else 1
        dramas_paginated = dramas_all[(page - 1) * per_page : page * per_page]
    else:
        dramas_all = get_drama_list_all()
        total = len(dramas_all)
        pages = math.ceil(total / per_page) if total > 0 else 1
        dramas_paginated = dramas_all[(page - 1) * per_page : page * per_page]
    
    if filter_type == "movie":
        dramas_paginated = [d for d in dramas_paginated if d['type'] == 'movie']
    elif filter_type == "series":
        dramas_paginated = [d for d in dramas_paginated if d['type'] == 'series']

    return render_template("index.html", 
                         dramas=dramas_paginated, 
                         q=q, 
                         page=page, 
                         pages=pages,
                         country=country,
                         category=category,
                         countries=COUNTRIES,
                         categories=CATEGORIES,
                         title="OppaDrama")

@app.route("/drama")
def drama_detail_route():
    slug = request.args.get("slug")
    if not slug:
        return "Drama not found", 404
    detail = get_drama_detail(slug)
    return render_template("detail.html", detail=detail, title=detail['title'], current_slug=slug)

if __name__ == "__main__":
    app.run(debug=True)