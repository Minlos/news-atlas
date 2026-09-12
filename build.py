#!/usr/bin/env python3
"""Fetch recent disaster news (natural + technogenic), cluster, write news-map.html."""

from __future__ import annotations

import email.utils
import html
import json
import os
import re
import ssl
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

TODAY = datetime.now(timezone.utc).date()
WINDOW_DAYS = 14
AFTER = (TODAY - timedelta(days=WINDOW_DAYS)).isoformat()
UA = "news-atlas/0.1 (personal map; +https://minlos.site/news)"
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "off").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:12b")
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4.3")
XAI_URL = "https://api.x.ai/v1/chat/completions"
FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("BBC Asia", "https://feeds.bbci.co.uk/news/world/asia/rss.xml"),
    ("The Guardian", "https://www.theguardian.com/world/rss"),
    ("Guardian environment", "https://www.theguardian.com/environment/rss"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("NPR World", "https://feeds.npr.org/1004/rss.xml"),
    ("NYT World", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
    ("France 24", "https://www.france24.com/en/rss"),
    ("DW", "https://rss.dw.com/rdf/rss-en-world"),
    ("ABC Australia", "https://www.abc.net.au/news/feed/51120/rss.xml"),
    ("The Hindu", "https://www.thehindu.com/news/international/feeder/default.rss"),
    ("Kathmandu Post", "https://kathmandupost.com/rss"),
    ("Floodlist", "https://floodlist.com/feed"),
    ("ReliefWeb", "https://reliefweb.int/updates/rss.xml?disaster_type[]=wild-fire&disaster_type[]=flood&disaster_type[]=earthquake&disaster_type[]=tropical-cyclone&disaster_type[]=land-slide&disaster_type[]=volcano&disaster_type[]=tsunami&disaster_type[]=technological-disaster"),
    ("Google News", f"https://news.google.com/rss/search?q=flood%20OR%20wildfire%20OR%20earthquake%20OR%20hurricane%20OR%20typhoon%20OR%20landslide%20after:{AFTER}&hl=en-US&gl=US&ceid=US:en"),
    ("Google wildfires", f"https://news.google.com/rss/search?q=wildfire%20OR%20bushfire%20OR%20%22forest%20fire%22%20OR%20%22fires%20rage%22%20OR%20%22acres%20burned%22%20after:{AFTER}&hl=en-US&gl=US&ceid=US:en"),
    ("Google technogenic", "https://news.google.com/rss/search?q=chemical%20spill%20OR%20%22oil%20spill%22%20OR%20%22gas%20explosion%22%20OR%20%22factory%20explosion%22%20OR%20%22mine%20collapse%22%20OR%20%22mining%20accident%22%20OR%20%22industrial%20accident%22%20OR%20%22refinery%20fire%22%20OR%20%22pipeline%20explosion%22%20when:7d&hl=en-US&gl=US&ceid=US:en"),
    ("Google industrial", "https://news.google.com/rss/search?q=%22mine%20collapse%22%20OR%20%22mining%20accident%22%20OR%20%22gas%20explosion%22%20OR%20%22industrial%20accident%22%20OR%20%22refinery%20fire%22%20OR%20%22pipeline%20explosion%22%20when:7d&hl=en-US&gl=US&ceid=US:en"),
    ("TASS", "https://tass.ru/rss/v2.xml"),
    ("RIA Novosti", "https://ria.ru/export/rss2/index.xml"),
    ("Interfax", "https://www.interfax.ru/rss.asp"),
    ("Moscow Times", "https://www.themoscowtimes.com/rss/news"),
    ("YSIA Yakutia", "https://ysia.ru/feed/"),
    ("Yakutia24", "https://yk24.ru/feed/"),
    ("NGS Krasnoyarsk", "https://ngs24.ru/text/rss.xml"),
    ("IRCity Irkutsk", "https://www.ircity.ru/text/rss.xml"),
    ("NGS Kuzbass", "https://ngs42.ru/text/rss.xml"),
    ("KP Kamchatka", "https://www.kamchatka.kp.ru/rss/allsections.xml"),
    ("KP Far East", "https://www.dv.kp.ru/rss/allsections.xml"),
    ("Chita.ru", "https://www.chita.ru/rss/"),
    ("Yamal 89.ru", "https://89.ru/text/rss.xml"),
    ("E1 Yekaterinburg", "https://www.e1.ru/text/rss.xml"),
    ("74.ru Chelyabinsk", "https://74.ru/text/rss.xml"),
    ("Google RU disasters", "https://news.google.com/rss/search?q=%D0%BB%D0%B5%D1%81%D0%BD%D0%BE%D0%B9%20%D0%BF%D0%BE%D0%B6%D0%B0%D1%80%20OR%20%D0%BF%D0%B0%D0%B2%D0%BE%D0%B4%D0%BE%D0%BA%20OR%20%D0%BD%D0%B0%D0%B2%D0%BE%D0%B4%D0%BD%D0%B5%D0%BD%D0%B8%D0%B5%20OR%20%D0%B7%D0%B5%D0%BC%D0%BB%D0%B5%D1%82%D1%80%D1%8F%D1%81%D0%B5%D0%BD%D0%B8%D0%B5%20OR%20%D0%B8%D0%B7%D0%B2%D0%B5%D1%80%D0%B6%D0%B5%D0%BD%D0%B8%D0%B5%20when:7d&hl=ru&gl=RU&ceid=RU:ru"),
    ("Google RU industrial", "https://news.google.com/rss/search?q=%D1%80%D0%B0%D0%B7%D0%BB%D0%B8%D0%B2%20%D0%BD%D0%B5%D1%84%D1%82%D0%B8%20OR%20%22%D0%B2%D0%B7%D1%80%D1%8B%D0%B2%20%D0%BD%D0%B0%20%D1%88%D0%B0%D1%85%D1%82%D0%B5%22%20OR%20%22%D0%B0%D0%B2%D0%B0%D1%80%D0%B8%D1%8F%20%D0%BD%D0%B0%20%D0%9D%D0%9F%D0%97%22%20OR%20%22%D0%BF%D0%BE%D0%B6%D0%B0%D1%80%20%D0%BD%D0%B0%20%D0%9D%D0%9F%D0%97%22%20OR%20%22%D0%BE%D0%B1%D1%80%D1%83%D1%88%D0%B5%D0%BD%D0%B8%D0%B5%20%D1%88%D0%B0%D1%85%D1%82%D1%8B%22%20when:7d&hl=ru&gl=RU&ceid=RU:ru"),
]

# City first, then country. Longer names win via sorted match.
PLACES = [
    ("Washington", 38.9072, -77.0369, "Americas"),
    ("New York", 40.7128, -74.0060, "Americas"),
    ("Los Angeles", 34.0522, -118.2437, "Americas"),
    ("Mexico City", 19.4326, -99.1332, "Americas"),
    ("Buenos Aires", -34.6037, -58.3816, "Americas"),
    ("Sao Paulo", -23.5505, -46.6333, "Americas"),
    ("Rio de Janeiro", -22.9068, -43.1729, "Americas"),
    ("Brasilia", -15.7975, -47.8919, "Americas"),
    ("Toronto", 43.6532, -79.3832, "Americas"),
    ("Ottawa", 45.4215, -75.6972, "Americas"),
    ("Havana", 23.1136, -82.3666, "Americas"),
    ("Bogota", 4.7110, -74.0721, "Americas"),
    ("Caracas", 10.4806, -66.9036, "Americas"),
    ("Lima", -12.0464, -77.0428, "Americas"),
    ("Santiago", -33.4489, -70.6693, "Americas"),
    ("London", 51.5074, -0.1278, "Europe"),
    ("Paris", 48.8566, 2.3522, "Europe"),
    ("Berlin", 52.5200, 13.4050, "Europe"),
    ("Brussels", 50.8503, 4.3517, "Europe"),
    ("Rome", 41.9028, 12.4964, "Europe"),
    ("Madrid", 40.4168, -3.7038, "Europe"),
    ("Barcelona", 41.3874, 2.1686, "Europe"),
    ("Lisbon", 38.7223, -9.1393, "Europe"),
    ("Amsterdam", 52.3676, 4.9041, "Europe"),
    ("Vienna", 48.2082, 16.3738, "Europe"),
    ("Warsaw", 52.2297, 21.0122, "Europe"),
    ("Prague", 50.0755, 14.4378, "Europe"),
    ("Budapest", 47.4979, 19.0402, "Europe"),
    ("Athens", 37.9838, 23.7275, "Europe"),
    ("Stockholm", 59.3293, 18.0686, "Europe"),
    ("Oslo", 59.9139, 10.7522, "Europe"),
    ("Helsinki", 60.1699, 24.9384, "Europe"),
    ("Copenhagen", 55.6761, 12.5683, "Europe"),
    ("Dublin", 53.3498, -6.2603, "Europe"),
    ("Zurich", 47.3769, 8.5417, "Europe"),
    ("Geneva", 46.2044, 6.1432, "Europe"),
    ("Kyiv", 50.4501, 30.5234, "Europe"),
    ("Kiev", 50.4501, 30.5234, "Europe"),
    ("Moscow", 55.7558, 37.6173, "Europe"),
    ("St Petersburg", 59.9311, 30.3609, "Europe"),
    ("Yakutsk", 62.0355, 129.6755, "Asia"),
    ("Yakutia", 66.7613, 124.1238, "Asia"),
    ("Krasnoyarsk", 56.0153, 92.8932, "Asia"),
    ("Krasnoyarsky Krai", 64.2500, 95.0000, "Asia"),
    ("Evenkia", 64.2833, 100.2500, "Asia"),
    ("Turukhansk", 65.7960, 87.9620, "Asia"),
    ("Taymyr", 73.5000, 80.5000, "Asia"),
    ("Lesosibirsk", 58.2217, 92.5037, "Asia"),
    ("Yeniseysk", 58.4497, 92.1797, "Asia"),
    ("Norilsk", 69.3558, 88.1893, "Asia"),
    ("Irkutsk", 52.2870, 104.3050, "Asia"),
    ("Khabarovsk", 48.4827, 135.0840, "Asia"),
    ("Vladivostok", 43.1155, 131.8855, "Asia"),
    ("Petropavlovsk-Kamchatsky", 53.0370, 158.6559, "Asia"),
    ("Kamchatka", 56.0000, 159.0000, "Asia"),
    ("Yuzhno-Sakhalinsk", 46.9591, 142.7380, "Asia"),
    ("Sakhalin", 50.0000, 143.0000, "Asia"),
    ("Magadan", 59.5612, 150.8090, "Asia"),
    ("Chita", 52.0515, 113.4712, "Asia"),
    ("Transbaikalia", 52.8000, 116.0000, "Asia"),
    ("Ulan-Ude", 51.8272, 107.6063, "Asia"),
    ("Buryatia", 53.0000, 109.0000, "Asia"),
    ("Blagoveshchensk", 50.2906, 127.5272, "Asia"),
    ("Novosibirsk", 55.0084, 82.9357, "Asia"),
    ("Tomsk", 56.4846, 84.9476, "Asia"),
    ("Omsk", 54.9885, 73.3242, "Asia"),
    ("Barnaul", 53.3548, 83.7698, "Asia"),
    ("Kemerovo", 55.3541, 86.0898, "Asia"),
    ("Novokuznetsk", 53.7596, 87.1216, "Asia"),
    ("Kuzbass", 54.9000, 86.9000, "Asia"),
    ("Salekhard", 66.5299, 66.6143, "Asia"),
    ("Yamal", 67.0000, 74.0000, "Asia"),
    ("Surgut", 61.2540, 73.3962, "Asia"),
    ("Nizhnevartovsk", 60.9397, 76.5696, "Asia"),
    ("Yekaterinburg", 56.8389, 60.6057, "Europe"),
    ("Chelyabinsk", 55.1644, 61.4368, "Europe"),
    ("Magnitogorsk", 53.4072, 58.9794, "Europe"),
    ("Perm", 58.0105, 56.2502, "Europe"),
    ("Ufa", 54.7388, 55.9721, "Europe"),
    ("Kazan", 55.7887, 49.1221, "Europe"),
    ("Murmansk", 68.9585, 33.0827, "Europe"),
    ("Arkhangelsk", 64.5399, 40.5146, "Europe"),
    ("Vorkuta", 67.4974, 64.0355, "Europe"),
    ("Rostov-on-Don", 47.2357, 39.7015, "Europe"),
    ("Krasnodar", 45.0355, 38.9753, "Europe"),
    ("Sochi", 43.6028, 39.7342, "Europe"),
    ("Volgograd", 48.7080, 44.5133, "Europe"),
    ("Primorye", 45.0000, 135.0000, "Asia"),
    ("Far East", 54.0000, 140.0000, "Asia"),
    ("Komi", 64.0000, 54.0000, "Europe"),
    ("Tuapse", 44.1053, 39.0833, "Europe"),
    ("Bashkortostan", 54.5000, 56.9000, "Europe"),
    ("Mirny", 62.5353, 113.9610, "Asia"),
    ("Neryungri", 56.6584, 124.7250, "Asia"),
    ("Khakassia", 53.5000, 90.0000, "Asia"),
    ("Tsimlyansk", 47.6473, 42.0947, "Europe"),
    ("Istanbul", 41.0082, 28.9784, "Europe"),
    ("Ankara", 39.9334, 32.8597, "Middle East"),
    ("Tel Aviv", 32.0853, 34.7818, "Middle East"),
    ("Jerusalem", 31.7683, 35.2137, "Middle East"),
    ("Gaza", 31.5017, 34.4668, "Middle East"),
    ("Ramallah", 31.9074, 35.2044, "Middle East"),
    ("Beirut", 33.8938, 35.5018, "Middle East"),
    ("Damascus", 33.5138, 36.2765, "Middle East"),
    ("Amman", 31.9454, 35.9284, "Middle East"),
    ("Baghdad", 33.3152, 44.3661, "Middle East"),
    ("Tehran", 35.6892, 51.3890, "Middle East"),
    ("Riyadh", 24.7136, 46.6753, "Middle East"),
    ("Jeddah", 21.4858, 39.1925, "Middle East"),
    ("Doha", 25.2854, 51.5310, "Middle East"),
    ("Abu Dhabi", 24.4539, 54.3773, "Middle East"),
    ("Dubai", 25.2048, 55.2708, "Middle East"),
    ("Cairo", 30.0444, 31.2357, "Middle East"),
    ("Sanaa", 15.3694, 44.1910, "Middle East"),
    ("Tripoli", 32.8872, 13.1913, "Middle East"),
    ("Tunis", 36.8065, 10.1815, "Africa"),
    ("Algiers", 36.7538, 3.0588, "Africa"),
    ("Rabat", 34.0209, -6.8416, "Africa"),
    ("Casablanca", 33.5731, -7.5898, "Africa"),
    ("Lagos", 6.5244, 3.3792, "Africa"),
    ("Abuja", 9.0765, 7.3986, "Africa"),
    ("Nairobi", -1.2921, 36.8219, "Africa"),
    ("Addis Ababa", 9.0320, 38.7469, "Africa"),
    ("Khartoum", 15.5007, 32.5599, "Africa"),
    ("Johannesburg", -26.2041, 28.0473, "Africa"),
    ("Cape Town", -33.9249, 18.4241, "Africa"),
    ("Kinshasa", -4.4419, 15.2663, "Africa"),
    ("Mogadishu", 2.0469, 45.3182, "Africa"),
    ("Beijing", 39.9042, 116.4074, "Asia"),
    ("Shanghai", 31.2304, 121.4737, "Asia"),
    ("Hong Kong", 22.3193, 114.1694, "Asia"),
    ("Taipei", 25.0330, 121.5654, "Asia"),
    ("Tokyo", 35.6762, 139.6503, "Asia"),
    ("Osaka", 34.6937, 135.5023, "Asia"),
    ("Seoul", 37.5665, 126.9780, "Asia"),
    ("Pyongyang", 39.0392, 125.7625, "Asia"),
    ("New Delhi", 28.6139, 77.2090, "Asia"),
    ("Delhi", 28.6139, 77.2090, "Asia"),
    ("Mumbai", 19.0760, 72.8777, "Asia"),
    ("Islamabad", 33.6844, 73.0479, "Asia"),
    ("Karachi", 24.8607, 67.0011, "Asia"),
    ("Lahore", 31.5204, 74.3587, "Asia"),
    ("Kabul", 34.5553, 69.2075, "Asia"),
    ("Islamabad", 33.6844, 73.0479, "Asia"),
    ("Dhaka", 23.8103, 90.4125, "Asia"),
    ("Bangkok", 13.7563, 100.5018, "Asia"),
    ("Hanoi", 21.0278, 105.8342, "Asia"),
    ("Jakarta", -6.2088, 106.8456, "Asia"),
    ("Manila", 14.5995, 120.9842, "Asia"),
    ("Singapore", 1.3521, 103.8198, "Asia"),
    ("Sydney", -33.8688, 151.2093, "Asia"),
    ("Melbourne", -37.8136, 144.9631, "Asia"),
    ("Canberra", -35.2809, 149.1300, "Asia"),
    ("Wellington", -41.2865, 174.7762, "Asia"),
    ("Kathmandu", 27.7172, 85.3240, "Asia"),
    ("Rasuwagadhi", 28.2789, 85.3775, "Asia"),
    ("Timure", 28.2780, 85.3570, "Asia"),
    ("Syabrubesi", 28.1639, 85.3478, "Asia"),
    ("Dhunche", 28.1106, 85.2983, "Asia"),
    ("Rasuwa", 28.1750, 85.3300, "Asia"),
    ("Trishuli 3A", 27.9160, 85.1450, "Asia"),
    ("Trishuli River", 28.0500, 85.2200, "Asia"),
    ("Trishuli", 27.9070, 85.1360, "Asia"),
    ("Nepal-Tibet border", 28.2789, 85.3775, "Asia"),
    ("Lende Khola", 28.2750, 85.3720, "Asia"),
    ("Bidur", 27.8960, 85.1460, "Asia"),
    ("Nuwakot", 27.8700, 85.1700, "Asia"),
    ("Dhading", 27.9100, 84.8900, "Asia"),
    ("Chitwan", 27.5291, 84.3542, "Asia"),
    ("Gorkha", 28.0460, 84.6200, "Asia"),
    ("Tanahu", 27.9440, 84.2500, "Asia"),
    ("Chilime", 28.2090, 85.3130, "Asia"),
    ("Mailung", 28.0800, 85.2200, "Asia"),
    ("Betrawati", 27.9700, 85.1800, "Asia"),
    ("Langtang", 28.2150, 85.5650, "Asia"),
    ("Barhabise", 27.7900, 85.8950, "Asia"),
    ("Sindhupalchok", 27.8000, 85.7000, "Asia"),
    ("Bhotekoshi", 27.8100, 85.8900, "Asia"),
    ("Kerung", 28.3900, 85.3250, "Asia"),
    ("Nepal", 28.3949, 84.1240, "Asia"),
    ("California", 36.7783, -119.4179, "Americas"),
    ("Hawaii", 19.8968, -155.5828, "Americas"),
    ("Alberta", 53.9333, -116.5769, "Americas"),
    ("British Columbia", 53.7267, -127.6476, "Americas"),
    ("Greece", 37.9838, 23.7275, "Europe"),
    ("Portugal", 38.7223, -9.1393, "Europe"),
    ("Chile", -33.4489, -70.6693, "Americas"),
    ("Haiti", 18.5944, -72.3074, "Americas"),
    ("El Salvador", 13.7942, -88.8965, "Americas"),
    ("Libya", 32.8872, 13.1913, "Middle East"),
    ("Siberia", 60.0000, 100.0000, "Asia"),
    ("Amazon", -3.4653, -62.2159, "Americas"),
    ("Oregon", 43.8041, -120.5542, "Americas"),
    ("Montana", 46.8797, -110.3626, "Americas"),
    ("Idaho", 44.0682, -114.7420, "Americas"),
    ("Yukon", 64.2823, -135.0000, "Americas"),
    ("Saskatchewan", 52.9399, -106.4509, "Americas"),
    ("Texas", 31.9686, -99.9018, "Americas"),
    ("Nebraska", 41.4925, -99.9018, "Americas"),
    ("Colorado", 39.5501, -105.7821, "Americas"),
    ("Arkansas", 35.2010, -91.8318, "Americas"),
    ("Ohio", 40.4173, -82.9071, "Americas"),
    ("Illinois", 40.6331, -89.3985, "Americas"),
    ("Louisiana", 30.9843, -91.9623, "Americas"),
    ("Iowa", 41.8780, -93.0977, "Americas"),
    ("North Dakota", 47.5515, -101.0020, "Americas"),
    ("Missouri", 37.9643, -91.8318, "Americas"),
    ("Michigan", 44.3148, -85.6024, "Americas"),
    ("Pennsylvania", 41.2033, -77.1945, "Americas"),
    ("Alabama", 32.3182, -86.9023, "Americas"),
    ("Florida", 27.6648, -81.5158, "Americas"),
    ("Georgia", 32.1656, -82.9001, "Americas"),
    ("Nevada", 38.8026, -116.4194, "Americas"),
    ("Arizona", 34.0489, -111.0937, "Americas"),
    ("Wyoming", 43.0760, -107.2903, "Americas"),
    ("Alaska", 64.2008, -152.4783, "Americas"),
    ("South Carolina", 33.8361, -81.1637, "Americas"),
    ("Tennessee", 35.5175, -86.5804, "Americas"),
    ("Kentucky", 37.8393, -84.2700, "Americas"),
    ("Minnesota", 46.7296, -94.6859, "Americas"),
    ("Wisconsin", 43.7844, -88.7879, "Americas"),
    ("Oklahoma", 35.0078, -97.0929, "Americas"),
    ("Kansas", 39.0119, -98.4842, "Americas"),
    ("Indiana", 40.2672, -86.1349, "Americas"),
    ("Mississippi", 32.3547, -89.3985, "Americas"),
    ("West Virginia", 38.5976, -80.4549, "Americas"),
    ("Quebec", 46.8139, -71.2080, "Americas"),
    ("Houston", 29.7604, -95.3698, "Americas"),
    ("Chicago", 41.8781, -87.6298, "Americas"),
    ("Detroit", 42.3314, -83.0458, "Americas"),
    ("Seattle", 47.6062, -122.3321, "Americas"),
    ("Cleveland", 41.4993, -81.6944, "Americas"),
    ("Pittsburgh", 40.4406, -79.9959, "Americas"),
    ("Charleston", 32.7765, -79.9311, "Americas"),
    ("Atlanta", 33.7490, -84.3880, "Americas"),
    ("Dallas", 32.7767, -96.7970, "Americas"),
    ("Miami", 25.7617, -80.1918, "Americas"),
    ("Philadelphia", 39.9526, -75.1652, "Americas"),
    ("Denver", 39.7392, -104.9903, "Americas"),
    ("Phoenix", 33.4484, -112.0740, "Americas"),
    ("El Paso", 31.7619, -106.4850, "Americas"),
    ("Twin Falls", 42.5559, -114.4701, "Americas"),
    ("Fort Smith", 35.3880, -94.4265, "Americas"),
    ("Slidell", 30.2752, -89.7812, "Americas"),
    ("Loudon County", 35.7490, -84.3203, "Americas"),
    ("Anclote Power Plant", 28.1843, -82.7875, "Americas"),
    ("Longview", 46.1377, -122.9345, "Americas"),
    ("Nippon Dynawave", 46.1302, -122.9807, "Americas"),
    ("Rome NY", 43.2102, -75.4584, "Americas"),
    ("Port Harcourt", 4.8156, 7.0498, "Africa"),
    ("Bille", 4.5764, 6.8879, "Africa"),
    ("Rubaya", -1.5472, 28.8743, "Africa"),
    ("Yaroslavl", 57.6266, 39.8937, "Europe"),
    ("DR Congo", -4.0383, 21.7587, "Africa"),
    ("Washington State", 47.7511, -120.7401, "Americas"),
    ("Yosemite", 37.8651, -119.5383, "Americas"),
    ("Mariposa", 37.4849, -119.9663, "Americas"),
    ("Algeria", 36.7538, 3.0588, "Africa"),
    ("Sumatra", 0.5897, 101.3431, "Asia"),
    ("Luzon", 16.0000, 121.0000, "Asia"),
    ("United States", 38.9072, -77.0369, "Americas"),
    ("America", 38.9072, -77.0369, "Americas"),
    ("Canada", 45.4215, -75.6972, "Americas"),
    ("Mexico", 19.4326, -99.1332, "Americas"),
    ("Brazil", -15.7975, -47.8919, "Americas"),
    ("Argentina", -34.6037, -58.3816, "Americas"),
    ("Venezuela", 10.4806, -66.9036, "Americas"),
    ("Colombia", 4.7110, -74.0721, "Americas"),
    ("United Kingdom", 51.5074, -0.1278, "Europe"),
    ("Britain", 51.5074, -0.1278, "Europe"),
    ("England", 51.5074, -0.1278, "Europe"),
    ("France", 48.8566, 2.3522, "Europe"),
    ("Germany", 52.5200, 13.4050, "Europe"),
    ("Italy", 41.9028, 12.4964, "Europe"),
    ("Spain", 40.4168, -3.7038, "Europe"),
    ("Poland", 52.2297, 21.0122, "Europe"),
    ("Ukraine", 50.4501, 30.5234, "Europe"),
    ("Russia", 55.7558, 37.6173, "Europe"),
    ("Turkey", 39.9334, 32.8597, "Middle East"),
    ("Israel", 31.7683, 35.2137, "Middle East"),
    ("Palestine", 31.9074, 35.2044, "Middle East"),
    ("Lebanon", 33.8938, 35.5018, "Middle East"),
    ("Syria", 33.5138, 36.2765, "Middle East"),
    ("Iraq", 33.3152, 44.3661, "Middle East"),
    ("Iran", 35.6892, 51.3890, "Middle East"),
    ("Saudi Arabia", 24.7136, 46.6753, "Middle East"),
    ("Yemen", 15.3694, 44.1910, "Middle East"),
    ("Qatar", 25.2854, 51.5310, "Middle East"),
    ("Egypt", 30.0444, 31.2357, "Middle East"),
    ("Sudan", 15.5007, 32.5599, "Africa"),
    ("Nigeria", 9.0765, 7.3986, "Africa"),
    ("Kenya", -1.2921, 36.8219, "Africa"),
    ("Ethiopia", 9.0320, 38.7469, "Africa"),
    ("South Africa", -26.2041, 28.0473, "Africa"),
    ("Morocco", 34.0209, -6.8416, "Africa"),
    ("China", 39.9042, 116.4074, "Asia"),
    ("Taiwan", 25.0330, 121.5654, "Asia"),
    ("Japan", 35.6762, 139.6503, "Asia"),
    ("South Korea", 37.5665, 126.9780, "Asia"),
    ("North Korea", 39.0392, 125.7625, "Asia"),
    ("India", 28.6139, 77.2090, "Asia"),
    ("Pakistan", 33.6844, 73.0479, "Asia"),
    ("Afghanistan", 34.5553, 69.2075, "Asia"),
    ("Bangladesh", 23.8103, 90.4125, "Asia"),
    ("Myanmar", 16.8409, 96.1735, "Asia"),
    ("Thailand", 13.7563, 100.5018, "Asia"),
    ("Vietnam", 21.0278, 105.8342, "Asia"),
    ("Indonesia", -6.2088, 106.8456, "Asia"),
    ("Philippines", 14.5995, 120.9842, "Asia"),
    ("Australia", -35.2809, 149.1300, "Asia"),
]

CITIES = {n for n, _, _, _ in PLACES if n not in {
    "United States", "America", "Canada", "Mexico", "Brazil", "Argentina", "Venezuela",
    "Colombia", "United Kingdom", "Britain", "England", "France", "Germany", "Italy",
    "Spain", "Poland", "Ukraine", "Russia", "Turkey", "Israel", "Palestine", "Lebanon",
    "Syria", "Iraq", "Iran", "Saudi Arabia", "Yemen", "Qatar", "Egypt", "Sudan",
    "Nigeria", "Kenya", "Ethiopia", "South Africa", "Morocco", "China", "Taiwan",
    "Japan", "South Korea", "North Korea", "India", "Pakistan", "Afghanistan",
    "Bangladesh", "Myanmar", "Thailand", "Vietnam", "Indonesia", "Philippines",
    "Australia", "Nepal", "California", "Hawaii", "Alberta", "British Columbia",
    "Nuwakot", "Dhading", "Chitwan", "Gorkha", "Tanahu", "Rasuwa",
    "Greece", "Portugal", "Chile", "Haiti", "El Salvador", "Libya", "Siberia",
    "Oregon", "Montana", "Idaho", "Yukon", "Saskatchewan", "Texas", "Nebraska",
    "Colorado", "Arkansas", "Ohio", "Illinois", "Louisiana", "Iowa", "North Dakota",
    "Missouri", "Michigan", "Pennsylvania", "Alabama", "Florida", "Georgia",
    "Nevada", "Arizona", "Wyoming", "Alaska", "South Carolina", "Tennessee",
    "Kentucky", "Minnesota", "Wisconsin", "Oklahoma", "Kansas", "Indiana",
    "Mississippi", "West Virginia", "Quebec", "Amazon", "Algeria", "DR Congo",
    "Washington State",
    "Yakutia", "Krasnoyarsky Krai", "Evenkia", "Taymyr", "Kamchatka", "Sakhalin",
    "Transbaikalia", "Buryatia", "Kuzbass", "Yamal", "Primorye", "Far East", "Komi",
    "Siberia", "Bashkortostan", "Khakassia",
}}

STOP = {
    "the", "a", "an", "and", "or", "of", "in", "on", "for", "to", "from", "after",
    "with", "as", "at", "by", "over", "into", "says", "say", "said", "against",
    "new", "more", "than", "its", "his", "her", "their", "who", "after", "under",
    "about", "have", "has", "will", "been", "were", "this", "that", "with", "from",
    "world", "news", "video", "live", "update", "updates", "could", "would", "over",
}

HAZARDS = [
    ("wildfire", re.compile(
        r"\bwildfires?\b|\bbushfires?\b|\bforest fires?\b|\bwild fire\b|"
        r"\bpeat fires?\b|\bgrass fires?\b|\bbrush fires?\b|"
        r"\b(acres|hectares)\s+burned\b|"
        r"\bfires?\s+(?:rage|raging|spread|spreading|burn|burning|engulf)|"
        r"\b(?:rage|raging|spread|burning)\s+fires?\b|"
        r"\bblaze\b.{0,40}\b(?:forest|bush|wild)|"
        r"\bлесн\w{0,10}\s+пожар\w*|\bпожар\w*\s+в\s+лес\w*|"
        r"\bландшафтн\w{0,8}\s+пожар\w*|\bторфян\w{0,8}\s+пожар\w*|"
        r"\bзадымлен\w*|\bдым\w{0,8}.{0,40}пожар", re.I)),
    ("flood", re.compile(
        r"\bfloods?\b|\bflooding\b|\bflooded\b|\bflash floods?\b|"
        r"\bнаводнен\w*|\bпаводок\w*|\bподтоплен\w*", re.I)),
    ("earthquake", re.compile(
        r"\bearthquakes?\b|\baftershocks?\b|\bземлетрясен\w*|"
        r"\b(?<!earth)quakes?\b", re.I)),
    ("cyclone", re.compile(
        r"\bhurricanes?\b|\btyphoons?\b|\bcyclones?\b|\btropical storms?\b|"
        r"\bураган\w*|\bтайфун\w*", re.I)),
    ("tornado", re.compile(r"\btornadoes?\b|\btwisters?\b", re.I)),
    ("volcano", re.compile(r"\bvolcanos?\b|\bvolcanoes?\b|\beruptions?\b|\bизвержен\w*", re.I)),
    ("landslide", re.compile(r"\blandslides?\b|\bmudslides?\b|\bоползн\w*", re.I)),
    ("tsunami", re.compile(r"\btsunamis?\b|\bцунами\b", re.I)),
    ("avalanche", re.compile(r"\bavalanches?\b|\bлавин\w*", re.I)),
    ("technogenic", re.compile(
        r"\bindustrial accidents?\b|\btechnogenic\b|"
        r"\bтехногенн\w{0,8}\s+(?:авари\w*|катастроф\w*|чп)\b|"
        r"\bindustrial (?:explosions?|fires?|blasts?|disasters?)\b|"
        r"\bchemical spills?\b|\btoxic (?:spills?|leaks?|clouds?|gas)\b|"
        r"\boil spills?\b|\bgas (?:leaks?|explosions?|blasts?)\b|"
        r"\bpipeline (?:explosions?|blasts?|leaks?|ruptures?)\b|"
        r"\brefinery (?:fires?|explosions?|blasts?)\b|"
        r"\bfactory (?:explosions?|blasts?|fires?)\b|"
        r"\b(?:plant|warehouse) (?:explosions?|blasts?)\b|"
        r"\bexplosions? at (?:a |the )?(?:plant|factory|refinery|mine|warehouse|chemical)\b|"
        r"\bmine (?:collapses?|accidents?|explosions?|blasts?)\b|"
        r"\b(?:coal )?mining accidents?\b|"
        r"\bnuclear (?:accidents?|leaks?|meltdowns?|disasters?)\b|"
        r"\bradiation leaks?\b|\bразлив\w{0,6}\s+нефт|"
        r"\bвзрыв\w{0,6}\s+на\s+(?:шахте|заводе|нпз|трубопроводе|нефтепроводе|газопроводе)|"
        r"\bавари\w{0,6}\s+на\s+(?:шахте|заводе|нпз|трубопроводе|тэц|аэс)|"
        r"\bпожар\w{0,6}\s+на\s+(?:нпз|нефтепровод\w*|газопровод\w*|шахте|заводе)|"
        r"\bобрушен\w{0,8}.{0,12}шахт|"
        r"\bвыброс\w{0,6}\s+(?:хлора|аммиака)|"
        r"\b(?:train|freight|rail(?:way|road)?) derailments?\b|"
        r"\btrains? derail(?:s|ed|ing)?\b|"
        r"\bhazmat\b|\bchlorine leaks?\b|\bammonia leaks?\b|"
        r"\bdam (?:bursts?|failures?|breaches?|collapses?)\b",
        re.I)),
]

HAZARD_COLOR = {
    "wildfire": "#d4784a",
    "flood": "#6a9ec4",
    "earthquake": "#c4898a",
    "cyclone": "#8aa0c4",
    "tornado": "#9b8ac4",
    "volcano": "#c45a3a",
    "landslide": "#9b8a6a",
    "tsunami": "#4a7a8c",
    "avalanche": "#c4d0d8",
    "technogenic": "#c4a85a",
}

REJECT = re.compile(
    r"\belections?\b|\bfar-right\b|\bparliament\b|\bsentenced\b|\btrial\b|\bjury\b|"
    r"\bhostilit\w*|\bairstrikes?\b|\bceasefire\b|\benvoys?\b|\bsanctions\b|"
    r"\bprotesters?\b|\bvoted to\b|\bprotection cluster\b|\bweekly situation\b|"
    r"\brevealed:\b|\blessons learned\b|\breview [–-]\b|\bhere are some other\b|"
    r"\bextraordinary rescues\b|\bcompanies\b.{0,40}\bwater\b|\bwar in\b|"
    r"\btroops\b|\barmed conflict\b|\bPM says\b|"
    r"\bwhat we know about the link\b|\bclimate crisis\b|"
    r"\bliability\b|\bPG&E\b|\bState Farm\b|"
    r"\bwildfire (?:bill|reform|deal|costs?|plan|claims?)\b|"
    r"\blegislat(?:e|ure|ive)\b|"
    r"\bnuclear (?:deal|talks?|weapon|warheads?|enrichment|proliferation|summit)\b|"
    r"\bchemical weapons?\b|"
    r"\bmissiles?\b|\bbombing\b|\bshelling\b|"
    r"\boil prices?\b|"
    r"\bспецоперац\w*|\bобстрел\w*|\bбеспилотник\w*|\bбпла\b",
    re.I,
)

TECH_STALE = re.compile(
    r"\bten years later\b|\byears later\b|"
    r"\bguidance for\b|\bschizophrenia\b|"
    r"\bmarket size\b|\bcooking oil\b|"
    r"\b(?:18-wheeler|tractor-trailer)\b.{0,40}\boil spill|"
    r"\boil spill.{0,40}\b(?:highway|expressway|interstate|lanes?)\b|"
    r"\b(?:highway|expressway|interstate)\b.{0,40}\boil spill",
    re.I,
)

HAPPENING = re.compile(
    r"\brescued?\b|\bkilled\b|\bdead\b|\bdeaths?\b|\bdeath toll\b|\bmissing\b|"
    r"\bevacuat\w*|\bstranded\b|\braging\b|\bflooded\b|\bflash floods?\b|"
    r"\bcollapsed\b|\btrapped\b|\bdestroyed\b|\bwash(?:ed)? away\b|"
    r"\baftershocks?\b|\blandfall\b|\berupt\w*|\bhaze\b|\bwildfires?\b|"
    r"\bbushfires?\b|\btunnel\b|\bdisplaced\b|\bdamaged?\b|\bhit by\b|"
    r"\brescue\b|\bsurvivors?\b|\bwarning\b|\balert\b|"
    r"\bcyclones?\b|\btyphoons?\b|\bhurricanes?\b|\bearthquakes?\b|"
    r"\bпогиб\w*|\bэвакуир\w*|\bпотушил\w*|\bдействует\s+пожар|"
    r"\bплощад\w{0,6}.{0,12}\bга\b|\bчс\b",
    re.I,
)


def classify_hazard(text: str) -> str | None:
    hits = [name for name, rx in HAZARDS if rx.search(text or "")]
    if "technogenic" in hits:
        return "technogenic"
    return hits[0] if hits else None


def is_happening(title: str, summary: str) -> bool:
    text = f"{title} {summary}"
    if REJECT.search(text):
        return False
    hazard = classify_hazard(text)
    if hazard == "technogenic" and TECH_STALE.search(title):
        return False
    if hazard:
        return True
    return bool(HAPPENING.search(text))

PLACE_BY_NAME = {n.lower(): (n, lat, lng, region) for n, lat, lng, region in PLACES}
PLACE_NAMES = sorted(PLACE_BY_NAME, key=len, reverse=True)

# Finer beats coarser: site 0, town 1, district 2, country 3.
PLACE_GRAIN = {
    "Rasuwagadhi": 0, "Trishuli 3A": 0, "Trishuli River": 0, "Nepal-Tibet border": 0,
    "Lende Khola": 0, "Bhotekoshi": 0, "Chilime": 0, "Mailung": 0,
    "Timure": 1, "Syabrubesi": 1, "Dhunche": 1, "Betrawati": 1, "Barhabise": 1,
    "Langtang": 1, "Kerung": 1, "Bidur": 1, "Trishuli": 1, "Kathmandu": 1,
    "Rasuwa": 2, "Nuwakot": 2, "Dhading": 2, "Chitwan": 2, "Gorkha": 2,
    "Tanahu": 2, "Sindhupalchok": 2, "Nepal": 3,
    "Sumatra": 2, "Luzon": 2, "Hawaii": 2, "California": 2,
    "Amazon": 2, "Oregon": 2, "Montana": 2, "Idaho": 2, "Yukon": 2, "Saskatchewan": 2,
    "Texas": 2, "Nebraska": 2, "Colorado": 2, "Arkansas": 2, "Yosemite": 1, "Mariposa": 1,
    "Algeria": 2,
    "Ohio": 2, "Illinois": 2, "Louisiana": 2, "Iowa": 2, "North Dakota": 2,
    "Missouri": 2, "Michigan": 2, "Pennsylvania": 2, "Alabama": 2, "Florida": 2,
    "Georgia": 2, "Nevada": 2, "Arizona": 2, "Wyoming": 2, "Alaska": 2,
    "South Carolina": 2, "Tennessee": 2, "Kentucky": 2, "Minnesota": 2, "Wisconsin": 2,
    "Oklahoma": 2, "Kansas": 2, "Indiana": 2, "Mississippi": 2, "West Virginia": 2,
    "Quebec": 2, "DR Congo": 2, "Washington State": 2,
    "Twin Falls": 1, "Fort Smith": 1, "Slidell": 1, "Loudon County": 1,
    "Anclote Power Plant": 0, "Longview": 1, "Nippon Dynawave": 0, "Rome NY": 1,
    "Bille": 1, "Rubaya": 1, "Yaroslavl": 1, "El Paso": 1, "Port Harcourt": 1,
    "Yakutsk": 1, "Yakutia": 2, "Krasnoyarsk": 1, "Krasnoyarsky Krai": 2,
    "Evenkia": 2, "Turukhansk": 1, "Taymyr": 2, "Lesosibirsk": 1, "Yeniseysk": 1,
    "Norilsk": 1, "Irkutsk": 1, "Khabarovsk": 1, "Vladivostok": 1,
    "Petropavlovsk-Kamchatsky": 1, "Kamchatka": 2, "Yuzhno-Sakhalinsk": 1,
    "Sakhalin": 2, "Magadan": 1, "Chita": 1, "Transbaikalia": 2, "Ulan-Ude": 1,
    "Buryatia": 2, "Blagoveshchensk": 1, "Novosibirsk": 1, "Tomsk": 1, "Omsk": 1,
    "Barnaul": 1, "Kemerovo": 1, "Novokuznetsk": 1, "Kuzbass": 2, "Salekhard": 1,
    "Yamal": 2, "Surgut": 1, "Nizhnevartovsk": 1, "Yekaterinburg": 1,
    "Chelyabinsk": 1, "Magnitogorsk": 1, "Perm": 1, "Ufa": 1, "Kazan": 1,
    "Murmansk": 1, "Arkhangelsk": 1, "Vorkuta": 1, "Rostov-on-Don": 1,
    "Krasnodar": 1, "Sochi": 1, "Volgograd": 1, "Primorye": 2, "Far East": 2,
    "Komi": 2, "Siberia": 2, "Tuapse": 1, "Bashkortostan": 2, "Mirny": 1,
    "Neryungri": 1, "Khakassia": 2, "Tsimlyansk": 1,
}


def place_grain(name: str) -> int:
    if name in PLACE_GRAIN:
        return PLACE_GRAIN[name]
    if name in CITIES:
        return 1
    return 3


NEPAL_FINE = {n for n, g in PLACE_GRAIN.items() if n != "Nepal"}

# Plant, border and village coords from OSM Nominatim and Global Energy Monitor.
ACCURATE = {
    "Trishuli 3A": (28.02559, 85.18605),
    "Trishuli River": (28.02559, 85.18605),
    "Trishuli": (27.92241, 85.14880),
    "Rasuwagadhi": (28.23920, 85.35750),
    "Nepal-Tibet border": (28.27777, 85.37778),
    "Lende Khola": (28.27600, 85.37500),
    "Timure": (28.25285, 85.36667),
    "Dhunche": (28.11279, 85.29606),
    "Rasuwa": (28.11279, 85.29606),
    "Bidur": (27.89526, 85.14645),
    "Nuwakot": (27.89526, 85.14645),
    "Barhabise": (27.78781, 85.89958),
    "Chilime": (28.18362, 85.30224),
    "Betrawati": (27.97311, 85.18595),
    "Mailung": (28.07177, 85.20700),
    "Syabrubesi": (28.17250, 85.34780),
    "Twin Falls": (42.55585, -114.47007),
    "Fort Smith": (35.38803, -94.42650),
    "Slidell": (30.27519, -89.78117),
    "Loudon County": (35.74900, -84.32029),
    "Anclote Power Plant": (28.18429, -82.78745),
    "Longview": (46.13770, -122.93446),
    "Nippon Dynawave": (46.13022, -122.98074),
    "Rome NY": (43.21022, -75.45840),
    "El Paso": (31.76010, -106.48705),
    "Bille": (4.57642, 6.88786),
    "Rubaya": (-1.54724, 28.87433),
    "Yaroslavl": (57.62657, 39.89369),
}


def with_coords(place: dict) -> dict:
    pair = ACCURATE.get(place["name"])
    if pair:
        return {**place, "lat": pair[0], "lng": pair[1]}
    return place
PLACE_ALIASES = [
    (re.compile(r"rasuwagadhi|rasuwa[\s\-]?gadhi", re.I), "Rasuwagadhi"),
    (re.compile(r"trishuli[\s\-]?3a", re.I), "Trishuli 3A"),
    (re.compile(r"trishuli hydropower|hydropower.{0,40}trishuli|trishuli.{0,40}hydropower", re.I), "Trishuli 3A"),
    (re.compile(r"syabrubesi(?:\s+bazar)?", re.I), "Syabrubesi"),
    (re.compile(r"barhabise|barabishe", re.I), "Barhabise"),
    (re.compile(r"bhote[\s\-]?koshi|bhote[\s\-]?kosi", re.I), "Bhotekoshi"),
    (re.compile(r"trishuli river|river trishuli|trisuli river", re.I), "Trishuli River"),
    (re.compile(r"lende khola|lende river", re.I), "Lende Khola"),
    (re.compile(
        r"border of nepal and tibet|nepal.{0,20}tibet border|tibet.{0,20}nepal border|"
        r"china.{0,16}nepal border|nepal.{0,16}china border|"
        r"nepal[\s\-–]+tibet(?:\s+border)?|nepal[\s\-–]+china(?:\s+border)?|"
        r"near the border.{0,40}(?:nepal|tibet|china)",
        re.I,
    ), "Nepal-Tibet border"),
    (re.compile(r"(?:\b9\b|nine|10|ten)\s+days.{0,80}tunnel|tunnel.{0,80}(?:\b9\b|nine|10|ten)\s+days", re.I), "Trishuli 3A"),
    (re.compile(r"sound transit", re.I), "Seattle"),
    (re.compile(r"garden grove", re.I), "Los Angeles"),
    (re.compile(r"east palestine", re.I), "Ohio"),
    (re.compile(r"yellowstone river", re.I), "Montana"),
    (re.compile(r"fraser river", re.I), "British Columbia"),
    (re.compile(r"\bdr congo\b|\bdrc\b|democratic republic of (?:the )?congo", re.I), "DR Congo"),
    (re.compile(
        r"\brubaya\b|(?:coltan|mine collapse).{0,40}(?:congo|drc)|(?:congo|drc).{0,40}mine collapse",
        re.I,
    ), "Rubaya"),
    (re.compile(r"\bbille\b|\brivers community\b", re.I), "Bille"),
    (re.compile(r"twin falls", re.I), "Twin Falls"),
    (re.compile(r"fort smith", re.I), "Fort Smith"),
    (re.compile(r"slidell", re.I), "Slidell"),
    (re.compile(r"loudon county|\bloudon\b", re.I), "Loudon County"),
    (re.compile(r"anclote|duke energy.{0,30}anclote", re.I), "Anclote Power Plant"),
    (re.compile(r"nippon(?:\s+dynawave)?", re.I), "Nippon Dynawave"),
    (re.compile(r"\blongview\b", re.I), "Longview"),
    (re.compile(r"el[\s\-]?paso", re.I), "El Paso"),
    (re.compile(r"\brome\b.{0,40}wktv|wktv.{0,40}\brome\b|rome,?\s*n\.?y", re.I), "Rome NY"),
    (re.compile(r"yaroslavl", re.I), "Yaroslavl"),
    (re.compile(r"якутск", re.I), "Yakutsk"),
    (re.compile(r"якути[яииюе]|саха \(якутия\)|республик\w{0,4} саха", re.I), "Yakutia"),
    (re.compile(r"красноярск\w{0,10}\s+кра", re.I), "Krasnoyarsky Krai"),
    (re.compile(r"красноярск", re.I), "Krasnoyarsk"),
    (re.compile(r"эвенки", re.I), "Evenkia"),
    (re.compile(r"туруханск", re.I), "Turukhansk"),
    (re.compile(r"таймыр", re.I), "Taymyr"),
    (re.compile(r"лесосибирск", re.I), "Lesosibirsk"),
    (re.compile(r"енисейск", re.I), "Yeniseysk"),
    (re.compile(r"норильск", re.I), "Norilsk"),
    (re.compile(r"иркутск", re.I), "Irkutsk"),
    (re.compile(r"хабаровск", re.I), "Khabarovsk"),
    (re.compile(r"владивосток", re.I), "Vladivostok"),
    (re.compile(r"петропавловск-камчатск|петропавловск камчатск", re.I), "Petropavlovsk-Kamchatsky"),
    (re.compile(r"камчатк", re.I), "Kamchatka"),
    (re.compile(r"южно-сахалинск", re.I), "Yuzhno-Sakhalinsk"),
    (re.compile(r"сахалин", re.I), "Sakhalin"),
    (re.compile(r"магадан", re.I), "Magadan"),
    (re.compile(r"\bчит[аеуы]\b", re.I), "Chita"),
    (re.compile(r"забайкал", re.I), "Transbaikalia"),
    (re.compile(r"улан-уд[эе]", re.I), "Ulan-Ude"),
    (re.compile(r"бурят", re.I), "Buryatia"),
    (re.compile(r"благовещенск", re.I), "Blagoveshchensk"),
    (re.compile(r"новосибирск", re.I), "Novosibirsk"),
    (re.compile(r"\bтомск", re.I), "Tomsk"),
    (re.compile(r"\bомск", re.I), "Omsk"),
    (re.compile(r"барнаул", re.I), "Barnaul"),
    (re.compile(r"кемеров", re.I), "Kemerovo"),
    (re.compile(r"новокузнецк", re.I), "Novokuznetsk"),
    (re.compile(r"кузбасс", re.I), "Kuzbass"),
    (re.compile(r"салехард", re.I), "Salekhard"),
    (re.compile(r"ямал", re.I), "Yamal"),
    (re.compile(r"сургут", re.I), "Surgut"),
    (re.compile(r"нижневартовск", re.I), "Nizhnevartovsk"),
    (re.compile(r"екатеринбург", re.I), "Yekaterinburg"),
    (re.compile(r"челябинск", re.I), "Chelyabinsk"),
    (re.compile(r"магнитогорск", re.I), "Magnitogorsk"),
    (re.compile(r"\bперм[иьие]", re.I), "Perm"),
    (re.compile(r"\bуф[аеуы]", re.I), "Ufa"),
    (re.compile(r"казан", re.I), "Kazan"),
    (re.compile(r"мурманск", re.I), "Murmansk"),
    (re.compile(r"архангельск", re.I), "Arkhangelsk"),
    (re.compile(r"воркут", re.I), "Vorkuta"),
    (re.compile(r"ростов-на-дону|ростовской област", re.I), "Rostov-on-Don"),
    (re.compile(r"краснодар", re.I), "Krasnodar"),
    (re.compile(r"\bсочи\b", re.I), "Sochi"),
    (re.compile(r"волгоград", re.I), "Volgograd"),
    (re.compile(r"приморск\w{0,6}\s+кра[яй]|приморье", re.I), "Primorye"),
    (re.compile(r"дальн\w{0,6}\s+восток", re.I), "Far East"),
    (re.compile(r"\bсибир", re.I), "Siberia"),
    (re.compile(r"\bкоми\b", re.I), "Komi"),
    (re.compile(r"ярославл", re.I), "Yaroslavl"),
    (re.compile(r"туапсе", re.I), "Tuapse"),
    (re.compile(r"башкири|башкортостан", re.I), "Bashkortostan"),
    (re.compile(r"мирнинск|\bмирны", re.I), "Mirny"),
    (re.compile(r"нерюнгр", re.I), "Neryungri"),
    (re.compile(r"хакас", re.I), "Khakassia"),
    (re.compile(r"цимлянск", re.I), "Tsimlyansk"),
    (re.compile(r"янао|ямало-ненецк", re.I), "Yamal"),
    (re.compile(r"поморь", re.I), "Arkhangelsk"),
    (re.compile(r"хангаласск", re.I), "Yakutsk"),
]


def fetch(url: str) -> bytes | None:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml"})
    try:
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            return r.read()
    except Exception as e:
        print(f"  fail {url}: {e}")
        return None


def parse_date(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        ts = email.utils.parsedate_to_datetime(raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.replace("Z", "+0000"), fmt).astimezone(timezone.utc)
        except Exception:
            continue
    return None


def local_name(tag: str) -> str:
    return tag.split("}")[-1]


def item_text(el: ET.Element, names: list[str]) -> str:
    for child in list(el):
        if local_name(child.tag) in names and (child.text or "").strip():
            return child.text.strip()
    return ""


def parse_feed(blob: bytes, source: str) -> list[dict]:
    try:
        root = ET.fromstring(blob)
    except ET.ParseError as e:
        print(f"  xml {source}: {e}")
        return []
    items = [el for el in root.iter() if local_name(el.tag) in ("item", "entry")]
    out = []
    for el in items:
        title = re.sub(r"\s+", " ", item_text(el, ["title"])).strip()
        if not title:
            continue
        link = item_text(el, ["link"])
        if not link:
            for child in el:
                if local_name(child.tag) == "link" and child.get("href"):
                    link = child.get("href")
                    break
        summary = re.sub(r"<[^>]+>", " ", item_text(el, ["description", "summary", "encoded"]))
        summary = re.sub(r"\s+", " ", summary).strip()[:2000]
        pub = parse_date(item_text(el, ["pubDate", "date", "published", "updated"]))
        out.append({"title": title, "link": link, "summary": summary, "source": source, "when": pub})
        if len(out) >= 100:
            break
    return out


def article_text(url: str) -> str:
    if not url or not url.startswith("http"):
        return ""
    if "news.google.com" in url:
        return ""
    blob = fetch(url)
    if not blob:
        return ""
    raw = blob.decode("utf-8", "ignore")[:80000]
    raw = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    return re.sub(r"\s+", " ", raw).strip()[:8000]


def load_dotenv() -> str:
    source = ""
    grok = Path.home() / "grok_api"
    if grok.is_file():
        raw = grok.read_text(encoding="utf-8").strip()
        if raw.startswith("xai-"):
            os.environ["XAI_API_KEY"] = raw.splitlines()[0].strip()
            source = "grok_api"
        elif "=" in raw:
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("XAI_API_KEY="):
                    os.environ["XAI_API_KEY"] = line.split("=", 1)[1].strip().strip("'").strip('"')
                    source = "grok_api"
    path = Path(__file__).resolve().parent / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip("'").strip('"'))
        if not source and (os.environ.get("XAI_API_KEY") or "").strip():
            source = ".env"
    return source or "none"


def parse_place_list(raw: str) -> list[str]:
    try:
        obj = json.loads(raw)
    except Exception:
        return []
    places = obj.get("places") if isinstance(obj, dict) else obj
    if not isinstance(places, list):
        return []
    out = []
    for item in places:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict) and item.get("name"):
            out.append(str(item["name"]).strip())
    return out[:5]


