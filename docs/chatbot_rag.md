# Chatbot RAG — Instalación y configuración

Asistente virtual de Servicios Automotores S.A. basado en **RAG** (Recuperación +
Generación) sobre la base de conocimiento del sitio, embebido como widget
flotante y administrado desde el panel Wagtail.

## Arquitectura

```
Widget (HTML/JS/CSS)  →  /api/chatbot/consulta/  →  orquestador (ia.py)
                                                        ├─ moderación (seguridad.py)
                                                        ├─ búsqueda vectorial (vectorstore.py)
                                                        ├─ embeddings (embeddings.py)
                                                        └─ generación LLM (llm_cliente.py)
                                                              ├─ Ollama / LM Studio / OpenAI / Anthropic
                                                              └─ respuesta local (sin dependencias)
```

- Los documentos se guardan en `DocumentoConocimiento`; al guardar se extrae el
  texto (PDF/DOCX/TXT/MD/URL/manual), se parte en `FragmentoDocumento` con su
  vector y se persiste un hash para re-ingestar solo cuando cambia.
- **Sin dependencias obligatorias**: embeddings `hash` locales y respuesta
  compuesta local. *Opcionales*: `pdfplumber|pypdf`, `python-docx`,
  `sentence-transformers`, `ollama`, `openai`.

## Instalación

1. Aplicar migraciones:

   ```bash
   python manage.py migrate
   ```

2. Indexar la base de conocimiento (fragmentos clásicos + páginas Wagtail):

   ```bash
   python manage.py indexar_contenido
   ```

3. Ingestar los documentos al RAG (extracción + embeddings):

   ```bash
   python manage.py ingestar_documentos
   # Estado:  python manage.py ingestar_documentos --info
   # Re-ingesta forzada: --fuerza  |  por ids: --docs 3 5 8
   ```

4. (Opcional) Conectar un LLM:

   - **Ollama** (local): `ollama pull llama3.2`, URL `http://localhost:11434`.
   - **LM Studio**: URL `http://localhost:1234/v1`, elegir el modelo local.
   - **OpenAI**: API key y URL `https://api.openai.com/v1`.
   - **Anthropic**: API key y URL `https://api.anthropic.com/v1`.
   - Sin LLM el chatbot responde con el componedor local (fragmentos + fuentes).

5. (Opcional) Embeddings semánticos:

   - `hash` (por defecto): funciona siempre, sin instalar nada.
   - `sentence_transformers`: `pip install sentence-transformers` y elegir el
     modelo en el panel (ej. `paraphrase-multilingual-MiniLM-L12-v2`).
   - `ollama` / `openai`: servidor en línea (igual que el LLM).
   - `pgvector`: con PostgreSQL, `python manage.py ingestar_documentos --pgvector`
     y `CHATBOT_VECTOR_DB=pgvector`.

## Configuración (panel)

`Ajustes → Chatbot IA` (`ConfiguracionChatbot`):

- Mensajes de bienvenida / no encontrado / error / escalado.
- Proveedor, modelo, URL y API key (cifrada con `SECRET_KEY`) del LLM.
- Proveedor de embeddings, umbral de similitud (0.30) y límite de fragmentos.
- Prompt del sistema editable, máx. mensajes por sesión y por pregunta.
- Moderación de contenido y caché de respuestas (1 h).

## Endpoints API

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/chatbot/consulta/` | `{pregunta, session_id}` → respuesta + fuentes + `escalable` |
| POST | `/api/chatbot/feedback/` | `{session_id, valoracion: up\|down}` (o `puntuacion` 1-5) |
| POST | `/api/chatbot/escalar/` | `{session_id, nombre?, telefono?, motivo}` → crea `LeadChatbot` |
| POST | `/api/chatbot/historial/` | `{session_id}` → últimos mensajes de la sesión |
| POST | `/api/chatbot/limpiar/` | `{session_id}` → cierra la sesión |
| GET | `/api/chatbot/info/` | Config pública del widget (sin secretos) |

## Widget

Se incluye con `{% include "chatbot/widget.html" %}` (ya está en
`base_automotive.html`): botón flotante, chat claro/oscuro, feedback 👍/👎,
citas de fuentes, chips de sugerencias, historial por sesión y formulario de
escalado a un asesor humano.

## Panel de administración

Menú **Chatbot IA** → **Dashboard** (`/cms/chatbot/dashboard/`):

- Métricas: consultas hoy/ayer, % contestadas, tasa de utilidad, leads pendientes.
- Exportación CSV de conversaciones y acción de re-ingesta.
- Listados: documentos, fragmentos, conversaciones, mensajes, leads y registros.

## Seguridad

- Moderación de contenido (palabras prohibidas, fuga de prompt / jailbreak,
  intentos de revelar datos personales). Se bloquea la pregunta y se sugiere
  escalar a un humano.
- Límite de preguntas por IP (`cache` de Django), máx. de caracteres y de
  mensajes por sesión.
- La API key se cifra con `django.core.signing`; nunca se expone por API.
- El aviso de privacidad se muestra en el widget.

## Extensión

- Documentos: subir archivos o pegar texto desde `Snippets → Documentos de
  conocimiento`; el guardado re-ingesta automáticamente (idempotente por hash).
- Idiomas: el bot detecta es/en por *stop words* y la configuración es por
  sitio (Wagtail `BaseSiteSetting`).