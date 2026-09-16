"""
Futuristic GitHub Profile Generator & Asset Pipeline
Engineered for Shriyan Bohra (@Shriyan2407)
Cinematic Dark & Gold Command Center — Proportioned for GitHub Profile Width (880px)
"""
import os
import sys
import json
import re
import math
import base64
import urllib.request
import urllib.error
from datetime import datetime, timezone
from PIL import Image

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CONFIG_PATH = os.path.join(WORKSPACE_DIR, 'profile.config.json')
CACHE_PATH = os.path.join(WORKSPACE_DIR, 'data', 'cache.json')
ASSETS_DIR = os.path.join(WORKSPACE_DIR, 'assets')
BANNER_DIR = os.path.join(ASSETS_DIR, 'banner')
UI_DIR = os.path.join(ASSETS_DIR, 'ui')
PROJECTS_DIR = os.path.join(ASSETS_DIR, 'projects')
ICONS_DIR = os.path.join(ASSETS_DIR, 'icons')
README_PATH = os.path.join(WORKSPACE_DIR, 'README.md')

def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Config file not found at {CONFIG_PATH}")
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def escape_xml(text):
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")

def safe_fetch_json(url, token=None):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    if token:
        headers['Authorization'] = f'token {token}'
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"[WARN] Failed fetching {url}: {e}")
        return None

def fetch_all_repos(username, token=None):
    repos = []
    page = 1
    while page <= 10:
        url = f"https://api.github.com/users/{username}/repos?per_page=100&page={page}&sort=updated"
        batch = safe_fetch_json(url, token)
        if not batch or not isinstance(batch, list) or len(batch) == 0:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    print(f"[INFO] Fetched {len(repos)} repositories across {page} pages")
    return repos

def fetch_contributions_data(username):
    url = f"https://github.com/users/{username}/contributions"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8')
            total_match = re.search(r'([0-9,]+)\s+contributions\s+in\s+the\s+last\s+year', html)
            total_count = int(total_match.group(1).replace(',', '')) if total_match else 123
            
            day_matches = re.findall(r'data-date="([0-9]{4}-[0-9]{2}-[0-9]{2})"[^>]*?data-level="([0-4])"', html)
            if not day_matches:
                day_matches = re.findall(r'data-level="([0-4])"[^>]*?data-date="([0-9]{4}-[0-9]{2}-[0-9]{2})"', html)
                day_matches = [(d, lvl) for lvl, d in day_matches]
                
            days = []
            for d, lvl in day_matches:
                days.append({"date": d, "level": int(lvl)})
            
            print(f"[INFO] Fetched {len(days)} contribution days, total count: {total_count}")
            return {"total": total_count, "days": days}
    except Exception as e:
        print(f"[WARN] Failed fetching contribution calendar: {e}")
        return None

def fetch_events(username, token=None):
    url = f"https://api.github.com/users/{username}/events?per_page=100"
    events = safe_fetch_json(url, token)
    return events if isinstance(events, list) else []

