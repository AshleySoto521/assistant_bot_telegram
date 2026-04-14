import http.client
import json
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# Configuración de la conexión
conn = http.client.HTTPSConnection("generativelanguage.googleapis.com")

# El cuerpo del mensaje en formato JSON puro
payload = json.dumps({
  "contents": [{
    "parts": [{
      "text": "Responde solo con la palabra: EXITO"
    }]
  }]
})

headers = {
  'Content-Type': 'application/json'
}

print(f"Probando conexión directa con: {api_key[:8]}...")

try:
    # Intentamos la ruta v1 (estable) que es la que debería funcionar en 2026
    url = f"/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    conn.request("POST", url, payload, headers)
    res = conn.getresponse()
    data = res.read().decode("utf-8")
    
    json_data = json.loads(data)
    
    if res.status == 200:
        print("✅ ¡CONEXIÓN EXITOSA!")
        print("Respuesta de la IA:", json_data['candidates'][0]['content']['parts'][0]['text'])
    else:
        print(f"❌ ERROR {res.status}")
        print("Causa:", json_data.get('error', {}).get('message', 'Error desconocido'))
        
except Exception as e:
    print(f"❌ Fallo crítico: {e}")
finally:
    conn.close()