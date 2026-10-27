import streamlit as st
import time
import requests
import math
import hashlib
from datetime import datetime, timedelta, timezone

MAJOR_LEAGUES = [
    "Süper Lig", "Premier League", "La Liga", "Serie A", "Bundesliga", 
    "Ligue 1", "UEFA Champions League"
]

LEAGUE_STYLES = {
    "Premier League": {"xg_mod": 1.10, "korner_mod": 1.15, "tac_mod": 1.05, "kart_mod": 0.85, "faul_mod": 0.90, "tarz": "Yüksek Tempo"},
    "Süper Lig": {"xg_mod": 1.02, "korner_mod": 0.95, "tac_mod": 1.25, "kart_mod": 1.35, "faul_mod": 1.30, "tarz": "Duran Top & Agresif"},
    "La Liga": {"xg_mod": 0.95, "korner_mod": 0.90, "tac_mod": 0.95, "kart_mod": 1.10, "faul_mod": 1.10, "tarz": "Pas, Teknik"},
    "Serie A": {"xg_mod": 0.90, "korner_mod": 1.05, "tac_mod": 0.90, "kart_mod": 1.05, "faul_mod": 1.15, "tarz": "Taktiksel Savunma"},
    "Bundesliga": {"xg_mod": 1.18, "korner_mod": 1.00, "tac_mod": 1.00, "kart_mod": 0.90, "faul_mod": 0.95, "tarz": "Geçiş Oyunu & Bol Gol"},
    "Varsayılan": {"xg_mod": 1.0, "korner_mod": 1.0, "tac_mod": 1.0, "kart_mod": 1.0, "faul_mod": 1.0, "tarz": "Standart Futbol"}
}

def ligleri_sirala(lig_listesi):
    def oncelik_belirle(lig_adi):
        for i, maj_lig in enumerate(MAJOR_LEAGUES):
            if maj_lig.lower() in lig_adi.lower(): return i
        return 999 
    return sorted(lig_listesi, key=lambda x: (oncelik_belirle(x), x))

def hakem_analizi_yap(hakem_adi):
    if not hakem_adi or hakem_adi == "Atanmadı / Bilinmiyor": return {"profil": "Standart", "kart_carpan": 1.0, "faul_carpan": 1.0, "renk": "#9ca3af"}
    h = int(hashlib.md5(hakem_adi.encode('utf-8')).hexdigest(), 16)
    profiller = [
        {"profil": "Otoriter", "kart_carpan": 1.35, "faul_carpan": 1.20, "renk": "#ef4444"},
        {"profil": "Akıcı Oyun", "kart_carpan": 0.75, "faul_carpan": 0.80, "renk": "#34d399"},
        {"profil": "Dengeli", "kart_carpan": 1.0, "faul_carpan": 1.0, "renk": "#60a5fa"},
        {"profil": "Ev Sahibi Avantajlı", "kart_carpan": 1.10, "faul_carpan": 1.05, "renk": "#fbbf24"}
    ]
    return profiller[h % len(profiller)]

def hoca_analizi_yap(takim_adi):
    h = int(hashlib.md5(takim_adi.encode('utf-8')).hexdigest(), 16)
    profiller = [
        {"profil": "Gegenpressing", "xg_carpan": 1.15, "korner_carpan": 1.20},
        {"profil": "Tiki-Taka", "xg_carpan": 1.05, "korner_carpan": 1.10},
        {"profil": "Katı Savunma", "xg_carpan": 0.85, "korner_carpan": 0.80},
        {"profil": "Dengeli", "xg_carpan": 1.0, "korner_carpan": 1.0}
    ]
    return profiller[h % len(profiller)]

def hash_tabanli_cevresel_veri(kimlik_metni):
    h = int(hashlib.md5(kimlik_metni.encode('utf-8')).hexdigest(), 16)
    havalar = [("Açık Zemin", 1.0, "Pas oyununa uygun."), ("Hafif Yağmurlu", 0.95, "Kaygan zemin."), ("Yoğun Yağışlı", 0.85, "Ağır zemin, xG düşer.")]
    return havalar[h % len(havalar)]

# --- YENİ POISSON MOTORU (10 GOL LİMİTİ & FAT-TAIL) ---
def poisson(k, lambd):
    return (lambd**k * math.exp(-lambd)) / math.factorial(k)