XAI_DISABLED = False
XAI_BATCH = int(os.environ.get("XAI_BATCH", "8") or "8")
XAI_DAILY_MAX = int(
    os.environ.get("XAI_DAILY_MAX") or os.environ.get("XAI_MAX") or "24" or "24"
)


def xai_daily_path() -> Path:
    return Path(__file__).resolve().parent / "logs" / "xai-daily.json"


def xai_daily_used() -> int:
    path = xai_daily_path()
    if not path.is_file():
        return 0
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    if obj.get("date") != TODAY.isoformat():
        return 0
    try:
        return int(obj.get("headlines") or 0)
    except Exception:
        return 0


def xai_daily_add(n: int) -> int:
    used = xai_daily_used() + n
    path = xai_daily_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "date": TODAY.isoformat(),
            "headlines": used,
            "cap": XAI_DAILY_MAX,
            "model": XAI_MODEL,
        })
        + "\n",
        encoding="utf-8",
    )
    return used


def xai_key() -> str:
    return (os.environ.get("XAI_API_KEY") or "").strip()


def xai_post(messages: list[dict], timeout: int = 40) -> dict | None:
    global XAI_DISABLED
    key = xai_key()
    if not key or XAI_DISABLED:
        return None
    payload = {
        "model": XAI_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }
    req = urllib.request.Request(
        XAI_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + key,
            "User-Agent": UA,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            err = json.loads(raw)
            code = str(err.get("code") or "")
            msg = str(err.get("error") or "")[:180]
        except Exception:
            code, msg = "", raw[:180]
        print(f"  xai fail: {e.code} {code} {msg}", flush=True)
        blob = f"{code} {msg}".lower()
        if e.code in (401, 403) and any(
            s in blob for s in ("credit", "spending", "permission-denied", "blocked")
        ):
            XAI_DISABLED = True
            print("  xai off: credits or spending limit", flush=True)
        return None
    except Exception as e:
        print(f"  xai fail: {e}", flush=True)
        return None


def xai_content(data: dict | None) -> str:
    if not data:
        return ""
    return (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""


def xai_extract(title: str, summary: str, body: str) -> list[str]:
    data = xai_post(
        [
            {
                "role": "system",
                "content": (
                    "Extract WHERE a natural or industrial disaster is happening. "
                    "Ignore newsrooms, bylines, and cities named only because officials spoke there. "
                    "Prefer the most specific named site: plant, mine, village, district, island. "
                    "JSON only: {\"places\": [\"...\"]} with 1-5 names. Empty list if none."
                ),
            },
            {"role": "user", "content": f"{title}\n{summary}\n{(body or '')[:1500]}".strip()},
        ]
    )
    return parse_place_list(xai_content(data))


def parse_batch_items(raw: str, ids: list[int]) -> dict[int, list[str]]:
    try:
        obj = json.loads(raw)
    except Exception:
        return {}
    found: dict[int, list[str]] = {}

    def take(i: object, places_obj: object) -> None:
        try:
            n = int(i)
        except Exception:
            return
        wrapped = {"places": places_obj} if not isinstance(places_obj, dict) else places_obj
        found[n] = parse_place_list(json.dumps(wrapped))

    if isinstance(obj, dict) and isinstance(obj.get("items"), list):
        for item in obj["items"]:
            if isinstance(item, dict):
                take(item.get("id", item.get("i")), item.get("places") or [])
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                take(item.get("id", item.get("i")), item.get("places") or [])
    elif isinstance(obj, dict) and "places" in obj and len(ids) == 1:
        take(ids[0], obj.get("places") or [])
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k in {"items", "places"}:
                continue
            take(k, v)
    return {i: found[i] for i in ids if i in found}


def xai_extract_batch(rows: list[dict]) -> dict[int, list[str]]:
    if not rows:
        return {}
    chunks = []
    for i, row in enumerate(rows, start=1):
        a = row["article"]
        body = (row.get("extra") or "")[:700]
        chunks.append(
            f"{i}. [{a.get('hazard')}] {a['title']}\n{a.get('summary') or ''}\n{body}".strip()
        )
    data = xai_post(
        [
            {
                "role": "system",
                "content": (
                    "Each numbered story is a disaster. For each id, extract WHERE it is happening. "
                    "Ignore newsrooms and bylines. Prefer plant, mine, village, district, island. "
                    'JSON only: {"items":[{"id":1,"places":["..."]}, ...]} with 1-5 names per story. '
                    "Use the same ids. Empty places if none."
                ),
            },
            {"role": "user", "content": "\n\n".join(chunks)},
        ],
        timeout=90,
    )
    ids = list(range(1, len(rows) + 1))
    parsed = parse_batch_items(xai_content(data), ids)
    return {i - 1: parsed[i] for i in parsed}


def ollama_on() -> bool:
    if not OLLAMA_HOST or OLLAMA_HOST in {"off", "0", "none"}:
        return False
    try:
        req = urllib.request.Request(OLLAMA_HOST + "/api/tags", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def ollama_extract(title: str, summary: str, body: str) -> list[str]:
    text = f"{title}\n{summary}\n{(body or '')[:1500]}".strip()
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "format": "json",
        "think": False,
        "options": {"temperature": 0, "num_predict": 160},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Extract WHERE a natural or industrial disaster is happening. "
                    "Ignore newsrooms, bylines, and cities named only because officials spoke there. "
                    "Prefer the most specific named site: plant, mine, village, district, island. "
                    "JSON only: {\"places\": [\"...\"]} with 1-5 names. Empty list if none."
                ),
            },
            {"role": "user", "content": text},
        ],
    }
    req = urllib.request.Request(
        OLLAMA_HOST + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": UA},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as e:
        print(f"  ollama fail: {e}")
        return []
    raw = (data.get("message") or {}).get("content") or ""
    return parse_place_list(raw)


def llm_extract(title: str, summary: str, body: str) -> list[str]:
    if xai_key():
        return xai_extract(title, summary, body)
    if ollama_on():
        return ollama_extract(title, summary, body)
    return []


def pin_from_names(names: list[str], article: dict, existing: list[dict]) -> list[dict]:
    tech = article.get("hazard") == "technogenic"
    found = locate_hits(" " + " ; ".join(names) + " " + article["title"], allow_capitals=tech)
    found = [
        p for p in found
        if not is_coarse(p, hazard=article.get("hazard"))
        or (tech and p["name"] in CAPITALS and p["name"] not in AMBIGUOUS_CAPITALS)
    ]
    if not found:
        return existing
    merged = {p["name"]: p for p in found + existing}
    return list(merged.values())


def locate_hits(text: str, allow_capitals: bool = False) -> list[dict]:
    blob = " " + (text or "") + " "
    blob = re.sub(r"\bin Kathmandu\b", " ", blob, flags=re.I)
    lower = blob.lower()
    for rx, canon in PLACE_ALIASES:
        if rx.search(lower):
            lower += " " + canon.lower() + " "
    found = {}
    for name in PLACE_NAMES:
        if re.search(r"[^a-z0-9]" + re.escape(name) + r"[^a-z0-9]", lower):
            canon, lat, lng, region = PLACE_BY_NAME[name]
            if canon in CAPITALS and not allow_capitals:
                continue
            grain = place_grain(canon)
            if grain >= 3:
                continue
            pos = lower.find(name)
            prev = found.get(canon)
            if prev is None or (grain, pos, -len(name)) < prev[0]:
                found[canon] = ((grain, pos, -len(name)), with_coords(
                    {"name": canon, "lat": lat, "lng": lng, "region": region}
                ))
    places = [p for _, p in found.values()]
    names = [p["name"] for p in places]
    places = [p for p in places if not any(q != p["name"] and q.startswith(p["name"]) for q in names)]
    places.sort(key=lambda p: (place_grain(p["name"]), p["name"]))
    return places


def locate(text: str, allow_capitals: bool = False) -> dict | None:
    hits = locate_hits(text, allow_capitals=allow_capitals)
    return hits[0] if hits else None


def locate_article_places(title: str, summary: str, body: str, allow_capitals: bool = False) -> list[dict]:
    title_hits = locate_hits(title, allow_capitals=allow_capitals)
    core = [p for p in title_hits if p["name"] not in NEWSROOM]
    if core:
        title_hits = core
    lead = f"{summary} {body}"[:1800]
    lead_hits = locate_hits(lead, allow_capitals=allow_capitals)
    body_hits = locate_hits(f"{title} {summary} {body}", allow_capitals=allow_capitals)
    if title_hits:
        extra = [
            p for p in lead_hits + body_hits
            if place_grain(p["name"]) <= 2 and p["name"] not in NEWSROOM
        ]
        merged = {p["name"]: p for p in title_hits + extra}
        return list(merged.values())[:5]
    merged = {
        p["name"]: p for p in lead_hits + body_hits if p["name"] not in NEWSROOM
    }
    ranked = sorted(merged.values(), key=lambda p: place_grain(p["name"]))
    return ranked[:5]


CAPITALS = {
    "Kathmandu", "Washington", "London", "Paris", "Berlin", "Moscow", "New Delhi",
    "Delhi", "Beijing", "Jakarta", "Manila", "Tokyo", "Islamabad", "Cairo", "Riyadh",
    "Ankara", "Rome", "Madrid", "Brussels",
}
# US towns share these names; do not pin industrial accidents on the European city.
AMBIGUOUS_CAPITALS = {"Rome", "Paris", "Moscow", "London"}
# Where the reporter sits, not where the event is — keep if the title names them.
NEWSROOM = {"New York", "London", "Geneva", "Washington", "Paris", "Brussels"}


def place_record(name: str) -> dict:
    canon, lat, lng, region = PLACE_BY_NAME[name.lower()]
    return with_coords({"name": canon, "lat": lat, "lng": lng, "region": region})


def is_coarse(place: dict | None, hazard: str | None = None) -> bool:
    if not place:
        return True
    name = place["name"]
    if name in CAPITALS:
        return True
    grain = place_grain(name)
    if grain >= 3:
        return True
    # Technogenic events belong on the plant or town, not a state centroid.
    if hazard == "technogenic" and grain >= 2:
        return True
    return False


def refine_place(article: dict, place: dict | None) -> dict | None:
    """Do not leave events on a capital or country centroid."""
    text = f"{article['title']} {article['summary']}".lower()
    name = place["name"] if place else ""
    nepalish = "nepal" in text or name in NEPAL_FINE or name in {"Nepal", "Kathmandu"}
    if nepalish:
        if re.search(r"\btunnel|\btrishuli", text):
            if re.search(r"trishuli river", text):
                return place_record("Trishuli River")
            return place_record("Trishuli 3A")
        if re.search(r"tibet|rasuwagadhi|border", text):
            return place_record("Nepal-Tibet border")
        if re.search(r"\brasuwa\b", text):
            return place_record("Rasuwa")
        if re.search(r"\bnuwakot\b", text):
            return place_record("Nuwakot")
        if re.search(r"\bdhading\b", text):
            return place_record("Dhading")
        if article.get("hazard") == "flood" and is_coarse(place):
            return place_record("Rasuwa")
        if is_coarse(place):
            return None
        return place
    if is_coarse(place) and article.get("hazard") == "wildfire" and re.search(r"indonesia|sumatra|kalimantan", text):
        return place_record("Sumatra")
    if is_coarse(place) and article.get("hazard") == "cyclone" and re.search(r"philippines|luzon|monsoon", text):
        return place_record("Luzon")
    if is_coarse(place):
        if article.get("hazard") == "technogenic" and name in CAPITALS:
            return place
        return None
    return place


def tokens(title: str) -> set[str]:
    words = re.findall(r"[A-Za-z][A-Za-z'-]{3,}", title)
    return {w.lower() for w in words if w.lower() not in STOP}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cluster(articles: list[dict]) -> list[list[int]]:
    n = len(articles)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    toks = [tokens(a["title"]) for a in articles]
    for i in range(n):
        for j in range(i + 1, n):
            same_place = (
                articles[i]["place"]
                and articles[j]["place"]
                and articles[i]["place"]["name"] == articles[j]["place"]["name"]
            )
            if not same_place:
                continue
            same_hazard = articles[i].get("hazard") and articles[i]["hazard"] == articles[j].get("hazard")
            jac = jaccard(toks[i], toks[j])
            overlap = toks[i] & toks[j]
            if same_hazard or jac >= 0.28 or (len(overlap) >= 3 and jac >= 0.22):
                union(i, j)
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return list(groups.values())


def mention_snippet(text: str, names: list[str]) -> str:
    if not text or not names:
        return ""
    hits = []
    for sent in re.split(r"(?<=[.!?])\s+", text):
        s = sent.strip()
        if len(s) < 40 or len(s) > 300:
            continue
        if any(re.search(r"\b" + re.escape(n) + r"\b", s, re.I) for n in names):
            if s not in hits:
                hits.append(s)
        if len(hits) == 2:
            break
    return " ".join(hits)


def cluster_title(members: list[dict]) -> str:
    members = sorted(members, key=lambda a: len(a["title"]))
    return members[0]["title"]


def cluster_located(located: list[dict]) -> list[dict]:
    by_place: dict[tuple[str, str], list] = defaultdict(list)
    for a in located:
        for p in a["places"]:
            by_place[(p["name"], a["hazard"])].append((a, p))
    clusters = []
    for (_name, _hazard), pairs in by_place.items():
        members = [a for a, _ in pairs]
        place = pairs[0][1]
        seen = set()
        uniq = []
        for m in members:
            key = re.sub(r"\W+", "", m["title"].lower())[:80]
            if key in seen:
                continue
            seen.add(key)
            uniq.append({
                "title": html.escape(m["title"]),
                "link": m["link"],
                "source": html.escape(m["source"]),
                "today": m["today"],
                "places": [html.escape(p["name"]) for p in m["places"]],
                "snippet": html.escape(m.get("snippet") or ""),
            })
        hazards = Counter(m["hazard"] for m in members)
        clusters.append({
            "title": cluster_title(members),
            "place": place["name"],
            "lat": place["lat"],
            "lng": place["lng"],
            "region": place["region"],
            "hazard": hazards.most_common(1)[0][0],
            "articles": uniq,
        })
    clusters.sort(key=lambda c: (-len(c["articles"]), c["place"]))
    return clusters


def materialize(rows: list[dict], key: str) -> tuple[list[dict], int]:
    located = []
    skipped = 0
    for row in rows:
        a = row["article"]
        places = row.get(key) or []
        if not places:
            skipped += 1
            continue
        names = [p["name"] for p in places]
        extra = row.get("extra") or ""
        located.append({
            "title": a["title"],
            "link": a["link"],
            "source": a["source"],
            "today": a["today"],
            "hazard": a["hazard"],
            "places": places,
            "place": places[0],
            "snippet": mention_snippet(
                a["title"] + ". " + a["summary"] + " " + extra, names
            ),
        })
    return cluster_located(located), skipped


def pin_diff_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    diffs = []
    missing = []
    for row in rows:
        a = row["article"]
        gaz = [p["name"] for p in row.get("gazetteer") or []]
        grok = [p["name"] for p in row.get("places") or []]
        rec = {
            "title": a["title"],
            "link": a["link"],
            "hazard": a.get("hazard") or "",
            "gazetteer": gaz,
            "grok": grok,
        }
        if not gaz and not grok:
            missing.append(rec)
        elif gaz != grok:
            diffs.append(rec)
    return diffs, missing


def write_compare(
    root: Path,
    *,
    api_note: str,
    gaz_clusters: list[dict],
    gaz_skip: int,
    grok_clusters: list[dict],
    grok_skip: int,
    n_rows: int,
    diffs: list[dict],
    missing: list[dict],
    llm_n: int,
) -> None:
    def names(xs: list[str]) -> str:
        return ", ".join(html.escape(x) for x in xs) or "—"

    def nloc(skip: int) -> int:
        return n_rows - skip

    rescued = sum(1 for d in diffs if not d["gazetteer"] and d["grok"])
    rows_html = []
    for d in diffs:
        kind = "new pin" if not d["gazetteer"] and d["grok"] else "changed"
        rows_html.append(
            "<tr><td>"
            + html.escape(d["hazard"])
            + '</td><td><a href="'
            + html.escape(d["link"], quote=True)
            + '">'
            + html.escape(d["title"][:110])
            + "</a></td><td>"
            + names(d["gazetteer"])
            + "</td><td>"
            + names(d["grok"])
            + "</td><td>"
            + kind
            + "</td></tr>"
        )
    miss_html = "".join(
        "<li><a href='"
        + html.escape(m["link"], quote=True)
        + "'>"
        + html.escape(m["title"][:110])
        + "</a></li>"
        for m in missing[:40]
    )
    table = (
        "<p>No pin changes this run. Grok and the gazetteer agree, or Grok did not run.</p>"
        if not rows_html
        else "<table><thead><tr><th>Hazard</th><th>Headline</th><th>Gazetteer</th><th>Grok</th><th></th></tr></thead><tbody>"
        + "".join(rows_html)
        + "</tbody></table>"
    )
    page = COMPARE_HTML
    page = page.replace("__TODAY__", html.escape(TODAY.isoformat()))
    page = page.replace("__WINDOW__", str(WINDOW_DAYS))
    page = page.replace("__API__", html.escape(api_note))
    page = page.replace("__GAZ_LOC__", str(nloc(gaz_skip)))
    page = page.replace("__GAZ_SKIP__", str(gaz_skip))
    page = page.replace("__GAZ_CL__", str(len(gaz_clusters)))
    page = page.replace("__GROK_LOC__", str(nloc(grok_skip)))
    page = page.replace("__GROK_SKIP__", str(grok_skip))
    page = page.replace("__GROK_CL__", str(len(grok_clusters)))
    page = page.replace("__DIFFS__", str(len(diffs)))
    page = page.replace("__RESCUED__", str(rescued))
    page = page.replace("__MISSING__", str(len(missing)))
    page = page.replace("__LLM_N__", str(llm_n))
    page = page.replace("__TABLE__", table)
    page = page.replace("__MISS_LIST__", miss_html or "<li>None</li>")
    path = root / "compare.html"
    tmp = root / "compare.html.tmp"
    tmp.write_text(page, encoding="utf-8")
    tmp.replace(path)
    print(f"wrote {path}")


COMPARE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Gazetteer vs Grok — disaster atlas</title>
  <style>
    :root {
      --ink: #efe6d6; --muted: #9b917f; --paper: #101218;
      --panel: #161922; --line: #323848; --accent: #d4b07a;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--paper); color: var(--ink);
      font-family: Georgia, "Iowan Old Style", Palatino, serif; padding: 28px 22px 60px; }
    a { color: var(--accent); }
    h1 { font-size: 1.4rem; font-weight: 600; margin: 0 0 6px; }
    .sub { color: var(--muted); font-size: .9rem; line-height: 1.5; max-width: 42em; }
    .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 22px 0;
      max-width: 720px; }
    .card { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 14px 16px; }
    .card h2 { margin: 0 0 8px; font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); font-weight: 600; }
    .card p { margin: 0; font-size: 1.05rem; }
    .num { color: var(--accent); font-variant-numeric: tabular-nums; }
    table { width: 100%; border-collapse: collapse; font-size: .88rem; margin-top: 8px; }
    th, td { text-align: left; vertical-align: top; padding: 8px 10px 8px 0; border-bottom: 1px solid var(--line); }
    th { color: var(--muted); font-size: .7rem; letter-spacing: .08em; text-transform: uppercase; }
    ul { padding-left: 1.1em; color: var(--muted); font-size: .88rem; max-width: 52em; }
    li { margin: 4px 0; }
  </style>