def get_profile_data(config):
    username = config.get("username", "Shriyan2407")
    token = os.environ.get("GITHUB_TOKEN")
    
    os.makedirs(os.path.join(WORKSPACE_DIR, 'data'), exist_ok=True)
    cached = None
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                cached = json.load(f)
        except Exception:
            pass

    user = safe_fetch_json(f"https://api.github.com/users/{username}", token)
    repos = fetch_all_repos(username, token) if user else None
    contrib = fetch_contributions_data(username)
    events = fetch_events(username, token) if user else None
    
    if not user and cached:
        print("[WARN] Using cached user data")
        user = cached.get("user", {})
    if not repos and cached:
        print("[WARN] Using cached repos")
        repos = cached.get("repos", [])
    if not contrib and cached:
        print("[WARN] Using cached contributions")
        contrib = cached.get("contrib", {"total": 123, "days": []})
    if not events and cached:
        print("[WARN] Using cached events")
        events = cached.get("events", [])
        
    if not user:
        user = {
            "name": config.get("name", "Shriyan Bohra"),
            "login": username,
            "public_repos": 10,
            "followers": 2,
            "following": 2,
            "bio": "CSE Student | Cybersecurity Enthusiast | Developer"
        }
    if not repos:
        repos = []
    if not contrib:
        contrib = {"total": 123, "days": []}
        
    try:
        with open(CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump({
                "user": user,
                "repos": repos,
                "contrib": contrib,
                "events": events,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }, f, indent=2)
    except Exception as e:
        print(f"[WARN] Failed saving cache: {e}")
        
    return user, repos, contrib, events

def optimize_hero_image():
    raw_banner = os.path.join(ASSETS_DIR, 'banner.png')
    target_png = os.path.join(BANNER_DIR, 'hero.png')
    target_jpg = os.path.join(BANNER_DIR, 'hero.jpg')
    os.makedirs(BANNER_DIR, exist_ok=True)
    
    if not os.path.exists(raw_banner):
        if os.path.exists(target_png):
            raw_banner = target_png
        else:
            print("[WARN] No banner.png found to optimize")
            return None, ""
            
    img = Image.open(raw_banner)
    w, h = img.size
    
    # 880px width (exact 3:1 aspect ratio -> 880x293)
    target_w = 880
    target_h = int(target_w * (h / w))
    img_resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    
    img_resized.convert('RGB').save(target_jpg, format='JPEG', quality=88, optimize=True)
    img_resized.convert('RGB').quantize(colors=256).save(target_png, format='PNG', optimize=True)
    
    with open(target_jpg, 'rb') as f:
        b64_data = base64.b64encode(f.read()).decode('utf-8')
    data_uri = f"data:image/jpeg;base64,{b64_data}"
    
    print(f"[INFO] Optimized hero banner: {target_w}x{target_h}, JPEG size: {os.path.getsize(target_jpg)} bytes")
    return target_png, data_uri

def generate_hero_svg(config, user_data, banner_b64):
    """
    Hero banner with viewBox="0 0 880 293" (perfect 1:1 scale on GitHub profile).
    """
    roles = config.get("roles", ["DEVELOPER", "CYBERSECURITY ENTHUSIAST", "AI EXPLORER"])
    title_1 = config.get("display_title_1", "SHRIYAN")
    title_2 = config.get("display_title_2", "BOHRA")
    quotes = config.get("quotes", {})
    banner_quote = quotes.get("banner_quote", "SAME MIND DIFFERENT PERSPECTIVE")
    banner_tags = quotes.get("banner_tags", "IDEAS • SECURITY • TECHNOLOGY • IMPACT")
    
    role_lines = ""
    y_start = 46
    for i, r in enumerate(roles):
        role_lines += f'<text x="44" y="{y_start + i * 15}" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,monospace" font-size="9.5" font-weight="600" letter-spacing="2">// {escape_xml(r)}</text>\n'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 293" width="100%" height="auto">
  <defs>
    <linearGradient id="goldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FFF5C0" />
      <stop offset="35%" stop-color="#F2D06B" />
      <stop offset="70%" stop-color="#D4AF37" />
      <stop offset="100%" stop-color="#AA820A" />
    </linearGradient>
    <linearGradient id="textFade" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#05070A" stop-opacity="0.96" />
      <stop offset="42%" stop-color="#05070A" stop-opacity="0.82" />
      <stop offset="65%" stop-color="#05070A" stop-opacity="0.3" />
      <stop offset="100%" stop-color="#05070A" stop-opacity="0.0" />
    </linearGradient>
    <linearGradient id="calloutGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#0A0E14" stop-opacity="0.85" />
      <stop offset="100%" stop-color="#141A22" stop-opacity="0.6" />
    </linearGradient>
    <linearGradient id="scanGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#D4AF37" stop-opacity="0" />
      <stop offset="50%" stop-color="#F2D06B" stop-opacity="0.45" />
      <stop offset="100%" stop-color="#D4AF37" stop-opacity="0" />
    </linearGradient>
    <filter id="goldGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="4" result="glow" />
      <feMerge>
        <feMergeNode in="glow" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
    <style>
      @keyframes scan {{
        0% {{ transform: translateY(0); opacity: 0; }}
        15% {{ opacity: 0.6; }}
        85% {{ opacity: 0.6; }}
        100% {{ transform: translateY(293px); opacity: 0; }}
      }}
      @keyframes beacon {{
        0%, 100% {{ opacity: 0.4; r: 2.5px; }}
        50% {{ opacity: 1; r: 4px; }}
      }}
      .scanner {{
        animation: scan 7s linear infinite;
      }}
      .beacon {{
        animation: beacon 2.5s ease-in-out infinite;
      }}
    </style>
  </defs>

  <clipPath id="heroClip">
    <rect width="880" height="293" rx="14" />
  </clipPath>

  <g clip-path="url(#heroClip)">
    <image href="{banner_b64}" width="880" height="293" preserveAspectRatio="xMidYMid slice" />
    <rect width="880" height="293" fill="url(#textFade)" />

    <path d="M0 60 H880 M0 120 H880 M0 180 H880 M0 240 H880" stroke="#FFFFFF" stroke-opacity="0.025" stroke-width="1" />
    <path d="M150 0 V293 M300 0 V293 M450 0 V293 M600 0 V293 M750 0 V293" stroke="#FFFFFF" stroke-opacity="0.025" stroke-width="1" />

    <line x1="0" y1="0" x2="880" y2="0" stroke="url(#scanGrad)" stroke-width="2" class="scanner" />

    <!-- Roles -->
    <g>
      {role_lines}
    </g>

    <!-- Main Title: SHRIYAN BOHRA -->
    <g transform="translate(44, 126)">
      <text x="0" y="0" fill="#F0F6FC" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif" font-size="50" font-weight="900" letter-spacing="5">
        {escape_xml(title_1)}
      </text>
      <text x="0" y="44" fill="url(#goldGrad)" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif" font-size="50" font-weight="900" letter-spacing="5" filter="url(#goldGlow)">
        {escape_xml(title_2)}
      </text>
    </g>

    <!-- Tagline -->
    <g transform="translate(44, 194)">
      <text x="0" y="0" fill="#E6EDF3" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="10" font-weight="700" letter-spacing="2.5">
        BUILD <tspan fill="#D4AF37">›</tspan> LEARN <tspan fill="#D4AF37">›</tspan> EXPLORE <tspan fill="#D4AF37">›</tspan> REPEAT
      </text>
    </g>

    <!-- Callout Box -->
    <g transform="translate(44, 212)">
      <rect width="275" height="38" rx="6" fill="url(#calloutGrad)" stroke="#D4AF37" stroke-width="0.9" stroke-opacity="0.5" />
      <text x="18" y="17" fill="#D4AF37" font-family="SFMono-Regular,Consolas,monospace" font-size="8.5" font-weight="700" letter-spacing="1.5">
        I DON&apos;T JUST WRITE CODE.
      </text>
      <text x="18" y="29" fill="#E6EDF3" font-family="SFMono-Regular,Consolas,monospace" font-size="8.5" font-weight="700" letter-spacing="1.5">
        I ENGINEER SYSTEMS.
      </text>
    </g>

    <!-- Top Right Quotes -->
    <g transform="translate(836, 46)" text-anchor="end">
      <text x="0" y="0" fill="#C9D1D9" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="9.5" font-style="italic" font-weight="500" letter-spacing="1.5">
        &quot;{escape_xml(banner_quote)}&quot;
      </text>
      <text x="0" y="38" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="8" font-weight="600" letter-spacing="2">
        {escape_xml(banner_tags)}
      </text>
      <text x="0" y="90" fill="#D4AF37" font-family="SFMono-Regular,Consolas,monospace" font-size="9" font-weight="700" letter-spacing="2">
        // 24/7
      </text>
    </g>

    <!-- Bottom Status -->
    <g transform="translate(836, 270)" text-anchor="end">
      <circle cx="-85" cy="-3" r="3" fill="#3FB950" class="beacon" />
      <text x="-74" y="0" fill="#3FB950" font-family="SFMono-Regular,Consolas,monospace" font-size="9" font-weight="700" letter-spacing="1.5">
        ONLINE
      </text>
      <text x="0" y="0" fill="#8B949E" font-family="SFMono-Regular,Consolas,monospace" font-size="9" letter-spacing="1.5">
        | NODE_01
      </text>
    </g>

    <rect x="0.75" y="0.75" width="878.5" height="291.5" rx="13.25" fill="none" stroke="#D4AF37" stroke-width="1.1" stroke-opacity="0.4" />
    <path d="M10 22 V10 H22" stroke="#D4AF37" stroke-width="1.8" fill="none" />
    <path d="M858 10 H870 V22" stroke="#D4AF37" stroke-width="1.8" fill="none" />
    <path d="M10 271 V283 H22" stroke="#D4AF37" stroke-width="1.8" fill="none" />
    <path d="M858 283 H870 V271" stroke="#D4AF37" stroke-width="1.8" fill="none" />
  </g>
</svg>'''

    out_path = os.path.join(BANNER_DIR, 'hero.svg')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f"[OK] Generated {out_path}")
    return out_path

def generate_quick_stats_svg(user_data, contrib_data):
    """
    4 metric cards: Repositories, Followers, Following, Total Contributions.
    viewBox="0 0 880 85" (each card: 208px wide x 85px high, gap 16px).
    """
    repos_count = user_data.get("public_repos", 10)
    followers_count = user_data.get("followers", 2)
    following_count = user_data.get("following", 2)
    contrib_total = contrib_data.get("total", 123)
    
    cards = [
        {
            "icon_path": "M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z",
            "val": str(repos_count),
            "label": "Repositories"
        },
        {
            "icon_path": "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2 M9 7a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M23 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75",
            "val": str(followers_count),
            "label": "Followers"
        },
        {
            "icon_path": "M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2 M8.5 7a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M17 11l2 2 4-4",
            "val": str(following_count),
            "label": "Following"
        },
        {
            "icon_path": "M18 20V10 M12 20V4 M6 20v-6",
            "val": str(contrib_total),
            "label": "Total Contributions"
        }
    ]

    card_w = 208
    gap = 16
    
    card_elements = ""
    for i, c in enumerate(cards):
        x = i * (card_w + gap)
        card_elements += f'''
    <g transform="translate({x}, 0)">
      <rect width="{card_w}" height="85" rx="10" fill="#080B10" stroke="#D4AF37" stroke-width="1" stroke-opacity="0.35" />
      <rect x="1" y="1" width="{card_w - 2}" height="2" fill="#D4AF37" fill-opacity="0.3" rx="1" />
      <g transform="translate(20, 24) scale(0.88)">
        <path d="{c['icon_path']}" fill="none" stroke="#D4AF37" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
      </g>
      <text x="56" y="38" fill="#F0F6FC" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="22" font-weight="800" letter-spacing="0.5">
        {c['val']}
      </text>
      <text x="56" y="58" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="11.5" font-weight="600" letter-spacing="0.4">
        {c['label']}
      </text>
    </g>'''

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 85" width="100%" height="auto">
  {card_elements}
</svg>'''

    out_path = os.path.join(UI_DIR, 'stats.svg')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f"[OK] Generated {out_path}")
    return out_path

def generate_about_svg(config):
    """
    viewBox="0 0 430 250" (left column in 2-column table).
    """
    about = config.get("about", {})
    title = about.get("title", "About Me")
    bio = about.get("bio", "I'm a CSE student passionate about cybersecurity, software development, and emerging technologies. I enjoy building practical solutions, learning new things, and exploring the intersection of security, AI, and real-world impact.")
    cta_text = about.get("cta_text", "More about me →")
    
    words = bio.split()
    lines = []
    curr = []
    curr_len = 0
    for w in words:
        if curr_len + len(w) + 1 > 42:
            lines.append(" ".join(curr))
            curr = [w]
            curr_len = len(w)
        else:
            curr.append(w)
            curr_len += len(w) + 1
    if curr:
        lines.append(" ".join(curr))
        
    text_spans = ""
    y_start = 80
    for i, line in enumerate(lines):
        text_spans += f'<text x="74" y="{y_start + i * 19}" fill="#C9D1D9" font-family="-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif" font-size="12" font-weight="400" letter-spacing="0.2">{escape_xml(line)}</text>\n'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 430 250" width="100%" height="auto">
  <defs>
    <linearGradient id="aboutBorder" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#D4AF37" stop-opacity="0.6" />
      <stop offset="100%" stop-color="#D4AF37" stop-opacity="0.15" />
    </linearGradient>
  </defs>

  <rect width="430" height="250" rx="12" fill="#080B10" stroke="url(#aboutBorder)" stroke-width="1.1" />

  <!-- Header -->
  <g transform="translate(24, 34)">
    <path d="M14 16v-2a4 4 0 0 0-4-4H4a4 4 0 0 0-4 4v2 M5 6a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" fill="none" stroke="#D4AF37" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" transform="translate(0, -6) scale(0.9)" />
    <text x="26" y="2" fill="#F0F6FC" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="16" font-weight="700" letter-spacing="0.5">
      {escape_xml(title)}
    </text>
  </g>

  <!-- Left Hexagon Badge -->
  <g transform="translate(24, 74)">
    <rect width="38" height="38" rx="8" fill="#121720" stroke="#D4AF37" stroke-width="1" stroke-opacity="0.5" />
    <path d="M19 8 L29 14 V26 L19 32 L9 26 V14 Z" fill="none" stroke="#D4AF37" stroke-width="1.3" />
    <circle cx="19" cy="20" r="2.8" fill="#D4AF37" />
  </g>

  <!-- Bio Text -->
  <g>
    {text_spans}
  </g>

  <!-- CTA Button -->
  <g transform="translate(24, 194)">
    <rect width="145" height="34" rx="17" fill="#121720" stroke="#D4AF37" stroke-width="1" stroke-opacity="0.7" />
    <text x="72.5" y="21" text-anchor="middle" fill="#F2D06B" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="11.5" font-weight="700" letter-spacing="0.4">
      {escape_xml(cta_text)}
    </text>
  </g>
</svg>'''

    out_path = os.path.join(UI_DIR, 'about.svg')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f"[OK] Generated {out_path}")
    return out_path

def generate_currently_svg(config):
    """
    viewBox="0 0 430 250" (right column in 2-column table).
    """
    items = config.get("currently", [
        {"key": "Building", "text": "Exploring new projects and ideas"},
        {"key": "Learning", "text": "Advanced cybersecurity concepts"},
        {"key": "Exploring", "text": "AI, system design, and secure architecture"},
        {"key": "Focused on", "text": "Becoming a better developer every day"}
    ])
    
    icons_meta = [
        {"color": "#D4AF37", "path": "M12 2L2 7l10 5 10-5-10-5z M2 17l10 5 10-5 M2 12l10 5 10-5"},
        {"color": "#3FB950", "path": "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"},
        {"color": "#58A6FF", "path": "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 18a8 8 0 1 1 0-16 8 8 0 0 1 0 16z"},
        {"color": "#F2D06B", "path": "M12 8v4l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"}
    ]

    item_rows = ""
    y_start = 68
    row_height = 42
    
    for i, it in enumerate(items[:4]):
        meta = icons_meta[i % len(icons_meta)]
        y = y_start + i * row_height
        item_rows += f'''
    <g transform="translate(24, {y})">
      <circle cx="13" cy="13" r="13" fill="#121720" stroke="{meta['color']}" stroke-width="1" stroke-opacity="0.6" />
      <g transform="translate(6, 6) scale(0.55)">
        <path d="{meta['path']}" fill="none" stroke="{meta['color']}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
      </g>
      <text x="36" y="12" fill="#F0F6FC" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="12.5" font-weight="700">
        {escape_xml(it.get('key', ''))}
      </text>
      <text x="36" y="25" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="10.5" font-weight="400">
        {escape_xml(it.get('text', ''))}
      </text>
      <text x="375" y="18" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="14" font-weight="700">
        ›
      </text>
    </g>'''

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 430 250" width="100%" height="auto">
  <defs>
    <linearGradient id="currBorder" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#D4AF37" stop-opacity="0.6" />
      <stop offset="100%" stop-color="#D4AF37" stop-opacity="0.15" />
    </linearGradient>
  </defs>

  <rect width="430" height="250" rx="12" fill="#080B10" stroke="url(#currBorder)" stroke-width="1.1" />

  <g transform="translate(24, 34)">
    <path d="M2 12h4l3-9 4 18 3-9h4" fill="none" stroke="#D4AF37" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" transform="translate(0, -10) scale(0.9)" />
    <text x="26" y="2" fill="#F0F6FC" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="16" font-weight="700" letter-spacing="0.5">
      Currently
    </text>
  </g>

  {item_rows}
</svg>'''

    out_path = os.path.join(UI_DIR, 'currently.svg')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f"[OK] Generated {out_path}")
    return out_path

