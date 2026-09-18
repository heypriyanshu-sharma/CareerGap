import os

from dotenv import load_dotenv
from google import genai


# Load environment variables from .env
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY was not found in .env")


# Create the Gemini client
client = genai.Client(api_key=api_key)


# Send a simple test request
interaction = client.interactions.create(
    model="gemini-3.6-flash",
    input="Say hello to CareerGap in one sentence."
)


# Print Gemini's response
print(interaction.output_text)