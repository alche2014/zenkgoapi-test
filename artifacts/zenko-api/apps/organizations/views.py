from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Organization, Membership
from .serializers import OrganizationSerializer, MembershipSerializer


def get_membership(user, org_id):
    """Get user's membership in an org, or return None."""
    try:
        return Membership.objects.get(user=user, organization_id=org_id)
    except Membership.DoesNotExist:
        return None


@api_view(["POST", "GET"])
@permission_classes([IsAuthenticated])
def organizations_list(request):
    if request.method == "POST":
        serializer = OrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = serializer.save(created_by=request.user)
        Membership.objects.create(
            user=request.user,
            organization=org,
            role=Membership.Role.ORG_ADMIN,
        )
        return Response(OrganizationSerializer(org).data, status=status.HTTP_201_CREATED)

    user_org_ids = Membership.objects.filter(user=request.user).values_list("organization_id", flat=True)
    orgs = Organization.objects.filter(id__in=user_org_ids)
    return Response(OrganizationSerializer(orgs, many=True).data)


@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def organization_detail(request, org_id):
    membership = get_membership(request.user, org_id)
    if not membership:
        return Response({"detail": "Not found or not a member."}, status=status.HTTP_404_NOT_FOUND)

    try:
        org = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(OrganizationSerializer(org).data)

    if not membership.is_admin_level:
        return Response({"detail": "Only admins can update organization details."}, status=status.HTTP_403_FORBIDDEN)

    partial = request.method == "PATCH"
    serializer = OrganizationSerializer(org, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(["POST", "GET"])
@permission_classes([IsAuthenticated])
def members_list(request, org_id):
    membership = get_membership(request.user, org_id)
    if not membership:
        return Response({"detail": "Not found or not a member."}, status=status.HTTP_404_NOT_FOUND)

    try:
        org = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        members = Membership.objects.filter(organization=org).select_related("user")
        return Response(MembershipSerializer(members, many=True).data)

    if not membership.is_admin_level:
        return Response({"detail": "Only admins can add members."}, status=status.HTTP_403_FORBIDDEN)

    serializer = MembershipSerializer(data=request.data, context={"organization": org})
    serializer.is_valid(raise_exception=True)
    member = serializer.save()
    return Response(MembershipSerializer(member).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def member_detail(request, org_id, member_id):
    membership = get_membership(request.user, org_id)
    if not membership:
        return Response({"detail": "Not found or not a member."}, status=status.HTTP_404_NOT_FOUND)

    try:
        member = Membership.objects.get(id=member_id, organization_id=org_id)
    except Membership.DoesNotExist:
        return Response({"detail": "Member not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(MembershipSerializer(member).data)

    if not membership.is_admin_level:
        return Response({"detail": "Only admins can modify members."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "PATCH":
        serializer = MembershipSerializer(member, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    member.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
