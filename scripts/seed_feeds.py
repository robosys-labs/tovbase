"""Seed the feed_sources table with RSS/Atom feeds organized by country and category.

Coverage: major news, tech, finance, forums, and blogs across all continents.
Prioritizes editorially reliable, high-signal sources used by professionals.

Run: python -m scripts.seed_feeds
"""

from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.models import FeedSource

# ---------------------------------------------------------------------------
# Feed source definitions by continent/country
#
# Each entry: {name, url, source_type, category, language?, country_code,
#              continent, reliability_score, feed_type?, fetch_interval_minutes?}
#
# reliability_score scale:
#   0.90-0.95  Wire services, government, top academic journals
#   0.80-0.89  Major newspapers of record, established tech press
#   0.70-0.79  Quality specialist press, curated forums
#   0.60-0.69  Community-driven, startup press
#   0.50-0.59  Social aggregators, emerging outlets
#   <0.50      High-noise social feeds
# ---------------------------------------------------------------------------

FEEDS: list[dict] = [
    # =========================================================================
    # NORTH AMERICA
    # =========================================================================

    # ── United States ── Wire / General ──
    {"name": "Reuters (Top News)", "url": "https://www.reutersagency.com/feed/", "source_type": "news", "category": "general", "country_code": "US", "continent": "NA", "reliability_score": 0.95},
    {"name": "Associated Press", "url": "https://rsshub.app/apnews/topics/apf-topnews", "source_type": "news", "category": "general", "country_code": "US", "continent": "NA", "reliability_score": 0.95},
    {"name": "NPR News", "url": "https://feeds.npr.org/1001/rss.xml", "source_type": "news", "category": "general", "country_code": "US", "continent": "NA", "reliability_score": 0.90},
    {"name": "New York Times", "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "source_type": "news", "category": "general", "country_code": "US", "continent": "NA", "reliability_score": 0.90},
    {"name": "Washington Post", "url": "https://feeds.washingtonpost.com/rss/national", "source_type": "news", "category": "general", "country_code": "US", "continent": "NA", "reliability_score": 0.88},
    {"name": "PBS NewsHour", "url": "https://www.pbs.org/newshour/feeds/rss/headlines", "source_type": "news", "category": "general", "country_code": "US", "continent": "NA", "reliability_score": 0.90},

    # ── United States ── Tech ──
    {"name": "Hacker News (Front Page)", "url": "https://hnrss.org/frontpage", "source_type": "forum", "category": "technology", "country_code": "US", "continent": "NA", "reliability_score": 0.85, "fetch_interval_minutes": 10},
    {"name": "Hacker News (Best)", "url": "https://hnrss.org/best", "source_type": "forum", "category": "technology", "country_code": "US", "continent": "NA", "reliability_score": 0.85, "fetch_interval_minutes": 15},
    {"name": "Lobste.rs", "url": "https://lobste.rs/rss", "source_type": "forum", "category": "programming", "country_code": "US", "continent": "NA", "reliability_score": 0.80, "fetch_interval_minutes": 15},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "source_type": "news", "category": "technology", "country_code": "US", "continent": "NA", "reliability_score": 0.88},
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/", "source_type": "news", "category": "technology", "country_code": "US", "continent": "NA", "reliability_score": 0.90},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "source_type": "news", "category": "technology", "country_code": "US", "continent": "NA", "reliability_score": 0.80},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "source_type": "news", "category": "technology", "country_code": "US", "continent": "NA", "reliability_score": 0.78},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss", "source_type": "news", "category": "technology", "country_code": "US", "continent": "NA", "reliability_score": 0.80},
    {"name": "InfoQ", "url": "https://feed.infoq.com/", "source_type": "news", "category": "programming", "country_code": "US", "continent": "NA", "reliability_score": 0.82},

    # ── United States ── AI / ML ──
    {"name": "arXiv CS.AI", "url": "https://rss.arxiv.org/rss/cs.AI", "source_type": "academic", "category": "ai_ml", "country_code": "US", "continent": "NA", "reliability_score": 0.95, "fetch_interval_minutes": 360},
    {"name": "arXiv CS.CL (NLP)", "url": "https://rss.arxiv.org/rss/cs.CL", "source_type": "academic", "category": "ai_ml", "country_code": "US", "continent": "NA", "reliability_score": 0.95, "fetch_interval_minutes": 360},
    {"name": "arXiv CS.LG (ML)", "url": "https://rss.arxiv.org/rss/cs.LG", "source_type": "academic", "category": "ai_ml", "country_code": "US", "continent": "NA", "reliability_score": 0.95, "fetch_interval_minutes": 360},
    {"name": "OpenAI Blog", "url": "https://openai.com/blog/rss.xml", "source_type": "blog", "category": "ai_ml", "country_code": "US", "continent": "NA", "reliability_score": 0.88},
    {"name": "Google AI Blog", "url": "https://blog.research.google/feeds/posts/default", "source_type": "blog", "category": "ai_ml", "country_code": "US", "continent": "NA", "reliability_score": 0.90, "feed_type": "atom"},
    {"name": "Hugging Face Blog", "url": "https://huggingface.co/blog/feed.xml", "source_type": "blog", "category": "ai_ml", "country_code": "US", "continent": "NA", "reliability_score": 0.82},

    # ── United States ── Finance ──
    {"name": "Wall Street Journal", "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml", "source_type": "news", "category": "finance", "country_code": "US", "continent": "NA", "reliability_score": 0.90},
    {"name": "Bloomberg Markets", "url": "https://feeds.bloomberg.com/markets/news.rss", "source_type": "news", "category": "finance", "country_code": "US", "continent": "NA", "reliability_score": 0.90},
    {"name": "CNBC Top News", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "source_type": "news", "category": "finance", "country_code": "US", "continent": "NA", "reliability_score": 0.80},
    {"name": "Financial Times (via Nikkei)", "url": "https://www.ft.com/rss/home", "source_type": "news", "category": "finance", "country_code": "US", "continent": "NA", "reliability_score": 0.92},

    # ── United States ── Crypto / Web3 ──
    {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "source_type": "news", "category": "crypto_web3", "country_code": "US", "continent": "NA", "reliability_score": 0.75},
    {"name": "The Block", "url": "https://www.theblock.co/rss.xml", "source_type": "news", "category": "crypto_web3", "country_code": "US", "continent": "NA", "reliability_score": 0.78},
    {"name": "Decrypt", "url": "https://decrypt.co/feed", "source_type": "news", "category": "crypto_web3", "country_code": "US", "continent": "NA", "reliability_score": 0.70},

    # ── United States ── Security ──
    {"name": "Krebs on Security", "url": "https://krebsonsecurity.com/feed/", "source_type": "blog", "category": "security", "country_code": "US", "continent": "NA", "reliability_score": 0.92},
    {"name": "Schneier on Security", "url": "https://www.schneier.com/feed/", "source_type": "blog", "category": "security", "country_code": "US", "continent": "NA", "reliability_score": 0.92},
    {"name": "CISA Alerts", "url": "https://www.cisa.gov/cybersecurity-advisories/all.xml", "source_type": "gov", "category": "security", "country_code": "US", "continent": "NA", "reliability_score": 0.95},

    # ── United States ── Developer / Eng Blogs ──
    {"name": "GitHub Blog", "url": "https://github.blog/feed/", "source_type": "blog", "category": "programming", "country_code": "US", "continent": "NA", "reliability_score": 0.85},
    {"name": "Cloudflare Blog", "url": "https://blog.cloudflare.com/rss/", "source_type": "blog", "category": "infrastructure", "country_code": "US", "continent": "NA", "reliability_score": 0.88},
    {"name": "Stripe Blog", "url": "https://stripe.com/blog/feed.rss", "source_type": "blog", "category": "finance", "country_code": "US", "continent": "NA", "reliability_score": 0.85},
    {"name": "Netflix Tech Blog", "url": "https://netflixtechblog.com/feed", "source_type": "blog", "category": "infrastructure", "country_code": "US", "continent": "NA", "reliability_score": 0.85},
    {"name": "a16z Blog", "url": "https://a16z.com/feed/", "source_type": "blog", "category": "finance", "country_code": "US", "continent": "NA", "reliability_score": 0.80},
    {"name": "Y Combinator Blog", "url": "https://www.ycombinator.com/blog/rss", "source_type": "blog", "category": "finance", "country_code": "US", "continent": "NA", "reliability_score": 0.82},

    # ── United States ── Reddit ──
    {"name": "r/technology", "url": "https://www.reddit.com/r/technology/.rss", "source_type": "forum", "category": "technology", "country_code": "US", "continent": "NA", "reliability_score": 0.55, "fetch_interval_minutes": 15},
    {"name": "r/programming", "url": "https://www.reddit.com/r/programming/.rss", "source_type": "forum", "category": "programming", "country_code": "US", "continent": "NA", "reliability_score": 0.60, "fetch_interval_minutes": 15},
    {"name": "r/MachineLearning", "url": "https://www.reddit.com/r/MachineLearning/.rss", "source_type": "forum", "category": "ai_ml", "country_code": "US", "continent": "NA", "reliability_score": 0.70, "fetch_interval_minutes": 30},
    {"name": "r/netsec", "url": "https://www.reddit.com/r/netsec/.rss", "source_type": "forum", "category": "security", "country_code": "US", "continent": "NA", "reliability_score": 0.72, "fetch_interval_minutes": 30},
    {"name": "r/science", "url": "https://www.reddit.com/r/science/.rss", "source_type": "forum", "category": "science", "country_code": "US", "continent": "NA", "reliability_score": 0.68, "fetch_interval_minutes": 30},
    {"name": "r/worldnews", "url": "https://www.reddit.com/r/worldnews/.rss", "source_type": "forum", "category": "general", "country_code": "US", "continent": "NA", "reliability_score": 0.50, "fetch_interval_minutes": 15},

    # ── United States ── Government / Policy ──
    {"name": "US Federal Register", "url": "https://www.federalregister.gov/documents/search.rss", "source_type": "gov", "category": "politics", "country_code": "US", "continent": "NA", "reliability_score": 0.95},
    {"name": "SEC EDGAR Filings", "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&dateb=&owner=include&count=40&search_text=&start=0&output=atom", "source_type": "gov", "category": "finance", "country_code": "US", "continent": "NA", "reliability_score": 0.95, "feed_type": "atom"},

    # ── United States ── Product / Startup ──
    {"name": "Product Hunt", "url": "https://www.producthunt.com/feed", "source_type": "forum", "category": "product", "country_code": "US", "continent": "NA", "reliability_score": 0.62, "fetch_interval_minutes": 30},
    {"name": "Indie Hackers", "url": "https://www.indiehackers.com/feed.xml", "source_type": "forum", "category": "product", "country_code": "US", "continent": "NA", "reliability_score": 0.60},

    # ── Canada ──
    {"name": "CBC News", "url": "https://www.cbc.ca/webfeed/rss/rss-topstories", "source_type": "news", "category": "general", "country_code": "CA", "continent": "NA", "reliability_score": 0.88},
    {"name": "Globe and Mail (Business)", "url": "https://www.theglobeandmail.com/arc/outboundfeeds/rss/category/business/", "source_type": "news", "category": "finance", "country_code": "CA", "continent": "NA", "reliability_score": 0.85},
    {"name": "BetaKit", "url": "https://betakit.com/feed/", "source_type": "news", "category": "technology", "country_code": "CA", "continent": "NA", "reliability_score": 0.68},

    # ── Mexico ──
    {"name": "El Financiero", "url": "https://www.elfinanciero.com.mx/arc/outboundfeeds/rss/", "source_type": "news", "category": "finance", "language": "es", "country_code": "MX", "continent": "NA", "reliability_score": 0.78},
    {"name": "El Economista (MX)", "url": "https://www.eleconomista.com.mx/rss/", "source_type": "news", "category": "finance", "language": "es", "country_code": "MX", "continent": "NA", "reliability_score": 0.75},

    # =========================================================================
    # EUROPE
    # =========================================================================

    # ── United Kingdom ──
    {"name": "BBC News", "url": "https://feeds.bbci.co.uk/news/rss.xml", "source_type": "news", "category": "general", "country_code": "GB", "continent": "EU", "reliability_score": 0.92},
    {"name": "BBC Technology", "url": "https://feeds.bbci.co.uk/news/technology/rss.xml", "source_type": "news", "category": "technology", "country_code": "GB", "continent": "EU", "reliability_score": 0.90},
    {"name": "The Guardian (Tech)", "url": "https://www.theguardian.com/uk/technology/rss", "source_type": "news", "category": "technology", "country_code": "GB", "continent": "EU", "reliability_score": 0.85},
    {"name": "Financial Times", "url": "https://www.ft.com/rss/home", "source_type": "news", "category": "finance", "country_code": "GB", "continent": "EU", "reliability_score": 0.92},
    {"name": "The Register", "url": "https://www.theregister.com/headlines.atom", "source_type": "news", "category": "technology", "country_code": "GB", "continent": "EU", "reliability_score": 0.82, "feed_type": "atom"},
    {"name": "The Economist", "url": "https://www.economist.com/rss", "source_type": "news", "category": "general", "country_code": "GB", "continent": "EU", "reliability_score": 0.92},
    {"name": "Sifted (EU Startups)", "url": "https://sifted.eu/feed", "source_type": "news", "category": "finance", "country_code": "GB", "continent": "EU", "reliability_score": 0.72},

    # ── Germany ──
    {"name": "Heise Online", "url": "https://www.heise.de/rss/heise-atom.xml", "source_type": "news", "category": "technology", "language": "de", "country_code": "DE", "continent": "EU", "reliability_score": 0.85, "feed_type": "atom"},
    {"name": "Golem.de", "url": "https://rss.golem.de/rss.php?feed=RSS2.0", "source_type": "news", "category": "technology", "language": "de", "country_code": "DE", "continent": "EU", "reliability_score": 0.82},
    {"name": "Der Spiegel", "url": "https://www.spiegel.de/schlagzeilen/index.rss", "source_type": "news", "category": "general", "language": "de", "country_code": "DE", "continent": "EU", "reliability_score": 0.88},
    {"name": "Deutsche Welle", "url": "https://rss.dw.com/rss/en/top-stories/s-9097", "source_type": "news", "category": "general", "country_code": "DE", "continent": "EU", "reliability_score": 0.88},
    {"name": "Handelsblatt", "url": "https://www.handelsblatt.com/contentexport/feed/schlagzeilen", "source_type": "news", "category": "finance", "language": "de", "country_code": "DE", "continent": "EU", "reliability_score": 0.85},

    # ── France ──
    {"name": "Le Monde", "url": "https://www.lemonde.fr/rss/en_continu.xml", "source_type": "news", "category": "general", "language": "fr", "country_code": "FR", "continent": "EU", "reliability_score": 0.88},
    {"name": "France 24 (English)", "url": "https://www.france24.com/en/rss", "source_type": "news", "category": "general", "country_code": "FR", "continent": "EU", "reliability_score": 0.85},
    {"name": "Les Echos (Tech)", "url": "https://www.lesechos.fr/rss/rss_tech_medias.xml", "source_type": "news", "category": "technology", "language": "fr", "country_code": "FR", "continent": "EU", "reliability_score": 0.82},

    # ── Netherlands ──
    {"name": "The Next Web", "url": "https://thenextweb.com/feed", "source_type": "news", "category": "technology", "country_code": "NL", "continent": "EU", "reliability_score": 0.75},
    {"name": "Tweakers", "url": "https://feeds.feedburner.com/tweakers/mixed", "source_type": "news", "category": "technology", "language": "nl", "country_code": "NL", "continent": "EU", "reliability_score": 0.82},

    # ── Ireland ──
    {"name": "The Irish Times", "url": "https://www.irishtimes.com/cmlink/the-irish-times-news-1.1319192", "source_type": "news", "category": "general", "country_code": "IE", "continent": "EU", "reliability_score": 0.85},
    {"name": "SiliconRepublic", "url": "https://www.siliconrepublic.com/feed", "source_type": "news", "category": "technology", "country_code": "IE", "continent": "EU", "reliability_score": 0.72},

    # ── Switzerland ──
    {"name": "Swissinfo", "url": "https://www.swissinfo.ch/eng/rss/all-news", "source_type": "news", "category": "general", "country_code": "CH", "continent": "EU", "reliability_score": 0.88},

    # ── Spain ──
    {"name": "El País (English)", "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/english.elpais.com/portada", "source_type": "news", "category": "general", "language": "en", "country_code": "ES", "continent": "EU", "reliability_score": 0.82},
    {"name": "Xataka", "url": "https://www.xataka.com/feedburner.xml", "source_type": "news", "category": "technology", "language": "es", "country_code": "ES", "continent": "EU", "reliability_score": 0.75},

    # ── Italy ──
    {"name": "ANSA", "url": "https://www.ansa.it/sito/ansait_rss.xml", "source_type": "news", "category": "general", "language": "it", "country_code": "IT", "continent": "EU", "reliability_score": 0.82},
    {"name": "Il Sole 24 Ore", "url": "https://www.ilsole24ore.com/rss/economia.xml", "source_type": "news", "category": "finance", "language": "it", "country_code": "IT", "continent": "EU", "reliability_score": 0.85},

    # ── Sweden ──
    {"name": "The Local (Sweden)", "url": "https://www.thelocal.se/feeds/rss.php", "source_type": "news", "category": "general", "country_code": "SE", "continent": "EU", "reliability_score": 0.72},
    {"name": "Breakit", "url": "https://www.breakit.se/feed/artiklar", "source_type": "news", "category": "technology", "language": "sv", "country_code": "SE", "continent": "EU", "reliability_score": 0.70},

    # ── Poland ──
    {"name": "Niebezpiecznik", "url": "https://niebezpiecznik.pl/feed/", "source_type": "blog", "category": "security", "language": "pl", "country_code": "PL", "continent": "EU", "reliability_score": 0.78},
    {"name": "Wyborcza (Tech)", "url": "https://wyborcza.pl/rss/technologie", "source_type": "news", "category": "technology", "language": "pl", "country_code": "PL", "continent": "EU", "reliability_score": 0.75},

    # ── Romania ──
    {"name": "HotNews (Romania)", "url": "https://www.hotnews.ro/rss", "source_type": "news", "category": "general", "language": "ro", "country_code": "RO", "continent": "EU", "reliability_score": 0.72},

    # ── Czech Republic ──
    {"name": "Root.cz", "url": "https://www.root.cz/rss/clanky/", "source_type": "news", "category": "technology", "language": "cs", "country_code": "CZ", "continent": "EU", "reliability_score": 0.75},

    # ── Austria ──
    {"name": "Der Standard", "url": "https://www.derstandard.at/rss", "source_type": "news", "category": "general", "language": "de", "country_code": "AT", "continent": "EU", "reliability_score": 0.82},

    # ── EU Institutions ──
    {"name": "EU Commission Press", "url": "https://ec.europa.eu/commission/presscorner/api/rss", "source_type": "gov", "category": "politics", "country_code": "BE", "continent": "EU", "reliability_score": 0.92},

    # =========================================================================
    # ASIA
    # =========================================================================

    # ── Japan ──
    {"name": "Japan Times", "url": "https://www.japantimes.co.jp/feed/", "source_type": "news", "category": "general", "country_code": "JP", "continent": "AS", "reliability_score": 0.82},
    {"name": "Nikkei Asia", "url": "https://asia.nikkei.com/rss", "source_type": "news", "category": "finance", "country_code": "JP", "continent": "AS", "reliability_score": 0.88},
    {"name": "NHK World", "url": "https://www3.nhk.or.jp/rss/news/cat0.xml", "source_type": "news", "category": "general", "country_code": "JP", "continent": "AS", "reliability_score": 0.90},

    # ── India ──
    {"name": "The Hindu", "url": "https://www.thehindu.com/feeder/default.rss", "source_type": "news", "category": "general", "country_code": "IN", "continent": "AS", "reliability_score": 0.82},
    {"name": "Economic Times", "url": "https://economictimes.indiatimes.com/rssfeedstopstories.cms", "source_type": "news", "category": "finance", "country_code": "IN", "continent": "AS", "reliability_score": 0.80},
    {"name": "Moneycontrol", "url": "https://www.moneycontrol.com/rss/latestnews.xml", "source_type": "news", "category": "finance", "country_code": "IN", "continent": "AS", "reliability_score": 0.78},
    {"name": "LiveMint", "url": "https://www.livemint.com/rss/news", "source_type": "news", "category": "finance", "country_code": "IN", "continent": "AS", "reliability_score": 0.78},
    {"name": "MediaNama", "url": "https://www.medianama.com/feed/", "source_type": "news", "category": "technology", "country_code": "IN", "continent": "AS", "reliability_score": 0.72},
    {"name": "Inc42", "url": "https://inc42.com/feed/", "source_type": "news", "category": "technology", "country_code": "IN", "continent": "AS", "reliability_score": 0.68},
    {"name": "YourStory", "url": "https://yourstory.com/feed", "source_type": "news", "category": "technology", "country_code": "IN", "continent": "AS", "reliability_score": 0.65},

    # ── China ──
    {"name": "South China Morning Post", "url": "https://www.scmp.com/rss/91/feed", "source_type": "news", "category": "general", "country_code": "CN", "continent": "AS", "reliability_score": 0.78},
    {"name": "TechNode", "url": "https://technode.com/feed/", "source_type": "news", "category": "technology", "country_code": "CN", "continent": "AS", "reliability_score": 0.72},
    {"name": "Caixin Global", "url": "https://www.caixinglobal.com/rss.html", "source_type": "news", "category": "finance", "country_code": "CN", "continent": "AS", "reliability_score": 0.80},

    # ── South Korea ──
    {"name": "Korea Herald", "url": "https://www.koreaherald.com/common/rss_xml.php", "source_type": "news", "category": "general", "country_code": "KR", "continent": "AS", "reliability_score": 0.78},
    {"name": "Korea JoongAng Daily", "url": "https://koreajoongangdaily.joins.com/xmlFeed/total_rss.xml", "source_type": "news", "category": "general", "country_code": "KR", "continent": "AS", "reliability_score": 0.78},

    # ── Singapore ──
    {"name": "Straits Times", "url": "https://www.straitstimes.com/news/world/rss.xml", "source_type": "news", "category": "general", "country_code": "SG", "continent": "AS", "reliability_score": 0.85},
    {"name": "Tech in Asia", "url": "https://www.techinasia.com/feed", "source_type": "news", "category": "technology", "country_code": "SG", "continent": "AS", "reliability_score": 0.72},
    {"name": "e27", "url": "https://e27.co/feed/", "source_type": "news", "category": "technology", "country_code": "SG", "continent": "AS", "reliability_score": 0.65},

    # ── Indonesia ──
    {"name": "Jakarta Post", "url": "https://www.thejakartapost.com/feed", "source_type": "news", "category": "general", "country_code": "ID", "continent": "AS", "reliability_score": 0.75},
    {"name": "DailySocial.id", "url": "https://dailysocial.id/feed", "source_type": "news", "category": "technology", "language": "id", "country_code": "ID", "continent": "AS", "reliability_score": 0.65},

    # ── Vietnam ──
    {"name": "VnExpress International", "url": "https://e.vnexpress.net/rss/news.rss", "source_type": "news", "category": "general", "country_code": "VN", "continent": "AS", "reliability_score": 0.72},

    # ── Thailand ──
    {"name": "Bangkok Post", "url": "https://www.bangkokpost.com/rss/data/topstories.xml", "source_type": "news", "category": "general", "country_code": "TH", "continent": "AS", "reliability_score": 0.75},

    # ── Philippines ──
    {"name": "Rappler", "url": "https://www.rappler.com/feed/", "source_type": "news", "category": "general", "country_code": "PH", "continent": "AS", "reliability_score": 0.75},

    # ── Pakistan ──
    {"name": "Dawn", "url": "https://www.dawn.com/feed", "source_type": "news", "category": "general", "country_code": "PK", "continent": "AS", "reliability_score": 0.78},
    {"name": "The News International", "url": "https://www.thenews.com.pk/rss/1/1", "source_type": "news", "category": "general", "country_code": "PK", "continent": "AS", "reliability_score": 0.72},

    # ── Israel ──
    {"name": "Times of Israel", "url": "https://www.timesofisrael.com/feed/", "source_type": "news", "category": "general", "country_code": "IL", "continent": "AS", "reliability_score": 0.78},
    {"name": "Geektime", "url": "https://www.geektime.com/feed/", "source_type": "news", "category": "technology", "country_code": "IL", "continent": "AS", "reliability_score": 0.68},
    {"name": "Calcalist (EN)", "url": "https://www.calcalistech.com/ctech/home/0,7340,L-5765882,00.xml", "source_type": "news", "category": "technology", "country_code": "IL", "continent": "AS", "reliability_score": 0.75},

    # ── Turkey ──
    {"name": "Daily Sabah", "url": "https://www.dailysabah.com/rssFeed/", "source_type": "news", "category": "general", "country_code": "TR", "continent": "AS", "reliability_score": 0.68},
    {"name": "Hurriyet Daily News", "url": "https://www.hurriyetdailynews.com/rss", "source_type": "news", "category": "general", "country_code": "TR", "continent": "AS", "reliability_score": 0.70},

    # ── UAE / Gulf ──
    {"name": "Gulf News", "url": "https://gulfnews.com/rss", "source_type": "news", "category": "general", "country_code": "AE", "continent": "AS", "reliability_score": 0.72},
    {"name": "Arab News", "url": "https://www.arabnews.com/rss.xml", "source_type": "news", "category": "general", "country_code": "SA", "continent": "AS", "reliability_score": 0.72},

    # ── Middle East (pan-regional) ──
    {"name": "Al Jazeera English", "url": "https://www.aljazeera.com/xml/rss/all.xml", "source_type": "news", "category": "general", "country_code": "QA", "continent": "AS", "reliability_score": 0.80},
    {"name": "Middle East Eye", "url": "https://www.middleeasteye.net/rss", "source_type": "news", "category": "general", "country_code": "GB", "continent": "AS", "reliability_score": 0.75},

    # =========================================================================
    # AFRICA
    # =========================================================================

    # ── Nigeria ──
    {"name": "Nairametrics", "url": "https://nairametrics.com/feed/", "source_type": "news", "category": "finance", "country_code": "NG", "continent": "AF", "reliability_score": 0.80},
    {"name": "TechCabal", "url": "https://techcabal.com/feed/", "source_type": "news", "category": "technology", "country_code": "NG", "continent": "AF", "reliability_score": 0.75},
    {"name": "TechPoint Africa", "url": "https://techpoint.africa/feed/", "source_type": "news", "category": "technology", "country_code": "NG", "continent": "AF", "reliability_score": 0.72},
    {"name": "Punch Nigeria", "url": "https://punchng.com/feed/", "source_type": "news", "category": "general", "country_code": "NG", "continent": "AF", "reliability_score": 0.75},
    {"name": "Premium Times", "url": "https://www.premiumtimesng.com/feed", "source_type": "news", "category": "general", "country_code": "NG", "continent": "AF", "reliability_score": 0.78},
    {"name": "The Cable", "url": "https://www.thecable.ng/feed", "source_type": "news", "category": "general", "country_code": "NG", "continent": "AF", "reliability_score": 0.72},
    {"name": "BusinessDay Nigeria", "url": "https://businessday.ng/feed/", "source_type": "news", "category": "finance", "country_code": "NG", "continent": "AF", "reliability_score": 0.78},

    # ── South Africa ──
    {"name": "News24", "url": "https://feeds.news24.com/articles/news24/TopStories/rss", "source_type": "news", "category": "general", "country_code": "ZA", "continent": "AF", "reliability_score": 0.78},
    {"name": "Daily Maverick", "url": "https://www.dailymaverick.co.za/feed/", "source_type": "news", "category": "general", "country_code": "ZA", "continent": "AF", "reliability_score": 0.82},
    {"name": "MyBroadband", "url": "https://mybroadband.co.za/news/feed", "source_type": "news", "category": "technology", "country_code": "ZA", "continent": "AF", "reliability_score": 0.75},
    {"name": "BusinessDay (SA)", "url": "https://www.businesslive.co.za/rss/", "source_type": "news", "category": "finance", "country_code": "ZA", "continent": "AF", "reliability_score": 0.80},
    {"name": "Disrupt Africa", "url": "https://disrupt-africa.com/feed/", "source_type": "news", "category": "technology", "country_code": "ZA", "continent": "AF", "reliability_score": 0.68},

    # ── Kenya ──
    {"name": "Nation Media (Kenya)", "url": "https://nation.africa/kenya/rss.xml", "source_type": "news", "category": "general", "country_code": "KE", "continent": "AF", "reliability_score": 0.78},
    {"name": "Business Daily Africa", "url": "https://www.businessdailyafrica.com/rss.xml", "source_type": "news", "category": "finance", "country_code": "KE", "continent": "AF", "reliability_score": 0.75},
    {"name": "The Standard (Kenya)", "url": "https://www.standardmedia.co.ke/rss/headlines.php", "source_type": "news", "category": "general", "country_code": "KE", "continent": "AF", "reliability_score": 0.72},

    # ── Ghana ──
    {"name": "Joy Online", "url": "https://www.myjoyonline.com/feed/", "source_type": "news", "category": "general", "country_code": "GH", "continent": "AF", "reliability_score": 0.70},
    {"name": "Citi Newsroom", "url": "https://citinewsroom.com/feed/", "source_type": "news", "category": "general", "country_code": "GH", "continent": "AF", "reliability_score": 0.68},

    # ── Egypt ──
    {"name": "Ahram Online", "url": "https://english.ahram.org.eg/UI/Front/RSS.aspx", "source_type": "news", "category": "general", "country_code": "EG", "continent": "AF", "reliability_score": 0.72},
    {"name": "Daily News Egypt", "url": "https://www.dailynewsegypt.com/feed/", "source_type": "news", "category": "general", "country_code": "EG", "continent": "AF", "reliability_score": 0.68},

    # ── East Africa ──
    {"name": "The East African", "url": "https://www.theeastafrican.co.ke/rss.xml", "source_type": "news", "category": "general", "country_code": "KE", "continent": "AF", "reliability_score": 0.72},

    # ── Pan-African ──
    {"name": "African Arguments", "url": "https://africanarguments.org/feed/", "source_type": "news", "category": "general", "country_code": "GB", "continent": "AF", "reliability_score": 0.75},

    # =========================================================================
    # SOUTH AMERICA
    # =========================================================================

    # ── Brazil ──
    {"name": "Folha de São Paulo", "url": "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml", "source_type": "news", "category": "general", "language": "pt", "country_code": "BR", "continent": "SA", "reliability_score": 0.85},
    {"name": "Valor Econômico", "url": "https://valor.globo.com/rss/", "source_type": "news", "category": "finance", "language": "pt", "country_code": "BR", "continent": "SA", "reliability_score": 0.82},
    {"name": "Startse", "url": "https://www.startse.com/feed/", "source_type": "news", "category": "technology", "language": "pt", "country_code": "BR", "continent": "SA", "reliability_score": 0.65},

    # ── Argentina ──
    {"name": "La Nación", "url": "https://www.lanacion.com.ar/arcio/rss/", "source_type": "news", "category": "general", "language": "es", "country_code": "AR", "continent": "SA", "reliability_score": 0.80},
    {"name": "Infobae", "url": "https://www.infobae.com/feeds/rss/", "source_type": "news", "category": "general", "language": "es", "country_code": "AR", "continent": "SA", "reliability_score": 0.75},

    # ── Colombia ──
    {"name": "El Tiempo", "url": "https://www.eltiempo.com/rss/el_tiempo.xml", "source_type": "news", "category": "general", "language": "es", "country_code": "CO", "continent": "SA", "reliability_score": 0.78},
    {"name": "La República (CO)", "url": "https://www.larepublica.co/rss", "source_type": "news", "category": "finance", "language": "es", "country_code": "CO", "continent": "SA", "reliability_score": 0.75},

    # ── Chile ──
    {"name": "El Mercurio", "url": "https://www.emol.com/rss/rss.asp", "source_type": "news", "category": "general", "language": "es", "country_code": "CL", "continent": "SA", "reliability_score": 0.78},

    # ── Peru ──
    {"name": "El Comercio (Peru)", "url": "https://elcomercio.pe/arcio/rss/", "source_type": "news", "category": "general", "language": "es", "country_code": "PE", "continent": "SA", "reliability_score": 0.75},

    # =========================================================================
    # OCEANIA
    # =========================================================================

    {"name": "ABC News Australia", "url": "https://www.abc.net.au/news/feed/51120/rss.xml", "source_type": "news", "category": "general", "country_code": "AU", "continent": "OC", "reliability_score": 0.88},
    {"name": "Sydney Morning Herald (Tech)", "url": "https://www.smh.com.au/rss/technology.xml", "source_type": "news", "category": "technology", "country_code": "AU", "continent": "OC", "reliability_score": 0.82},
    {"name": "Australian Financial Review", "url": "https://www.afr.com/rss/feed.xml", "source_type": "news", "category": "finance", "country_code": "AU", "continent": "OC", "reliability_score": 0.85},
    {"name": "Stuff.co.nz", "url": "https://www.stuff.co.nz/rss", "source_type": "news", "category": "general", "country_code": "NZ", "continent": "OC", "reliability_score": 0.75},
    {"name": "NZ Herald", "url": "https://www.nzherald.co.nz/arc/outboundfeeds/rss/curated/78/", "source_type": "news", "category": "general", "country_code": "NZ", "continent": "OC", "reliability_score": 0.78},

    # =========================================================================
    # GLOBAL SCIENCE / ACADEMIC
    # =========================================================================

    {"name": "Nature News", "url": "https://www.nature.com/nature.rss", "source_type": "academic", "category": "science", "country_code": "GB", "continent": "EU", "reliability_score": 0.95, "fetch_interval_minutes": 360},
    {"name": "Science Magazine", "url": "https://www.science.org/rss/news_current.xml", "source_type": "academic", "category": "science", "country_code": "US", "continent": "NA", "reliability_score": 0.95, "fetch_interval_minutes": 360},
    {"name": "Phys.org", "url": "https://phys.org/rss-feed/", "source_type": "news", "category": "science", "country_code": "GB", "continent": "EU", "reliability_score": 0.80},
    {"name": "New Scientist", "url": "https://www.newscientist.com/feed/home/", "source_type": "news", "category": "science", "country_code": "GB", "continent": "EU", "reliability_score": 0.82},
]


