from flask import Flask, request, render_template, Response, jsonify
import requests, math
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import base64
from flask_caching import Cache
import re

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple', 'CACHE_DEFAULT_TIMEOUT': 300})
BASE_URL = "http://212.86.121.175/"
VERIFY_URL = BASE_URL + "?verify_human=1"
HEADERS = {"User-Agent": "Mozilla/5.0"}

session = requests.Session()

def safe_get(url, params=None, headers=None, timeout=5, **kwargs):
    # bypass verify dulu — tapi JANGAN bikin request utama gagal kalau verify-nya mati
    try:
        session.get(
            VERIFY_URL,
            headers=HEADERS,
            timeout=5
        )
    except Exception as e:
        print(f"⚠️ Verify dilewati: {e}")

    try:
        # request target
        return session.get(
            url,
            params=params,
            headers=headers or HEADERS,
            timeout=timeout,
            **kwargs
        )

    except Exception as e:
        print(f"❌ Error: {e}")
        return None
        
        
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

GENRES = {
    'action': 'Action',
    'adventure': 'Adventure',
    'animation': 'Animation',
    'anime': 'Anime',
    'comedy': 'Comedy',
    'drama': 'Drama',
    'fantasy-epic': 'Fantasy',
    'isekai': 'Isekai',
    'mystery': 'Mystery',
    'psychological': 'Psychological',
    'romance': 'Romance',
    'sci-fi': 'Sci-Fi'
}

@cache.memoize(timeout=300)
def scrape_single_page(page_num):
    """Scrape SINGLE PAGE saja - sangat ringan"""
    url = f"{BASE_URL}/page/{page_num}/"
    try:
        r = safe_get(url, headers=HEADERS, timeout=5)
        if r.status_code != 200: 
            return []
        
        soup = BeautifulSoup(r.text, "html.parser")
        dramas = []
        
        for a in soup.find_all("a", href=True):
            title = a.get("title")
            eps = a.find("span", class_="epx")
            jam = a.find("div", class_="timeago")
            thumb = a.find("img")
            if title and eps and jam:
                slug = urlparse(a["href"]).path.lstrip("/")
                is_movie = is_movie_content(slug)
                is_hot = bool(a.find("div", class_="hotbadge"))
                dramas.append({
                    "title": title.strip(),
                    "eps": eps.text.strip(),
                    "jam": jam.text.strip(),
                    "thumb": thumb["src"] if thumb else "",
                    "link": slug,
                    "type": "movie" if is_movie else "series",
                    "hot": is_hot
                })
        
        print(f"📄 Scraped page {page_num}: {len(dramas)} dramas")
        return dramas
        
    except Exception as e:
        print(f"❌ Error scraping page {page_num}: {e}")
        return []

@cache.memoize(timeout=300)
def scrape_movies_only(page_num):
    """Scrape khusus FILM saja - handle pagination untuk film"""
    dramas = []
    start_page = (page_num - 1) * 3 + 1  # 3 page per pagination
    pages_to_scrape = 3
    
    for current_page in range(start_page, start_page + pages_to_scrape):
        url = f"{BASE_URL}/page/{current_page}/"
        try:
            r = safe_get(url, headers=HEADERS, timeout=5)
            if r.status_code != 200: 
                continue
            
            soup = BeautifulSoup(r.text, "html.parser")
            
            for a in soup.find_all("a", href=True):
                title = a.get("title")
                eps = a.find("span", class_="epx")
                jam = a.find("div", class_="timeago")
                thumb = a.find("img")
                
                if title and eps and jam:
                    slug = urlparse(a["href"]).path.lstrip("/")
                    # FILTER: hanya ambil yang movie
                    if is_movie_content(slug):
                        dramas.append({
                            "title": title.strip(),
                            "eps": eps.text.strip(),
                            "jam": jam.text.strip(),
                            "thumb": thumb["src"] if thumb else "",
                            "link": slug,
                            "type": "movie"
                        })
            
            print(f"🎬 Movie search page {current_page}: Found {len(dramas)} movies")
            
        except Exception as e:
            print(f"❌ Error scraping movie page {current_page}: {e}")
            continue
    
    return dramas

