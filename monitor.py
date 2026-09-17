"""Controlla il sito dell'Ambito Territoriale di Torino e avvisa su Telegram
quando compare un nuovo articolo con "nomina" / "nomine" nel titolo."""

import html
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

FEED_URL = os.environ.get("FEED_URL", "https://www.istruzionepiemonte.it/torino/feed/")
PAROLA = re.compile(r"nomin", re.IGNORECASE)  # trova "nomina", "nomine", "nominati"...
FILE_STATO = "visti.json"
AVVISO_DOPO_ERRORI = 8  # circa 2 ore di errori di fila con controllo ogni 15 minuti

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def scarica(url):
    richiesta = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (avviso personale nuove nomine)"}
    )
    with urllib.request.urlopen(richiesta, timeout=30) as risposta:
        return risposta.read()


def leggi_articoli(contenuto):
    radice = ET.fromstring(contenuto)
    articoli = []
    for item in radice.iter("item"):
        titolo = html.unescape((item.findtext("title") or "").strip())
        link = (item.findtext("link") or "").strip()
        if link:
            articoli.append((titolo, link))
    return articoli


def invia_telegram(testo):
    dati = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": testo}).encode()
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    urllib.request.urlopen(url, data=dati, timeout=30)


def carica_stato():
    if not os.path.exists(FILE_STATO):
        return None
    with open(FILE_STATO, encoding="utf-8") as f:
        return json.load(f)


def salva_stato(stato):
    stato["visti"] = stato["visti"][-500:]
    with open(FILE_STATO, "w", encoding="utf-8") as f:
        json.dump(stato, f, ensure_ascii=False, indent=1)


def main():
    stato = carica_stato()
    primo_avvio = stato is None
    if primo_avvio:
        stato = {"visti": [], "errori": 0}

    try:
        articoli = leggi_articoli(scarica(FEED_URL))
    except Exception as errore:
        print("Errore nella lettura del sito:", errore)
        if primo_avvio:
            invia_telegram(f"⚠️ Il bot è collegato, ma non riesce a leggere il sito: {errore}")
            return
        stato["errori"] = stato.get("errori", 0) + 1
        if stato["errori"] == AVVISO_DOPO_ERRORI:
            invia_telegram("⚠️ Da circa 2 ore non riesco a leggere il sito. Controllerò ancora.")
        salva_stato(stato)
        return

    if stato.get("errori"):
        stato["errori"] = 0

    if primo_avvio:
        stato["visti"] = [link for _, link in articoli]
        salva_stato(stato)
        invia_telegram(
            f"✅ Bot attivo! Controllo il sito ogni 15 minuti "
            f"e ti scrivo quando esce un articolo con \"nomina\" o \"nomine\" nel titolo."
        )
        return

    nuovi = [(t, l) for t, l in reversed(articoli) if l not in stato["visti"]]
    for titolo, link in nuovi:
        stato["visti"].append(link)
        if PAROLA.search(titolo):
            invia_telegram(f"📢 Nuovo documento pubblicato:\n\n{titolo}\n\n{link}")
            print("Avviso inviato:", titolo)

    salva_stato(stato)


if __name__ == "__main__":
    main()
