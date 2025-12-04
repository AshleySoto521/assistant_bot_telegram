# 🤖 Telegram Influencer AI Bot (Smart Handoff 4.0 PRO)

Este es un bot de Telegram avanzado diseñado para influencers y marcas personales. A diferencia de los bots tradicionales, este utiliza **Inteligencia Artificial (Gemini 2.5 Flash)** para "leer la mente" del usuario: distingue automáticamente entre una charla casual y una oportunidad de negocio.

El sistema opera bajo la arquitectura **"Human-in-the-Loop"**: La IA entretiene a la audiencia, pero cuando detecta dinero (intención de compra), le pasa el control al humano.

**Coste de Operación:** 0€ (Usando Free Tier de Google y Hosting Local).

## 🆕 Novedades Versión 4.0

- ⏰ **Horarios Inteligentes**: Configura horarios específicos para publicaciones automáticas
- 📜 **Historial Contextual**: Envío automático del historial de conversación cuando se detecta un lead
- 💎 **Modo PRO Gratuito**: Features adicionales sin costo (memoria conversacional, posts variados)
- 📊 **Estadísticas Avanzadas**: Comando `/stats` para ver métricas del bot
- 🔍 **Ver Historial**: Comando `/historial [user_id]` para revisar conversaciones

## ✨ Características Principales

* **🧠 Cerebro Clasificador (Smart Filter):** Ya no usa listas de palabras tontas. La IA analiza el contexto de cada mensaje.
    * *Ejemplo:* "Tu ropa es linda" -> **IA Responde** (Chat).
    * *Ejemplo:* "Quiero comprar esa ropa" -> **Te avisa a ti** (Venta).
* **🎟️ Sistema de Tickets (/cerrar):** Cuando terminas de atender a un cliente humano, usas un comando para que la IA vuelva a tomar el control de ese usuario automáticamente.
* **📢 Megáfono (/post):** Comando administrativo para enviar anuncios de texto directamente al canal/grupo desde el chat privado del bot.
* **📸 Modo Espejo (Fotos):** Si envías una foto al bot por privado, él la "repostea" en el grupo añadiendo botones de contacto (Call to Action).
* **⏰ Publicador Automático:** Genera temas de conversación picantes/interesantes mediante IA y los publica en el grupo cada 4 horas para mantener el engagement.
* **📂 Base de Datos Local:** Gestión de historial y estados de usuario mediante SQLite (100% privado y sin servidores).

## 🛠️ Requisitos Técnicos

* Python 3.10 o superior.
* Una cuenta de Google AI Studio (API Key de Gemini).
* Un Bot de Telegram (creado con @BotFather).

## 📦 Instalación y Dependencias

1.  **Clonar/Descargar el proyecto** en tu equipo local.
2.  **Instalar dependencias:**
    Abre tu terminal en la carpeta del proyecto y ejecuta:
    ```bash
    pip install -r requirements.txt
    ```
    *Contenido del requirements.txt:*
    ```text
    python-telegram-bot[job-queue]
    google-generativeai
    python-dotenv
    ```

## ⚙️ Configuración (.env)

El proyecto utiliza un archivo de seguridad. Crea un archivo llamado `.env` en la raíz del proyecto y configura tus claves:

```env
# Configuración básica
TOKEN_TELEGRAM=tu_token_aqui
GOOGLE_API_KEY=tu_api_key_de_google
ID_TU_GRUPO=-100xxxxxxxxxx  # ID del grupo (incluir el signo menos)
ID_ADMIN=123456789          # Tu ID personal para permisos admin

# Configuración de horarios (NUEVO en v4.0)
HORA_INICIO_POST=09:00      # Hora inicio publicaciones automáticas
HORA_FIN_POST=21:00         # Hora fin publicaciones automáticas
TIMEZONE=America/Mexico_City # Zona horaria

# Versión PRO - 100% GRATIS (NUEVO en v4.0)
VERSION_PRO=true            # true para activar features PRO sin costo
```

## 🎮 Comandos Disponibles

### Comandos para Usuarios
- `/start` - Inicia la conversación con el bot

### Comandos de Administrador

**Comandos Básicos:**
- `/post [mensaje]` - Publica un mensaje en el grupo con botón de contacto
- `/cerrar` - Cierra un ticket y devuelve el usuario a la IA (responder al mensaje del usuario)

**Comandos Nuevos v4.0:**
- `/stats` - Ver estadísticas completas del bot (usuarios, leads, mensajes, configuración)
- `/historial [user_id]` - Ver el historial de conversación de un usuario específico

### Funciones Automáticas

**Publicaciones con Horario:**
- Las publicaciones automáticas solo se ejecutan dentro del horario configurado
- Si se intenta publicar fuera de horario, se omite automáticamente
- Perfecto para no molestar a tu audiencia de madrugada

**Detección de Leads:**
- Cuando la IA detecta intención de compra/negocio:
  1. Notifica al admin con el mensaje que activó el lead
  2. Envía automáticamente el historial completo de la conversación
  3. Cambia el usuario a modo "humano" para que respondas personalmente

## 💎 Diferencias entre Versión FREE y PRO

| Feature | FREE | PRO |
|---------|------|-----|
| Detección de leads con IA | ✅ | ✅ |
| Publicaciones automáticas | ✅ | ✅ |
| Control de horarios | ✅ | ✅ |
| Envío de historial en leads | ✅ | ✅ |
| Comandos admin (stats, historial) | ✅ | ✅ |
| Memoria conversacional (contexto) | ❌ | ✅ |
| Posts variados y creativos | ❌ | ✅ |
| Análisis mejorado de leads | ❌ | ✅ |
| Personalización avanzada | ❌ | ✅ |
| **Costo** | **GRATIS** | **GRATIS** |

**Nota:** Ambas versiones son 100% gratuitas. La versión PRO simplemente activa features adicionales del modelo de IA sin costos extra.