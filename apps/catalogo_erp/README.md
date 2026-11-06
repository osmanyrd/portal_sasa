# Módulo Catálogo ERP — Servicios Automotores S.A

Catálogo de productos **conectado al ERP de SASA** (PostgreSQL). El sitio solo
almacena *categorías*; la disponibilidad de cada producto se consulta en
tiempo real contra la base del ERP.

## Requisitos

- Django 4+ / Wagtail 5+ (proyecto de desarrollo: Django 5.1 / Wagtail 6.4;
  producción: Django 6.0 / Wagtail 7.4).
- `psycopg2-binary` (ya incluido en `requirements.txt`).
- `cryptography` (cifrado de la contraseña; ya incluido en `requirements.txt`).

## Instalación

```bash
pip install -r requirements.txt
python manage.py migrate                # crea las tablas del módulo
```

Agrega la app en `config/settings/base.py` → `INSTALLED_APPS`:
`"apps.catalogo_erp"`. La URL del API se registra en `config/urls.py`
(`/api/catalogo/buscar/`).

## Configuración contra el ERP real

El comando `configurar_erp_real` crea (o actualiza con `--forzar`) la
configuración, la categoría **Neumáticos** y la página pública:

```bash
# La contraseña se pasa por entorno; nunca se escribe en el código.
set ERP_PASSWORD=...
python manage.py configurar_erp_real --probar --buscar 185
python manage.py configurar_erp_real --buscar 12V --en-todas
python manage.py configurar_erp_real --listar
```

El comando crea las 9 categorías con su consulta de disponibilidad, desactiva
las categorías de ejemplo que apuntan a tablas inexistentes y asegura la
página pública. `--en-todas` prueba el mismo término en cada categoría, útil
para ver cuáles tienen existencias.

Parámetros que usa por defecto (se pueden cambiar con `--host`, `--puerto`,
`--nombre-bd`, `--usuario` o las variables `ERP_HOST`, `ERP_PUERTO`, `ERP_BD`,
`ERP_USUARIO`):

| Dato      | Valor             |
| --------- | ----------------- |
| Host      | `192.168.52.10`   |
| Puerto    | `5432`            |
| Base      | `distra-sasa`     |
| Usuario   | `zeolides`        |
| Contraseña| solo por `ERP_PASSWORD` (se cifra al guardar) |

La contraseña se cifra con `cryptography.fernet` al guardarse; el comando la
toma de `--password` o de `ERP_PASSWORD` y no la escribe en ningún archivo.

La clave de cifrado se deriva de `SECRET_KEY`. En local la `SECRET_KEY` sale de
`.env` y **no debe sobreescribirse** en el lanzador: si `start_server.bat`,
`runserver.py` o la consola definen otra, la contraseña guardada deja de poder
descifrarse y el catálogo responde «la SECRET_KEY del servidor es distinta de
la usada al cifrarla». Si la `SECRET_KEY` cambia, hay que volver a guardar la
contraseña en Configuración ERP.

También se puede hacer todo desde el panel:

1. **Snippets → Configuración ERP**: host, puerto, base, usuario y contraseña de
   un usuario **solo lectura**. Botón **Probar conexión** para verificar.
2. **Snippets → Categorías ERP**: cada categoría define tabla, columnas, método
   de búsqueda y, si hace falta, una **consulta SQL** propia.
3. **Páginas → Catálogo**: la página pública (slug `catalogo`).

## Categoría Neumáticos (consulta real)

Disponibilidad por UEB (dependencia), agregando `dat_producto.disponible`:

- `mod_logistica.dat_producto` → existencias (`disponible`, `idestructura`,
  `idestructuracomun`, `idindicador`).
- `mod_datosmaestros.nom_indicador` → `numeropieza` y `denominacion`.
- `mod_datosmaestros.nom_naturaleza` → `codigo` de la naturaleza.
- `mod_estructuracomp.v_dametodasestructuras` → UEB (`idorgano = -2`) y
  depósito (`idorgano = -1`).
- `mod_logdistribucion.conf_depositopublico` → filtra los depósitos públicos.

Filtra `NOT (disponible = 0)`, agrupa por UEB y muestra hasta 50 dependencias
por consulta (200 en la búsqueda general).

### Categorías configuradas

