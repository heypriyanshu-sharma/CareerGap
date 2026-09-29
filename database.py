import os

import requests
from dotenv import load_dotenv


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv(
    "SUPABASE_PUBLISHABLE_KEY"
)


def save_analysis(
    access_token,
    user_id,
    resume,
    job_description,
    projects,
    analysis,
):
    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/career_analyses",
        headers={
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json={
            "user_id": user_id,
            "resume_text": resume,
            "job_description": job_description,
            "projects": projects,
            "analysis": analysis,
        },
        timeout=10,
    )

def get_analysis_history(access_token):
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/career_analyses",
        headers={
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "Authorization": f"Bearer {access_token}",
        },
        params={
            "select": "id,job_description,analysis,created_at",
            "order": "created_at.desc",
        },
        timeout=10,
    )

    response.raise_for_status()
def get_analysis_history(access_token):
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/career_analyses",
        headers={
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "Authorization": f"Bearer {access_token}",
        },
        params={
            "select": "id,job_description,analysis,created_at",
            "order": "created_at.desc",
        },
        timeout=10,
    )

    response.raise_for_status()

    return response.json()

def delete_analysis(
    access_token,
    analysis_id
):
    response = requests.delete(
        f"{SUPABASE_URL}/rest/v1/career_analyses",
        headers={
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "Authorization": f"Bearer {access_token}",
        },
        params={
            "id": f"eq.{analysis_id}"
        },
        timeout=10,
    )

    response.raise_for_status()

