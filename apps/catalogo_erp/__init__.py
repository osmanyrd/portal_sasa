"""Aplicación de catálogo de productos conectada al sistema ERP.

El catálogo NO guarda productos locales: solo categorías (snippets). Al
seleccionar una categoría, un modal consulta la disponibilidad real en
PostgreSQL (base ERP) mediante consultas directas, parametrizadas y de
solo lectura.
"""