import os
import json

from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY was not found in .env")

client = genai.Client(api_key=api_key)


def build_advisor_prompt(career_gap_data):
    """Convert structured CareerGap evidence into an AI advisor prompt."""
    evidence = json.dumps(career_gap_data, indent=2, ensure_ascii=False)
    return f"""
You are the AI career advisor for CareerGap.

CareerGap is an evidence-based career readiness engine.
Your job is to interpret CareerGap's deterministic evidence and give
clear, practical advice.

IMPORTANT RULES:
- Do not invent skills, market data, projects, or resources.
- Do not change the CareerGap score.
- Treat job importance and market demand as separate evidence.
- A required job skill can be more important than a preferred skill even
  when the preferred skill has stronger market evidence.
- Mention market demand only when CareerGap provides a recorded value.
- Missing market data means UNKNOWN, not zero demand.
- Never claim that a skill is the market's "highest-demand" skill unless
  the provided evidence actually supports that comparison.
- Do not recommend forcing a skill into a project when CareerGap says
  the skill does not meaningfully fit.
- If a project already demonstrates a missing skill, say that it is
  already demonstrated rather than recommending the user add it again.
- Keep advice realistic for a student.

CAREERGAP EVIDENCE:
{evidence}

Give the user:
1. A short assessment of their current position.
2. The most important skill gap, prioritizing job importance first and
   using market demand only as supporting evidence.
3. A practical action plan.
4. Advice about improving existing projects.
5. A short explanation of what they should focus on next.

When discussing market demand, say "recorded market demand" when useful.
Keep the response concise and actionable.
"""


def generate_career_advice(career_gap_data):
    """Generate career advice from structured CareerGap evidence."""
    prompt = build_advisor_prompt(career_gap_data)
    interaction = client.interactions.create(
        model="gemini-3.6-flash",
        input=prompt
    )
    return interaction.output_text
