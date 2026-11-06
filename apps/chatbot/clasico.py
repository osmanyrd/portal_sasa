"""
Chatbot — Motor de búsqueda clásico (sin IA).

Búsqueda por sinónimos, stemming y relevancia, con detección de
intenciones y tolerancia a errores tipográficos.

Se conserva como respaldo del motor RAG: las intenciones cordiales
(saludo, despedida, ayuda, gracias) se responden aquí, y si el motor
RAG falla se usa como fallback final.
"""
import difflib
import logging
import re
import unicodedata

from apps.chatbot.models import DocumentoConocimiento

logger = logging.getLogger(__name__)

# ── Configuración ──────────────────────────────────────────────
UMBRAL_SIMILITUD = 0.15
UMBRAL_FUZZY = 0.72  # ratio mínimo para considerar tokens "parecidos"
MAX_RESPUESTA_DOCUMENTOS = 2

MENSAJE_NO_ENCONTRADO = (
    "Lo siento, no encontré información en el sitio sobre esa consulta. "
    "Probá con alguna de estas opciones o reformulá tu pregunta:"
)

MENSAJE_AYUDA = (
    "Puedo ayudarte con información sobre:\n"
    "**- Servicios** (mantenimiento, reparación, grua, repuestos)\n"
    "**- Ubicación y horarios**\n"
    "**- Contacto y cotizaciones**\n"
    "**- La empresa**\n"
    "Por ejemplo podés preguntarme:"
)

SUGERENCIAS_DEFAULT = [
    "¿Qué servicios ofrecen?",
    "¿Cuáles son sus horarios?",
    "¿Dónde están ubicados?",
    "¿Cómo puedo contactarlos?",
]


def _normalizar(texto):
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\s+", " ", texto)
    texto = re.sub(r"[^\w\s]", " ", texto)
    return texto


def _stem(palabra):
    p = palabra
    if len(p) <= 3:
        return p
    if p.startswith("ubic"):
        return "ubic"
    if p.endswith("es") and len(p) > 4 and not p.endswith("mes") and not p.endswith("tes"):
        base = p[:-2]
        if len(base) > 3:
            p = base
    elif p.endswith("s") and not p.endswith("as") and not p.endswith("es"):
        p = p[:-1]
    for suf in ("aciones", "ación", "cion", "cciones", "ccion", "ciones"):
        if p.endswith(suf) and len(p) > len(suf) + 2:
            p = p[: -len(suf)] + "o"
            break
    return p


PALABRAS_VACIAS = {
    "de", "del", "la", "el", "en", "un", "una", "unos", "unas", "los", "las",
    "que", "es", "se", "no", "por", "con", "para", "al", "lo", "como",
    "mas", "pero", "sus", "le", "ya", "o", "este", "porque", "esta", "son",
    "entre", "cuando", "muy", "sin", "sobre", "tambien", "me", "hasta",
    "hay", "donde", "quien", "desde", "todo", "nos", "durante", "todos",
    "uno", "les", "ni", "contra", "otros", "fue", "ese", "eso", "ante",
    "ellos", "e", "esto", "mi", "antes", "algunos", "que", "unos", "yo",
    "otro", "otras", "otra", "el", "tanto", "esa", "estos", "mucho",
    "quienes", "nada", "muchos", "cual", "poco", "ella", "estar", "estas",
    "algunas", "algo", "nosotros", "mis", "tu", "te", "ti", "tus", "ellas",
    "nosotras", "vosotras", "os", "mio", "mia", "mios", "mias",
    "tuyo", "tuya", "tuyos", "tuyas", "suyo", "suya", "suyos", "suyas",
    "nuestro", "nuestra", "nuestros", "nuestras", "vuestro", "vuestra",
    "puede", "pueden", "puedo", "quiero", "necesito", "quieres", "saber",
    "decir", "hacer", "ir", "venir", "todas", "todos", "cada", "cuales",
    "quien", "cual", "cuando", "cuanto", "cuanta", "porque", "como",
    "usted", "ustedes", "pudiera", "pudieran", "quisiera", "me", "seria",
    "estaria", "estan", "estamos", "este", "esta", "se", "quieren",
}


