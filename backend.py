from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from career_gap import run_careergap


app = FastAPI(
    title="CareerGap API",
    description="Evidence-Based Career Readiness Engine",
    version="1.0.0",
)


# Allow the frontend to communicate with the backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProjectInput(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


class CareerGapRequest(BaseModel):
    resume: str = Field(min_length=1)
    job_description: str = Field(min_length=1)
    projects: list[ProjectInput] = Field(min_length=1)


@app.get("/")
def home():
    return {
        "message": "CareerGap API is running",
        "status": "ok",
    }


@app.post("/analyze")
def analyze(request: CareerGapRequest):
    projects = [
        {
            "name": project.name,
            "description": project.description,
        }
        for project in request.projects
    ]

    try:
        return run_careergap(
            request.resume,
            request.job_description,
            projects,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="CareerGap analysis failed unexpectedly.",
        )