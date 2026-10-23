#!/usr/bin/env python3
"""Fabrique index.html (page météo pour vieil iPad, iOS 9) à partir d'Open-Meteo.

Lancé toutes les 30 min par .github/workflows/meteo.yml. La page produite est
du HTML déjà rempli, sans chargement en arrière-plan : le Safari d'iOS 9
lancé depuis l'écran d'accueil refuse ces chargements (erreur « code 0 »).
La page se recharge elle-même toutes les 10 min.

Les tâches programmées de GitHub sautent souvent des passages : la page embarque
donc les prévisions heure par heure sur 48 h (blocs HTML déjà fabriqués), et
l'iPad affiche lui-même le bloc de l'heure en cours. L'affichage reste juste même
si GitHub ne passe que quelques fois par jour.

Usage : python3 gen.py [fichier_sortie]
"""
import datetime
import json
import sys
import time
import urllib.request
from zoneinfo import ZoneInfo

VILLE = "Urcuit"
LAT, LON = 43.487, -1.338
REFRESH_SECONDS = 600
HEURES = 48           # prévisions horaires embarquées dans la page
VIEUX_HEURES = 12     # au-delà, l'heure des prévisions s'affiche en rouge

URL = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
       "&timezone=Europe%%2FParis&forecast_days=7"
       "&hourly=temperature_2m,weather_code,wind_speed_10m,pressure_msl,precipitation,precipitation_probability"
       "&past_hours=3&forecast_hours=%d"
       "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset,daylight_duration"
       % (LAT, LON, HEURES + 1))

# Couleur Tempo EDF (service gratuit api-couleur-tempo.fr, données RTE)
TEMPO_URL = "https://www.api-couleur-tempo.fr/api/jourTempo/%s"   # today / tomorrow
TEMPO = {1: ("Bleu", "#2f6fd6", "#fff"), 2: ("Blanc", "#eee", "#000"), 3: ("Rouge", "#d33", "#fff")}

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


def tempo():
    """{date Tempo: code} pour aujourd'hui et demain ; {} si le service ne répond pas."""
    res = {}
    for j in ("today", "tomorrow"):
        try:
            r = get_json(TEMPO_URL % j)
            res[r["dateJour"]] = r.get("codeJour", 0)
        except Exception as e:
            print("Tempo indisponible (%s) : %s" % (j, e))
    return res


def pastille(code):
    if code in TEMPO:
        nom, fond, txt = TEMPO[code]
        return '<span class="tp" style="background:%s;color:%s">%s</span>' % (fond, txt, nom)
    return '<span class="tp nc">non publiée</span>'


