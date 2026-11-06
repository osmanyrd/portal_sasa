from django.core.management.base import BaseCommand

from apps.mapa.models import ConfiguracionMapa, Dependencia, Provincia
from wagtail.images.models import Image


# Extensión geográfica de la isla principal de Cuba (grados), usada para
# proyectar lat/lon -> % sobre la imagen real 'Cuba_Provinces-map.png' (1068x409).
# Ajusta estos valores si tu mapa usa otro encuadre.
LON_MIN, LON_MAX = -85.0, -74.1
LAT_MIN, LAT_MAX = 19.7, 23.3


def coordenadas_porcentaje(lat, lon):
    """Convierte (lat, lon) a porcentajes x/y para posicionar el pin."""
    x = round((lon - LON_MIN) / (LON_MAX - LON_MIN) * 100, 1)
    y = round((1 - (lat - LAT_MIN) / (LAT_MAX - LAT_MIN)) * 100, 1)
    # Recortar a 0-100 para no salirse de la imagen
    x = max(0.0, min(100.0, x))
    y = max(0.0, min(100.0, y))
    return int(round(x)), int(round(y))


# Solo nombre y código; las coordenadas van en las dependencias
PROVINCIAS = [
    ("Pinar del Río", "PR"),
    ("Artemisa", "AR"),
    ("La Habana", "LH"),
    ("Mayabeque", "MJ"),
    ("Matanzas", "MT"),
    ("Cienfuegos", "CF"),
    ("Villa Clara", "VC"),
    ("Sancti Spíritus", "SS"),
    ("Ciego de Ávila", "CA"),
    ("Camagüey", "CM"),
    ("Las Tunas", "LT"),
    ("Holguín", "HO"),
    ("Granma", "GR"),
    ("Santiago de Cuba", "SC"),
    ("Guantánamo", "GT"),
    ("Isla de la Juventud", "IJ"),
]

# (codigo_prov, nombre, tipo, direccion, telefono, email, horario, lat, lon)
SAMPLE_DEPS = [
    ("PR", "Sucursal Pinar del Río Centro", "sucursal",
     "Calle Martí #120, Pinar del Río", "+53 877 123456", "sucursal.pr@servauto.cu",
     "Lun-Vie 8:00-17:00", 22.4160, -83.6783),
    ("PR", "Taller Reparaciones San Diego", "taller",
     "Carretera San Diego km 5, Pinar del Río", "+53 877 654321", "",
     "Lun-Sáb 7:00-16:00", 22.4750, -83.7100),
    ("AR", "Sucursal Artemisa", "sucursal",
     "Avenida Julio Antonio Mella #50, Artemisa", "+53 47 334567", "sucursal.ar@servauto.cu",
     "Lun-Vie 8:00-17:00", 22.8130, -82.7578),
    ("AR", "Almacén Central Artemisa", "almacen",
     "Carretera del Nazareno km 2, Artemisa", "+53 47 339876", "",
     "Lun-Vie 7:00-15:00", 22.8200, -82.7700),
    ("LH", "Sucursal Vedado", "sucursal",
     "Calle 23 #60, Vedado, La Habana", "+53 7 8334567", "sucursal.vedado@servauto.cu",
     "Lun-Vie 8:00-18:00, Sáb 8:00-12:00", 23.1370, -82.3810),
    ("LH", "Taller Centro Habana", "taller",
     "Calle G #305 esq. 23, Centro Habana", "+53 7 8621234", "taller.centro@servauto.cu",
     "Lun-Vie 7:30-16:30", 23.1390, -82.3670),
    ("VC", "Sucursal Santa Clara", "sucursal",
     "Calle Marta Abreu #250, Santa Clara, Villa Clara", "+53 42 208000", "sucursal.vc@servauto.cu",
     "Lun-Vie 8:00-17:00", 22.4070, -79.9620),
    ("CM", "Taller Camagüey Norte", "taller",
     "Avenida de la Libertad km 3, Camagüey", "+53 32 291000", "",
     "Lun-Vie 7:00-16:00", 21.3890, -77.9080),
    # ── Santiago de Cuba: 5 dependencias para demostración de badge múltiple ──
    ("SC", "Sucursal Santiago Centro", "sucursal",
     "Avenida de los Libertadores #200, Santiago de Cuba", "+53 22 651234", "sucursal.sc@servauto.cu",
     "Lun-Vie 8:00-17:00", 20.0174, -75.8268),
    ("SC", "Taller Renfe Santiago", "taller",
     "Calle Bernabé Aronaz #312, Santiago de Cuba", "+53 22 645678", "",
     "Lun-Vie 7:00-16:00", 20.0200, -75.8300),
    ("SC", "Almacén Puerto Boniato", "almacen",
     "Carretera de Boniato km 8, Santiago de Cuba", "+53 22 678901", "",
     "Lun-Vie 6:00-14:00", 20.0400, -75.8100),
    ("SC", "Oficina Regional Santiago", "oficina",
     "Avenida Manduley #115, Reparto Sueño, Santiago de Cuba", "+53 22 632100", "oficina.sc@servauto.cu",
     "Lun-Vie 8:00-16:00", 20.0250, -75.8200),
    ("SC", "Sucursal Santiago Sur", "sucursal",
     "Calle Calcagno #305 esq. Sandozag, Santiago de Cuba", "+53 22 649800", "sur.sc@servauto.cu",
     "Lun-Vie 8:00-17:00, Sáb 8:00-12:00", 20.0100, -75.8350),
]


class Command(BaseCommand):
    help = "Carga 16 provincias cubanas y dependencias de ejemplo con coordenadas (%)"

    def handle(self, *args, **options):
        found_image = Image.objects.first()
        if not found_image:
            self.stderr.write(self.style.ERROR(
                "No hay imágenes en Wagtail. Sube al menos una imagen primero."
            ))
            return

        for i, (nombre, codigo) in enumerate(PROVINCIAS):
            provincia, created = Provincia.objects.update_or_create(
                codigo=codigo,
                defaults={
                    "nombre": nombre,
                    "orden": i,
                    "activo": True,
                },
            )
            status = "CREADA" if created else "actualizada"
            self.stdout.write(f"  {status}: {provincia}")

        for (
            prov_codigo, nombre, tipo, direccion, telefono, email,
            horario, lat, lon,
        ) in SAMPLE_DEPS:
            prov = Provincia.objects.get(codigo=prov_codigo)
            px, py = coordenadas_porcentaje(lat, lon)
            dep, created = Dependencia.objects.update_or_create(
                nombre=nombre,
                provincia=prov,
                defaults={
                    "tipo": tipo,
                    "foto": found_image,
                    "posicion_x": px,
                    "posicion_y": py,
                    "descripcion": f"Dependencia de tipo {tipo} en {prov.nombre}.",
                    "direccion": direccion,
                    "telefono": telefono,
                    "email": email,
                    "horario": horario,
                    "latitud": lat,
                    "longitud": lon,
                    "activo": True,
                },
            )
            status = "CREADA" if created else "actualizada"
            self.stdout.write(
                f"  {status}: {dep} @({px}%, {py}%)"
            )

        # Guardar dimensiones de referencia en la configuración
        try:
            conf = ConfiguracionMapa.objects.first()
            if conf:
                conf.ancho_imagen = 1068
                conf.alto_imagen = 409
                conf.save()
        except Exception:
            pass

        self.stdout.write(self.style.SUCCESS("\nDatos de ejemplo cargados."))