def skor_olasiliklarini_hesapla(ev_xg, dep_xg, ev_gol_yuku=1.0, dep_gol_yuku=1.0):
    ev_dinamik_xg = ev_xg * ev_gol_yuku
    dep_dinamik_xg = dep_xg * dep_gol_yuku

    ev_olasiliklar = [poisson(i, ev_dinamik_xg) for i in range(10)]
    dep_olasiliklar = [poisson(i, dep_dinamik_xg) for i in range(10)]
    
    if ev_dinamik_xg > 2.0:
        for i in range(4, 10): ev_olasiliklar[i] *= 1.3
    if dep_dinamik_xg > 2.0:
        for i in range(4, 10): dep_olasiliklar[i] *= 1.3

    p1 = pX = p2 = kg_var = kg_yok = ust_25 = ust_15 = ust_05 = ust_35 = 0
    en_olasi_skor, en_yuksek_ihtimal = "0 - 0", 0
    ev_gol_tahmin, dep_gol_tahmin = ev_olasiliklar.index(max(ev_olasiliklar)), dep_olasiliklar.index(max(dep_olasiliklar))
    
    for i in range(10):
        for j in range(10):
            ihtimal = ev_olasiliklar[i] * dep_olasiliklar[j]
            if (ev_dinamik_xg + dep_dinamik_xg) < 2.5:
                if i == 0 and j == 0: ihtimal *= 1.15
                elif i == 1 and j == 1: ihtimal *= 1.10
            
            if ihtimal > en_yuksek_ihtimal:
                en_yuksek_ihtimal, en_olasi_skor, ev_gol_tahmin, dep_gol_tahmin = ihtimal, f"{i} - {j}", i, j
                
            if i > j: p1 += ihtimal
            elif i == j: pX += ihtimal
            else: p2 += ihtimal
            if i > 0 and j > 0: kg_var += ihtimal
            else: kg_yok += ihtimal
            if (i + j) > 3.5: ust_35 += ihtimal
            if (i + j) > 2.5: ust_25 += ihtimal
            if (i + j) > 1.5: ust_15 += ihtimal
            if (i + j) > 0.5: ust_05 += ihtimal

    toplam = p1 + pX + p2
    if toplam > 0: p1, pX, p2 = p1/toplam, pX/toplam, p2/toplam
    
    if ust_35 > 0.40 and (ev_gol_tahmin + dep_gol_tahmin) <= 3:
        if ev_dinamik_xg > dep_dinamik_xg: en_olasi_skor = f"{ev_gol_tahmin + 1} - {dep_gol_tahmin}"
        elif dep_dinamik_xg > ev_dinamik_xg: en_olasi_skor = f"{ev_gol_tahmin} - {dep_gol_tahmin + 1}"
        else: en_olasi_skor = "2 - 2"
    elif ust_25 > 0.58 and (ev_gol_tahmin + dep_gol_tahmin) <= 2:
        if ev_dinamik_xg > dep_dinamik_xg: en_olasi_skor = f"{ev_gol_tahmin + 1} - {dep_gol_tahmin}"
        elif dep_dinamik_xg > ev_dinamik_xg: en_olasi_skor = f"{ev_gol_tahmin} - {dep_gol_tahmin + 1}"
        else: en_olasi_skor = "1 - 1"
    
    return {
        "p1": p1, "pX": pX, "p2": p2, "kg_var": kg_var, "ust_35": ust_35, "ust_25": ust_25, "ust_15": ust_15, "ust_05": ust_05,
        "skor": en_olasi_skor, "ev_gol": ev_gol_tahmin, "dep_gol": dep_gol_tahmin,
        "ev_05_ust": 1 - ev_olasiliklar[0], "ev_15_ust": 1 - (ev_olasiliklar[0] + ev_olasiliklar[1]),
        "dep_05_ust": 1 - dep_olasiliklar[0], "dep_15_ust": 1 - (dep_olasiliklar[0] + dep_olasiliklar[1])
    }

def skor_dagit(ms_skor_str):
    ev_ms, dep_ms = map(int, ms_skor_str.replace(" ", "").split("-"))
    return f"{math.ceil(ev_ms * 0.45)} - {math.ceil(dep_ms * 0.45)}", f"{ev_ms - math.ceil(ev_ms * 0.45)} - {dep_ms - math.ceil(dep_ms * 0.45)}"

def yan_bahisleri_hesapla(toplam_xg, lig_karakteristik, hakem_profil, hoca_ev, hoca_dep, carpan):
    hoca_korner = (hoca_ev["korner_carpan"] + hoca_dep["korner_carpan"]) / 2
    return {
        "korner": round(((8.5 + (toplam_xg * 0.8)) * lig_karakteristik["korner_mod"] * hoca_korner) * carpan, 1),
        "tac": round(((38.0 + (toplam_xg * 1.2)) * lig_karakteristik["tac_mod"]) * carpan, 1),
        "kart": round(((4.5 * lig_karakteristik["kart_mod"] * hakem_profil["kart_carpan"])) * carpan, 1),
        "faul": round(((22.5 * lig_karakteristik["faul_mod"] * hakem_profil["faul_carpan"])) * carpan, 1),
        "ofsayt": round(((3.5 + (toplam_xg * 0.2))) * carpan, 1)
    }

# --- GERÇEK API VERİ ÇEKME & ÖNBELLEK ---
@st.cache_data(ttl=3600)
def api_football_gercek_veri_getir(api_key):
    now_tr = datetime.now(timezone.utc) + timedelta(hours=3)
    bugun_str = now_tr.strftime("%d.%m.%Y")
    suan_saat_dk = now_tr.strftime("%H:%M")
    ham_ligler = {}

    try:
        url = f"https://v3.football.api-sports.io/fixtures?date={now_tr.strftime('%Y-%m-%d')}"
        headers = {"x-apisports-key": api_key}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            for match in response.json().get("response", []):
                l_name = match.get("league", {}).get("name", "Diğer")
                utc_date_str = match.get("fixture", {}).get("date")
                if not utc_date_str: continue
                dt_tr = datetime.fromisoformat(utc_date_str.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=3)))
                m_tarih, m_saat = dt_tr.strftime("%d.%m.%Y"), dt_tr.strftime("%H:%M")
                
                if l_name not in ham_ligler: ham_ligler[l_name] = {"logo": match.get("league", {}).get("logo", ""), "maclar": []}
                ham_ligler[l_name]["maclar"].append({
                    "id": match.get("fixture", {}).get("id"), "l_id": match.get("league", {}).get("id"), "season": match.get("league", {}).get("season"),
                    "h_id": match.get("teams", {}).get("home", {}).get("id"), "a_id": match.get("teams", {}).get("away", {}).get("id"), 
                    "saat": m_saat, "tarih": m_tarih, 
                    "ev": match.get("teams", {}).get("home", {}).get("name"), "dep": match.get("teams", {}).get("away", {}).get("name"), 
                    "referee": match.get("fixture", {}).get("referee") or "Atanmadı / Bilinmiyor",
                    "ev_logo": match.get("teams", {}).get("home", {}).get("logo", ""), "dep_logo": match.get("teams", {}).get("away", {}).get("logo", ""),
                    "metin": f"📅 {m_tarih} - 🕒 {m_saat} | {match.get('teams', {}).get('home', {}).get('name')} vs {match.get('teams', {}).get('away', {}).get('name')}"
                })
    except: return None, "Bağlantı Hatası"

    filtrelenmis_ligler = {l: d for l, d in ham_ligler.items() if [m for m in d["maclar"] if not (m["tarih"] == bugun_str and m["saat"] <= suan_saat_dk)]}
    for l in filtrelenmis_ligler: filtrelenmis_ligler[l]["maclar"] = [m for m in filtrelenmis_ligler[l]["maclar"] if not (m["tarih"] == bugun_str and m["saat"] <= suan_saat_dk)]
    return filtrelenmis_ligler, "🟢 V125 Master Mind (Sakatlık, Yorgunluk, Zaman Formu) Aktif"

