from dataclasses import dataclass

from apps.ops.models import Family, Student
from apps.tenancy.models import Membership

from .models import PortalAccessLink


class PortalAccessError(Exception):
    """Raised when a user has no valid portal access in this tenant."""


@dataclass
class PortalScope:
    family_ids: list[int]
    student_ids: list[int]
    can_view_billing: bool
    can_view_resources: bool


def resolve_portal_scope(*, membership) -> PortalScope:
    role = membership.role
    tenant = membership.tenant

    # Staff roles can access whole tenant datasets.
    if role in {
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
        Membership.Role.STAFF,
        Membership.Role.TEACHER,
    }:
        return PortalScope(
            family_ids=list(Family.objects.filter(tenant=tenant).values_list("id", flat=True)),
            student_ids=list(Student.objects.filter(tenant=tenant).values_list("id", flat=True)),
            can_view_billing=True,
            can_view_resources=True,
        )

    links = PortalAccessLink.objects.filter(
        tenant=tenant,
        user=membership.user,
        is_active=True,
    ).select_related("family", "student")

    if not links.exists():
        raise PortalAccessError("No active portal access link found for this user.")

    family_ids = set()
    student_ids = set()
    can_view_billing = False
    can_view_resources = False

    for link in links:
        if link.family_id:
            family_ids.add(link.family_id)
            family_student_ids = Student.objects.filter(family_id=link.family_id).values_list(
                "id", flat=True
            )
            student_ids.update(family_student_ids)
        if link.student_id:
            student_ids.add(link.student_id)
            if link.student and link.student.family_id:
                family_ids.add(link.student.family_id)

        can_view_billing = can_view_billing or link.can_view_billing
        can_view_resources = can_view_resources or link.can_view_resources

    return PortalScope(
        family_ids=sorted(family_ids),
        student_ids=sorted(student_ids),
        can_view_billing=can_view_billing,
        can_view_resources=can_view_resources,
    )