@cache.memoize(timeout=300) 
def scrape_series_only(page_num):
    """Scrape khusus SERIES saja - handle pagination untuk series"""
    dramas = []
    start_page = (page_num - 1) * 2 + 1  # 2 page per pagination
    pages_to_scrape = 2
    
    for current_page in range(start_page, start_page + pages_to_scrape):
        url = f"{BASE_URL}/page/{current_page}/"
        try:
            r = safe_get(url, headers=HEADERS, timeout=5)
            if r.status_code != 200: 
                continue
            
            soup = BeautifulSoup(r.text, "html.parser")
            
            for a in soup.find_all("a", href=True):
                title = a.get("title")
                eps = a.find("span", class_="epx")
                jam = a.find("div", class_="timeago")
                thumb = a.find("img")
                
                if title and eps and jam:
                    slug = urlparse(a["href"]).path.lstrip("/")
                    # FILTER: hanya ambil yang series (bukan movie)
                    if not is_movie_content(slug):
                        dramas.append({
                            "title": title.strip(),
                            "eps": eps.text.strip(),
                            "jam": jam.text.strip(),
                            "thumb": thumb["src"] if thumb else "",
                            "link": slug,
                            "type": "series"
                        })
            
            print(f"📺 Series search page {current_page}: Found {len(dramas)} series")
            
        except Exception as e:
            print(f"❌ Error scraping series page {current_page}: {e}")
            continue
    
    return dramas

@cache.memoize(timeout=300)
def scrape_filtered_page(page_num, country=None, category=None, genre=None, status=None):
    """Scrape SINGLE PAGE untuk filter"""
    params = {}

    if genre:
        if page_num == 1:
            url = f"{BASE_URL}/genres/{genre}/"
        else:
            url = f"{BASE_URL}/genres/{genre}/page/{page_num}/"
    elif status:
        url = f"{BASE_URL}/series/"
        params = {'status': status, 'type': '', 'order': 'update', 'page': page_num}
    elif country and category:
        url = f"{BASE_URL}/series/"
        params = {
            'country[]': country,
            'type': category.capitalize() if category != 'tv-show' else 'TV Show',
            'order': 'update',
            'page': page_num
        }
    elif country:
        if page_num == 1:
            url = f"{BASE_URL}/country/{country}/"
        else:
            url = f"{BASE_URL}/country/{country}/page/{page_num}/"
    elif category:
        url = f"{BASE_URL}/series/"
        if category == 'animation':
            params = {'genre[0]': 'animation', 'type': '', 'order': 'update', 'page': page_num}
        elif category == 'tv-show':
            params = {'type': 'TV Show', 'order': 'update', 'page': page_num}
        else:
            params = {'type': category.capitalize(), 'order': 'update', 'page': page_num}
    else:
        return []
    
    try:
        r = safe_get(url, params=params, headers=HEADERS, timeout=5)
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
    
    print(f"🎯 Filter {country or category} page {page_num}: {len(dramas)} dramas")
    return dramas

@cache.memoize(timeout=300)
def search_drama(query):
    """Search drama - 1 page saja"""
    url = f"{BASE_URL}/?s={query}"
    r = safe_get(url, headers=HEADERS, timeout=5)
    if not r or r.status_code != 200:
        return []
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
def is_movie_content(slug):
    slug_lower = slug.lower()
    if 'movie' in slug_lower and 'episode' not in slug_lower: return True
    movie_pattern = re.search(r'-\d{4}($|-)', slug_lower)
    if movie_pattern and 'episode' not in slug_lower: return True
    if 'bluray' in slug_lower and 'episode' not in slug_lower: return True
    return False