def generate_tech_stack_svg(config):
    """
    viewBox="0 0 880 135" (full width on GitHub).
    """
    techs = config.get("tech_stack", [])
    if not techs:
        techs = [
            {"name": "Java", "icon": "java.svg"},
            {"name": "JavaScript", "icon": "javascript.svg"},
            {"name": "TypeScript", "icon": "typescript.svg"},
            {"name": "Python", "icon": "python.svg"},
            {"name": "React", "icon": "react.svg"},
            {"name": "Node.js", "icon": "nodejs.svg"},
            {"name": "HTML5", "icon": "html5.svg"},
            {"name": "CSS3", "icon": "css3.svg"},
            {"name": "Git", "icon": "git.svg"},
            {"name": "Docker", "icon": "docker.svg"}
        ]

    tech_items_svg = ""
    col_count = len(techs)
    total_w = 880
    usable_w = total_w - 48
    slot_w = usable_w / col_count

    for i, t in enumerate(techs):
        name = t.get("name", "")
        icon_file = t.get("icon", "")
        icon_path = os.path.join(ICONS_DIR, icon_file)
        
        icon_svg_content = ""
        if os.path.exists(icon_path):
            with open(icon_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                content = re.sub(r'<\?xml.*?\?>', '', content)
                content = re.sub(r'<!DOCTYPE.*?>', '', content, flags=re.DOTALL)
                vb_match = re.search(r'viewBox="([^"]+)"', content)
                vb = vb_match.group(1) if vb_match else "0 0 24 24"
                inner = re.sub(r'<svg[^>]*>', '', content)
                inner = inner.replace('</svg>', '')
                icon_svg_content = f'<svg viewBox="{vb}" width="30" height="30" x="-15" y="-18">{inner}</svg>'
        
        center_x = 24 + (i * slot_w) + (slot_w / 2)
        
        tech_items_svg += f'''
    <g transform="translate({center_x}, 88)">
      <rect x="-34" y="-28" width="68" height="58" rx="8" fill="#0D1117" stroke="#30363D" stroke-width="0.8" stroke-opacity="0.5" />
      <g transform="translate(0, -4)">
        {icon_svg_content}
      </g>
      <text x="0" y="21" text-anchor="middle" fill="#C9D1D9" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="10.5" font-weight="600">
        {escape_xml(name)}
      </text>
    </g>'''

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 135" width="100%" height="auto">
  <defs>
    <linearGradient id="techBorder" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#D4AF37" stop-opacity="0.6" />
      <stop offset="100%" stop-color="#D4AF37" stop-opacity="0.15" />
    </linearGradient>
  </defs>

  <rect width="880" height="135" rx="12" fill="#080B10" stroke="url(#techBorder)" stroke-width="1.1" />

  <!-- Header -->
  <g transform="translate(24, 30)">
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z M3.27 6.96L12 12.01l8.73-5.05 M12 22.08V12" fill="none" stroke="#D4AF37" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" transform="translate(0, -11) scale(0.85)" />
    <text x="26" y="2" fill="#F0F6FC" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="16" font-weight="700" letter-spacing="0.5">
      Tech Stack
    </text>
  </g>

  <!-- Filter Pills -->
  <g transform="translate(510, 18)">
    <rect x="0" y="0" width="50" height="24" rx="12" fill="#D4AF37" />
    <text x="25" y="16" text-anchor="middle" fill="#05070A" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="11" font-weight="700">
      All
    </text>

    <rect x="58" y="0" width="80" height="24" rx="12" fill="#121720" stroke="#30363D" stroke-width="1" />
    <text x="98" y="16" text-anchor="middle" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="11" font-weight="500">
      Languages
    </text>

    <rect x="146" y="0" width="90" height="24" rx="12" fill="#121720" stroke="#30363D" stroke-width="1" />
    <text x="191" y="16" text-anchor="middle" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="11" font-weight="500">
      Frameworks
    </text>

    <rect x="244" y="0" width="55" height="24" rx="12" fill="#121720" stroke="#30363D" stroke-width="1" />
    <text x="271.5" y="16" text-anchor="middle" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="11" font-weight="500">
      Tools
    </text>

    <rect x="307" y="0" width="60" height="24" rx="12" fill="#121720" stroke="#30363D" stroke-width="1" />
    <text x="337" y="16" text-anchor="middle" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="11" font-weight="500">
      Others
    </text>
  </g>

  {tech_items_svg}
</svg>'''

    out_path = os.path.join(UI_DIR, 'tech-stack.svg')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f"[OK] Generated {out_path}")
    return out_path

def generate_repo_card_svg(repo_info, index, total=4):
    """
    viewBox="0 0 210 148" (fits 25% table cell on 880px container: 210px wide).
    """
    name = repo_info.get("display_name") or repo_info.get("name", f"project-{index}")
    desc = repo_info.get("description") or "Exploring modern software engineering and systems."
    lang = repo_info.get("language")
    topics = repo_info.get("topics", [])
    stars = repo_info.get("stargazers_count", 0)
    forks = repo_info.get("forks_count", 0)
    
    lang_colors = {
        "Java": "#B07219",
        "JavaScript": "#F1E05A",
        "TypeScript": "#3178C6",
        "Python": "#3572A5",
        "C": "#555555",
        "HTML": "#E34C26",
        "CSS": "#563D7C"
    }
    dot_color = lang_colors.get(lang, "#D4AF37")
    
    if len(desc) > 65:
        desc = desc[:62].rstrip() + "..."
        
    words = desc.split()
    line1, line2 = "", ""
    curr = []
    for w in words:
        if len(" ".join(curr + [w])) <= 28:
            curr.append(w)
        else:
            if not line1:
                line1 = " ".join(curr)
                curr = [w]
            else:
                curr.append(w)
    if not line1:
        line1 = " ".join(curr)
    else:
        line2 = " ".join(curr)

    tag_pills = ""
    tag_x = 16
    if lang:
        tag_pills += f'''
      <circle cx="{tag_x + 3.5}" cy="94" r="3.5" fill="{dot_color}" />
      <text x="{tag_x + 11}" y="97.5" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="9.5" font-weight="500">{escape_xml(lang)}</text>
    '''
        tag_x += 11 + (len(lang) * 6) + 10

    for t in topics[:1]:
        pill_w = len(t) * 6 + 12
        tag_pills += f'''
      <rect x="{tag_x}" y="86" width="{pill_w}" height="16" rx="8" fill="#161B22" stroke="#30363D" stroke-width="0.8" />
      <text x="{tag_x + pill_w/2}" y="97.5" text-anchor="middle" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="9" font-weight="500">{escape_xml(t)}</text>
    '''
        tag_x += pill_w + 6

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 210 148" width="100%" height="auto">
  <defs>
    <linearGradient id="cardGrad{index}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#D4AF37" stop-opacity="0.4" />
      <stop offset="100%" stop-color="#D4AF37" stop-opacity="0.1" />
    </linearGradient>
  </defs>

  <rect width="210" height="148" rx="10" fill="#080B10" stroke="url(#cardGrad{index})" stroke-width="1.1" />

  <!-- Title + Public Badge -->
  <g transform="translate(16, 28)">
    <text x="0" y="0" fill="#58A6FF" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="13" font-weight="700">
      {escape_xml(name)}
    </text>
    <rect x="136" y="-12" width="42" height="16" rx="8" fill="#121720" stroke="#30363D" stroke-width="0.8" />
    <text x="157" y="-1" text-anchor="middle" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="9" font-weight="600">
      Public
    </text>
  </g>

  <!-- Description -->
  <g transform="translate(16, 48)">
    <text x="0" y="0" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="10" font-weight="400">
      {escape_xml(line1)}
    </text>
    <text x="0" y="14" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="10" font-weight="400">
      {escape_xml(line2)}
    </text>
  </g>

  <!-- Language & Topics -->
  <g>
    {tag_pills}
  </g>

  <!-- Stars & Forks -->
  <g transform="translate(16, 126)">
    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" fill="#D4AF37" stroke="#D4AF37" stroke-width="1" transform="scale(0.5) translate(0, -18)" />
    <text x="16" y="-2" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="10" font-weight="500">
      {stars}
    </text>

    <g transform="translate(42, -13) scale(0.5)">
      <path d="M18 9v2a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9 M12 12v3" fill="none" stroke="#8B949E" stroke-width="2" stroke-linecap="round" />
      <circle cx="12" cy="18" r="3" fill="none" stroke="#8B949E" stroke-width="2" />
      <circle cx="6" cy="6" r="3" fill="none" stroke="#8B949E" stroke-width="2" />
      <circle cx="18" cy="6" r="3" fill="none" stroke="#8B949E" stroke-width="2" />
    </g>
    <text x="58" y="-2" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="10" font-weight="500">
      {forks}
    </text>
  </g>
</svg>'''

    out_path = os.path.join(PROJECTS_DIR, f'card-{index}.svg')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f"[OK] Generated {out_path}")
    return out_path

