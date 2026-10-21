#!/usr/bin/env python3
"""Fabrique index.html (page météo pour vieil iPad, iOS 9) à partir d'Open-Meteo.

Lancé toutes les 30 min par .github/workflows/meteo.yml. La page produite est
du HTML déjà rempli, sans chargement en arrière-plan : le Safari d'iOS 9
lancé depuis l'écran d'accueil refuse ces chargements (erreur « code 0 »).
La page se recharge elle-même toutes les 10 min.

Usage : python3 gen.py [fichier_sortie]
"""
import json
import sys
import time
import urllib.request

VILLE = "Urcuit"
LAT, LON = 43.487, -1.338
REFRESH_SECONDS = 600
VIEUX_MINUTES = 120   # au-delà, l'heure des données s'affiche en rouge

URL = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
       "&timezone=Europe%%2FParis&forecast_days=5"
       "&current=temperature_2m,weather_code,wind_speed_10m"
       "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
       % (LAT, LON))

WMO = {
    0: ("Ciel dégagé", "sun"), 1: ("Peu nuageux", "partly"), 2: ("Partiellement nuageux", "partly"),
    3: ("Couvert", "cloud"), 45: ("Brouillard", "fog"), 48: ("Brouillard givrant", "fog"),
    51: ("Bruine légère", "drizzle"), 53: ("Bruine", "drizzle"), 55: ("Bruine dense", "rain"),
    61: ("Pluie faible", "drizzle"), 63: ("Pluie", "rain"), 65: ("Forte pluie", "rain"),
    66: ("Pluie verglaçante", "rain"), 67: ("Pluie verglaçante", "rain"),
    71: ("Neige faible", "snow"), 73: ("Neige", "snow"), 75: ("Forte neige", "snow"),
    77: ("Grains de neige", "snow"), 80: ("Averses", "drizzle"), 81: ("Averses", "rain"),
    82: ("Fortes averses", "rain"), 85: ("Averses de neige", "snow"), 86: ("Averses de neige", "snow"),
    95: ("Orage", "storm"), 96: ("Orage et grêle", "storm"), 99: ("Orage et grêle", "storm"),
}

CLOUD = ('<circle cx="35" cy="52" r="17" fill="%(c)s"/><circle cx="55" cy="42" r="22" fill="%(c)s"/>'
         '<circle cx="76" cy="55" r="15" fill="%(c)s"/><rect x="35" y="52" width="41" height="18" fill="%(c)s"/>')
SUN = ('<circle cx="50" cy="50" r="20" fill="#fc3"/><g stroke="#fc3" stroke-width="6" stroke-linecap="round">'
       '<line x1="50" y1="12" x2="50" y2="22"/><line x1="50" y1="78" x2="50" y2="88"/>'
       '<line x1="12" y1="50" x2="22" y2="50"/><line x1="78" y1="50" x2="88" y2="50"/>'
       '<line x1="23" y1="23" x2="30" y2="30"/><line x1="70" y1="70" x2="77" y2="77"/>'
       '<line x1="23" y1="77" x2="30" y2="70"/><line x1="70" y1="30" x2="77" y2="23"/></g>')
SMALL_SUN = '<circle cx="32" cy="30" r="15" fill="#fc3"/>'
DROPS = '<g stroke="#5af" stroke-width="6" stroke-linecap="round"><line x1="38" y1="78" x2="34" y2="90"/><line x1="54" y1="78" x2="50" y2="90"/><line x1="70" y1="78" x2="66" y2="90"/></g>'
FLAKES = '<g fill="#cef"><circle cx="38" cy="82" r="5"/><circle cx="54" cy="88" r="5"/><circle cx="70" cy="82" r="5"/></g>'
BOLT = '<polygon points="55,66 42,86 52,86 47,100 66,76 55,76" fill="#fc3"/>'
FOG = '<g stroke="#9ab" stroke-width="7" stroke-linecap="round"><line x1="22" y1="40" x2="78" y2="40"/><line x1="14" y1="56" x2="86" y2="56"/><line x1="26" y1="72" x2="74" y2="72"/></g>'
ICONS = {
    "sun": SUN, "fog": FOG,
    "partly": SMALL_SUN + CLOUD % {"c": "#bcd"},
    "cloud": CLOUD % {"c": "#9ab"},
    "drizzle": CLOUD % {"c": "#9ab"} + DROPS.replace("78", "76").replace("90", "86"),
    "rain": CLOUD % {"c": "#789"} + DROPS,
    "snow": CLOUD % {"c": "#9ab"} + FLAKES,
    "storm": CLOUD % {"c": "#567"} + BOLT,
}
JOURS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]


