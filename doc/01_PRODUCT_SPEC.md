# Product Spec (Musico Teach placeholder)

## Product goal

Build a simpler alternative to MyMusicStaff for music teachers and small music schools with better UX and mobile-first daily workflows.

## Primary users

1. Studio owner/admin
2. Teacher
3. Parent
4. Student (secondary at v1)

## Core jobs-to-be-done

1. Manage students/families and contact info.
2. Schedule lessons/events and handle reschedules.
3. Track attendance and notes quickly.
4. Generate invoices and collect payments.
5. Send reminders/messages.
6. Share resources (PDF/files) without heavy workflow.

## Information architecture (v1)

1. Dashboard
2. Students & Families
3. Calendar
4. Invoices & Payments
5. Messaging
6. Resources
7. Settings (studio, billing, domain)

## MVP feature scope

### 1) Tenancy + Roles

1. Tenant isolation by `tenant_id`.
2. Roles: owner/admin, teacher, parent, student.
3. Permission-based route and action controls.

### 2) Students/Families

1. Add/edit/archive students.
2. Family contacts and relationships.
3. Basic tags/notes.

### 3) Calendar

1. Day/week/month views.
2. Lesson/event creation.
3. Recurrence.
4. Attendance status.
5. Reschedule and cancellation flows.

### 4) Invoicing + Payments

1. Create invoices from lessons/manual line items.
2. Status lifecycle: draft/sent/paid/overdue/void.
3. Parent payment via Stripe.
4. Basic ledger and transaction history.

### 5) Messaging + Reminders

1. Email reminders for upcoming lessons/invoices.
2. Template-based notifications.
3. Delivery logs.

### 6) Resources (replace Lending Library complexity)

1. Upload files (PDF/images/audio links).
2. Assign resources to student/family.
3. Parent/student secure access.

## Out of scope for initial release

1. Website builder (full CMS).
2. Lending item inventory workflow.
3. Advanced accounting modules (mileage, tax complexity).
4. Advanced BI/report builder.
5. Deep multi-teacher payroll automation.

## Mobile-first requirements

1. Parent top actions reachable in 1-3 taps:
- view upcoming lesson
- pay invoice
- open shared resource
- send message
2. Teacher top actions reachable in 1-3 taps:
- mark attendance
- add quick note
- send reminder
- reschedule
3. Large tap targets and sticky primary actions.

## Success metrics (first phase)

1. Parent payment completion rate.
2. Reminder delivery success rate.
3. Time-to-attendance-entry per lesson.
4. Weekly active teachers.
5. Support tickets per 100 active users.
