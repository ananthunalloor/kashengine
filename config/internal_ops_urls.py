"""Internal URL resolver for Ops handlers reused by the React API."""

from django.urls import include, path

urlpatterns = [path("ops/", include("apps.ops.urls"))]
