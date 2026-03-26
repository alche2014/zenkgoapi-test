import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


def compute_quarter(date):
    """Return quarter string like Q1-2026 from a date."""
    if date is None:
        return None
    quarter = (date.month - 1) // 3 + 1
    return f"Q{quarter}-{date.year}"


class Objective(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_APPROVAL = "pending_approval", "Pending Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

    class Priority(models.TextChoices):
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="objectives",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="owned_objectives",
    )
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    due_date = models.DateField()
    quarter = models.CharField(max_length=10, blank=True, default="")
    rejection_reason = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_objectives",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "objectives"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.due_date:
            self.quarter = compute_quarter(self.due_date)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def progress_pct(self):
        """
        Weighted average of Key Result progress.
        Returns None if there are no KRs or if KR weightages don't sum to 100.
        """
        krs = list(self.key_results.all())
        if not krs:
            return None
        total_weight = sum(kr.weightage for kr in krs)
        if total_weight != 100:
            return None
        total = 0.0
        for kr in krs:
            total += kr.progress_pct * kr.weightage
        return round(total / 100, 2)


class KeyResult(models.Model):
    class Type(models.TextChoices):
        NUMERIC = "numeric", "Numeric"
        PERCENTAGE = "percentage", "Percentage"
        BOOLEAN = "boolean", "Boolean"
        CURRENCY = "currency", "Currency"

    class RagStatus(models.TextChoices):
        NOT_STARTED = "not_started", "Not Started"
        GREEN = "green", "Green"
        AMBER = "amber", "Amber"
        RED = "red", "Red"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    objective = models.ForeignKey(
        Objective,
        on_delete=models.CASCADE,
        related_name="key_results",
    )
    title = models.CharField(max_length=255)
    metric_label = models.CharField(max_length=255)
    type = models.CharField(max_length=15, choices=Type.choices, default=Type.NUMERIC)
    start_value = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    target_value = models.DecimalField(max_digits=15, decimal_places=4, default=100)
    current_value = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    unit = models.CharField(max_length=50, blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="owned_key_results",
    )
    co_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="co_owned_key_results",
    )
    due_date = models.DateField()
    weightage = models.IntegerField(default=0, help_text="Integer % weight toward parent Objective (all KRs must sum to 100)")
    rag_status = models.CharField(max_length=15, choices=RagStatus.choices, default=RagStatus.NOT_STARTED)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_key_results",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "key_results"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def progress_pct(self):
        """
        Progress as a percentage between 0 and 100.
        For Boolean type: 0 or 100.
        """
        if self.type == self.Type.BOOLEAN:
            return 100.0 if float(self.current_value) >= 1 else 0.0

        start = float(self.start_value)
        target = float(self.target_value)
        current = float(self.current_value)

        if target == start:
            return 100.0 if current >= target else 0.0

        pct = (current - start) / (target - start) * 100
        return max(0.0, min(100.0, round(pct, 2)))

    def compute_rag(self):
        """
        Compute RAG status based on progress.
        Returns RagStatus choice value.
        """
        has_history = self.history.exists()
        if float(self.current_value) == float(self.start_value) and not has_history:
            return self.RagStatus.NOT_STARTED

        pct = self.progress_pct
        if pct >= 100:
            return self.RagStatus.GREEN
        elif pct >= 80:
            return self.RagStatus.AMBER
        else:
            return self.RagStatus.RED


class KeyResultHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key_result = models.ForeignKey(
        KeyResult,
        on_delete=models.CASCADE,
        related_name="history",
    )
    previous_value = models.DecimalField(max_digits=15, decimal_places=4)
    new_value = models.DecimalField(max_digits=15, decimal_places=4)
    previous_rag_status = models.CharField(max_length=15, choices=KeyResult.RagStatus.choices)
    new_rag_status = models.CharField(max_length=15, choices=KeyResult.RagStatus.choices)
    note = models.TextField(blank=True, default="")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="kr_history_entries",
    )
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "key_result_history"
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"KR {self.key_result_id} history @ {self.recorded_at}"