| # | Categoría | Códigos de naturaleza | Piezas con stock |
|---|-----------|-----------------------|------------------|
| 1 | Neumáticos | `NEU` | 319 |
| 2 | Neumáticos de motocicleta | `NMT` | 75 |
| 3 | Baterías | `BAT`, `BMT` | 144 |
| 4 | Aceites y lubricantes | `GYL` | 317 |
| 5 | Filtros | `FIL` | **0** |
| 6 | Frenos | `FRE` | **0** |
| 7 | Sistema de inyección | `INY` | 377 |
| 8 | Accesorios | `ACC` | 882 |
| 9 | Búsqueda general | (todas) | ~50.000 |

> **Filtros y Frenos devuelven siempre 0 resultados**: el ERP tiene los códigos
> en el maestro (`nom_indicador`) pero **ningún registro** en
> `dat_producto` para esas naturalezas (`filas=0`), así que no hay existencias
> que consultar. Las consultas están correctas y van a funcionar solas en
> cuanto se carguen esos inventarios. Si preferís no mostrarlas al público,
> desactivá esas dos categorías desde el panel.

### Búsqueda por código, nombre y detalle

El buscador usa un **único campo**: el mismo término busca a la vez en el
código (`numeropieza`) y en la descripción (`denominacion`):

```sql
AND (
  NULLIF(:q, '') IS NOT NULL
  AND (
    ind.numeropieza ILIKE '%' || :q || '%'
    OR COALESCE(ind.denominacion, '') ILIKE '%' || :q || '%'
  )
)
```

El placeholder `:q` puede repetirse: cada aparición se parametriza por
separado. Por compatibilidad siguen aceptándose `:q1`/`:q2`/`:q3` (los
usaba el buscador anterior de tres campos).

### Provincia: de dónde sale el stock que se muestra

El ERP **no tiene columna de provincia**. Su unidad responsable de
expendeduría (UEB) solo tiene nombre, en
`mod_estructuracomp.v_dametodasestructuras` con `idorgano = -2`. La provincia
se cruza en Django contra las dependencias que el cliente mantiene en el
panel del mapa:

- `mapa.Dependencia.ueb_erp` guarda el nombre **exacto** de la UEB en el ERP
  (lo llena `sincronizar_uebs`). Si está vacío se compara con el nombre de la
  dependencia, normalizando acentos, mayúsculas y puntuación
  (`AGENCIA CAIBARIEN` empareja con `Agencia Caibarién`).
- Cuando el mapeo ya está sincronizado, solo se usan las UEBs confirmadas: una
  filial o una tienda que no existen en el ERP no hacen aparecer una provincia
  que siempre devolvería cero.
- El filtro se aplica en PostgreSQL envolviendo la consulta de la categoría y
  moviendo el `LIMIT` hacia afuera, para no truncar filas de otras provincias.
  El tope es de **productos**, no de filas: cada fila es un par producto×UEB, así
  que un tope de filas devolvería menos productos en el ámbito nacional (17 UEBs)
  que en una provincia con dos agencias:

```sql
WITH disponibilidad AS ( ...consulta de la categoría... ),
     filtrada AS (SELECT * FROM disponibilidad WHERE "dependencia" IN (%s, %s, ...)),
     elegido AS (SELECT DISTINCT "codigo" FROM filtrada ORDER BY "codigo" LIMIT %s)
SELECT filtrada.* FROM filtrada
INNER JOIN elegido ON elegido.codigo = filtrada."codigo"
ORDER BY filtrada."codigo", filtrada."dependencia"
```

Sync del mapeo (solo lectura del ERP; escribe en la tabla del mapa):

```bash
python manage.py sincronizar_uebs              # simulación: informa qué falta
python manage.py sincronizar_uebs --aplicar    # guarda mapa.Dependencia.ueb_erp
```

UEBs del ERP que hoy no tienen dependencia local: `CASA MATRIZ`, `MYPIME` y
`UNIDAD LOGISTICA CENTRAL`. Las tres son unidades de cobertura nacional, no
agencias de provincia, así que **no se registran como `mapa.Dependencia`**: el
mapa público dibuja todas las dependencias activas y un almacén central no es un
punto de venta. Se controlan en `apps/catalogo_erp/provincias.py`:

- `UEB_SIN_PROVINCIA`: se suman solo en el ámbito nacional. Sin esto sus
  productos son invisibles al filtrar por provincia, y `UNIDAD LOGISTICA CENTRAL`
  es el mayor depósito del ERP (~114.000 unidades solo en la búsqueda `185`).