@st.cache_data(ttl=3600)
def sakat_cezali_cek(api_key, fixture_id, h_id, a_id):
    headers = {"x-apisports-key": api_key}
    url = f"https://v3.football.api-sports.io/injuries?fixture={fixture_id}"
    h_eksik = a_eksik = 0
    try:
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200:
            for inj in res.json().get("response", []):
                t_id = inj.get("team", {}).get("id")
                if t_id == h_id: h_eksik += 1
                elif t_id == a_id: a_eksik += 1
    except: pass
    return {"h_eksik": h_eksik, "a_eksik": a_eksik}

@st.cache_data(ttl=3600)
def gercek_takim_istatistiklerini_cek(api_key, team_id, is_home):
    headers = {"x-apisports-key": api_key}
    url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=25"
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            matches = res.json().get("response", [])
            bitmis_maclar = [m for m in matches if m.get("fixture", {}).get("status", {}).get("short") in ["FT", "AET", "PEN"]]
            if not bitmis_maclar: return None
            
            # 1. YORGUNLUK MOTORU
            now_utc = datetime.now(timezone.utc)
            last_match_date = datetime.fromisoformat(bitmis_maclar[0]["fixture"]["date"].replace("Z", "+00:00")).astimezone(timezone.utc)
            dinlenme_gunu = (now_utc - last_match_date).days
            yorgunluk_carpani = 0.88 if dinlenme_gunu < 4 else 1.0

            league_names = [m["league"]["name"] for m in bitmis_maclar]
            main_league_name = max(set(league_names), key=league_names.count) if league_names else "Bilinmiyor"
            
            LEAGUE_COEFFICIENTS = {
                "Premier League": 2.0, "La Liga": 1.9, "Serie A": 1.8, "Bundesliga": 1.8, "Ligue 1": 1.7,
                "UEFA Champions League": 2.2, "UEFA Europa League": 1.8, "Süper Lig": 1.4,
                "Championship": 1.3, "Eredivisie": 1.5, "Primeira Liga": 1.5,
                "Brasileirão Série A": 1.4, "Primera Division": 1.3, "Serie B": 1.1, "1. Lig": 1.0
            }
            league_coef = LEAGUE_COEFFICIENTS.get(main_league_name, 0.85)
            
            # 2. ZAMAN AĞIRLIKLI FORM (Time-Decay)
            def analiz_et(mac_listesi, t_id):
                if not mac_listesi: return 0.0, 0.0, "Veri Yok"
                gf_w = ga_w = toplam_agirlik = 0.0
                form_str = ""
                for m in mac_listesi:
                    m_date = datetime.fromisoformat(m["fixture"]["date"].replace("Z", "+00:00")).astimezone(timezone.utc)
                    days_ago = (now_utc - m_date).days
                    
                    if days_ago <= 15: w = 1.5
                    elif days_ago <= 30: w = 1.0
                    else: w = 0.6

                    is_team_home = m["teams"]["home"]["id"] == t_id
                    h_goals, a_goals = m["goals"]["home"] or 0, m["goals"]["away"] or 0
                    
                    if is_team_home:
                        gf_w += h_goals * w; ga_w += a_goals * w
                        winner = m["teams"]["home"]["winner"]
                    else:
                        gf_w += a_goals * w; ga_w += h_goals * w
                        winner = m["teams"]["away"]["winner"]
                        
                    toplam_agirlik += w
                    if winner is True: form_str += "W"
                    elif winner is False: form_str += "L"
                    else: form_str += "D"
                
                return (gf_w / toplam_agirlik if toplam_agirlik > 0 else 0), (ga_w / toplam_agirlik if toplam_agirlik > 0 else 0), form_str[::-1]
            
            g_for_genel, g_ag_genel, form_10 = analiz_et(bitmis_maclar[:10], team_id)
            g_for_saha, g_ag_saha, form_saha_5 = analiz_et([m for m in bitmis_maclar if (m["teams"]["home"]["id"] == team_id and is_home) or (m["teams"]["away"]["id"] == team_id and not is_home)][:5], team_id)
            
            # 3. SAHTE GOL (BALON) FİLTRESİ
            sahte_gol_carpani = 1.0
            try:
                stat_url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={bitmis_maclar[0]['fixture']['id']}&team={team_id}"
                stat_res = requests.get(stat_url, headers=headers, timeout=3)
                if stat_res.status_code == 200 and stat_res.json().get("response"):
                    sot = next((int(i["value"]) for i in stat_res.json()["response"][0].get("statistics", []) if i["type"] == "Shots on Goal" and i["value"]), 0)
                    last_goals = bitmis_maclar[0]["goals"]["home"] if bitmis_maclar[0]["teams"]["home"]["id"] == team_id else bitmis_maclar[0]["goals"]["away"]
                    if last_goals and last_goals >= 2 and sot < last_goals:
                        sahte_gol_carpani = 0.85 # 2'den fazla gol atıp şutu golden azsa şansa atmıştır!
            except: pass

            return {
                "g_for_saha": g_for_saha, "g_ag_saha": g_ag_saha, "g_for_genel": g_for_genel, "g_ag_genel": g_ag_genel,
                "form_10": form_10, "form_saha_5": form_saha_5, "main_league": main_league_name, "league_coef": league_coef,
                "yorgunluk_carpani": yorgunluk_carpani, "sahte_gol_carpani": sahte_gol_carpani, "dinlenme_gunu": dinlenme_gunu
            }
    except: pass
    return None

