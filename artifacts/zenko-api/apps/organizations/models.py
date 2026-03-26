import uuid
from django.conf import settings
from django.db import models


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_organizations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organizations"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        APP_ADMIN = "app_admin", "App Admin"
        ORG_ADMIN = "org_admin", "Org Admin"
        HR_MANAGER = "hr_manager", "HR Manager"
        TEAM_LEAD = "team_lead", "Team Lead"
        TEAM_MEMBER = "team_member", "Team Member"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.TEAM_MEMBER)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_reports_memberships",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "memberships"
        unique_together = [("user", "organization")]

    def __str__(self):
        return f"{self.user.email} @ {self.organization.name} ({self.role})"

    @property
    def is_admin_level(self):
        return self.role in (self.Role.APP_ADMIN, self.Role.ORG_ADMIN)

    @property
    def can_approve_objectives(self):
        return self.role in (self.Role.ORG_ADMIN, self.Role.TEAM_LEAD)
