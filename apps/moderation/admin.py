from django.contrib import admin

from .models import Flag


@admin.register(Flag)
class FlagAdmin(admin.ModelAdmin):
    list_display = ["posting", "reason", "reporter_fingerprint", "created_at"]
    search_fields = ["posting__title", "reporter_fingerprint"]
