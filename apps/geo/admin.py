from django.contrib import admin

from .models import Area, Site


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "hostname", "is_active"]
    search_fields = ["name", "slug", "hostname"]


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "site", "sort_order"]
    search_fields = ["name", "slug"]