</head>
<body>
  <p class="sub"><a href="./">← map</a></p>
  <h1>Gazetteer vs Grok</h1>
  <p class="sub">Same __WINDOW__-day headlines, two pin methods. Gazetteer is the word list. Grok is a proof of concept with a daily headline cap, misses first. __TODAY__. API: __API__. Asked Grok on __LLM_N__ headlines.</p>
  <div class="stats">
    <div class="card">
      <h2>Without API</h2>
      <p><span class="num">__GAZ_LOC__</span> located · __GAZ_SKIP__ no place · __GAZ_CL__ clusters</p>
    </div>
    <div class="card">
      <h2>With API</h2>
      <p><span class="num">__GROK_LOC__</span> located · __GROK_SKIP__ no place · __GROK_CL__ clusters</p>
    </div>
    <div class="card">
      <h2>Pins Grok changed</h2>
      <p><span class="num">__DIFFS__</span> headlines · __RESCUED__ had no gazetteer pin</p>
    </div>
    <div class="card">
      <h2>Still unpinned</h2>
      <p><span class="num">__MISSING__</span> — not in the gazetteer, so Grok names cannot drop a pin</p>
    </div>
  </div>
  <h2>Where they disagree</h2>
  __TABLE__
  <h2>Still no pin</h2>
  <ul>__MISS_LIST__</ul>
