from decimal import Decimal
from rest_framework import serializers
from apps.authentication.serializers import UserSerializer
from .models import Objective, KeyResult, KeyResultHistory


class KeyResultHistorySerializer(serializers.ModelSerializer):
    updated_by = UserSerializer(read_only=True)

    class Meta:
        model = KeyResultHistory
        fields = [
            "id", "previous_value", "new_value",
            "previous_rag_status", "new_rag_status",
            "note", "updated_by", "recorded_at",
        ]
        read_only_fields = fields


class KeyResultSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    owner_id = serializers.IntegerField(write_only=True, required=True)
    co_owner = UserSerializer(read_only=True)
    co_owner_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    progress_pct = serializers.SerializerMethodField()
    history_count = serializers.SerializerMethodField()

    class Meta:
        model = KeyResult
        fields = [
            "id", "objective", "title", "metric_label", "type",
            "start_value", "target_value", "current_value", "unit",
            "owner", "owner_id", "co_owner", "co_owner_id",
            "due_date", "weightage", "rag_status",
            "progress_pct", "history_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "rag_status", "objective", "created_at", "updated_at"]

    def get_progress_pct(self, obj):
        return obj.progress_pct

    def get_history_count(self, obj):
        return obj.history.count()

    def _check_org_member(self, user_id, label):
        from apps.organizations.models import Membership
        org = self.context.get("organization")
        if org and not Membership.objects.filter(user_id=user_id, organization=org).exists():
            raise serializers.ValidationError(f"{label} must be a member of this organization.")

    def validate_owner_id(self, value):
        from apps.authentication.models import User
        try:
            User.objects.get(pk=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Owner user not found.")
        self._check_org_member(value, "Owner")
        return value

    def validate_co_owner_id(self, value):
        if value is None:
            return value
        from apps.authentication.models import User
        try:
            User.objects.get(pk=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Co-owner user not found.")
        self._check_org_member(value, "Co-owner")
        return value

    def validate_weightage(self, value):
        if not (0 <= value <= 100):
            raise serializers.ValidationError("Weightage must be between 0 and 100.")
        return value

    def _validate_total_weightage(self, objective, weightage, instance=None):
        """
        Enforce that the total of all sibling KR weightages (including this one)
        equals exactly 100% on every individual create/update operation.
        Skipped during bulk replace (use PUT /key-results/ for multi-KR atomicity).
        """
        if self.context.get("bulk_replace"):
            return
        existing = objective.key_results.all()
        if instance:
            existing = existing.exclude(id=instance.id)
        current_total = sum(kr.weightage for kr in existing)
        new_total = current_total + weightage
        if new_total != 100:
            remaining = 100 - new_total
            raise serializers.ValidationError({
                "error": "Weightage validation failed",
                "current_total": new_total,
                "remaining": remaining,
            })

    def create(self, validated_data):
        from apps.authentication.models import User
        owner_id = validated_data.pop("owner_id")
        co_owner_id = validated_data.pop("co_owner_id", None)
        objective = validated_data["objective"]
        weightage = validated_data["weightage"]

        self._validate_total_weightage(objective, weightage)

        owner = User.objects.get(pk=owner_id)
        co_owner = User.objects.get(pk=co_owner_id) if co_owner_id else None

        kr = KeyResult.objects.create(
            owner=owner,
            co_owner=co_owner,
            created_by=self.context["request"].user,
            **validated_data,
        )
        kr.rag_status = kr.compute_rag()
        kr.save(update_fields=["rag_status"])
        return kr

    def update(self, instance, validated_data):
        from apps.authentication.models import User

        owner_id = validated_data.pop("owner_id", None)
        co_owner_id = validated_data.pop("co_owner_id", None)

        weightage = validated_data.get("weightage", instance.weightage)
        objective = instance.objective
        self._validate_total_weightage(objective, weightage, instance=instance)

        old_value = instance.current_value
        old_rag = instance.rag_status

        if owner_id is not None:
            validated_data["owner"] = User.objects.get(pk=owner_id)
        if "co_owner_id" in self.initial_data:
            validated_data["co_owner"] = User.objects.get(pk=co_owner_id) if co_owner_id else None

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        new_rag = instance.compute_rag()
        instance.rag_status = new_rag
        instance.save()

        new_value = instance.current_value
        if old_value != new_value or old_rag != new_rag:
            KeyResultHistory.objects.create(
                key_result=instance,
                previous_value=old_value,
                new_value=new_value,
                previous_rag_status=old_rag,
                new_rag_status=new_rag,
                note=self.context["request"].data.get("note", ""),
                updated_by=self.context["request"].user,
            )

        return instance


class ObjectiveSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    owner_id = serializers.IntegerField(write_only=True, required=True)
    created_by = UserSerializer(read_only=True)
    progress_pct = serializers.SerializerMethodField()
    key_results = KeyResultSerializer(many=True, read_only=True)
    key_result_count = serializers.SerializerMethodField()

    class Meta:
        model = Objective
        fields = [
            "id", "organization", "title", "description",
            "owner", "owner_id", "priority", "status",
            "due_date", "quarter", "rejection_reason",
            "progress_pct", "key_results", "key_result_count",
            "created_by", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "quarter", "rejection_reason",
            "created_by", "created_at", "updated_at", "organization",
        ]

    def get_progress_pct(self, obj):
        return obj.progress_pct

    def get_key_result_count(self, obj):
        return obj.key_results.count()

    def validate_owner_id(self, value):
        from apps.authentication.models import User
        from apps.organizations.models import Membership
        try:
            User.objects.get(pk=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Owner user not found.")
        org = self.context.get("organization")
        if org and not Membership.objects.filter(user_id=value, organization=org).exists():
            raise serializers.ValidationError("Owner must be a member of this organization.")
        return value

    def create(self, validated_data):
        from apps.authentication.models import User
        from apps.organizations.models import Membership

        owner_id = validated_data.pop("owner_id")
        owner = User.objects.get(pk=owner_id)
        request = self.context["request"]
        organization = validated_data["organization"]

        membership = Membership.objects.filter(
            user=request.user, organization=organization
        ).first()

        if membership and membership.is_admin_level:
            validated_data["status"] = Objective.Status.APPROVED
        else:
            validated_data["status"] = Objective.Status.DRAFT

        return Objective.objects.create(
            owner=owner,
            created_by=request.user,
            **validated_data,
        )

    def update(self, instance, validated_data):
        from apps.authentication.models import User

        owner_id = validated_data.pop("owner_id", None)
        if owner_id is not None:
            validated_data["owner"] = User.objects.get(pk=owner_id)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class ObjectiveListSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    progress_pct = serializers.SerializerMethodField()
    key_result_count = serializers.SerializerMethodField()

    class Meta:
        model = Objective
        fields = [
            "id", "title", "priority", "status", "quarter",
            "due_date", "owner", "progress_pct", "key_result_count",
            "created_at", "updated_at",
        ]

    def get_progress_pct(self, obj):
        return obj.progress_pct

    def get_key_result_count(self, obj):
        return obj.key_results.count()