def seed_feeds():
    """Insert all feed sources, skipping duplicates by URL."""
    db = SessionLocal()
    try:
        added = 0
        skipped = 0
        for feed_data in FEEDS:
            url = feed_data["url"]
            existing = db.execute(
                select(FeedSource).where(FeedSource.url == url)
            ).scalar_one_or_none()

            if existing:
                skipped += 1
                continue

            source = FeedSource(
                name=feed_data["name"],
                url=url,
                feed_type=feed_data.get("feed_type", "rss"),
                source_type=feed_data.get("source_type", "news"),
                category=feed_data.get("category", "general"),
                language=feed_data.get("language", "en"),
                country_code=feed_data.get("country_code", "US"),
                continent=feed_data.get("continent", "NA"),
                reliability_score=feed_data.get("reliability_score", 0.5),
                fetch_interval_minutes=feed_data.get("fetch_interval_minutes", 60),
            )
            db.add(source)
            added += 1

        db.commit()
        print(f"Feed sources seeded: {added} added, {skipped} skipped (already exist)")

        # Print summary by continent
        continent_names = {"NA": "North America", "EU": "Europe", "AS": "Asia", "AF": "Africa", "SA": "South America", "OC": "Oceania"}
        for code, name in continent_names.items():
            count = sum(1 for f in FEEDS if f.get("continent") == code)
            countries = sorted(set(f["country_code"] for f in FEEDS if f.get("continent") == code))
            print(f"  {name}: {count} feeds across {len(countries)} countries ({', '.join(countries)})")

        print(f"\nTotal: {len(FEEDS)} feeds")

    finally:
        db.close()


if __name__ == "__main__":
    seed_feeds()