def _tokenizar(texto):
    tokens = _normalizar(texto).split()
    resultado = set()
    for t in tokens:
        t = _stem(t)
        if t in PALABRAS_VACIAS or len(t) <= 1:
            continue
        resultado.add(t)
    return resultado


# ── Sinónimos y variantes ──────────────────────────────────────
SINONIMOS = {
    "telefon": {"telefon", "tel", "comunica", "llamar", "llama", "llame"},
    "contact": {"contact", "contacto", "comunica", "mensaje", "mensajer", "correo", "email", "mail", "escribir", "llamar", "whatsapp"},
    "correo": {"correo", "email", "mail", "mensaje"},
    "servici": {"servici", "servicio", "ofrece", "ofrecen", "brinda", "brindan", "prestaci", "presta", "hac", "hace", "hacen", "haran", "pueden", "dedican"},
    "mantenimiento": {"mantenimiento", "mantenimient", "revision", "reparacion", "service", "taller"},
    "reparaci": {"reparaci", "reparacion", "arregl", "arreglo", "mecanica", "mecanic"},
    "precio": {"precio", "costo", "cost", "cuanto", "cuanto_cuesta", "cotizacion", "cotiza", "presupuesto", "tarifa", "valor", "pagar", "pago", "cuesta"},
    "cotizaci": {"cotizaci", "cotizacion", "presupuesto", "precio", "tarifa"},
    "horario": {"horario", "horarios", "hora", "abierto", "abren", "abre", "atenci", "atencion", "cierra", "cierre"},
    "ubicaci": {"ubicaci", "ubicacion", "ubic", "donde", "direccion", "direcci", "sucursal", "lugar", "arribar", "llegar", "encuentra", "localiza"},
    "grua": {"grua", "gruas", "remolque", "asistenci", "asistencia", "ayuda", "vial"},
    "vehiculo": {"vehiculo", "vehiculos", "carro", "carros", "auto", "autos", "coche"},
    "repuesto": {"repuesto", "repuestos", "accesorio", "accesorios", "pieza", "piezas", "parte", "partes"},
    "garantia": {"garantia", "garantias", "cobertura", "respaldo"},
    "empresa": {"empresa", "compania", "compani", "sasa", "automotor", "organizaci", "organizacion"},
    "mision": {"mision"},
    "vision": {"vision"},
    "valor": {"valor", "valores", "principio", "principios"},
    "estadistica": {"estadistica", "estadisticas", "dato", "datos", "cifra", "cifras"},
    "parqueo": {"parqueo", "parqueadero", "estacionamiento", "aparcar", "estacionar"},
    "transporte": {"transporte", "transport", "bus", "guagua", "taxi", "omnibus"},
    "diagnostico": {"diagnostico", "computarizado", "scanner", "escane", "chequeo"},
}


def _expandir_sinonimos(tokens):
    expandidos = set(tokens)
    for token in list(tokens):
        for _raiz, variantes in SINONIMOS.items():
            if token in variantes or token == _raiz:
                expandidos |= variantes
    return {t for t in expandidos if t not in PALABRAS_VACIAS and len(t) > 1}


def _coincide_fuzzy(token, lista_fija, umbral=UMBRAL_FUZZY):
    mejor = None
    mejor_ratio = 0.0
    for fija in lista_fija:
        if token == fija:
            return True, fija
        ratio = difflib.SequenceMatcher(None, token, fija).ratio()
        if ratio > mejor_ratio:
            mejor_ratio = ratio
            mejor = fija
    if mejor_ratio >= umbral:
        return True, mejor
    return False, None


# ── Intenciones ────────────────────────────────────────────────
INTENCIONES = []


