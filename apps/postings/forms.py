from django import forms
from django.db.models import Count
from django.urls import reverse

from apps.taxonomy.models import Category


class PostingCreateForm(forms.Form):
    """Field-level cleaning only — domain rules (leaf category, price policy, area
    requirement) stay in create_posting() per CLAUDE.md §7."""

    category = forms.ModelChoiceField(queryset=Category.objects.none())
    area = forms.ModelChoiceField(queryset=None, required=False)
    title = forms.CharField(max_length=200)
    body = forms.CharField(widget=forms.Textarea)
    price = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    contact_email = forms.EmailField()
    contact_name = forms.CharField(max_length=100, required=False)
    contact_phone = forms.CharField(max_length=32, required=False)
    show_phone = forms.BooleanField(required=False)
    location_text = forms.CharField(max_length=200, required=False)

    def __init__(self, *args, site, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = (
            Category.objects.filter(is_active=True)
            .annotate(child_count=Count("children"))
            .filter(child_count=0)
        )
        # Category.__str__ is "channel_slug/code" (useful in admin/shell), not fit for
        # a poster-facing dropdown — show the human-readable name instead.
        self.fields["category"].label_from_instance = lambda category: category.name
        # The category select drives an htmx swap of the price field to reflect its
        # price_policy (spec 002 §4.5) — the one thing a static form can't express.
        self.fields["category"].widget.attrs.update(
            {
                "hx-get": reverse("postings:price_field", args=[site.slug]),
                "hx-trigger": "change",
                "hx-target": "#price-field-wrapper",
            }
        )
        if site.areas.exists():
            self.fields["area"].queryset = site.areas.all()
            self.fields["area"].required = True
        else:
            del self.fields["area"]