def ligne_tempo(t, heure):
    """Le jour Tempo va de 6 h à 6 h : à 2 h du matin, c'est encore la couleur de la veille."""
    if not t:
        return ""
    jt = datetime.datetime.strptime(heure, "%Y-%m-%dT%H:%M") - datetime.timedelta(hours=6)
    auj, dem = jt.strftime("%Y-%m-%d"), (jt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    if auj not in t:
        return ""
    return '<div id="tempo">EDF Tempo · auj. %s &nbsp; demain %s</div>' % (pastille(t[auj]), pastille(t.get(dem, 0)))


def bloc_heure(h, i, t):
    """Partie haute de la page pour l'heure n° i des prévisions horaires."""
    label, icon = WMO.get(h["weather_code"][i], ("", "cloud"))
    txt = "Pression %d hPa" % round(h["pressure_msl"][i])
    if i >= 3:
        ecart = h["pressure_msl"][i] - h["pressure_msl"][i - 3]
        if ecart >= 1:
            txt += " · en hausse (+%d en 3 h)" % round(ecart)
        elif ecart <= -1:
            txt += " · en baisse (%d en 3 h)" % round(ecart)
        else:
            txt += " · stable"
    haut = ('%s<div id="t">%d°</div><div class="v">%s · vent %d km/h</div><div class="v2">%s</div>'
            % (svg(icon, 100), round(h["temperature_2m"][i]), label, round(h["wind_speed_10m"][i]), txt))
    return haut, ligne_tempo(t, h["time"][i])


def ligne_jours(day, k):
    """Les 5 colonnes de prévisions à partir du jour n° k."""
    rows = ""
    for i in range(k, min(k + 5, len(day["time"]))):
        wd = time.strptime(day["time"][i], "%Y-%m-%d").tm_wday
        _, i2 = WMO.get(day["weather_code"][i], ("", "cloud"))
        rows += ('<td><div class="j">%s</div><div class="ic">%s</div>'
                 '<div>%d° / %d°</div><div class="s">%s %%</div></td>') % (
            "Auj." if i == k else JOURS[wd], svg(i2, 70), round(day["temperature_2m_max"][i]),
            round(day["temperature_2m_min"][i]), day["precipitation_probability_max"][i] or 0)
    return "<table><tr>%s</tr></table>" % rows


LUNES = [(1.84, "\U0001F311", "Nouvelle lune"), (5.53, "\U0001F312", "Premier croissant"),
         (9.22, "\U0001F313", "Premier quartier"), (12.91, "\U0001F314", "Gibbeuse croissante"),
         (16.61, "\U0001F315", "Pleine lune"), (20.30, "\U0001F316", "Gibbeuse décroissante"),
         (23.99, "\U0001F317", "Dernier quartier"), (27.68, "\U0001F318", "Dernier croissant"),
         (99, "\U0001F311", "Nouvelle lune")]


def lune(date):
    """Phase de la lune à midi (âge depuis la nouvelle lune de référence du 6/1/2000)."""
    j = datetime.datetime.strptime(date, "%Y-%m-%d").replace(hour=11)   # ~midi à Paris, en UTC
    age = ((j - datetime.datetime(2000, 1, 6, 18, 14)).total_seconds() / 86400.0) % 29.530588853
    for lim, emoji, nom in LUNES:
        if age < lim:
            return '<span class="lu">%s</span> %s' % (emoji, nom)


def ligne_ciel(day, k):
    """Lever / coucher du soleil, durée du jour et phase de la lune pour le jour n° k."""
    try:
        lev, cou = day["sunrise"][k][11:16], day["sunset"][k][11:16]
        dur = int(day["daylight_duration"][k] // 60)
        soleil = ('<span class="so">\u2600\ufe0e</span> lever %s · coucher %s (%d h %02d)'
                  % (lev, cou, dur // 60, dur % 60))
    except Exception:
        soleil = ""
    return soleil + (" &nbsp;·&nbsp; " if soleil else "") + lune(day["time"][k])


# Vigilance Météo-France, relayée sans clé par le flux européen MeteoAlarm
ALERTES_URL = "https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-france"
DEPT_NOMS = ("Pyrénées-Atlantiques",)
DEPT_CODES = ("FR615", "FRI15")          # code NUTS du département (ancienne et nouvelle nomenclature)
NIVEAUX = {"Moderate": 1, "Severe": 2, "Extreme": 3}   # jaune, orange, rouge
PHENOMENES = [("thunder", "Orages"), ("rain-flood", "Pluie-inondation"), ("flood", "Crues"),
              ("wind", "Vent violent"), ("snow", "Neige-verglas"), ("ice", "Neige-verglas"),
              ("avalanche", "Avalanches"), ("high-temperature", "Canicule"), ("heat", "Canicule"),
              ("low-temperature", "Grand froid"), ("cold", "Grand froid"), ("coastal", "Vagues-submersion"),
              ("wave", "Vagues-submersion"), ("fog", "Brouillard")]


def alertes():
    """Liste des vigilances du département : [phénomène, niveau 1-3, début ms, fin ms]."""
    import xml.etree.ElementTree as ET
    req = urllib.request.Request(ALERTES_URL, headers={"User-Agent": "ipad-meteo (GitHub Actions)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        racine = ET.fromstring(r.read())
    def champ(e, nom):
        for x in e.iter():
            if x.tag.split("}")[-1] == nom:
                return (x.text or "").strip()
        return ""
    res = []
    for e in racine:
        if e.tag.split("}")[-1] != "entry":
            continue
        zone = champ(e, "areaDesc")
        codes = [(x.text or "").strip() for x in e.iter() if x.tag.split("}")[-1] == "value"]
        if not (any(n in zone for n in DEPT_NOMS) or any(c in codes for c in DEPT_CODES)):
            continue
        if champ(e, "message_type") == "Cancel" or champ(e, "status") not in ("", "Actual"):
            continue
        niv = NIVEAUX.get(champ(e, "severity"))
        if not niv:
            continue
        ev = champ(e, "event").lower()
        nom = next((n for k, n in PHENOMENES if k in ev), champ(e, "event"))
        def ms(txt):
            return int(datetime.datetime.fromisoformat(txt.replace("Z", "+00:00")).timestamp() * 1000)
        try:
            debut = ms(champ(e, "onset") or champ(e, "effective"))
            fin = ms(champ(e, "expires"))
        except Exception:
            continue
        res.append([nom, niv, debut, fin])
    return res


def js(obj):
    return json.dumps(obj, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")


def render(d, t, maintenant, al=None):
    h, day = d["hourly"], d["daily"]
    hautes, tempos = {}, {}
    for i, heure in enumerate(h["time"]):
        if i < 3:          # les 3 heures passées ne servent qu'à la tendance de pression
            continue
        hautes[heure[:13]], tempos[heure[:13]] = bloc_heure(h, i, t)
    # pluie heure par heure : [mm, probabilité %] ; la frise des 12 h est dessinée par l'iPad
    pluie = {"t": [x[:13] for x in h["time"][3:]],
             "mm": [round(x or 0, 1) for x in h["precipitation"][3:]],
             "pr": [x or 0 for x in h["precipitation_probability"][3:]]}
    jours, ciel = {}, {}
    for k in range(3):     # aujourd'hui, demain, après-demain
        jours[day["time"][k]] = ligne_jours(day, k)
        ciel[day["time"][k]] = ligne_ciel(day, k)
    cle = maintenant.strftime("%Y-%m-%dT%H")
    if cle not in hautes:
        cle = sorted(hautes)[0]
    return """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="apple-mobile-web-app-title" content="Météo">
<meta http-equiv="refresh" content="%(refresh)d">
<title>Météo</title>
<!-- Page fabriquée automatiquement par gen.py : ne pas modifier à la main. -->
<style>
html,body{overflow-x:hidden}
body{margin:0;background:#000;-webkit-text-size-adjust:100%%;color:#eee;font-family:Helvetica,Arial,sans-serif;text-align:center}
#h{font-size:72px;font-weight:200;margin-top:6px;line-height:1}
.v{font-size:28px;color:#9ab}
#t{font-size:84px;font-weight:200;line-height:1}
.s{color:#889;font-size:20px}
table{width:100%%;table-layout:fixed;border-collapse:collapse;margin-top:10px;font-size:24px}
td{width:20%%}
.j{color:#9ab;margin-bottom:6px}
.v2{font-size:22px;color:#789;margin-top:4px}
#tempo{font-size:22px;color:#9ab;margin-top:10px}
#ciel{font-size:20px;color:#789;margin-top:8px}
.lu{font-size:22px}
.so{color:#fc3}
.al{display:inline-block;margin-left:10px;padding:1px 10px;border-radius:10px;font-size:20px;font-weight:bold;vertical-align:4px}
#pluie{width:86%%;margin:10px auto 0;font-size:14px;color:#667}
#pluie table{margin:0}
#pluie td{width:auto;vertical-align:bottom;padding:0 2px;font-size:14px;color:#667}
.bar{background:#5af;border-radius:3px 3px 0 0;margin:0 auto;width:80%%}
.sec{font-size:20px;color:#678;padding:14px 0}
.tp{display:inline-block;padding:2px 12px;border-radius:12px;font-weight:bold}
.tp.nc{color:#667;border:1px solid #445;font-weight:normal}
#maj{color:#556;font-size:16px;margin-top:10px}
#maj.err{color:#a66}
</style></head><body>
<div id="h">--:--</div>
<div class="v">%(ville)s<span id="al"></span></div>
<div id="haut">%(haut0)s</div>
<div id="pluie"></div>
<div id="jours">%(jours0)s</div>
<div id="tp">%(tempo0)s</div>
<div id="ciel">%(ciel0)s</div>
<div id="maj">Prévisions de %(gen)s</div>
<script>
var HAUT=%(hautes)s;
var TEMPO=%(tempos)s;
var JOURS=%(jours)s;
var CIEL=%(ciels)s;
var PLUIE=%(pluie)s;
var ALERTES=%(alertes)s;
var COUL=["","#f2c200","#f28c00","#e01b1b"], TXT=["","#000","#000","#fff"];
// Vigilances en cours (jaune / orange / rouge), avec leur heure de fin
function vigilance(){
  var now=new Date().getTime(), html="", i, a, f;
  for(i=0;i<ALERTES.length;i++){
    a=ALERTES[i];
    if(now<a[2]||now>a[3]) continue;
    f=new Date(a[3]);
    html+='<span class="al" style="background:'+COUL[a[1]]+';color:'+TXT[a[1]]+'">\u26a0\ufe0e '+a[0]+
      ' \u00b7 jusqu\\'\u00e0 '+p(f.getHours())+'h</span>';
  }
  return html;
}
var GEN=new Date(%(gy)d,%(gmo)d,%(gd)d,%(gh)d,%(gmi)d).getTime();
var dejaH="", dejaJ="%(jour0)s";
function p(n){return n<10?"0"+n:""+n}
function $(id){return document.getElementById(id)}
// Frise de pluie des 12 prochaines heures (barres proportionnelles aux mm/h)
function pluie(cle){
  var i, k=-1, n=12, html="", lab="", mx=0, tot=0;
  for(i=0;i<PLUIE.t.length;i++){ if(PLUIE.t[i]===cle){ k=i; break; } }
  if(k<0) return "";
  for(i=k;i<k+n&&i<PLUIE.t.length;i++){ tot+=PLUIE.mm[i]; if(PLUIE.mm[i]>mx) mx=PLUIE.mm[i]; }
  if(tot<0.2) return '<div class="sec">Pas de pluie prévue d\\'ici 12 h</div>';
  var echelle=mx<2?2:mx;
  for(i=k;i<k+n&&i<PLUIE.t.length;i++){
    var mm=PLUIE.mm[i], pr=PLUIE.pr[i], hgt=mm>=0.1?Math.max(3,Math.round(mm/echelle*44)):0;
    var op=pr>=60?1:(pr>=30?0.65:0.35);
    html+='<td><div class="bar" style="height:'+hgt+'px;opacity:'+op+'"></div></td>';
    lab+='<td>'+((i-k)%%3===0?PLUIE.t[i].substring(11,13)+"h":"")+'</td>';
  }
  return '<div style="text-align:left;margin-bottom:2px">Pluie 12 h · max '+String(mx).replace(".",",")+' mm/h</div>'+
    '<table><tr style="height:46px">'+html+'</tr><tr>'+lab+'</tr></table>';
}
function tick(){
  var d=new Date();
  $("h").innerHTML=p(d.getHours())+":"+p(d.getMinutes());
  $("al").innerHTML=vigilance();
  var jour=d.getFullYear()+"-"+p(d.getMonth()+1)+"-"+p(d.getDate());
  var cle=jour+"T"+p(d.getHours());
  if(cle!==dejaH && HAUT[cle]){ $("haut").innerHTML=HAUT[cle]; $("tp").innerHTML=TEMPO[cle]; $("pluie").innerHTML=pluie(cle); dejaH=cle; }
  if(jour!==dejaJ && JOURS[jour]){ $("jours").innerHTML=JOURS[jour]; $("ciel").innerHTML=CIEL[jour]; dejaJ=jour; }
  var vieux=(d.getTime()-GEN>%(vieux)d*3600000)||!HAUT[cle];
  $("maj").className=vieux?"err":"";
  $("maj").innerHTML="Prévisions de %(gen)s"+(vieux?" — pas de mise à jour depuis longtemps":"");
}
tick();setInterval(tick,10000);
</script></body></html>
""" % dict(refresh=REFRESH_SECONDS, ville=VILLE, haut0=hautes[cle], tempo0=tempos[cle],
           jours0=jours[day["time"][0]], jour0=day["time"][0], cle=cle,
           hautes=js(hautes), tempos=js(tempos), jours=js(jours),
           ciel0=ciel[day["time"][0]], ciels=js(ciel), pluie=js(pluie), alertes=js(al or []),
           gen=maintenant.strftime("%H:%M"), gy=maintenant.year, gmo=maintenant.month - 1,
           gd=maintenant.day, gh=maintenant.hour, gmi=maintenant.minute, vieux=VIEUX_HEURES)


if __name__ == "__main__":
    sortie = sys.argv[1] if len(sys.argv) > 1 else "index.html"
    if len(sys.argv) > 2:   # test hors ligne : python3 gen.py sortie.html donnees.json
        data = json.load(open(sys.argv[2]))
        t = data.get("_tempo", {})
        al = data.get("_alertes", [])
    else:
        data = get_json(URL)
        t = tempo()        # une panne Tempo n'empêche pas la météo
        try:
            al = alertes()
            print("Vigilances %s :" % DEPT_NOMS[0], al or "aucune")
        except Exception as e:
            print("Vigilance indisponible :", e)
            al = []
    maintenant = datetime.datetime.now(ZoneInfo("Europe/Paris")).replace(tzinfo=None)
    html = render(data, t, maintenant, al)    # échoue avant d'écrire si les données sont incomplètes
    with open(sortie, "w", encoding="utf-8") as f:
        f.write(html)
    print("Page écrite :", sortie, "(%d Ko)" % (len(html.encode("utf-8")) // 1024))
