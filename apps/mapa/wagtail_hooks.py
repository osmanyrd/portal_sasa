from wagtail import hooks


@hooks.register("insert_editor_js")
def mapa_admin_preview_js():
    """Inyecta JS de vista previa + arrastre de pines en las páginas de edición del admin.
    El script se auto-desactiva salvo en la edición del snippet Provincia
    (cuando existe la sección data-contentpath="dependencias")."""
    return '<script src="/static/mapa/js/mapa_admin_preview.js"></script>'


@hooks.register("insert_global_admin_css")
def mapa_admin_preview_css():
    """Estilos para la vista previa del mapa en el admin."""
    return '<link rel="stylesheet" href="/static/mapa/css/mapa_admin_preview.css">'
