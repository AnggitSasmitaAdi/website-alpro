import json
import os
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "atlas-local-development-key")

API_FIELDS = "name,cca2,flags,capital,region,subregion,population,area,currencies,languages,timezones,continents,landlocked,borders,maps,coatOfArms,independent,unMember,startOfWeek,car"
COUNTRY_ALIASES = {
    "amerika": "united states",
    "amerika serikat": "united states",
    "belanda": "netherlands",
    "cina": "china",
    "inggris": "united kingdom",
    "jepang": "japan",
    "jerman": "germany",
    "korea selatan": "south korea",
    "korea utara": "north korea",
    "mesir": "egypt",
    "prancis": "france",
    "rusia": "russia",
    "selandia baru": "new zealand",
    "spanyol": "spain",
    "tiongkok": "china",
    "turki": "turkey",
}


@lru_cache(maxsize=128)
def fetch_country_matches(query):
    url = f"https://restcountries.com/v3.1/name/{quote(query, safe='')}?fields={API_FIELDS}"
    request_object = Request(url, headers={"User-Agent": "AtlasWorldExplorer/1.0"})
    with urlopen(request_object, timeout=8) as response:
        return json.load(response)


def number_id(value):
    return f"{int(value):,}".replace(",", ".")


def prepare_country(country):
    names = country.get("name") or {}
    languages = list((country.get("languages") or {}).values())
    currencies = [
        {"name": item.get("name", ""), "symbol": item.get("symbol", "")}
        for item in (country.get("currencies") or {}).values()
    ]
    borders = country.get("borders") or []
    timezones = country.get("timezones") or []
    facts = []

    if len(languages) > 1:
        facts.append(f"Kehidupan sehari-hari di sini menggunakan {len(languages)} bahasa resmi.")
    if len(timezones) > 1:
        facts.append(f"Wilayah negara ini membentang melintasi {len(timezones)} zona waktu.")
    if borders:
        facts.append(f"Negara ini berbagi perbatasan darat dengan {len(borders)} negara tetangga.")
    elif country.get("landlocked"):
        facts.append("Negara ini tidak memiliki garis pantai dan dikelilingi daratan.")
    else:
        facts.append("Tidak ada perbatasan darat; perjalanan ke negara tetangga melewati laut atau udara.")
    if country.get("startOfWeek"):
        facts.append(f"Pekan resmi dimulai pada hari {country['startOfWeek']}.")
    if country.get("car", {}).get("side"):
        side = "kiri" if country["car"]["side"] == "left" else "kanan"
        facts.append(f"Kendaraan di negara ini berjalan di sisi {side} jalan.")

    return {
        "name": names.get("common", "Nama tidak tersedia"),
        "official_name": names.get("official", ""),
        "code": country.get("cca2", "").lower(),
        "flag": (country.get("flags") or {}).get("svg") or (country.get("flags") or {}).get("png", ""),
        "flag_alt": (country.get("flags") or {}).get("alt", "Bendera negara"),
        "coat_of_arms": (country.get("coatOfArms") or {}).get("svg") or (country.get("coatOfArms") or {}).get("png", ""),
        "capital": ", ".join(country.get("capital") or []) or "Tidak tercatat",
        "region": country.get("region", "Tidak diketahui"),
        "subregion": country.get("subregion", ""),
        "continents": country.get("continents") or [],
        "population": country.get("population", 0),
        "area": country.get("area", 0),
        "languages": languages,
        "currencies": currencies,
        "timezones": timezones,
        "neighbors": len(borders),
        "landlocked": country.get("landlocked", False),
        "independent": country.get("independent", False),
        "un_member": country.get("unMember", False),
        "week_start": country.get("startOfWeek", ""),
        "driving_side": (country.get("car") or {}).get("side", ""),
        "map_url": (country.get("maps") or {}).get("googleMaps", ""),
        "facts": facts[:4],
    }


@app.get("/")
def index():
    return render_template("explore.html")


@app.get("/api/country")
def country_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify(error="Ketik nama negara yang ingin kamu jelajahi."), 400
    if len(query) > 80:
        return jsonify(error="Nama negara terlalu panjang. Coba gunakan nama yang lebih singkat."), 400

    normalized_query = COUNTRY_ALIASES.get(query.casefold(), query)
    try:
        matches = fetch_country_matches(normalized_query)
    except HTTPError as error:
        if error.code == 404:
            return jsonify(error="Negara belum ditemukan. Coba nama lain, misalnya Japan atau Jepang."), 404
        return jsonify(error="Layanan data negara sedang sulit dijangkau. Coba lagi sebentar."), 502
    except (URLError, TimeoutError, json.JSONDecodeError):
        return jsonify(error="Tidak bisa menghubungi layanan data negara. Periksa koneksi lalu coba lagi."), 502

    if not isinstance(matches, list) or not matches:
        return jsonify(error="Negara belum ditemukan. Periksa ejaan nama negara."), 404

    normalized = normalized_query.casefold()
    matches.sort(
        key=lambda item: (
            (item.get("name") or {}).get("common", "").casefold() != normalized,
            (item.get("name") or {}).get("official", "").casefold() != normalized,
            (item.get("name") or {}).get("common", "").casefold(),
        )
    )
    return jsonify(country=prepare_country(matches[0]))


if __name__ == "__main__":
    app.run(debug=False)
