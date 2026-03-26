from django.urls import path, include

urlpatterns = [
    path("zenko/api/v1/auth/", include("apps.authentication.urls")),
    path("zenko/api/v1/organizations/", include("apps.organizations.urls")),
    path("zenko/api/v1/", include("apps.okr.urls")),
]
