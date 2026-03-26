from django.urls import path
from . import views

urlpatterns = [
    path("", views.organizations_list, name="organizations-list"),
    path("<uuid:org_id>/", views.organization_detail, name="organization-detail"),
    path("<uuid:org_id>/members/", views.members_list, name="members-list"),
    path("<uuid:org_id>/members/<uuid:member_id>/", views.member_detail, name="member-detail"),
]
