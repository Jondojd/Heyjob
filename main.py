import os
from fastapi import FastAPI, Query, HTTPException
from typing import List, Dict
from datetime import datetime, timezone, timedelta
import requests

app = FastAPI(title="HeyJob - Job Finder API")

POLE_EMPLOI_CLIENT_ID = os.getenv("POLE_EMPLOI_CLIENT_ID", "")
POLE_EMPLOI_CLIENT_SECRET = os.getenv("POLE_EMPLOI_CLIENT_SECRET", "")

def get_pole_emploi_token() -> str:
    url = "https://entreprise.pole-emploi.fr/connexion/oauth2/access_token?realm=/partenaire"
    data = {
        "grant_type": "client_credentials",
        "client_id": POLE_EMPLOI_CLIENT_ID,
        "client_secret": POLE_EMPLOI_CLIENT_SECRET,
        "scope": "api_offresdemploiv2 o2dsoffre"
    }
    resp = requests.post(url, data=data)
    if resp.status_code == 200:
        return resp.json()["access_token"]
    raise HTTPException(status_code=500, detail="Erreur d'authentification Pôle Emploi")

def fetch_jobs_from_pole_emploi(keyword: str) -> List[Dict]:
    token = get_pole_emploi_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "motsCles": keyword,
        "range": "0-49",  # 50 offres max
        "sort": 1,        # Offres les plus récentes d'abord
    }
    url = "https://api.pole-emploi.io/partenaire/offresdemploi/v2/offres/search"
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération des offres d'emploi")
    jobs = resp.json().get("resultats", [])
    return jobs

def filter_recent_jobs(jobs: List[Dict]) -> List[Dict]:
    now = datetime.now(timezone.utc)
    recent_jobs = []
    for job in jobs:
        date_str = job.get("dateCreation")
        if date_str:
            try:
                date_pub = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z")
            except ValueError:
                try:
                    date_pub = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")
                except Exception:
                    continue
            if (now - date_pub) <= timedelta(minutes=10):
                recent_jobs.append({
                    "title": job.get("intitule"),
                    "company": job.get("entreprise", {}).get("nom"),
                    "location": job.get("lieuTravail", {}).get("libelle"),
                    "published_at": date_str,
                    "url": job.get("origineOffre", {}).get("urlOrigine"),
                    "description": job.get("description")
                })
    return recent_jobs

@app.get("/jobs", summary="Rechercher les offres publiées il y a moins de 10 min")
def search_jobs(q: str = Query(..., description="Mot-clé à rechercher")) -> List[Dict]:
    jobs = fetch_jobs_from_pole_emploi(q)
    recent = filter_recent_jobs(jobs)
    return recent