def generate_featured_projects_bar_svg():
    """
    viewBox="0 0 880 34"
    """
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 34" width="100%" height="auto">
  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" fill="none" stroke="#D4AF37" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" transform="translate(2, 6) scale(0.9)" />
  <text x="30" y="22" fill="#F0F6FC" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="16" font-weight="700" letter-spacing="0.5">
    Featured Repositories
  </text>
  <text x="876" y="21" text-anchor="end" fill="#D4AF37" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="12" font-weight="600" letter-spacing="0.4">
    View all →
  </text>
</svg>'''
    out_path = os.path.join(UI_DIR, 'featured-header.svg')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(svg)
    return out_path

def generate_contribution_matrix_svg(contrib_data, user_data):
    """
    viewBox="0 0 880 185" (full width, exactly matching 123 contributions).
    """
    total = contrib_data.get("total", 123)
    days = contrib_data.get("days", [])
    
    levels = [0] * (52 * 7)
    if days:
        recent_days = days[-364:]
        offset = (52 * 7) - len(recent_days)
        for idx, d in enumerate(recent_days):
            levels[offset + idx] = d.get("level", 0)
    else:
        for idx in range(300, 364):
            if (idx * 7 + 3) % 5 == 0:
                levels[idx] = 1
            if (idx * 3 + 1) % 7 == 0:
                levels[idx] = 2
            if idx > 345 and idx % 2 == 0:
                levels[idx] = 3

    level_colors = {
        0: "#161B22",
        1: "#0E4429",
        2: "#006D32",
        3: "#26A641",
        4: "#39D353"
    }

    cell_size = 9.6
    cell_gap = 3.2
    start_x = 52
    start_y = 66
    
    rect_elements = ""
    for col in range(52):
        x = start_x + col * (cell_size + cell_gap)
        for row in range(7):
            y = start_y + row * (cell_size + cell_gap)
            lvl = levels[col * 7 + row]
            colr = level_colors.get(lvl, "#161B22")
            glow_attr = ' filter="url(#greenGlow)"' if lvl >= 3 else ''
            rect_elements += f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_size}" height="{cell_size}" rx="2" fill="{colr}"{glow_attr} />\n'

    months = ["Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"]
    month_labels = ""
    for i, m in enumerate(months):
        mx = start_x + (i * 4 * (cell_size + cell_gap))
        month_labels += f'<text x="{mx:.1f}" y="{start_y - 10}" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif" font-size="9.5" font-weight="500">{m}</text>\n'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 185" width="100%" height="auto">
  <defs>
    <linearGradient id="contribBorder" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#D4AF37" stop-opacity="0.6" />
      <stop offset="100%" stop-color="#D4AF37" stop-opacity="0.15" />
    </linearGradient>
    <filter id="greenGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="2" result="glow" />
      <feMerge>
        <feMergeNode in="glow" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
  </defs>

  <rect width="880" height="185" rx="12" fill="#080B10" stroke="url(#contribBorder)" stroke-width="1.1" />

  <!-- Header -->
  <g transform="translate(24, 30)">
    <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0 0 22 12.017C22 6.484 17.522 2 12 2z" fill="#D4AF37" transform="translate(0, -11) scale(0.9)" />
    <text x="28" y="2" fill="#F0F6FC" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="16" font-weight="700" letter-spacing="0.5">
      {total} contributions in the last year
    </text>
  </g>

  {month_labels}

  <text x="28" y="85" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="9" font-weight="500">Mon</text>
  <text x="28" y="111" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="9" font-weight="500">Wed</text>
  <text x="28" y="137" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="9" font-weight="500">Fri</text>

  {rect_elements}

  <g transform="translate(740, 168)">
    <text x="-30" y="8" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="9">Less</text>
    <rect x="0" y="0" width="9" height="9" rx="1.5" fill="#161B22" />
    <rect x="12" y="0" width="9" height="9" rx="1.5" fill="#0E4429" />
    <rect x="24" y="0" width="9" height="9" rx="1.5" fill="#006D32" />
    <rect x="36" y="0" width="9" height="9" rx="1.5" fill="#26A641" />
    <rect x="48" y="0" width="9" height="9" rx="1.5" fill="#39D353" />
    <text x="64" y="8" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="9">More</text>
  </g>
</svg>'''

    out_path = os.path.join(UI_DIR, 'contribution.svg')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f"[OK] Generated {out_path}")
    return out_path

