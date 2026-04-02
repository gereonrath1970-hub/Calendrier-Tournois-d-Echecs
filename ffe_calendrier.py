import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.echecs.asso.fr/Calendrier.aspx"

@dataclass
class EvenementCalendrier:
    date: str
    titre: str
    url_source: str
    cadence: str
    lieu: str
    arbitre: str

def classifier_cadence_titre(titre: str) -> str:
    t = titre.lower()
    if "blitz" in t: return "Blitz"
    if "semi-rapide" in t or "semi rapide" in t or "rapide" in t: return "Rapide"
    return "Lente"

def extraire_details(url: str, session: requests.Session):
    """Le robot rentre dans la fiche du tournoi pour lire les détails !"""
    try:
        r = session.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Le site de la FFE utilise ces "ID" spécifiques pour ranger ses textes
        elem_lieu = soup.find(id=re.compile(r"LabelLieu", re.I))
        elem_arbitre = soup.find(id=re.compile(r"LabelArbitre", re.I))
        
        # On extrait le texte, sinon on met "Non précisé"
        lieu = elem_lieu.get_text(" ", strip=True) if elem_lieu else "Non précisé"
        arbitre = elem_arbitre.get_text(" ", strip=True) if elem_arbitre else "Non précisé"
        
        # Si le lieu est vide après nettoyage, on le signale
        if not lieu: lieu = "Non précisé"
        if not arbitre: arbitre = "Non précisé"
            
        return lieu, arbitre
    except:
        return "Information indisponible", "Information indisponible"

def parse_page_jour(html: str, date_iso: str, session: requests.Session) -> list[EvenementCalendrier]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    vu = set()

    for tr in soup.find_all("tr", class_=re.compile(r"liste_clair|liste_fonce")):
        a = tr.find("a", href=re.compile(r"FicheTournoi", re.I))
        if not a: continue
        
        titre = " ".join(a.get_text().split()).strip()
        if not titre or (date_iso, titre) in vu: continue
        vu.add((date_iso, titre))

        lien_specifique = a["href"]
        url_complete = f"https://www.echecs.asso.fr/{lien_specifique}"

        # --- C'EST ICI QU'IL PLONGE DANS LA FICHE ---
        print(f"  🔍 Fouille : {titre[:40]}...")
        lieu, arbitre = extraire_details(url_complete, session)

        out.append(EvenementCalendrier(
            date=date_iso,
            titre=titre,
            url_source=url_complete,
            cadence=classifier_cadence_titre(titre),
            lieu=lieu,
            arbitre=arbitre
        ))
    return out

def iter_evenements(debut: date, fin: date):
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    d = debut
    while d <= fin:
        jour = f"{d.day:02d}/{d.month:02d}/{d.year}"
        url = f"{BASE_URL}?jour={quote(jour, safe='')}"
        print(f"\n📅 Lecture du {jour}...")
        try:
            r = s.get(url, timeout=30)
            r.encoding = r.apparent_encoding or "utf-8"
            for ev in parse_page_jour(r.text, d.isoformat(), s):
                yield ev
        except Exception as e:
            print(f"Erreur sur {jour}: {e}")
        d += timedelta(days=1)

def _main():
    p = argparse.ArgumentParser()
    p.add_argument("--debut", type=str)
    p.add_argument("--fin", type=str)
    p.add_argument("--json", type=str)
    args = p.parse_args()

    debut = datetime.strptime(args.debut, "%Y-%m-%d").date()
    fin = datetime.strptime(args.fin, "%Y-%m-%d").date()

    print(f"🚀 Démarrage du robot FFE du {debut} au {fin}...")
    evts = list(iter_evenements(debut, fin))
    evts.sort(key=lambda e: (e.date, e.titre))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            f.write(json.dumps([asdict(e) for e in evts], ensure_ascii=False, indent=2))
        print(f"\n✅ Terminé : {len(evts)} événements enregistrés avec tous les détails !")

if __name__ == "__main__":
    _main()