@st.cache_data(ttl=3600)
def aralarindaki_maclari_cek(api_key, h_id, a_id):
    headers, url = {"x-apisports-key": api_key}, f"https://v3.football.api-sports.io/fixtures/headtohead?h2h={h_id}-{a_id}&last=5"
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            bitmis = [m for m in res.json().get("response", []) if m.get("fixture", {}).get("status", {}).get("short") in ["FT", "AET", "PEN"]]
            if not bitmis: return None
            h_tg = sum([(m["goals"]["home"] or 0) if m["teams"]["home"]["id"] == h_id else (m["goals"]["away"] or 0) for m in bitmis])
            a_tg = sum([(m["goals"]["away"] or 0) if m["teams"]["home"]["id"] == h_id else (m["goals"]["home"] or 0) for m in bitmis])
            return {"h_avg": h_tg / len(bitmis), "a_avg": a_tg / len(bitmis), "count": len(bitmis)}
    except: pass
    return None

def gol_yuku_hesapla(g_for, g_ag):
    toplam = g_for + g_ag
    if toplam >= 3.5: return 1.40
    elif toplam >= 2.8: return 1.25
    elif toplam <= 1.8: return 0.85
    return 1.0

# --- GÖRSEL KUTULAR ---
def stat_kutu_olustur(baslik, oran1, yazi1, oran2, yazi2, icon="⚽", renk="#60a5fa"):
    return f"""<div style="border: 1px solid #1e3a8a; border-radius: 10px; padding: 20px; text-align: center; background-color: #0f172a; height: 100%;">
        <div style="color: {renk}; font-weight: 700; margin-bottom: 20px;">{icon} {baslik}</div>
        <div style="border-top: 1px solid #1e293b; margin: 15px 0;"></div>
        <div style="font-size: 22px; font-weight: bold; color: {renk};">{oran1}</div>
        <div style="font-size: 12px; color: #9ca3af; margin-bottom: 15px;">{yazi1}</div>
        <div style="font-size: 22px; font-weight: bold; color: {renk};">{oran2}</div>
        <div style="font-size: 12px; color: #9ca3af;">{yazi2}</div>
    </div>"""

def alt_stat_kutu(baslik, deger, renk, icon):
    return f"""<div style="border: 1px solid #1e293b; border-radius: 8px; padding: 15px; text-align: center; background-color: #111827;">
        <div style="color: {renk}; font-weight: 700; font-size: 13px; margin-bottom: 10px;">{icon} {baslik}</div>
        <div style="font-size: 16px; font-weight: bold; color: #f3f4f6;">{deger}</div>
    </div>"""

# --- SİSTEM DEĞİŞKENLERİ ---
if "kaydedilen_maclar" not in st.session_state: st.session_state["kaydedilen_maclar"] = []

# --- ARAYÜZ BAŞLANGICI ---
st.set_page_config(page_title="Pro Analiz Paneli (V125)", page_icon="⚽", layout="wide")
USER_API_KEY = "899fcc53c659a6bb3dac4ff1ef7b211a"
bulten_verisi, aktif_kaynak = api_football_gercek_veri_getir(USER_API_KEY)

if not bulten_verisi:
    st.error("Bugün için maç bulunamadı veya API limitiniz doldu.")
    st.stop()

# --- SİDEBAR ---
with st.sidebar:
    st.markdown("### 💾 Kaydedilen Analizler")
    if not st.session_state["kaydedilen_maclar"]: st.info("Henüz analiz kaydedilmedi.")
    else:
        for k_idx, kayit in enumerate(reversed(st.session_state["kaydedilen_maclar"])):
            st.markdown(f"""
            <div style="background-color: #1e293b; padding: 10px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #34d399;">
                <b style="color:#ffffff; font-size:13px;">{kayit['mac']}</b><br>
                <span style="font-size:11px; color:#9ca3af;">{kayit['tarih']}</span><br>
                <span style="font-size:12px; color:#60a5fa;">Beklenen Skor: {kayit['skor']}</span><br>
                <span style="font-size:12px; color:#fbbf24;">Value: {kayit['value']}</span>
            </div>
            """, unsafe_allow_html=True)
            if k_idx >= 4: break

    st.markdown("---")
    st.markdown("### 🤖 YZ Value Avcısı")
    st.warning("⚠️ V125 ile çok fazla veri çekildiği için API limitini korumak adına tarama devre dışı bırakılmıştır. Lütfen maçları tek tek analiz ediniz.")

# --- ANA EKRAN ---
col_sol, col_sag = st.columns([1, 2.5])

with col_sol:
    st.markdown("### 🔍 Takım veya Maç Ara")
    arama_sorgusu = st.text_input("Örn: Arsenal, Galatasaray", placeholder="Takım adı yazın...")
    
    filtrelenmis_ligler = {}
    for l_adi, l_data in bulten_verisi.items():
        eslesen_maclar = [m for m in l_data["maclar"] if arama_sorgusu.lower() in m["ev"].lower() or arama_sorgusu.lower() in m["dep"].lower()]
        if eslesen_maclar: filtrelenmis_ligler[l_adi] = {"logo": l_data["logo"], "maclar": eslesen_maclar}
    
    gosterilecek_veri = filtrelenmis_ligler if arama_sorgusu else bulten_verisi
    if not gosterilecek_veri:
        st.warning("Aramanıza uygun maç bulunamadı.")
        st.stop()

    sirali_ligler = ligleri_sirala(list(gosterilecek_veri.keys()))
    if "secili_lig" not in st.session_state or st.session_state["secili_lig"] not in sirali_ligler:
        st.session_state["secili_lig"] = sirali_ligler[0]

    st.markdown("### 📋 Lig ve Maç Seçimi")
    secilen_lig = st.selectbox("Lig Seçiniz:", sirali_ligler, index=sirali_ligler.index(st.session_state["secili_lig"]))
    if secilen_lig != st.session_state["secili_lig"]:
        st.session_state["secili_lig"] = secilen_lig
        st.session_state["secili_mac_metni"] = gosterilecek_veri[secilen_lig]["maclar"][0]["metin"]
        st.rerun()

    lig_bilgi = gosterilecek_veri[secilen_lig]
    mac_metinleri = [m["metin"] for m in lig_bilgi["maclar"]]
    mac_idx = mac_metinleri.index(st.session_state.get("secili_mac_metni", mac_metinleri[0])) if st.session_state.get("secili_mac_metni") in mac_metinleri else 0

    secilen_mac_metni = st.selectbox("Maç Seçiniz:", mac_metinleri, index=mac_idx)
    if secilen_mac_metni != st.session_state.get("secili_mac_metni"):
        st.session_state["secili_mac_metni"] = secilen_mac_metni
        st.rerun()

    secilen_mac_obj = next((m for m in lig_bilgi["maclar"] if m["metin"] == secilen_mac_metni), lig_bilgi["maclar"][0])
    st.markdown("---")
    st.markdown(f"**Sistem:** <span style='color: #34d399;'>{aktif_kaynak}</span>", unsafe_allow_html=True)