@cache.memoize(timeout=300)
def get_all_episodes_from_series(slug):
    url = urljoin(BASE_URL, slug)
    try:
        r = safe_get(url, headers=HEADERS, timeout=5)
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
def get_film_pilihan():
    try:
        r = safe_get(BASE_URL, headers=HEADERS, timeout=5)
        if not r or r.status_code != 200: return []
        soup = BeautifulSoup(r.text, "html.parser")
        films = []
        for article in soup.select("article.stylefor"):
            a = article.select_one("a.tip, a[href]")
            if not a: continue
            title = a.get("title") or a.text.strip()
            thumb = article.select_one("img")
            slug = urlparse(a["href"]).path.lstrip("/")
            films.append({
                "title": title.strip(),
                "thumb": thumb["src"] if thumb else "",
                "link": slug,
            })
        return films[:8]
    except Exception as e:
        print(f"Film pilihan error: {e}")
        return []

@cache.memoize(timeout=300)
def get_series_baru():
    try:
        r = safe_get(BASE_URL, headers=HEADERS, timeout=5)
        if not r or r.status_code != 200: return []
        soup = BeautifulSoup(r.text, "html.parser")
        series = []
        for li in soup.select(".serieslist ul li"):
            a = li.select_one(".leftseries h4 a") or li.select_one("a.series")
            if not a: continue
            title = a.get("title") or a.text.strip()
            if not title:
                img_alt = li.select_one("img")
                title = img_alt.get("alt", "").strip() if img_alt else ""
            if not title: continue
            thumb = li.select_one("img")
            slug = urlparse(a["href"]).path.lstrip("/")
            genres_el = li.select(".leftseries span a")
            genres = [g.text.strip() for g in genres_el]
            date_spans = li.select(".leftseries span")
            date = date_spans[-1].text.strip() if date_spans else ""
            series.append({
                "title": title,
                "thumb": thumb["src"] if thumb else "",
                "link": slug,
                "genres": genres[:3],
                "date": date,
            })
        return series[:6]
    except Exception as e:
        print(f"Series baru error: {e}")
        return []


@cache.memoize(timeout=300)
def scrape_movie_page(page=1):
    """Scrape film dari /series/?type=Movie"""
    try:
        url = f"{BASE_URL}/series/?type=Movie&order=update&page={page}"
        r = safe_get(url, headers=HEADERS, timeout=5)
        if not r or r.status_code != 200: return [], 1
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
            dramas.append({
                "title": title.strip(),
                "eps": eps.text.strip() if eps else "",
                "jam": jam.text.strip() if jam else "",
                "thumb": thumb["src"] if thumb else "",
                "link": slug,
                "type": "movie",
                "hot": False
            })
        has_next = soup.select_one(".hpage a.r") is not None
        total = 50 if has_next else page
        return dramas, total
    except Exception as e:
        print(f"scrape_movie_page error: {e}")
        return [], 1

@cache.memoize(timeout=300)
def get_ongoing_dramas():
    """Mendapatkan list drama yang sedang tayang"""
    try:
        url = BASE_URL
        r = safe_get(url, headers=HEADERS, timeout=5)
        if r.status_code != 200:
            return []
        
        soup = BeautifulSoup(r.text, "html.parser")
        ongoing_section = soup.select_one(".ongoingseries")
        
        if not ongoing_section:
            return []
        
        ongoing_dramas = []
        for li in ongoing_section.select("li"):
            a = li.find("a", href=True)
            if not a:
                continue
                
            title_span = li.select_one(".l")
            episode_span = li.select_one(".r")
            
            if title_span and episode_span:
                # Bersihkan judul dari icon
                title_text = title_span.text.strip()
                if "›" in title_text:
                    title_text = title_text.split("›", 1)[1].strip()
                
                drama_data = {
                    "title": title_text,
                    "episode": episode_span.text.strip(),
                    "link": urlparse(a["href"]).path.lstrip("/")
                }
                ongoing_dramas.append(drama_data)
        
        return ongoing_dramas[:10]  # Limit to 10 items
        
    except Exception as e:
        print(f"Error getting ongoing dramas: {e}")
        return []