</body>
</html>
"""


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Disaster atlas — wildfires, floods, quakes</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    :root {
      --ink: #efe6d6; --muted: #9b917f; --paper: #101218;
      --panel: rgba(22, 25, 34, .92); --line: #323848; --accent: #d4b07a;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; margin: 0; background: var(--paper); color: var(--ink);
      font-family: Georgia, "Iowan Old Style", Palatino, serif; }
    #map { position: absolute; inset: 0; }
    .leaflet-container { background: #101218; font-family: inherit; }
    .leaflet-tile-pane { filter: invert(1) hue-rotate(180deg) brightness(.92) contrast(.88) saturate(.3); }
    .panel {
      position: absolute; z-index: 500; top: 14px; left: 14px;
      width: min(400px, calc(100vw - 28px));
      background: var(--panel); backdrop-filter: blur(12px);
      border: 1px solid var(--line); border-radius: 16px;
      padding: 18px 18px 14px; box-shadow: 0 18px 50px rgba(0,0,0,.5);
      max-height: calc(100vh - 28px); overflow: auto;
    }
    h1 { font-size: 1.28rem; font-weight: 600; margin: 0 2px 2px; }
    .sub { color: var(--muted); font-size: .8rem; line-height: 1.5; margin: 0 0 14px; }
    .legend { display: flex; flex-wrap: wrap; gap: 8px 14px; margin-top: 12px; font-size: .75rem; color: var(--muted); }
    .swatch { width: 9px; height: 9px; border-radius: 50%; display: inline-block; margin-right: 5px; vertical-align: middle; }
    label { display: block; font-size: .68rem; letter-spacing: .12em; text-transform: uppercase;
      color: var(--muted); margin: 11px 0 5px; }
    select, button {
      width: 100%; background: #12141c; color: var(--ink); border: 1px solid var(--line);
      border-radius: 8px; padding: 8px 10px; font: inherit; font-size: .86rem;
    }
    .row { display: flex; gap: 8px; margin-top: 10px; }
    .row button { cursor: pointer; }
    .row button:hover, .row button.on { border-color: var(--accent); color: var(--accent); }
    .panel a { color: var(--accent); }
    .count { color: var(--accent); font-variant-numeric: tabular-nums; }
    .leaflet-popup-content-wrapper {
      background: #1a1d27; color: var(--ink); border-radius: 12px;
      border: 1px solid var(--line); max-width: 340px;
    }
    .leaflet-popup-tip { background: #1a1d27; }
    .leaflet-popup-content { margin: 13px 15px; font-size: .9rem; line-height: 1.45; }
    .popup-kicker { font-size: .68rem; letter-spacing: .04em; color: var(--accent); margin: 0 0 5px; }
    .popup-title { font-size: 1.02rem; margin: 0 0 8px; }
    .popup-item { margin: 0 0 10px; }
    .popup-item a { color: var(--ink); }
    .popup-places { color: var(--accent); font-size: .75rem; margin: 3px 0 0; }
    .popup-snip { color: #d8d0c2; font-size: .78rem; margin: 4px 0 0; line-height: 1.4; }
    .popup-src { color: var(--muted); font-size: .75rem; }
    .leaflet-control-attribution { background: rgba(16,18,24,.75) !important; color: #6e675c !important; }
    .leaflet-control-attribution a { color: #8e8576 !important; }
    @media (max-width: 640px) {
      .panel { top: auto; bottom: 10px; left: 10px; right: 10px; width: auto; max-height: 46vh; }
    }
  </style>
</head>
<body>
  <div id="map"></div>
  <aside class="panel">
    <h1>Disaster atlas</h1>
    <p class="sub"><span class="count" id="count"></span> things happening now: fires, floods, quakes, storms, industrial accidents. Last __WINDOW__ days. Politics and explainers stay off. <a href="compare.html">gazetteer vs Grok</a></p>
    <label>Pins</label>
    <div class="row">
      <button type="button" id="modeGrok" class="on">Grok</button>
      <button type="button" id="modeGaz">Gazetteer</button>
    </div>
    <label for="hazard">Hazard</label>
    <select id="hazard"></select>
    <label for="region">Region</label>
    <select id="region"></select>
    <label for="place">Place</label>
    <select id="place"></select>
    <div class="row">
      <button type="button" id="world">World</button>
      <button type="button" id="asia">Asia</button>
      <button type="button" id="americas">Americas</button>
    </div>
    <div class="legend" id="legend"></div>
  </aside>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const TODAY = __TODAY__;
    const GROK = __GROK__;
    const GAZ = __GAZ__;
    let CLUSTERS = GROK;
    const HAZARD_COLOR = __HAZARD_COLOR__;
    const map = L.map("map", { zoomControl: true, minZoom: 2 }).setView([20, 15], 2);
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", {
      attribution: "Tiles &copy; Esri · wires + ReliefWeb",
      maxZoom: 19
    }).addTo(map);
    const layer = L.layerGroup().addTo(map);
    const hazardSel = document.getElementById("hazard");
    const regionSel = document.getElementById("region");
    const placeSel = document.getElementById("place");
    function fillFilters() {
      const hazards = ["all"].concat([...new Set(CLUSTERS.map(c => c.hazard))].sort());
      const keepH = hazardSel.value || "all";
      hazardSel.innerHTML = hazards.map(h => '<option value="' + h + '">' + (h === "all" ? "All hazards" : h) + "</option>").join("");
      if (hazards.indexOf(keepH) !== -1) hazardSel.value = keepH;
      const regions = ["all"].concat([...new Set(CLUSTERS.map(c => c.region))].sort());
      const keepR = regionSel.value || "all";
      regionSel.innerHTML = regions.map(r => '<option value="' + r + '">' + (r === "all" ? "All regions" : r) + "</option>").join("");
      if (regions.indexOf(keepR) !== -1) regionSel.value = keepR;
      document.getElementById("legend").innerHTML = Object.keys(HAZARD_COLOR).filter(h => CLUSTERS.some(c => c.hazard === h)).map(h =>
        '<span><i class="swatch" style="background:' + HAZARD_COLOR[h] + '"></i>' + h + "</span>"
      ).join("");
    }
    function filtered() {
      const hazard = hazardSel.value, region = regionSel.value, place = placeSel.value;
      return CLUSTERS.filter(c => {
        if (hazard !== "all" && c.hazard !== hazard) return false;
        if (region !== "all" && c.region !== region) return false;
        if (place !== "all" && c.place !== place) return false;
        return true;
      });
    }
    function placesFor() {
      const names = [...new Set(filtered().map(c => c.place))].sort();
      const keep = placeSel.value;
      placeSel.innerHTML = '<option value="all">All places</option>' + names.map(n => '<option>' + n + "</option>").join("");
      if (names.indexOf(keep) !== -1) placeSel.value = keep;
    }
    function render() {
      layer.clearLayers();
      const shown = filtered();
      document.getElementById("count").textContent = shown.length;
      shown.forEach(c => {
        const r = Math.min(16, 7 + c.articles.length * 1.6);
        const m = L.circleMarker([c.lat, c.lng], {
          radius: r, color: "#0b0c10", weight: 1,
          fillColor: HAZARD_COLOR[c.hazard] || "#d4b483", fillOpacity: 0.92
        });
        const items = c.articles.map(a => {
          const where = (a.places && a.places.length) ? '<p class="popup-places">' + a.places.join(" · ") + "</p>" : "";
          const snip = a.snippet ? '<p class="popup-snip">' + a.snippet + "</p>" : "";
          return '<p class="popup-item"><a href="' + a.link + '" target="_blank" rel="noopener">' + a.title +
            "</a>" + where + snip + '<span class="popup-src">' + a.source + (a.today ? " · today" : "") + "</span></p>";
        }).join("");
        m.bindPopup(
          '<p class="popup-kicker">' + c.hazard + " · " + c.place + " · " + c.articles.length + " headline" + (c.articles.length > 1 ? "s" : "") + "</p>" +
          '<p class="popup-title">' + c.title + "</p>" + items
        );
        m.addTo(layer);
      });
    }
    hazardSel.addEventListener("change", function () { placesFor(); render(); });
    regionSel.addEventListener("change", function () { placesFor(); render(); });
    placeSel.addEventListener("change", render);
    document.getElementById("world").onclick = function () { map.setView([20, 15], 2); };
    document.getElementById("asia").onclick = function () { map.setView([28, 90], 4); };
    document.getElementById("americas").onclick = function () { map.setView([15, -80], 3); };
    function setMode(which) {
      CLUSTERS = which === "gaz" ? GAZ : GROK;
      document.getElementById("modeGrok").classList.toggle("on", which !== "gaz");
      document.getElementById("modeGaz").classList.toggle("on", which === "gaz");
      fillFilters();
      placesFor();
      render();
    }
    document.getElementById("modeGrok").onclick = function () { setMode("grok"); };
    document.getElementById("modeGaz").onclick = function () { setMode("gaz"); };
    fillFilters();
    placesFor();
    render();
    if (CLUSTERS.length) {
      map.fitBounds(CLUSTERS.map(c => [c.lat, c.lng]), { padding: [40, 40], maxZoom: 4 });
    }
  </script>
</body>
</html>
"""