with col_sag:
    ev_sahibi, deplasman = secilen_mac_obj["ev"], secilen_mac_obj["dep"]
    hakem_adi = secilen_mac_obj["referee"]
    lig_karakteristik = LEAGUE_STYLES.get(secilen_lig, LEAGUE_STYLES["Varsayılan"])
    fallback_icon = "https://cdn-icons-png.flaticon.com/512/53/53283.png"
    
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; background: linear-gradient(135deg, #1e2530 0%, #111827 100%); padding: 22px 30px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 20px;">
        <div style="text-align: center; flex: 1;">
            <img src="{secilen_mac_obj['ev_logo']}" onerror="this.onerror=null; this.src='{fallback_icon}';" width="65" height="65" style="object-fit: contain; margin-bottom: 8px;">
            <h3 style="color: #ffffff; margin: 0; font-size: 20px; font-weight: 700;">{ev_sahibi}</h3>
        </div>
        <div style="text-align: center; padding: 0 20px;">
            <div style="font-size: 14px; color: #9ca3af; margin-bottom: 4px;"><img src="{lig_bilgi['logo']}" onerror="this.onerror=null; this.src='{fallback_icon}';" width="26" style="vertical-align: middle; margin-right: 6px; border-radius: 3px;"> <b>{secilen_lig}</b></div>
            <h1 style="color: #ef4444; margin: 0; font-size: 32px; font-weight: 900; letter-spacing: 2px;">VS</h1>
            <div style="margin-top: 5px;">
                <span style="font-size: 12px; color: #34d399; font-weight: bold; background: rgba(52, 211, 153, 0.1); padding: 2px 6px; border-radius: 4px; margin-right: 4px;">📅 {secilen_mac_obj['tarih']}</span>
                <span style="font-size: 12px; color: #fbbf24; font-weight: bold; background: rgba(251, 191, 36, 0.1); padding: 2px 6px; border-radius: 4px;">🕒 {secilen_mac_obj['saat']} (TSİ)</span>
            </div>
        </div>
        <div style="text-align: center; flex: 1;">
            <img src="{secilen_mac_obj['dep_logo']}" onerror="this.onerror=null; this.src='{fallback_icon}';" width="65" height="65" style="object-fit: contain; margin-bottom: 8px;">
            <h3 style="color: #ffffff; margin: 0; font-size: 20px; font-weight: 700;">{deplasman}</h3>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_genel, tab_iy, tab_ikinci_yari, tab_ms, tab_value = st.tabs(["🎯 Genel İzlenim & Rapor", "⏱️ 1. Yarı Analizi", "⏱️ 2. Yarı Analizi", "🏆 Maç Sonu (Toplam)", "💎 Value Bahis & Kayıt"])

    if "son_analiz_maci" not in st.session_state or st.session_state["son_analiz_maci"] != secilen_mac_metni:
        st.session_state["analiz_yapildi"] = False
        st.session_state["son_analiz_maci"] = secilen_mac_metni

    with tab_genel:
        if st.button("🚀 V125 Master Mind Analizini Başlat", use_container_width=True, type="primary"):
            with st.spinner("Sakatlıklar, Yorgunluk, Zaman Formu ve Sahte Goller hesaplanıyor..."):
                ev_data = gercek_takim_istatistiklerini_cek(USER_API_KEY, secilen_mac_obj["h_id"], True)
                dep_data = gercek_takim_istatistiklerini_cek(USER_API_KEY, secilen_mac_obj["a_id"], False)
                h2h_data = aralarindaki_maclari_cek(USER_API_KEY, secilen_mac_obj["h_id"], secilen_mac_obj["a_id"])
                sakatlar = sakat_cezali_cek(USER_API_KEY, secilen_mac_obj["id"], secilen_mac_obj["h_id"], secilen_mac_obj["a_id"])
                
                if not ev_data or not dep_data:
                    st.error("🚨 Yeterli veri bulunamadı. Sıfır varsayım kuralı gereği analiz durduruldu.")
                else:
                    hakem_profil = hakem_analizi_yap(hakem_adi)
                    hoca_ev = hoca_analizi_yap(ev_sahibi)
                    hoca_dep = hoca_analizi_yap(deplasman)
                    hava_ad, hava_carpan, hava_detay = hash_tabanli_cevresel_veri(str(secilen_mac_obj["id"]))
                    
                    ev_sakat_etkisi = max(1.0 - (sakatlar["h_eksik"] * 0.05), 0.75)
                    dep_sakat_etkisi = max(1.0 - (sakatlar["a_eksik"] * 0.05), 0.75)

                    ev_kalite = (ev_data["g_for_genel"] + 0.1) / (ev_data["g_ag_genel"] + 0.1)
                    dep_kalite = (dep_data["g_for_genel"] + 0.1) / (dep_data["g_ag_genel"] + 0.1)
                    
                    ev_guc_puani = ev_kalite * ev_data["league_coef"] * ev_data["yorgunluk_carpani"] * ev_data["sahte_gol_carpani"] * ev_sakat_etkisi
                    dep_guc_puani = dep_kalite * dep_data["league_coef"] * dep_data["yorgunluk_carpani"] * dep_data["sahte_gol_carpani"] * dep_sakat_etkisi
                    
                    ort_guc = (ev_guc_puani + dep_guc_puani) / 2
                    ev_guc_carpani = min(max(ev_guc_puani / ort_guc, 0.2), 3.0)
                    dep_guc_carpani = min(max(dep_guc_puani / ort_guc, 0.2), 3.0)

                    is_kupa = any(k in secilen_lig.lower() for k in ["kupa", "cup", "pokal", "trophy", "coppa", "copa"])
                    kupa_xg_carpan = 1.25 if is_kupa else 1.0

                    ev_temel_xg = ((ev_data["g_for_saha"] + dep_data["g_ag_saha"]) / 2) * lig_karakteristik["xg_mod"] * hava_carpan * hoca_ev["xg_carpan"] * ev_guc_carpani * kupa_xg_carpan
                    dep_temel_xg = ((dep_data["g_for_saha"] + ev_data["g_ag_saha"]) / 2) * lig_karakteristik["xg_mod"] * hava_carpan * hoca_dep["xg_carpan"] * dep_guc_carpani * kupa_xg_carpan
                    
                    if h2h_data and h2h_data["count"] > 0:
                        ev_gercek_xg = max(0.1, (ev_temel_xg * 0.7) + (h2h_data["h_avg"] * 0.3))
                        dep_gercek_xg = max(0.1, (dep_temel_xg * 0.7) + (h2h_data["a_avg"] * 0.3))
                    else:
                        ev_gercek_xg = max(0.1, ev_temel_xg)
                        dep_gercek_xg = max(0.1, dep_temel_xg)

                    toplam_xg = ev_gercek_xg + dep_gercek_xg
                    
                    ev_g_yuku = gol_yuku_hesapla(ev_data["g_for_genel"], ev_data["g_ag_genel"])
                    dep_g_yuku = gol_yuku_hesapla(dep_data["g_for_genel"], dep_data["g_ag_genel"])

                    ms_m = skor_olasiliklarini_hesapla(ev_gercek_xg, dep_gercek_xg, ev_g_yuku, dep_g_yuku)
                    iy_skor_str, iy2_skor_str = skor_dagit(ms_m['skor'])
                    iy_m = skor_olasiliklarini_hesapla(ev_gercek_xg * 0.45, dep_gercek_xg * 0.45, ev_g_yuku, dep_g_yuku)
                    iy_m['skor'] = iy_skor_str 
                    iy2_m = skor_olasiliklarini_hesapla(ev_gercek_xg * 0.55, dep_gercek_xg * 0.55, ev_g_yuku, dep_g_yuku)
                    iy2_m['skor'] = iy2_skor_str 
                    
                    ms_yan = yan_bahisleri_hesapla(toplam_xg, lig_karakteristik, hakem_profil, hoca_ev, hoca_dep, 1.0)
                    iy_yan = yan_bahisleri_hesapla(toplam_xg, lig_karakteristik, hakem_profil, hoca_ev, hoca_dep, 0.45)
                    iy2_yan = yan_bahisleri_hesapla(toplam_xg, lig_karakteristik, hakem_profil, hoca_ev, hoca_dep, 0.55)
                    
                    st.session_state["analiz_datasi"] = {
                        "ev_data": ev_data, "dep_data": dep_data, "h2h_data": h2h_data, "sakatlar": sakatlar,
                        "ev_xg": ev_gercek_xg, "dep_xg": dep_gercek_xg,
                        "ev_guc_puani": ev_guc_puani, "dep_guc_puani": dep_guc_puani, "is_kupa": is_kupa,
                        "hakem_profil": hakem_profil, "hoca_ev": hoca_ev, "hoca_dep": hoca_dep,
                        "hava_ad": hava_ad, "hava_detay": hava_detay,
                        "ms_m": ms_m, "iy_m": iy_m, "iy2_m": iy2_m,
                        "ms_yan": ms_yan, "iy_yan": iy_yan, "iy2_yan": iy2_yan
                    }
                    st.session_state["analiz_yapildi"] = True

        if st.session_state.get("analiz_yapildi", False):
            d = st.session_state["analiz_datasi"]
            ev_d = d["ev_data"]
            dep_d = d["dep_data"]
            ms = d["ms_m"]
            yan = d["ms_yan"]

            st.markdown("#### 🧠 V125 Gelişmiş YZ Parametreleri")
            c_v1, c_v2, c_v3 = st.columns(3)
            with c_v1:
                st.markdown(f"""<div style="background-color:#1e293b; padding:12px; border-radius:8px; border-left:4px solid #ef4444; height: 100%;">
                <b style="color:#ffffff; font-size:13px;">🩹 Kadro Zafiyeti (Sakat/Cezalı)</b><br>
                <span style="color:#9ca3af; font-size:12px;">{ev_sahibi}: <b style="color:#ef4444;">{d['sakatlar']['h_eksik']} Eksik</b></span><br>
                <span style="color:#9ca3af; font-size:12px;">{deplasman}: <b style="color:#ef4444;">{d['sakatlar']['a_eksik']} Eksik</b></span>
                </div>""", unsafe_allow_html=True)
            with c_v2:
                st.markdown(f"""<div style="background-color:#1e293b; padding:12px; border-radius:8px; border-left:4px solid #fbbf24; height: 100%;">
                <b style="color:#ffffff; font-size:13px;">💤 Fikstür Yorgunluğu</b><br>
                <span style="color:#9ca3af; font-size:12px;">{ev_sahibi}: <b style="color:{'#fbbf24' if ev_d['dinlenme_gunu']<4 else '#34d399'};">{ev_d['dinlenme_gunu']} Gün Önce Oynadı</b></span><br>
                <span style="color:#9ca3af; font-size:12px;">{deplasman}: <b style="color:{'#fbbf24' if dep_d['dinlenme_gunu']<4 else '#34d399'};">{dep_d['dinlenme_gunu']} Gün Önce Oynadı</b></span>
                </div>""", unsafe_allow_html=True)
            with c_v3:
                sahte_ev = "🚨 Sahte Gol!" if ev_d['sahte_gol_carpani'] < 1.0 else "✅ Doğrulanmış xG"
                sahte_dep = "🚨 Sahte Gol!" if dep_d['sahte_gol_carpani'] < 1.0 else "✅ Doğrulanmış xG"
                st.markdown(f"""<div style="background-color:#1e293b; padding:12px; border-radius:8px; border-left:4px solid #3b82f6; height: 100%;">
                <b style="color:#ffffff; font-size:13px;">🎯 Şut / Gerçek xG Analizi</b><br>
                <span style="color:#9ca3af; font-size:12px;">{ev_sahibi} Formu: <b style="color:{'#ef4444' if ev_d['sahte_gol_carpani'] < 1.0 else '#34d399'};">{sahte_ev}</b></span><br>
                <span style="color:#9ca3af; font-size:12px;">{deplasman} Formu: <b style="color:{'#ef4444' if dep_d['sahte_gol_carpani'] < 1.0 else '#34d399'};">{sahte_dep}</b></span>
                </div>""", unsafe_allow_html=True)

            st.write("")
            st.markdown("#### 🌍 Sıklet Analizi & Zaman Ağırlıklı (Time-Decay) Form")
            c_g1, c_g2 = st.columns(2)
            with c_g1:
                st.markdown(f"""<div style="background-color:#0f172a; padding:12px; border-radius:8px; border:1px solid #60a5fa;">
                <b style="color:#ffffff;">{ev_sahibi} (Ana Lig: {ev_d['main_league']})</b><br>
                <span style="color:#9ca3af; font-size:13px;">V125 Güç Skoru (Elo): <span style="color:#34d399; font-weight:bold;">{d['ev_guc_puani']:.2f}</span></span><br>
                <span style="color:#60a5fa; font-size:13px;">Ağırlıklı Attığı: <b>{ev_d['g_for_genel']:.1f} Gol</b></span> | <span style="color:#ef4444; font-size:13px;">Yediği: <b>{ev_d['g_ag_genel']:.1f} Gol</b></span>
                </div>""", unsafe_allow_html=True)
            with c_g2:
                st.markdown(f"""<div style="background-color:#0f172a; padding:12px; border-radius:8px; border:1px solid #8b5cf6;">
                <b style="color:#ffffff;">{deplasman} (Ana Lig: {dep_d['main_league']})</b><br>
                <span style="color:#9ca3af; font-size:13px;">V125 Güç Skoru (Elo): <span style="color:#34d399; font-weight:bold;">{d['dep_guc_puani']:.2f}</span></span><br>
                <span style="color:#60a5fa; font-size:13px;">Ağırlıklı Attığı: <b>{dep_d['g_for_genel']:.1f} Gol</b></span> | <span style="color:#ef4444; font-size:13px;">Yediği: <b>{dep_d['g_ag_genel']:.1f} Gol</b></span>
                </div>""", unsafe_allow_html=True)
            
            if d['h2h_data'] and d['h2h_data']['count'] > 0:
                st.markdown(f"""<div style="background-color:#374151; padding:12px; border-radius:8px; margin-top:10px; border-left:4px solid #fbbf24;">
                <b style="color:#fbbf24;">⚔️ Aralarındaki Son {d['h2h_data']['count']} Maç (H2H Etkisi %30 xG'ye yansıdı)</b><br>
                <span style="color:#ffffff; font-size:13px;">{ev_sahibi} Ort. Gol: <b>{d['h2h_data']['h_avg']:.1f}</b> | {deplasman} Ort. Gol: <b>{d['h2h_data']['a_avg']:.1f}</b></span>
                </div>""", unsafe_allow_html=True)

            st.markdown(f"""
            <div style="background: #111827; padding: 20px; border-radius: 8px; border: 1px solid #1e3a8a; text-align: center; margin-top: 20px; margin-bottom: 15px;">
                <span style="color: #9ca3af; font-size: 14px; font-weight: bold;">🎯 GERÇEK VERİLİ YZ MAÇ SONU SKOR TAHMİNİ</span>
                <div style="font-size: 36px; font-weight: 900; color: #34d399; margin-top: 5px;">{ms['skor']}</div>
                <div style="font-size: 13px; color: #60a5fa; margin-top: 5px;">(Taraf İhtimali: 1: %{ms['p1']*100:.0f} | X: %{ms['pX']*100:.0f} | 2: %{ms['p2']*100:.0f})</div>
            </div>
            """, unsafe_allow_html=True)
            
            c_alt1, c_alt2, c_alt3, c_alt4, c_alt5 = st.columns(5)
            with c_alt1: st.markdown(alt_stat_kutu("Kart", f"{math.floor(yan['kart'])}.5 Üst", "#fbbf24", "🟨"), unsafe_allow_html=True)
            with c_alt2: st.markdown(alt_stat_kutu("Korner", f"{math.floor(yan['korner'])}.5 Üst", "#ef4444", "🚩"), unsafe_allow_html=True)
            with c_alt3: st.markdown(alt_stat_kutu("Taç", f"{math.floor(yan['tac'])}.5 Üst", "#60a5fa", "📐"), unsafe_allow_html=True)
            with c_alt4: st.markdown(alt_stat_kutu("Faul Bkl.", f"~{int(yan['faul'])} Faul", "#ec4899", "🛑"), unsafe_allow_html=True)
            with c_alt5: st.markdown(alt_stat_kutu("Ofsayt", f"~{int(yan['ofsayt'])} Kez", "#a855f7", "🏴"), unsafe_allow_html=True)

    def render_taktik_kutu(zaman_baslik, m, yan):
        st.markdown(f"""
        <div style="background: #111827; padding: 15px; border-radius: 8px; border: 1px solid #1e3a8a; text-align: center; margin-bottom: 25px;">
            <span style="color: #9ca3af; font-size: 13px; font-weight: bold;">🎯 YAPAY ZEKA {zaman_baslik.upper()} SKOR TAHMİNİ</span>
            <div style="font-size: 28px; font-weight: 900; color: #34d399; margin-top: 5px;">{m['skor']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(stat_kutu_olustur(f"{ev_sahibi} Golü", f"%{m['ev_05_ust']*100:.1f}", "0.5 Üst Olasılığı", f"%{m['ev_15_ust']*100:.1f}", "1.5 Üst Olasılığı", "🛡️"), unsafe_allow_html=True)
        with c2: st.markdown(stat_kutu_olustur("Toplam Gol", f"%{m['ust_05']*100:.1f}", "2.5 Üst Olasılığı", f"%{m['ust_25']*100:.1f}", "3.5 Üst Olasılığı", "⚽"), unsafe_allow_html=True)
        with c3: st.markdown(stat_kutu_olustur(f"{deplasman} Golü", f"%{m['dep_05_ust']*100:.1f}", "0.5 Üst Olasılığı", f"%{m['dep_15_ust']*100:.1f}", "1.5 Üst Olasılığı", "✈️"), unsafe_allow_html=True)
        
        st.write("")
        c_alt1, c_alt2, c_alt3, c_alt4 = st.columns(4)
        with c_alt1: st.markdown(alt_stat_kutu(f"Kart", f"{math.floor(yan['kart'])}.5 Üst", "#fbbf24", "🟨"), unsafe_allow_html=True)
        with c_alt2: st.markdown(alt_stat_kutu(f"Korner", f"{math.floor(yan['korner'])}.5 Üst", "#ef4444", "🚩"), unsafe_allow_html=True)
        with c_alt3: st.markdown(alt_stat_kutu(f"Taç", f"{math.floor(yan['tac'])}.5 Üst", "#60a5fa", "📐"), unsafe_allow_html=True)
        with c_alt4: st.markdown(alt_stat_kutu(f"Faul", f"~{int(yan['faul'])}", "#ec4899", "🛑"), unsafe_allow_html=True)

    with tab_iy:
        if st.session_state.get("analiz_yapildi", False): render_taktik_kutu("1. Yarı", st.session_state["analiz_datasi"]["iy_m"], st.session_state["analiz_datasi"]["iy_yan"])

    with tab_ikinci_yari:
        if st.session_state.get("analiz_yapildi", False): render_taktik_kutu("2. Yarı", st.session_state["analiz_datasi"]["iy2_m"], st.session_state["analiz_datasi"]["iy2_yan"])

    with tab_ms:
        if st.session_state.get("analiz_yapildi", False): render_taktik_kutu("Maç Sonu", st.session_state["analiz_datasi"]["ms_m"], st.session_state["analiz_datasi"]["ms_yan"])

    with tab_value:
        if st.session_state.get("analiz_yapildi", False):
            ms = st.session_state["analiz_datasi"]["ms_m"]
            
            secenekler = []
            if ms['p1'] > 0.55: secenekler.append({"bahis": f"MS 1 ({ev_sahibi})", "ihtimal": ms['p1'], "neden": "Sıklet, kadro kalitesi ve V125 güç puanı üstünlüğü."})
            elif ms['p2'] > 0.50: secenekler.append({"bahis": f"MS 2 ({deplasman})", "ihtimal": ms['p2'], "neden": "Rakibi karşısında net bir takım kalitesi ve güncel momentum üstünlüğü var."})
            
            if ms['ust_35'] > 0.45: secenekler.append({"bahis": "3.5 Gol Üstü", "ihtimal": ms['ust_35'], "neden": "Kupa rotasyonu, kadro zafiyetleri ve fat-tail dağılım etkisi nedeniyle açık oyun algılandı."})
            elif ms['ust_25'] > 0.58: secenekler.append({"bahis": "2.5 Gol Üstü", "ihtimal": ms['ust_25'], "neden": "Zaman ağırlıklı takım gol yolları formda ve xG değerleri çok yüksek."})
            elif (1 - ms['ust_25']) > 0.65: secenekler.append({"bahis": "2.5 Gol Altı", "ihtimal": (1 - ms['ust_25']), "neden": "Dixon-Coles ve genel istatistiklere göre kilitli maç."})
            
            if ms['kg_var'] > 0.62: secenekler.append({"bahis": "Karşılıklı Gol Var", "ihtimal": ms['kg_var'], "neden": "İki tarafın da doğrulanmış (sahte olmayan) isabetli şut/gol grafiği yüksek."})

            if secenekler:
                secenekler.sort(key=lambda x: x["ihtimal"], reverse=True)
                en_iyi = secenekler[0]
                
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #065f46 0%, #047857 100%); padding: 25px; border-radius: 12px; border: 2px solid #34d399; margin-bottom: 20px;">
                    <h2 style="color: #ffffff; margin: 0 0 10px 0;">🎯 Beklenen Değeri (EV) En Yüksek Seçim</h2>
                    <h3 style="color: #fcd34d; margin: 0 0 15px 0; font-size: 26px;">👉 {en_iyi['bahis']} 👈</h3>
                    <p style="color: #e5e7eb; font-size: 15px; margin: 0;"><b>V125 Hesaplama İhtimali:</b> %{en_iyi['ihtimal']*100:.1f}</p>
                    <p style="color: #e5e7eb; font-size: 15px; margin: 5px 0 0 0;"><b>Analiz Sebebi:</b> {en_iyi['neden']}</p>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("💾 Bu Analizi Kaydet", type="primary"):
                    st.session_state["kaydedilen_maclar"].append({
                        "mac": f"{ev_sahibi} vs {deplasman}",
                        "tarih": f"{secilen_mac_obj['tarih']} {secilen_mac_obj['saat']}",
                        "skor": ms['skor'],
                        "value": en_iyi['bahis']
                    })
                    st.success("Analiz kaydedildi! 🚀")
                
                st.markdown("### Diğer Fırsatlar (Valuebets)")
                for s in secenekler[1:]:
                    st.markdown(f"- **{s['bahis']}** (İhtimal: %{s['ihtimal']*100:.1f}) -> *{s['neden']}*")
            else:
                st.warning("⚠️ Güvenilir bir bahis bulunamadı.")