def _intencion(nombre, patrones, respuesta, sugerencias=None):
    INTENCIONES.append((nombre, patrones, respuesta, sugerencias or []))


_intencion("saludo", [r"^\s*(hola|buen[ao]s?\s+(d[ií]as|tardes|noches)|hey|buenas|saludos)\b"],
           "¡Hola! Soy el asistente virtual de Servicios Automotores S.A. "
           "¿En qué puedo ayudarte?",
           SUGERENCIAS_DEFAULT)

_intencion("gracias", [r"(gracias|muchas gracias|c[oó]mo agradecer|te agradezco)\b"],
           "¡De nada! Estoy para ayudarte. Si necesitás algo más, estoy a tu disposición.")

_intencion("despedida", [r"^\s*(chau|adi[oó]s|hasta luego|nos vemos|hasta pronto|bye)\b"],
           "¡Hasta luego! Gracias por escribirnos. Si tenés otra consulta, aquí estaré.",
           SUGERENCIAS_DEFAULT)

_intencion("ayuda", [r"(qu[eé] puedes hacer|ayuda|opciones|qu[eé] sabes|en qu[eé] me ayudas|qu[eé] información tienes)\b"],
           MENSAJE_AYUDA,
           SUGERENCIAS_DEFAULT)


def _buscar_intencion(pregunta_norm):
    for nombre, patrones, respuesta, sug in INTENCIONES:
        for pat in patrones:
            if re.search(pat, pregunta_norm):
                return nombre, respuesta, sug
    return None, None, None


# ── Categorías ─────────────────────────────────────────────────
PALABRAS_CATEGORIA = {
    "servicios": {"servici", "ofrece", "mantenimiento", "reparaci", "diagnostico", "revision", "service", "grua", "repuesto", "accesorio", "taller", "venta", "comprar", "vehiculo", "arreglo"},
    "contacto": {"contact", "telefon", "correo", "email", "mail", "llamar", "cotizaci", "presupuesto", "mensaje", "whatsapp"},
    "ubicacion": {"ubicaci", "ubic", "ubicad", "donde", "direccion", "sucursal", "parqueo", "transporte", "lugar", "llegar"},
    "empresa": {"empresa", "sasa", "compania", "mision", "vision", "valor", "estadistica", "que es"},
    "general": {"horario", "hora", "abierto"},
}

GENERICO = {
    "empresa", "compania", "compani", "sasa", "automotor", "automotriz",
    "organizaci", "organizacion", "web", "sitio", "informacion", "pagina",
    "pregunta", "necesito", "queremos", "informa",
}

SUGERENCIAS_POR_CATEGORIA = {
    "servicios": [
        "¿Qué servicios ofrecen?",
        "¿Hacen mantenimiento preventivo?",
        "¿Tienen grua o asistencia 24 horas?",
        "¿Venden repuestos y accesorios?",
    ],
    "contacto": [
        "¿Cómo puedo contactarlos?",
        "¿Cuál es el teléfono?",
        "¿Cómo hago una cotización?",
        "¿Cuál es el correo electrónico?",
    ],
    "ubicacion": [
        "¿Dónde están ubicados?",
        "¿Tienen parqueo?",
        "¿Cómo llego en transporte público?",
    ],
    "empresa": [
        "¿Qué es Servicios Automotores S.A?",
        "¿Cuál es la misión de la empresa?",
        "¿Cuál es la visión?",
    ],
    "general": [
        "¿Cuáles son sus horarios de atención?",
        "¿Dónde están ubicados?",
        "¿Cómo puedo contactarlos?",
    ],
}


def _sugerencias_para(categoria):
    return SUGERENCIAS_POR_CATEGORIA.get(categoria, SUGERENCIAS_DEFAULT)


# ── Cache de documentos en el proceso ──────────────────────────
_docs_cache = None
_docs_cache_key = None


