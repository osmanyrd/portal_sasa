"""
Comando de administración: ingestar_documentos

Ingesta (o re-ingesta) los documentos de conocimiento: extrae texto, hace
chunking y genera los embeddings. Idempotente por hash de contenido.

Uso:
    python manage.py ingestar_documentos                     # todos los activos
    python manage.py ingestar_documentos --docs 3 5 8        # solo esos ids
    python manage.py ingestar_documentos --fuerza            # re-ingesta aunque no cambió
    python manage.py ingestar_documentos --info              # resumen del estado
    python manage.py ingestar_documentos --pgvector          # habilita pgvector (Postgres)
"""
from django.core.management.base import BaseCommand

from apps.chatbot.embeddings import disponibilidad
from apps.chatbot.ingesta import reingestar_todo
from apps.chatbot.models import ConfiguracionChatbot, DocumentoConocimiento


class Command(BaseCommand):
    help = "Ingesta documentos de conocimiento para el chatbot RAG."

    def add_arguments(self, parser):
        parser.add_argument(
            "--docs",
            nargs="*",
            type=int,
            help="IDs de documentos concretos (vacío = todos los activos).",
        )
        parser.add_argument(
            "--fuerza", action="store_true",
            help="Re-ingesta aunque el hash del contenido no haya cambiado.",
        )
        parser.add_argument(
            "--info", action="store_true",
            help="Muestra el estado de la base de conocimiento y termina.",
        )
        parser.add_argument(
            "--pgvector", action="store_true",
            help="Habilita pgvector en la base (solo PostgreSQL).",
        )

    def handle(self, *args, **options):
        cfg = ConfiguracionChatbot.obtener()

        if options["pgvector"]:
            from apps.chatbot.vectorstore import migrar_pgvector

            if migrar_pgvector(384):
                self.stdout.write(self.style.SUCCESS("pgvector habilitado."))
            else:
                self.stdout.write(self.style.WARNING(
                    "No se pudo habilitar pgvector (requiere PostgreSQL + extensión)."))
            return

        total = DocumentoConocimiento.objects.count()
        activos = DocumentoConocimiento.objects.filter(activo=True).count()

        if options["info"]:
            self._mostrar_info(cfg, total, activos)
            return

        self.stdout.write(self.style.HTTP_INFO(
            f"=== Ingesta de documentos ===  ({activos} activos de {total})\n"))

        resumen = reingestar_todo(doc_ids=options["docs"])
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Ingesta completada: "
            f"{resumen['ok']} ingeridos, {resumen['sin_contenido']} sin contenido util."))
        self.stdout.write(f"Total de fragmentos: {self._count_fragmentos()}.")

    def _mostrar_info(self, cfg, total, activos):
        self.stdout.write("=== Estado del conocimiento ===\n")
        self.stdout.write(f"Documentos totales: {total}  |  activos: {activos}")
        for doc in DocumentoConocimiento.objects.filter(activo=True).order_by("titulo")[:20]:
            frags = doc.fragmentos.count()
            self.stdout.write(
                f"  - {doc.titulo}  [{doc.tipo}]  {frags} fragmentos"
                + ("  (sin ingerir)" if doc.hash_contenido else ""))
        if activos > 20:
            self.stdout.write(f"  ... y {activos - 20} más.")
        self.stdout.write("\n=== Motor de embeddings ===")
        try:
            disp = disponibilidad(cfg)
            self.stdout.write(
                f"Proveedor: {disp['proveedor']}  |  Modelo: {disp['modelo']}  |  "
                f"Dimensión: {disp['dimension']}"
                + ("  (degradado a hash)" if disp.get("degradado") else ""))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"No se pudo inspeccionar el embedder: {exc}"))
        self.stdout.write(f"\nProveedor LLM: {cfg.proveedor_llm}  |  "
                          f"Modelo: {cfg.llm_modelo_efectivo()}")

    def _count_fragmentos(self):
        from apps.chatbot.models import FragmentoDocumento

        return FragmentoDocumento.objects.count()