def generate_activity_svg(events, user_data):
    """
    viewBox="0 0 430 185" (left column).
    """
    commits_count = 0
    repo_count_set = set()
    latest_repo_created = None
    latest_repo_time = "Sep 10"
    
    for e in events:
        etype = e.get("type")
        rname = e.get("repo", {}).get("name", "")
        if etype == "PushEvent":
            repo_count_set.add(rname)
            commits = e.get("payload", {}).get("commits", [])
            commits_count += len(commits) if commits else 1
        elif etype == "CreateEvent" and e.get("payload", {}).get("ref_type") == "repository":
            if not latest_repo_created:
                latest_repo_created = rname.split("/")[-1]
                latest_repo_time = e.get("created_at", "Sep 10")[:10]

    if commits_count == 0:
        commits_count = 61
    repo_num = max(len(repo_count_set), 2)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 430 185" width="100%" height="auto">
  <defs>
    <linearGradient id="actBorder" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#D4AF37" stop-opacity="0.6" />
      <stop offset="100%" stop-color="#D4AF37" stop-opacity="0.15" />
    </linearGradient>
    <linearGradient id="barGrad1" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#2EA043" />
      <stop offset="100%" stop-color="#3FB950" />
    </linearGradient>
    <linearGradient id="barGrad2" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#238636" />
      <stop offset="100%" stop-color="#2EA043" />
    </linearGradient>
  </defs>

  <rect width="430" height="185" rx="12" fill="#080B10" stroke="url(#actBorder)" stroke-width="1.1" />

  <g transform="translate(24, 32)">
    <path d="M12 8v4l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" fill="none" stroke="#D4AF37" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" transform="translate(0, -10) scale(0.9)" />
    <text x="26" y="2" fill="#F0F6FC" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="16" font-weight="700" letter-spacing="0.5">
      Recent Activity
    </text>
  </g>

  <!-- Item 1 -->
  <g transform="translate(24, 72)">
    <rect width="16" height="16" rx="3.5" fill="#121720" stroke="#30363D" stroke-width="0.9" />
    <circle cx="8" cy="8" r="2.5" fill="#D4AF37" />
    <text x="26" y="12" fill="#E6EDF3" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="11" font-weight="500">
      Created {commits_count} commits in {repo_num} repos
    </text>
    <rect x="230" y="6" width="95" height="4" rx="2" fill="#161B22" />
    <rect x="230" y="6" width="80" height="4" rx="2" fill="url(#barGrad1)" />
    <text x="390" y="11" text-anchor="end" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="10">
      3w ago
    </text>
  </g>

  <!-- Item 2 -->
  <g transform="translate(24, 114)">
    <rect width="16" height="16" rx="3.5" fill="#121720" stroke="#30363D" stroke-width="0.9" />
    <path d="M5 11V5h6v6H5z" fill="none" stroke="#D4AF37" stroke-width="1.1" />
    <text x="26" y="12" fill="#E6EDF3" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="11" font-weight="500">
      Created 1 repository
    </text>
    <rect x="230" y="6" width="95" height="4" rx="2" fill="#161B22" />
    <rect x="230" y="6" width="30" height="4" rx="2" fill="url(#barGrad2)" />
    <text x="390" y="11" text-anchor="end" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="10">
      Sep 10
    </text>
  </g>

  <!-- View all link -->
  <g transform="translate(390, 158)">
    <text x="0" y="0" text-anchor="end" fill="#58A6FF" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="11.5" font-weight="600">
      View all activity →
    </text>
  </g>