def svg(kind, px):
    return ('<svg width="%d" height="%d" viewBox="0 0 100 100" style="display:block;margin:0 auto">%s</svg>'
            % (px, px, ICONS.get(kind, CLOUD % {"c": "#9ab"})))


def get_json(url):
    last = None
    for essai in range(3):
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # nouvel essai après une courte pause
            last = e
            time.sleep(5)
    raise last


def render(d):
    cur, day = d["current"], d["daily"]
    label, icon = WMO.get(cur["weather_code"], ("", "cloud"))
    rows = ""
    for i, date in enumerate(day["time"]):
        wd = time.strptime(date, "%Y-%m-%d").tm_wday
        _, i2 = WMO.get(day["weather_code"][i], ("", "cloud"))
        rows += ('<td><div class="j">%s</div><div class="ic">%s</div>'
                 '<div>%d° / %d°</div><div class="s">%s %%</div></td>') % (
            "Auj." if i == 0 else JOURS[wd], svg(i2, 70), round(day["temperature_2m_max"][i]),
            round(day["temperature_2m_min"][i]), day["precipitation_probability_max"][i] or 0)
    # cur["time"] est en heure de Paris, ex. "2026-10-21T23:15"
    y, mo, dd, hh, mi = [int(x) for x in cur["time"].replace("T", "-").replace(":", "-").split("-")[:5]]
    return """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="apple-mobile-web-app-title" content="Météo">
<meta http-equiv="refresh" content="%(refresh)d">
<title>Météo</title>
<!-- Page fabriquée automatiquement par gen.py : ne pas modifier à la main. -->
<style>
body{margin:0;background:#000;color:#eee;font-family:Helvetica,Arial,sans-serif;text-align:center}
#h{font-size:90px;font-weight:200;margin-top:14px;line-height:1.1}
.v{font-size:30px;color:#9ab}
#t{font-size:100px;font-weight:200;line-height:1.1}
.s{color:#889;font-size:20px}
table{width:100%%;margin-top:16px;font-size:26px}
td{width:20%%}
.j{color:#9ab;margin-bottom:6px}
#maj{color:#556;font-size:16px;margin-top:12px}
#maj.err{color:#a66}
</style></head><body>
<div id="h">--:--</div>
<div class="v">%(ville)s</div>
%(icon)s
<div id="t">%(temp)d°</div>
<div class="v">%(label)s · vent %(vent)d km/h</div>
<table><tr>%(rows)s</tr></table>
<div id="maj">Données de %(hh)02d:%(mi)02d</div>
<script>
function p(n){return n<10?"0"+n:n}
var DONNEES=new Date(%(y)d,%(mo)d,%(dd)d,%(hh)d,%(mi)d).getTime();
function tick(){
  var d=new Date();
  document.getElementById("h").innerHTML=p(d.getHours())+":"+p(d.getMinutes());
  if(d.getTime()-DONNEES>%(vieux)d*60000){
    var m=document.getElementById("maj");
    m.className="err";
    m.innerHTML="Données de %(hh)02d:%(mi)02d — pas de mise à jour depuis plus de 2 h";
  }
}
tick();setInterval(tick,10000);
</script></body></html>
""" % dict(refresh=REFRESH_SECONDS, ville=VILLE, icon=svg(icon, 150), temp=round(cur["temperature_2m"]),
           label=label, vent=round(cur["wind_speed_10m"]), rows=rows,
           y=y, mo=mo - 1, dd=dd, hh=hh, mi=mi, vieux=VIEUX_MINUTES)


if __name__ == "__main__":
    sortie = sys.argv[1] if len(sys.argv) > 1 else "index.html"
    if len(sys.argv) > 2:   # test hors ligne : python3 gen.py sortie.html donnees.json
        data = json.load(open(sys.argv[2]))
    else:
        data = get_json(URL)
    html = render(data)    # échoue avant d'écrire si les données sont incomplètes
    with open(sortie, "w", encoding="utf-8") as f:
        f.write(html)
    print("Page écrite :", sortie)