def _get_docs():
    global _docs_cache, _docs_cache_key
    seed = DocumentoConocimiento.objects.filter(activo=True).order_by("-ultima_actualizacion")[:1].values_list("id", "ultima_actualizacion")
    clave = tuple(seed)
    if _docs_cache is None or clave != _docs_cache_key:
        _docs_cache = []
        for doc in DocumentoConocimiento.objects.filter(activo=True):
            texto_norm = _normalizar(f"{doc.titulo} {doc.contenido}")
            _docs_cache.append(_PreparadoDocumento(doc, texto_norm, _tokenizar(texto_norm)))
        _docs_cache_key = clave
    return _docs_cache


class _PreparadoDocumento:
    __slots__ = ("doc", "texto_norm", "tokens", "tokens_titulo", "tokens_mapa")

    def __init__(self, doc, texto_norm, tokens):
        self.doc = doc
        self.texto_norm = texto_norm
        self.tokens = tokens
        self.tokens_titulo = _tokenizar(doc.titulo or "")
        self.tokens_mapa = None

    def mapa(self):
        if self.tokens_mapa is None:
            self.tokens_mapa = {t: True for t in self.tokens}
        return self.tokens_mapa


def _agrupar_familias(pregunta_tokens):
    familias = {}
    for t in pregunta_tokens:
        for raiz, variantes in SINONIMOS.items():
            if t in variantes:
                familias[raiz] = variantes | {raiz}
                break
        else:
            familias.setdefault("propio:" + t, {t})
    return familias


def _calcular_similitud(pregunta_tokens, doc, familias):
    if not pregunta_tokens:
        return 0.0
    mapa = doc.mapa()

    coincidencias_familia = 0
    for familia in familias.values():
        if familia & doc.tokens:
            coincidencias_familia += 1
    cobertura = coincidencias_familia / len(familias) if familias else 0.0

    exact = sum(1 for t in pregunta_tokens if t in mapa) / len(pregunta_tokens)

    faltantes = [t for t in pregunta_tokens if t not in mapa]
    fuzzy = 0.0
    if faltantes and doc.tokens:
        aciertos = 0
        for t in faltantes[:6]:
            ok, _m = _coincide_fuzzy(t, doc.tokens)
            if ok:
                aciertos += 1
        fuzzy = min(0.2, 0.5 * (aciertos / len(faltantes[:6])))

    puntuacion = 0.55 * cobertura + 0.35 * exact + fuzzy

    lista_preg = sorted(pregunta_tokens)
    if len(lista_preg) > 1:
        bigramas_preg = {
            f"{lista_preg[i]} {lista_preg[i + 1]}" for i in range(len(lista_preg) - 1)
        }
        doc_lista = sorted(doc.tokens)
        if doc_lista:
            bigramas_doc = {
                f"{doc_lista[i]} {doc_lista[i + 1]}" for i in range(len(doc_lista) - 1)
            }
            coincidentes = bigramas_preg & bigramas_doc
            puntuacion += 0.1 * (len(coincidentes) / len(bigramas_preg))

    puntuacion = min(puntuacion, 1.0)

    no_genericos = [t for t in pregunta_tokens if t not in GENERICO]
    if no_genericos and doc.tokens_titulo:
        hallados_titulo = sum(1 for t in no_genericos if t in doc.tokens_titulo)
        if not hallados_titulo:
            for familia in familias.values():
                if len(familia) <= 4 and familia & doc.tokens_titulo:
                    hallados_titulo = 1
                    break
        if hallados_titulo:
            puntuacion += 0.45 * (hallados_titulo / len(no_genericos))

    return puntuacion