def main() -> None:
    global XAI_MODEL
    src = load_dotenv()
    XAI_MODEL = os.environ.get("XAI_MODEL", XAI_MODEL)
    print(f"today UTC {TODAY.isoformat()}", flush=True)
    print(
        f"xai key loaded={bool(xai_key())} source={src} model={XAI_MODEL}",
        flush=True,
    )
    articles = []
    for name, url in FEEDS:
        print(f"fetch {name}")
        blob = fetch(url)
        if not blob:
            continue
        got = parse_feed(blob, name)
        print(f"  {len(got)} items")
        articles.extend(got)

    cutoff = TODAY - timedelta(days=WINDOW_DAYS)
    disasters = []
    for a in articles:
        if a["when"] and a["when"].date() < cutoff:
            continue
        text = a["title"] + " " + a["summary"]
        hazard = classify_hazard(text)
        if not hazard or not is_happening(a["title"], a["summary"]):
            continue
        a["hazard"] = hazard
        a["today"] = bool(a["when"] and a["when"].date() == TODAY)
        disasters.append(a)
    print(f"disasters in {WINDOW_DAYS}d: {len(disasters)} (today {sum(1 for a in disasters if a['today'])})")

    rows = []
    for a in disasters:
        extra = article_text(a["link"])
        tech = a.get("hazard") == "technogenic"
        places = locate_article_places(a["title"], a["summary"], extra, allow_capitals=tech)
        if not places:
            one = refine_place(a, locate(a["title"] + " " + a["summary"], allow_capitals=tech))
            places = [one] if one else []
        places = [
            p for p in places
            if not is_coarse(p, hazard=a.get("hazard"))
            or (tech and p["name"] in CAPITALS and p["name"] not in AMBIGUOUS_CAPITALS)
        ]
        rows.append({
            "article": a,
            "extra": extra,
            "places": places,
            "gazetteer": list(places),
        })

    llm_n = 0
    want = sorted(
        rows,
        key=lambda row: (
            0 if not row["places"] else min(place_grain(p["name"]) for p in row["places"]),
            row["article"]["title"],
        ),
    )
    already = xai_daily_used() if xai_key() else 0
    if xai_key() and XAI_DAILY_MAX > 0:
        room = max(0, XAI_DAILY_MAX - already)
        want = want[:room]
    if not xai_key() and not ollama_on():
        print("llm off (no XAI_API_KEY)", flush=True)
    elif xai_key() and XAI_DAILY_MAX > 0 and already >= XAI_DAILY_MAX:
        print(
            f"llm skip: daily cap {XAI_DAILY_MAX} already used {already} UTC {TODAY.isoformat()}",
            flush=True,
        )
        want = []
    elif not want:
        print("llm skip: no disasters", flush=True)
    else:
        who = f"xai {XAI_MODEL}" if xai_key() else f"ollama {OLLAMA_MODEL}"
        print(
            f"llm extract places via {who} on {len(want)}/{len(rows)} "
            f"(daily cap {XAI_DAILY_MAX}, already {already}, misses first)",
            flush=True,
        )
        if xai_key():
            n = max(1, XAI_BATCH)
            for start in range(0, len(want), n):
                if XAI_DISABLED:
                    print(f"  xai skipped remaining {len(want) - llm_n}", flush=True)
                    break
                chunk = want[start:start + n]
                got = xai_extract_batch(chunk)
                if XAI_DISABLED:
                    print(f"  xai skipped remaining {len(want) - llm_n}", flush=True)
                    break
                llm_n += len(chunk)
                xai_daily_add(len(chunk))
                for i, row in enumerate(chunk):
                    names = got.get(i) or []
                    if not names:
                        continue
                    a = row["article"]
                    before = [p["name"] for p in row["places"]]
                    row["places"] = pin_from_names(names, a, row["places"])
                    after = [p["name"] for p in row["places"]]
                    if after != before:
                        print(f"  llm {a['title'][:42]:42} {names} -> {after}")
        else:
            for row in want:
                a = row["article"]
                llm_n += 1
                names = llm_extract(a["title"], a["summary"], row["extra"])
                if not names:
                    continue
                before = [p["name"] for p in row["places"]]
                row["places"] = pin_from_names(names, a, row["places"])
                after = [p["name"] for p in row["places"]]
                if after != before:
                    print(f"  llm {a['title'][:42]:42} {names} -> {after}")
        print(f"llm place-extract {llm_n}")

    grok_clusters, grok_skip = materialize(rows, "places")
    gaz_clusters, gaz_skip = materialize(rows, "gazetteer")
    for row in rows:
        a = row["article"]
        places = row["places"]
        if not places:
            print(f"  no place | {a['title'][:70]}")
            continue
        print(f"  {', '.join(p['name'] for p in places):28} | {a['title'][:52]}")
    print(f"gazetteer located {len(rows) - gaz_skip}, no place {gaz_skip}, clusters {len(gaz_clusters)}")
    print(f"grok located {len(rows) - grok_skip}, no place {grok_skip}, clusters {len(grok_clusters)}")
    print("hazards", Counter((row["article"].get("hazard") or "") for row in rows if row["places"]))

    diffs, missing = pin_diff_rows(rows)
    if XAI_DISABLED:
        api_note = f"{XAI_MODEL} credits/spending limit"
    elif not xai_key() and not ollama_on():
        api_note = "off (no key)"
    elif llm_n:
        api_note = f"{XAI_MODEL if xai_key() else OLLAMA_MODEL}, {llm_n} headlines"
    else:
        api_note = "not called"

    out = HTML.replace("__TODAY__", json.dumps(TODAY.isoformat()))
    out = out.replace("__WINDOW__", str(WINDOW_DAYS))
    out = out.replace("__GROK__", json.dumps(grok_clusters, ensure_ascii=False))
    out = out.replace("__GAZ__", json.dumps(gaz_clusters, ensure_ascii=False))
    out = out.replace("__HAZARD_COLOR__", json.dumps(HAZARD_COLOR))
    root = Path(os.environ.get("OUT_DIR") or Path(__file__).resolve().parent)
    root.mkdir(parents=True, exist_ok=True)
    for name in ("news-map.html", "index.html"):
        path = root / name
        tmp = root / (name + ".tmp")
        tmp.write_text(out, encoding="utf-8")
        tmp.replace(path)
        print(f"wrote {path}")
    write_compare(
        root,
        api_note=api_note,
        gaz_clusters=gaz_clusters,
        gaz_skip=gaz_skip,
        grok_clusters=grok_clusters,
        grok_skip=grok_skip,
        n_rows=len(rows),
        diffs=diffs,
        missing=missing,
        llm_n=llm_n,
    )


if __name__ == "__main__":
    main()