- `UEB_ASIGNADAS`: UEBs que sí son agencia pero todavía no están en el mapa, con
  la provincia a la que pertenecen. Hoy `AGENCIA PUERTO HABANA` → `LH`. Alguien
  la carga en el panel y la asignación se puede borrar.

### Ámbito nacional

El buscador ofrece `NAC` ("Nacional (todas)") al final del selector: es la unión
de las UEBs de todas las provincias más `UEB_SIN_PROVINCIA`. Es la única forma
de ver el stock de los almacenes centrales y de los productos que solo existen
allí.

Se resuelve antes que una provincia real, así que devuelve `(None, uebs)` y no
un `Provincia`. En la API acepta `NAC`, `nac` o `todas`.

## Seguridad

- Contraseña **cifrada** con `cryptography.fernet` (fallback: cifrado
  autenticado con la biblioteca estándar si la dependencia no está). Al
  descifrarse se compara contra la `SECRET_KEY` del servidor: si no coincide,
  el panel lo avisa en vez de reportar un falso error de red.
- Consultas **parametrizadas**; identificadores citados con `psycopg2.sql`.
- En la consulta personalizada solo se acepta `SELECT`, sin `;`, y los `%`
  literales se escapan como `%%` (psycopg2 los trata como marcas de formato).
- Conexión **solo lectura** con `statement_timeout=20000ms` y
  `connect_timeout=8s`.
- Se **cachean las categorías** (5 min, invalidadas al guardar), nunca los
  resultados del ERP.
- Máx. 50 resultados por consulta (200 en la búsqueda general); errores con
  mensajes claros que distinguen credenciales, red y descifrado, sin exponer
  detalles de conexión.

> **Red:** el ERP `192.168.52.10` no es alcanzable desde el contenedor de
> producción (`192.168.51.3`, sin ruta a `192.168.52.0/24`). Además, la
> conectividad desde la red de desarrollo es intermitente: si el ERP no
> responde, el catálogo avisa "No hay conexión de red con el ERP". El catálogo
> funciona desde la red de desarrollo; para producción hay que habilitar la
> ruta entre ambas redes.

## Endpoint

`GET|POST /api/catalogo/buscar/?categoria_id=<id>&provincia=<codigo>&q=<term>`

- `categoria_id` (obligatorio): pk de una categoría activa.
- `provincia` (obligatorio): código de la provincia (`PR`, `LH`, `MTZ`…) o su
  pk. Define qué UEBs se consideran para la disponibilidad. Sin provincia la
  API responde `{"ok": false, "error": "Elegí la provincia…"}`. `NAC` (también
  `nac` o `todas`) devuelve la disponibilidad nacional: todas las UEBs de
  provincia más los almacenes centrales.
- `q` (obligatorio): término único, buscado en código y descripción. Por
  compatibilidad, si `q` viene vacío se usa el primero informado de
  `q1`/`q2`/`q3`.

Respuesta:

```json
{
  "ok": true,
  "productos": [
    {
      "codigo": "185/65R14ECLC",
      "nombre": "NEUMATICO LIGERO",
      "extra1": "NEUMATICOS PARA VEHICULOS AUTOMOTORES",
      "disponibilidad": [
        {"dependencia": "AGENCIA CAIBARIEN", "cantidad": 20},
        {"dependencia": "UNIDAD LOGISTICA CENTRAL", "cantidad": 24}
      ]
    }
  ],
  "provincia": "PR"
}
```

Las columnas del ERP se localizan **por nombre** (`codigo`, `nombre`,
`dependencia`, `cantidad` y opcionalmente `extra1..3`), así que su orden no
importa. Las cantidades se normalizan a `int`/`float` para que el JSON sea
válido (PostgreSQL devuelve `numeric` como `Decimal`).

Si no hay configuración activa o la consulta falla, devuelve
`{"ok": false, "error": "<mensaje claro>"}`.
## Pruebas

```bash
# Unitarias (no tocan el ERP) + E2E real si se define ERP_PASSWORD
set ERP_PASSWORD=...
python manage.py test apps.catalogo_erp
```

Las pruebas E2E se omiten solas si no hay `ERP_PASSWORD` o el ERP no responde.