@cache.memoize(timeout=300)
def get_drama_detail(slug):
    url = urljoin(BASE_URL, slug)
    try:
        r = safe_get(url, headers=HEADERS, timeout=5)
        if r.status_code != 200:
            fallback_url = f"{BASE_URL}/{slug}"
            r = safe_get(fallback_url, headers=HEADERS, timeout=5)
            if r.status_code != 200:
                return {"title": "Error - Content Not Found", "videos": [], "downloads": [], "all_episodes": [], "sinopsis": ""}
    except:
        return {"title": "Error - Connection Failed", "videos": [], "downloads": [], "all_episodes": [], "sinopsis": ""}
    
    soup = BeautifulSoup(r.text, "html.parser")
    title_tag = soup.find("h1", class_="entry-title")
    title = title_tag.text.strip() if title_tag else "Tanpa Judul"

    # Get alternative titles
    alter_title = ""
    alter_tag = soup.find("span", class_="alter")
    if alter_tag:
        alter_title = alter_tag.text.strip()

    # Get rating
    rating = "0.0"
    rating_tag = soup.find("strong", string=lambda x: x and "Rating" in x)
    if rating_tag:
        rating_text = rating_tag.text.strip()
        rating_match = re.search(r'Rating\s*([\d.]+)', rating_text)
        if rating_match:
            rating = rating_match.group(1)

    # Get drama info
    drama_info = {
        "status": "",
        "network": "",
        "released": "",
        "duration": "",
        "country": "",
        "type": "",
        "episodes": "",
        "director": "",
        "cast": "",
        "genres": []
    }

    # Extract info from .spe section
    spe_section = soup.select_one(".spe")
    if spe_section:
        spans = spe_section.find_all("span")
        for span in spans:
            text = span.get_text().strip()
            if "Status:" in text:
                drama_info["status"] = text.replace("Status:", "").strip()
            elif "Network:" in text:
                drama_info["network"] = re.sub(r'<a[^>]*>|</a>', '', text).replace("Network:", "").strip()
            elif "Dirilis:" in text:
                drama_info["released"] = text.replace("Dirilis:", "").strip()
            elif "Durasi:" in text:
                drama_info["duration"] = text.replace("Durasi:", "").strip()
            elif "Negara:" in text:
                drama_info["country"] = re.sub(r'<a[^>]*>|</a>', '', text).replace("Negara:", "").strip()
            elif "Tipe:" in text:
                drama_info["type"] = text.replace("Tipe:", "").strip()
            elif "Episode:" in text:
                drama_info["episodes"] = text.replace("Episode:", "").strip()
            elif "Sutradara:" in text:
                drama_info["director"] = re.sub(r'<a[^>]*>|</a>', '', text).replace("Sutradara:", "").strip()
            elif "Artis:" in text:
                drama_info["cast"] = re.sub(r'<a[^>]*>|</a>', '', text).replace("Artis:", "").strip()

    # Get genres
    genxed_section = soup.select_one(".genxed")
    if genxed_section:
        genre_links = genxed_section.find_all("a", href=True)
        drama_info["genres"] = [link.text.strip() for link in genre_links]

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
        "alter_title": alter_title,
        "rating": rating,
        "info": drama_info,
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