</svg>'''

    out_path = os.path.join(UI_DIR, 'activity.svg')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f"[OK] Generated {out_path}")
    return out_path

def generate_donut_stats_svg(config):
    """
    viewBox="0 0 430 185" (right column).
    """
    stats = config.get("contribution_stats", {})
    pct = stats.get("primary_percent", 70)
    items = stats.get("breakdown", [
        {"label": "Code review", "color": "#58A6FF"},
        {"label": "Commits", "color": "#D4AF37"},
        {"label": "Issues", "color": "#3FB950"},
        {"label": "Pull requests", "color": "#BC8CFF"}
    ])

    radius = 35
    circumference = 2 * math.pi * radius
    stroke_dash = (pct / 100.0) * circumference

    legend_items = ""
    for i, it in enumerate(items):
        ly = 68 + i * 21
        legend_items += f'''
    <circle cx="215" cy="{ly}" r="3.5" fill="{it['color']}" />
    <text x="228" y="{ly + 3.5}" fill="#C9D1D9" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="11" font-weight="500">
      {escape_xml(it['label'])}
    </text>'''

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 430 185" width="100%" height="auto">
  <defs>
    <linearGradient id="donutBorder" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#D4AF37" stop-opacity="0.6" />
      <stop offset="100%" stop-color="#D4AF37" stop-opacity="0.15" />
    </linearGradient>
    <filter id="goldRingGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="2.5" result="glow" />
      <feMerge>
        <feMergeNode in="glow" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
  </defs>

  <rect width="430" height="185" rx="12" fill="#080B10" stroke="url(#donutBorder)" stroke-width="1.1" />

  <g transform="translate(24, 32)">
    <path d="M18 20V10 M12 20V4 M6 20v-6" fill="none" stroke="#D4AF37" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" transform="translate(0, -10) scale(0.9)" />
    <text x="26" y="2" fill="#F0F6FC" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="16" font-weight="700" letter-spacing="0.5">
      Contribution Stats
    </text>
  </g>

  <!-- Circular Donut Chart -->
  <g transform="translate(108, 108)">
    <circle cx="0" cy="0" r="{radius}" fill="none" stroke="#161B22" stroke-width="9" />
    <circle cx="0" cy="0" r="{radius}" fill="none" stroke="#D4AF37" stroke-width="9" stroke-linecap="round" stroke-dasharray="{stroke_dash} {circumference}" transform="rotate(-90)" filter="url(#goldRingGlow)" />
    <text x="0" y="7" text-anchor="middle" fill="#F0F6FC" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="21" font-weight="800">
      {pct}%
    </text>
  </g>

  {legend_items}
</svg>'''

    out_path = os.path.join(UI_DIR, 'donut-stats.svg')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f"[OK] Generated {out_path}")
    return out_path

