import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# Forzamos al cliente a usar la versión v1 explícitamente
client = genai.Client(api_key=api_key, http_options={'api_version': 'v1'})

print(f"--- Probando FORZADO v1 con: {api_key[:5]}... ---")

try:
    # Intentamos con el nombre completo del modelo
    response = client.models.generate_content(
        model='models/gemini-1.5-flash', 
        contents="Hola"
    )
    print("✅ FUNCIONÓ EN v1:", response.text)
    
except Exception as e:
    print(f"\n❌ NI EN V1 FUNCIONÓ")
    print(f"Error: {e}")