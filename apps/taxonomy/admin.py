from django.contrib import admin

from .models import Category, Channel


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "sort_order"]
    search_fields = ["name", "slug"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "channel", "parent", "price_policy", "is_active"]
    search_fields = ["name", "code", "slug"]
