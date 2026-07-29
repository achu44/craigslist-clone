from django.contrib import admin

from .models import Posting, PostingImage


@admin.register(Posting)
class PostingAdmin(admin.ModelAdmin):
    list_display = ["title", "site", "category", "status", "created_at", "expires_at"]
    search_fields = ["title", "public_id", "contact_email"]


@admin.register(PostingImage)
class PostingImageAdmin(admin.ModelAdmin):
    list_display = ["posting", "sort_order", "created_at"]
    search_fields = ["posting__title"]