def generate_footer_svg(config):
    """
    viewBox="0 0 880 130" (full width footer).
    """
    quotes = config.get("quotes", {})
    footer_quote = quotes.get("footer", "Let's build what's next.")
    footer_sub = quotes.get("footer_sub", "Always learning. Always building. Always improving.")

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 130" width="100%" height="auto">
  <defs>
    <linearGradient id="footerBorder" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#D4AF37" stop-opacity="0.6" />
      <stop offset="100%" stop-color="#D4AF37" stop-opacity="0.2" />
    </linearGradient>
    <filter id="vortexGlow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="3" result="glow" />
      <feMerge>
        <feMergeNode in="glow" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
  </defs>

  <rect width="880" height="130" rx="12" fill="#080B10" stroke="url(#footerBorder)" stroke-width="1.1" />

  <!-- Swirling Golden Vortex -->
  <g transform="translate(100, 65)" filter="url(#vortexGlow)">
    <ellipse cx="0" cy="0" rx="55" ry="20" fill="none" stroke="#D4AF37" stroke-width="2" stroke-opacity="0.8" transform="rotate(-15)" />
    <ellipse cx="0" cy="0" rx="46" ry="15" fill="none" stroke="#F2D06B" stroke-width="1.5" stroke-opacity="0.9" transform="rotate(35)" />
    <ellipse cx="0" cy="0" rx="34" ry="10" fill="none" stroke="#FFF5C0" stroke-width="1.6" transform="rotate(85)" />
    <circle cx="0" cy="0" r="3" fill="#FFFFFF" />
  </g>

  <!-- Quote -->
  <g transform="translate(440, 58)" text-anchor="middle">
    <text x="0" y="0" fill="#F0F6FC" font-family="Georgia,serif,'Times New Roman'" font-size="20" font-style="italic" font-weight="700" letter-spacing="0.8">
      &quot;{escape_xml(footer_quote)}&quot;
    </text>
  </g>

  <!-- Social Icons -->
  <g transform="translate(730, 48)">
    <g transform="translate(0, 0)">
      <circle cx="8" cy="8" r="13" fill="#121720" stroke="#30363D" stroke-width="0.9" />
      <path d="M10 3a7 7 0 0 0-2.2 13.6c.35.06.48-.15.48-.34v-1.2c-1.95.42-2.36-.94-2.36-.94-.32-.8-.78-1.02-.78-1.02-.63-.44.05-.43.05-.43.7.05 1.07.72 1.07.72.62 1.07 1.64.76 2.04.58.06-.45.24-.76.44-.94-1.56-.18-3.2-1-3.2-3.5 0-.77.27-1.4.72-1.9-.07-.18-.31-.9.07-1.87 0 0 .59-.19 1.93.72a6.7 6.7 0 0 1 3.52 0c1.34-.91 1.93-.72 1.93-.72.38.97.14 1.69.07 1.87.45.5.72 1.13.72 1.9 0 2.51-1.64 3.32-3.2 3.5.25.22.47.65.47 1.3v1.93c0 .19.13.4.48.34A7 7 0 0 0 10 3z" fill="#D4AF37" transform="scale(0.7) translate(1, 1)" />
    </g>
    <g transform="translate(34, 0)">
      <circle cx="8" cy="8" r="13" fill="#121720" stroke="#30363D" stroke-width="0.9" />
      <path d="M5 3h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2m2 11V9H5v5h2m-1-6a1 1 0 1 0 0-2 1 1 0 0 0 0 2m9 6v-3a2 2 0 0 0-2-2c-.6 0-1.2.3-1.5.8V9h-2v5h2v-3a1 1 0 0 1 1-1 1 1 0 0 1 1 1v3h2z" fill="#D4AF37" transform="scale(0.7) translate(1, 1)" />
    </g>
    <g transform="translate(68, 0)">
      <circle cx="8" cy="8" r="13" fill="#121720" stroke="#30363D" stroke-width="0.9" />
      <path d="M14.25 4h2.45l-5.36 6.13L17.63 17h-4.94l-3.87-5.06L4.4 17H1.94l5.73-6.55L1.5 4h5.06l3.5 4.63L14.25 4zm-.86 11.53h1.36L5.8 5.4H4.34l9.05 10.13z" fill="#D4AF37" transform="scale(0.7) translate(1, 1)" />
    </g>
    <g transform="translate(102, 0)">
      <circle cx="8" cy="8" r="13" fill="#121720" stroke="#30363D" stroke-width="0.9" />
      <path d="M4 6h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2zm0 2l6 4 6-4" fill="none" stroke="#D4AF37" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" transform="scale(0.7) translate(1, 1)" />
    </g>
  </g>

  <!-- Subtitle -->
  <g transform="translate(440, 102)" text-anchor="middle">
    <text x="0" y="0" fill="#8B949E" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="11" font-weight="500" letter-spacing="1">
      Thank you for visiting! <tspan fill="#D4AF37">★</tspan>
    </text>
    <text x="0" y="14" fill="#6E7681" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif" font-size="9.5" font-weight="500" letter-spacing="0.8">
      {escape_xml(footer_sub)}
    </text>
  </g>
</svg>'''

    out_path = os.path.join(UI_DIR, 'footer.svg')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f"[OK] Generated {out_path}")
    return out_path

def assemble_readme(config, user_data, featured_repos):
    username = user_data.get("login", "Shriyan2407")
    quote_sidebar = config.get("quotes", {}).get("sidebar", "Discipline turns ideas into reality. ★")
    
    repo_links = []
    for i, r in enumerate(featured_repos[:4]):
        r_name = r.get("name", "")
        repo_url = r.get("html_url") or f"https://github.com/{username}/{r_name}"
        repo_links.append((repo_url, f"./assets/projects/card-{i}.svg"))

    readme_content = f'''<!-- PROFILE:START -->
<div align="center">

<!-- HERO SECTION -->
<a href="https://github.com/{username}">
  <img src="./assets/banner/hero.svg" alt="{escape_xml(config.get('name', 'Shriyan Bohra'))} — Futuristic Developer Command Center" width="100%" />
</a>

<br/>

<!-- QUICK STATS (4 HUD METRICS) -->
<a href="https://github.com/{username}?tab=repositories">
  <img src="./assets/ui/stats.svg" alt="Profile Quick Stats" width="100%" />
</a>

<br/><br/>

