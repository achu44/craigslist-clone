from django.urls import path

from . import views

app_name = "postings"

urlpatterns = [
    path("<slug:site_slug>/browse/", views.browse, name="browse"),
    path("<slug:site_slug>/post/", views.create, name="create"),
    path("<slug:site_slug>/post/price-field/", views.price_field_partial, name="price_field"),
    path("<slug:site_slug>/postings/<uuid:public_id>/", views.detail, name="detail"),
    path(
        "<slug:site_slug>/postings/<uuid:public_id>/submitted/<str:token>/",
        views.submitted,
        name="submitted",
    ),
    path(
        "<slug:site_slug>/postings/<uuid:public_id>/confirm/<str:token>/",
        views.confirm,
        name="confirm",
    ),
    path(
        "<slug:site_slug>/postings/<uuid:public_id>/manage/<str:token>/",
        views.manage,
        name="manage",
    ),
    path(
        "<slug:site_slug>/postings/<uuid:public_id>/manage/<str:token>/delete/",
        views.manage_delete,
        name="manage_delete",
    ),
    path(
        "<slug:site_slug>/postings/<uuid:public_id>/manage/<str:token>/renew/",
        views.manage_renew,
        name="manage_renew",
    ),
]
