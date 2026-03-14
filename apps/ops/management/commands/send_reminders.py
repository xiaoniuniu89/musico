from django.core.management.base import BaseCommand

from apps.ops.services import run_reminders_job


class Command(BaseCommand):
    help = "Queue and send due lesson reminder emails"

    def add_arguments(self, parser):
        parser.add_argument("--hours-ahead", type=int, default=24)

    def handle(self, *args, **options):
        hours = options["hours_ahead"]
        run = run_reminders_job(hours_ahead=hours)
        self.stdout.write(
            self.style.SUCCESS(
                f"run_id={run.id} status={run.status} queued={run.queued_count} "
                f"processed={run.processed_count} sent={run.success_count} "
                f"failed={run.failure_count} retry_scheduled={run.retry_scheduled_count}"
            )
        )
