from rest_framework import serializers
from apps.authentication.serializers import UserSerializer
from .models import Organization, Membership


class OrganizationSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "name", "description", "created_by", "member_count", "created_at", "updated_at"]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def get_member_count(self, obj):
        return obj.memberships.count()


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id", "user", "user_id", "organization_name",
            "role", "manager", "joined_at",
        ]
        read_only_fields = ["id", "joined_at", "organization_name"]

    def validate_user_id(self, value):
        from apps.authentication.models import User
        try:
            User.objects.get(pk=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")
        return value

    def validate(self, data):
        organization = self.context.get("organization")
        user_id = data.get("user_id")
        if organization and user_id:
            if Membership.objects.filter(user_id=user_id, organization=organization).exists():
                raise serializers.ValidationError(
                    {"user_id": "This user is already a member of this organization."}
                )
        return data

    def create(self, validated_data):
        from apps.authentication.models import User
        user_id = validated_data.pop("user_id")
        user = User.objects.get(pk=user_id)
        organization = self.context["organization"]
        return Membership.objects.create(user=user, organization=organization, **validated_data)