# FIX
    film_page = int(request.args.get("film_page", 1))
    film_total_pages = 1

    filter_type = request.args.get("type", "all")
    country = request.args.get("country", "")
    category = request.args.get("category", "")
    genre = request.args.get("genre", "")
    status = request.args.get("status", "")
    per_page = 24

    has_filter = bool(country or category or genre or status)

    # Get ongoing dramas
    ongoing_dramas = get_ongoing_dramas()
    film_pilihan = get_film_pilihan() if page == 1 and not q and not has_filter else []
    series_baru = get_series_baru() if page == 1 and not q and not has_filter else []

    dramas_paginated = []
    total_pages = 50

    if has_filter:
        dramas_paginated = scrape_filtered_page(page, country, category, genre, status)
        total_pages = 20
        
    elif q:
        dramas_paginated = search_drama(q)
        total_pages = 1
        
    elif filter_type == "movie":
        dramas_paginated, total_pages = scrape_movie_page(page)
        
        
        
    elif filter_type == "series":
        # SERIES: Single page + filter
        all_dramas = scrape_single_page(page)
        dramas_paginated = [d for d in all_dramas if d.get('type') == 'series']
        total_pages = 50
        
    else:
        dramas_paginated = scrape_single_page(page)
        total_pages = 50

    

    return render_template("index.html", 
                         dramas=dramas_paginated, 
                         q=q, 
                         page=page, 
                         pages=total_pages,
                         country=country,
                         category=category,
                         genre=genre,
                         status=status,
                         countries=COUNTRIES,
                         categories=CATEGORIES,
                         genres=GENRES,
                         ongoing_dramas=ongoing_dramas,
                         film_pilihan=film_pilihan,
                         series_baru=series_baru,
                         film_page=film_page,
                         film_total_pages=film_total_pages,
                         title="OppaDrama")

@app.route("/drama")
def drama_detail_route():
    slug = request.args.get("slug")
    if not slug:
        return "Drama not found", 404
    detail = get_drama_detail(slug)
    return render_template("detail.html", detail=detail, title=detail['title'], current_slug=slug)

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/az')
def az_list():
    letter = request.args.get('show', 'A').upper()
    try:
        url = f"{BASE_URL}/az-lists/?show={letter}"
        r = safe_get(url, headers=HEADERS, timeout=5)
        if not r or r.status_code != 200:
            return render_template("az.html", letter=letter, dramas=[], letters=list('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
        soup = BeautifulSoup(r.text, "html.parser")
        dramas = []
        for article in soup.select("article.bs, .listupd .bs"):
            a = article.select_one("a.tip, a[href]")
            if not a: continue
            title = a.get("title") or a.text.strip()
            thumb = article.select_one("img")
            eps = article.select_one(".epx")
            slug = urlparse(a["href"]).path.lstrip("/")
            dramas.append({
                "title": title.strip(),
                "eps": eps.text.strip() if eps else "",
                "thumb": thumb["src"] if thumb else "",
                "link": slug,
            })
        return render_template("az.html", letter=letter, dramas=dramas, letters=list('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
    except Exception as e:
        print(f"AZ error: {e}")
        return render_template("az.html", letter=letter, dramas=[], letters=list('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'))

@app.route("/suggest")
@cache.cached(timeout=120, query_string=True)
def suggest():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    try:
        url = f"{BASE_URL}/?s={q}"
        r = safe_get(url, headers=HEADERS, timeout=4)
        if not r or r.status_code != 200:
            return jsonify([])
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        for article in soup.select("article.bs")[:6]:
            a = article.select_one("a.tip")
            if not a: continue
            title = a.get("title") or a.text.strip()
            thumb = article.select_one("img")
            eps = article.select_one(".epx")
            status = article.select_one(".status")
            slug = urlparse(a["href"]).path.lstrip("/")
            eps_text = eps.text.strip() if eps else ""
            if eps_text in ["Completed", "Ongoing", ""]:
                eps_text = status.text.strip() if status else ""
            results.append({
                "title": title.strip(),
                "eps": eps_text,
                "thumb": thumb["src"] if thumb else "",
                "link": slug,
            })
        return jsonify(results)
    except Exception as e:
        print(f"Suggest error: {e}")
        return jsonify([])
        

    
if __name__ == "__main__":
    app.run(debug=True)