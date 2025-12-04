import os
import google.generativeai as genai
from dotenv import load_dotenv

# Cargar tus claves
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

print("🕵️  Preguntándole a Google qué modelos tienes disponibles...")
print("---------------------------------------------------------")

try:
    modelos = genai.list_models()
    encontrado = False
    for m in modelos:
        # Solo queremos modelos que sirvan para generar texto (generateContent)
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ NOMBRE EXACTO: {m.name}")
            encontrado = True
    
    if not encontrado:
        print("❌ No encontré ningún modelo disponible. Revisa tu API Key.")

except Exception as e:
    print(f"❌ Error grave: {e}")
    print("💡 Pista: Tal vez necesitas actualizar la librería: pip install -U google-generativeai")