def buscar_respuesta(pregunta):
    """Motor clásico. Devuelve dict con respuesta, documentos, puntuación, etc."""
    pregunta_norm = _normalizar(pregunta)
    nombre_int, resp_int, sug_int = _buscar_intencion(pregunta_norm)
    if resp_int:
        return {
            "respuesta": resp_int,
            "documentos": [],
            "puntuacion": 1.0,
            "respondido": True,
            "sugerencias": sug_int,
            "intencion": nombre_int,
        }

    tokens = _tokenizar(pregunta)
    if not tokens:
        return {
            "respuesta": "¿Podrías escribir tu pregunta de otra forma?",
            "documentos": [],
            "puntuacion": 0.0,
            "respondido": True,
            "sugerencias": SUGERENCIAS_DEFAULT,
            "intencion": None,
        }

    preg_expandidos = _expandir_sinonimos(tokens)
    familias = _agrupar_familias(tokens)
    categoria = _categoria_para_tokens(tokens) or _categoria_para_tokens(preg_expandidos)

    docs = _get_docs()
    resultados = []
    for preparado in docs:
        puntuacion = _calcular_similitud(tokens, preparado, familias)
        if puntuacion < UMBRAL_SIMILITUD:
            continue
        largo = len(preparado.doc.contenido)
        if largo > 100:
            factor = min(1.0, 320.0 / largo)
            puntuacion *= 0.6 + 0.4 * factor
        if preparado.doc.fuente_url and preparado.doc.fuente_url.startswith("#"):
            puntuacion *= 1.25
        if categoria and preparado.doc.categoria == categoria:
            puntuacion *= 1.15
        resultados.append((preparado, puntuacion))

    resultados.sort(key=lambda x: x[1], reverse=True)

    if not resultados:
        return _respuesta_no_encontrada(categoria)

    mejores = resultados[:4]
    mejor_puntuacion = mejores[0][1]

    fragmentos_respuesta = []
    docs_utilizados = []
    urls_ya_agregadas = set()
    textos_vistos = set()

    for preparado, sim in mejores:
        if sim < max(mejor_puntuacion * 0.45, UMBRAL_SIMILITUD):
            continue
        contenido = preparado.doc.contenido.strip()
        contenido_norm = _normalizar(contenido)
        if any(_calcular_similitud(_tokenizar(v), preparado, {}) > 0.75 for v in textos_vistos):
            continue
        if len(contenido) > 400:
            contenido = contenido[:400].rsplit(" ", 1)[0] + "..."
        textos_vistos.add(contenido_norm)

        fragmento = contenido
        if preparado.doc.fuente_url and preparado.doc.fuente_url not in urls_ya_agregadas:
            fragmento += f"\nMás información: {preparado.doc.fuente_url}"
            urls_ya_agregadas.add(preparado.doc.fuente_url)

        fragmentos_respuesta.append(fragmento)
        docs_utilizados.append(preparado.doc)
        if len(fragmentos_respuesta) >= MAX_RESPUESTA_DOCUMENTOS:
            break

    if not fragmentos_respuesta:
        return _respuesta_no_encontrada(categoria)

    if categoria:
        sugerencias = _sugerencias_para(categoria)
    else:
        sugerencias = []
        vistas_titulo = set()
        for preparado, _sim in resultados[1:6]:
            t = preparado.doc.titulo
            if t in vistas_titulo or len(sugerencias) >= 3:
                continue
            vistas_titulo.add(t)
            sugerencias.append(t)
    if not sugerencias:
        sugerencias = SUGERENCIAS_DEFAULT

    return {
        "respuesta": "\n\n".join(fragmentos_respuesta),
        "documentos": docs_utilizados,
        "puntuacion": round(min(mejor_puntuacion, 1.0), 3),
        "respondido": True,
        "sugerencias": sugerencias,
        "intencion": None,
    }


def _categoria_para_tokens(tokens):
    for cat, palabras in PALABRAS_CATEGORIA.items():
        if any(t in palabras for t in tokens):
            return cat
    return None


def _respuesta_no_encontrada(categoria=None):
    return {
        "respuesta": MENSAJE_NO_ENCONTRADO,
        "documentos": [],
        "puntuacion": 0.0,
        "respondido": False,
        "sugerencias": _sugerencias_para(categoria),
    }