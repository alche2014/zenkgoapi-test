from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.organizations.models import Membership
from .models import Objective, KeyResult, KeyResultHistory
from .serializers import (
    ObjectiveSerializer,
    ObjectiveListSerializer,
    KeyResultSerializer,
    KeyResultHistorySerializer,
)


def get_membership(user, org_id):
    try:
        return Membership.objects.get(user=user, organization_id=org_id)
    except Membership.DoesNotExist:
        return None


# ─────────────────────────── OBJECTIVES ───────────────────────────

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def objectives_list(request, org_id):
    membership = get_membership(request.user, org_id)
    if not membership:
        return Response({"detail": "Not a member of this organization."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        qs = Objective.objects.filter(
            organization_id=org_id
        ).exclude(
            status=Objective.Status.ARCHIVED
        ).select_related("owner").prefetch_related("key_results")
        return Response(ObjectiveListSerializer(qs, many=True).data)

    from apps.organizations.models import Organization
    try:
        org = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        return Response({"detail": "Organization not found."}, status=status.HTTP_404_NOT_FOUND)

    data = request.data.copy()
    data["organization"] = str(org_id)
    serializer = ObjectiveSerializer(
        data=data,
        context={"request": request}
    )
    serializer.is_valid(raise_exception=True)
    objective = serializer.save(organization=org)
    return Response(ObjectiveSerializer(objective, context={"request": request}).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def objective_detail(request, org_id, objective_id):
    membership = get_membership(request.user, org_id)
    if not membership:
        return Response({"detail": "Not a member of this organization."}, status=status.HTTP_403_FORBIDDEN)

    try:
        objective = Objective.objects.get(id=objective_id, organization_id=org_id)
    except Objective.DoesNotExist:
        return Response({"detail": "Objective not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(ObjectiveSerializer(objective, context={"request": request}).data)

    if request.method == "DELETE":
        if not membership.is_admin_level and objective.created_by != request.user:
            return Response({"detail": "You cannot delete this objective."}, status=status.HTTP_403_FORBIDDEN)
        objective.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    if not membership.is_admin_level and objective.owner != request.user and objective.created_by != request.user:
        return Response({"detail": "You cannot edit this objective."}, status=status.HTTP_403_FORBIDDEN)

    if objective.status == Objective.Status.ARCHIVED:
        return Response({"detail": "Archived objectives cannot be edited."}, status=status.HTTP_400_BAD_REQUEST)

    partial = request.method == "PATCH"
    serializer = ObjectiveSerializer(objective, data=request.data, partial=partial, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(ObjectiveSerializer(objective, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def objective_submit(request, org_id, objective_id):
    membership = get_membership(request.user, org_id)
    if not membership:
        return Response({"detail": "Not a member of this organization."}, status=status.HTTP_403_FORBIDDEN)

    try:
        objective = Objective.objects.get(id=objective_id, organization_id=org_id)
    except Objective.DoesNotExist:
        return Response({"detail": "Objective not found."}, status=status.HTTP_404_NOT_FOUND)

    if objective.status != Objective.Status.DRAFT:
        return Response(
            {"detail": f"Only draft objectives can be submitted. Current status: {objective.status}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if objective.created_by != request.user and not membership.is_admin_level:
        return Response({"detail": "You can only submit your own objectives."}, status=status.HTTP_403_FORBIDDEN)

    if membership.is_admin_level:
        objective.status = Objective.Status.APPROVED
    else:
        objective.status = Objective.Status.PENDING_APPROVAL
    objective.save(update_fields=["status", "updated_at"])

    return Response(ObjectiveSerializer(objective, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def objective_approve(request, org_id, objective_id):
    membership = get_membership(request.user, org_id)
    if not membership:
        return Response({"detail": "Not a member of this organization."}, status=status.HTTP_403_FORBIDDEN)

    if not membership.can_approve_objectives:
        return Response(
            {"detail": "Only Team Leads, HR Managers, and Admins can approve objectives."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        objective = Objective.objects.get(id=objective_id, organization_id=org_id)
    except Objective.DoesNotExist:
        return Response({"detail": "Objective not found."}, status=status.HTTP_404_NOT_FOUND)

    if objective.status != Objective.Status.PENDING_APPROVAL:
        return Response(
            {"detail": f"Only pending objectives can be approved. Current status: {objective.status}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    objective.status = Objective.Status.APPROVED
    objective.rejection_reason = ""
    objective.save(update_fields=["status", "rejection_reason", "updated_at"])

    return Response(ObjectiveSerializer(objective, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def objective_reject(request, org_id, objective_id):
    membership = get_membership(request.user, org_id)
    if not membership:
        return Response({"detail": "Not a member of this organization."}, status=status.HTTP_403_FORBIDDEN)

    if not membership.can_approve_objectives:
        return Response(
            {"detail": "Only Team Leads, HR Managers, and Admins can reject objectives."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        objective = Objective.objects.get(id=objective_id, organization_id=org_id)
    except Objective.DoesNotExist:
        return Response({"detail": "Objective not found."}, status=status.HTTP_404_NOT_FOUND)

    if objective.status != Objective.Status.PENDING_APPROVAL:
        return Response(
            {"detail": f"Only pending objectives can be rejected. Current status: {objective.status}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    reason = request.data.get("reason", "")
    if not reason:
        return Response({"detail": "A rejection reason is required."}, status=status.HTTP_400_BAD_REQUEST)

    objective.status = Objective.Status.REJECTED
    objective.rejection_reason = reason
    objective.save(update_fields=["status", "rejection_reason", "updated_at"])

    return Response(ObjectiveSerializer(objective, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def objective_archive(request, org_id, objective_id):
    membership = get_membership(request.user, org_id)
    if not membership:
        return Response({"detail": "Not a member of this organization."}, status=status.HTTP_403_FORBIDDEN)

    if not membership.is_admin_level:
        return Response({"detail": "Only admins can archive objectives."}, status=status.HTTP_403_FORBIDDEN)

    try:
        objective = Objective.objects.get(id=objective_id, organization_id=org_id)
    except Objective.DoesNotExist:
        return Response({"detail": "Objective not found."}, status=status.HTTP_404_NOT_FOUND)

    objective.status = Objective.Status.ARCHIVED
    objective.save(update_fields=["status", "updated_at"])

    return Response(ObjectiveSerializer(objective, context={"request": request}).data)


# ─────────────────────────── KEY RESULTS ───────────────────────────

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def key_results_list(request, org_id, objective_id):
    membership = get_membership(request.user, org_id)
    if not membership:
        return Response({"detail": "Not a member of this organization."}, status=status.HTTP_403_FORBIDDEN)

    try:
        objective = Objective.objects.get(id=objective_id, organization_id=org_id)
    except Objective.DoesNotExist:
        return Response({"detail": "Objective not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        krs = KeyResult.objects.filter(objective=objective).select_related("owner", "co_owner")
        return Response(KeyResultSerializer(krs, many=True, context={"request": request}).data)

    data = request.data.copy()
    data["objective"] = str(objective_id)
    serializer = KeyResultSerializer(data=data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    kr = serializer.save(objective=objective)
    return Response(KeyResultSerializer(kr, context={"request": request}).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def key_result_detail(request, org_id, objective_id, kr_id):
    membership = get_membership(request.user, org_id)
    if not membership:
        return Response({"detail": "Not a member of this organization."}, status=status.HTTP_403_FORBIDDEN)

    try:
        objective = Objective.objects.get(id=objective_id, organization_id=org_id)
    except Objective.DoesNotExist:
        return Response({"detail": "Objective not found."}, status=status.HTTP_404_NOT_FOUND)

    try:
        kr = KeyResult.objects.get(id=kr_id, objective=objective)
    except KeyResult.DoesNotExist:
        return Response({"detail": "Key Result not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(KeyResultSerializer(kr, context={"request": request}).data)

    if request.method == "DELETE":
        if not membership.is_admin_level and kr.created_by != request.user:
            return Response({"detail": "You cannot delete this Key Result."}, status=status.HTTP_403_FORBIDDEN)
        kr.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    partial = request.method == "PATCH"
    serializer = KeyResultSerializer(kr, data=request.data, partial=partial, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(KeyResultSerializer(kr, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def key_result_history(request, org_id, objective_id, kr_id):
    membership = get_membership(request.user, org_id)
    if not membership:
        return Response({"detail": "Not a member of this organization."}, status=status.HTTP_403_FORBIDDEN)

    try:
        objective = Objective.objects.get(id=objective_id, organization_id=org_id)
    except Objective.DoesNotExist:
        return Response({"detail": "Objective not found."}, status=status.HTTP_404_NOT_FOUND)

    try:
        kr = KeyResult.objects.get(id=kr_id, objective=objective)
    except KeyResult.DoesNotExist:
        return Response({"detail": "Key Result not found."}, status=status.HTTP_404_NOT_FOUND)

    history = KeyResultHistory.objects.filter(key_result=kr).select_related("updated_by")
    return Response(KeyResultHistorySerializer(history, many=True).data)
