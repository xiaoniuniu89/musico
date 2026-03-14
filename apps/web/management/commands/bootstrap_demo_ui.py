from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.growth.models import SiteMenuItem, SitePage
from apps.growth.services import get_or_create_theme, publish_page
from apps.ops.models import Family, Resource, ResourceAssignment, Student
from apps.ops.services import (
    create_event_with_recurrence,
    create_invoice,
    queue_message,
    send_due_messages,
)
from apps.portal.models import PortalAccessLink
from apps.tenancy.models import Membership
from apps.tenancy.services import add_membership, create_tenant_with_owner


class Command(BaseCommand):
    help = "Seed a demo tenant + data for the /app web UI"

    def handle(self, *args, **options):
        user_model = get_user_model()

        owner_email = "owner@musico.local"
        parent_email = "parent@musico.local"
        teacher_email = "teacher@musico.local"
        password = "testpass123"

        owner, _ = user_model.objects.get_or_create(
            email=owner_email,
            defaults={user_model.USERNAME_FIELD: owner_email},
        )
        owner.set_password(password)
        owner.save()

        parent, _ = user_model.objects.get_or_create(
            email=parent_email,
            defaults={user_model.USERNAME_FIELD: parent_email},
        )
        parent.set_password(password)
        parent.save()

        teacher, _ = user_model.objects.get_or_create(
            email=teacher_email,
            defaults={user_model.USERNAME_FIELD: teacher_email},
        )
        teacher.set_password(password)
        teacher.save()

        existing_membership = (
            Membership.objects.filter(
                user=owner,
                tenant__slug="demo-studio",
            )
            .select_related("tenant")
            .first()
        )

        if existing_membership:
            tenant = existing_membership.tenant
        else:
            tenant = create_tenant_with_owner(
                name="Demo Studio",
                slug="demo-studio",
                owner_user=owner,
            ).tenant

        if not Membership.objects.filter(user=teacher, tenant=tenant).exists():
            add_membership(
                user=teacher,
                tenant=tenant,
                role=Membership.Role.TEACHER,
                status=Membership.Status.ACTIVE,
                is_default=not Membership.objects.filter(user=teacher, is_default=True).exists(),
            )

        if not Membership.objects.filter(user=parent, tenant=tenant).exists():
            add_membership(
                user=parent,
                tenant=tenant,
                role=Membership.Role.PARENT,
                status=Membership.Status.ACTIVE,
                is_default=not Membership.objects.filter(user=parent, is_default=True).exists(),
            )

        family, _ = Family.objects.get_or_create(
            tenant=tenant,
            name="Jones Family",
            defaults={"email": parent.email, "phone": "+353870000000"},
        )

        student, _ = Student.objects.get_or_create(
            tenant=tenant,
            family=family,
            first_name="Ruby",
            last_name="Jones",
            defaults={"instrument": "Piano", "level": "Grade 2"},
        )

        now = timezone.now()
        if not tenant.events.exists():
            create_event_with_recurrence(
                tenant=tenant,
                title="Weekly Piano Lesson",
                student=student,
                teacher=teacher,
                created_by=owner,
                start_at=now + timedelta(days=1),
                end_at=now + timedelta(days=1, minutes=45),
                recurrence_type="weekly",
                recurrence_interval=1,
                recurrence_until=(now + timedelta(days=21)).date(),
            )

        if not tenant.invoices.exists():
            create_invoice(
                tenant=tenant,
                family=family,
                due_date=(timezone.localdate() + timedelta(days=7)),
                created_by=owner,
                notes="Demo monthly invoice",
                items=[
                    {
                        "description": "4 x lesson block",
                        "quantity": "4",
                        "unit_price_cents": 3000,
                    }
                ],
            )

        resource, _ = Resource.objects.get_or_create(
            tenant=tenant,
            title="Warmup Routine",
            defaults={"file_path": "resources/warmup-routine.pdf", "uploaded_by": owner},
        )
        if not ResourceAssignment.objects.filter(
            tenant=tenant,
            resource=resource,
            family=family,
            student__isnull=True,
        ).exists():
            ResourceAssignment.objects.create(
                tenant=tenant,
                resource=resource,
                family=family,
                assigned_by=owner,
            )

        PortalAccessLink.objects.get_or_create(
            tenant=tenant,
            user=parent,
            family=family,
            defaults={
                "can_view_billing": True,
                "can_view_resources": True,
                "is_active": True,
                "invited_by": owner,
            },
        )

        if not tenant.messages.exists():
            queue_message(
                tenant=tenant,
                to_email=parent.email,
                subject="Welcome to Musico",
                body="Your parent portal is ready.",
                created_by=owner,
            )
            send_due_messages(tenant=tenant)

        theme, _ = get_or_create_theme(tenant=tenant, updated_by=owner)
        theme.brand_name = "Demo Studio"
        theme.hero_title = "Music Starts Here"
        theme.hero_subtitle = "Book, learn, and grow in one place."
        theme.save()

        page, _ = SitePage.objects.get_or_create(
            tenant=tenant,
            slug="home",
            defaults={
                "title": "Welcome",
                "layout": SitePage.Layout.LANDING,
                "is_homepage": True,
                "is_published": True,
                "content": {"sections": [{"type": "hero", "title": "Learn Music Confidently"}]},
                "updated_by": owner,
            },
        )
        if not page.is_published:
            publish_page(page=page)

        SiteMenuItem.objects.get_or_create(
            tenant=tenant,
            page=page,
            label="Home",
            defaults={"order": 1, "is_visible": True},
        )

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write(self.style.SUCCESS(f"Owner login: {owner_email} / {password}"))
        self.stdout.write(self.style.SUCCESS(f"Parent login: {parent_email} / {password}"))
        self.stdout.write(self.style.SUCCESS(f"Teacher login: {teacher_email} / {password}"))
        self.stdout.write(
            self.style.SUCCESS(
                "Use host demo-studio.teach.localtest.me "
                "(maps to 127.0.0.1) for full tenant-host routing."
            )
        )