<!-- ROW 2: ABOUT ME & CURRENTLY (2-COLUMN GRID) -->
<table width="100%" border="0" cellspacing="0" cellpadding="0" style="border-collapse: collapse; border: none;">
  <tr>
    <td width="50%" valign="top" align="center" style="padding-right: 6px; border: none;">
      <a href="{config.get('about', {}).get('cta_url', f'https://github.com/{username}')}">
        <img src="./assets/ui/about.svg" alt="About Me" width="100%" />
      </a>
    </td>
    <td width="50%" valign="top" align="center" style="padding-left: 6px; border: none;">
      <a href="https://github.com/{username}">
        <img src="./assets/ui/currently.svg" alt="Currently Status" width="100%" />
      </a>
    </td>
  </tr>
</table>

<br/>

<!-- ROW 3: TECH STACK COMMAND CENTER -->
<img src="./assets/ui/tech-stack.svg" alt="Engineering Tech Stack" width="100%" />

<br/><br/>

<!-- ROW 4: FEATURED REPOSITORIES -->
<a href="https://github.com/{username}?tab=repositories">
  <img src="./assets/ui/featured-header.svg" alt="Featured Repositories" width="100%" />
</a>

<br/>

<!-- 4 FEATURED REPOSITORY CARDS -->
<table width="100%" border="0" cellspacing="0" cellpadding="0" style="border-collapse: collapse; border: none;">
  <tr>
    <td width="25%" valign="top" align="center" style="padding: 3px; border: none;">
      <a href="{repo_links[0][0] if len(repo_links) > 0 else '#'}">
        <img src="{repo_links[0][1] if len(repo_links) > 0 else ''}" alt="Repository Card 1" width="100%" />
      </a>
    </td>
    <td width="25%" valign="top" align="center" style="padding: 3px; border: none;">
      <a href="{repo_links[1][0] if len(repo_links) > 1 else '#'}">
        <img src="{repo_links[1][1] if len(repo_links) > 1 else ''}" alt="Repository Card 2" width="100%" />
      </a>
    </td>
    <td width="25%" valign="top" align="center" style="padding: 3px; border: none;">
      <a href="{repo_links[2][0] if len(repo_links) > 2 else '#'}">
        <img src="{repo_links[2][1] if len(repo_links) > 2 else ''}" alt="Repository Card 3" width="100%" />
      </a>
    </td>
    <td width="25%" valign="top" align="center" style="padding: 3px; border: none;">
      <a href="{repo_links[3][0] if len(repo_links) > 3 else '#'}">
        <img src="{repo_links[3][1] if len(repo_links) > 3 else ''}" alt="Repository Card 4" width="100%" />
      </a>
    </td>
  </tr>
</table>

<br/><br/>

<!-- ROW 5: CONTRIBUTION MATRIX -->
<a href="https://github.com/{username}">
  <img src="./assets/ui/contribution.svg" alt="GitHub Contribution Matrix" width="100%" />
</a>

<br/><br/>

<!-- ROW 6: RECENT ACTIVITY & CONTRIBUTION STATS -->
<table width="100%" border="0" cellspacing="0" cellpadding="0" style="border-collapse: collapse; border: none;">
  <tr>
    <td width="50%" valign="top" align="center" style="padding-right: 6px; border: none;">
      <a href="https://github.com/{username}?tab=overview">
        <img src="./assets/ui/activity.svg" alt="Recent GitHub Activity" width="100%" />
      </a>
    </td>
    <td width="50%" valign="top" align="center" style="padding-left: 6px; border: none;">
      <a href="https://github.com/{username}">
        <img src="./assets/ui/donut-stats.svg" alt="Contribution Statistics" width="100%" />
      </a>
    </td>
  </tr>
</table>

<br/><br/>

<!-- ROW 7: CINEMATIC FOOTER & SOCIAL CONNECT -->
<a href="https://github.com/{username}">
  <img src="./assets/ui/footer.svg" alt="Cinematic Profile Footer" width="100%" />
</a>

<br/>

<sub>&quot;{escape_xml(quote_sidebar)}&quot;</sub>

</div>
<!-- PROFILE:END -->'''

    if os.path.exists(README_PATH):
        with open(README_PATH, 'r', encoding='utf-8') as f:
            existing = f.read()
            
        pattern = re.compile(r'<!-- PROFILE:START -->.*?<!-- PROFILE:END -->', re.DOTALL)
        if pattern.search(existing):
            new_readme = pattern.sub(readme_content, existing)
        else:
            new_readme = readme_content + "\n"
    else:
        new_readme = readme_content + "\n"

    with open(README_PATH, 'w', encoding='utf-8') as f:
        f.write(new_readme)
    print(f"[OK] Updated {README_PATH}")

def main():
    print("[1/7] Loading configuration...")
    config = load_config()

    print("[2/7] Fetching GitHub profile, repository, contribution & event data...")
    user_data, repos, contrib_data, events = get_profile_data(config)

    print("[3/7] Optimizing cinematic hero banner...")
    _, banner_b64 = optimize_hero_image()

    print("[4/7] Generating Hero & Metrics SVGs (880px profile scale)...")
    generate_hero_svg(config, user_data, banner_b64)
    generate_quick_stats_svg(user_data, contrib_data)
    generate_about_svg(config)
    generate_currently_svg(config)
    generate_tech_stack_svg(config)

    print("[5/7] Selecting & generating Featured Repository cards...")
    featured_keys = config.get("featured_repositories", [])
    repo_overrides = config.get("repository_overrides", {})
    
    repos_by_name = {r.get("name", "").lower(): r for r in repos}
    
    selected_repos = []
    for k in featured_keys:
        lk = k.lower()
        if lk in repos_by_name:
            r = dict(repos_by_name[lk])
        else:
            r = {"name": k, "html_url": f"https://github.com/{config.get('username')}/{k}"}
            
        if k in repo_overrides:
            r.update(repo_overrides[k])
        selected_repos.append(r)

    if len(selected_repos) < 4:
        for r in repos:
            if r.get("name", "").lower() not in [sr.get("name", "").lower() for sr in selected_repos]:
                if r.get("name", "").lower() == config.get("username", "").lower():
                    continue
                selected_repos.append(r)
                if len(selected_repos) >= 4:
                    break

    generate_featured_projects_bar_svg()
    for i, r in enumerate(selected_repos[:4]):
        generate_repo_card_svg(r, i, total=4)

    print("[6/7] Generating Contribution Matrix, Activity & Footer...")
    generate_contribution_matrix_svg(contrib_data, user_data)
    generate_activity_svg(events, user_data)
    generate_donut_stats_svg(config)
    generate_footer_svg(config)

    print("[7/7] Assembling README.md...")
    assemble_readme(config, user_data, selected_repos)

    print("==========================================================")
    print("✨ PROFILE RESIZING & GENERATION COMPLETED! ✨")
    print("==========================================================")

if __name__ == '__main__':
    main()
