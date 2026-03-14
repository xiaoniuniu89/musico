# MyMusicStaff Replica - Technical Specification & Analysis

## 1. Project Overview
The goal is to build a modern, intuitive, and high-performance alternative to MyMusicStaff (MMS). The replica will focus on core utility—Student Management, Scheduling, and Billing—while replacing the dated ASP.NET interface with a fast, mobile-first React application.

---

## 2. Functional Modules & Requirements

### A. Dashboard (The Command Center)
*   **Current State:** Widget-heavy, cluttered.
*   **Replica Features:**
    *   **KPI Cards:** Active Students, Projected Monthly Revenue, Outstanding Invoices, Today's Lesson Count.
    *   **Smart Agenda:** Chronological list of today’s events with one-click "Take Attendance" (Present, Absent, Cancelled).
    *   **Quick Actions:** Floating Action Button (FAB) or Header Shortcuts for "Add Student", "Schedule Lesson", "Log Expense".
    *   **Recent Activity:** A feed of latest payments, new registrations, and student notes.

### B. Student Management (CRM)
*   **List View:** Searchable/filterable table with columns for Name, Family, Instrument, Status (Active/Inactive/Lead), and Account Balance.
*   **Student Profile (Deep View):**
    *   **Personal Information:** Full Name, Birthday, Gender, Start Date.
    *   **Family/Billing:** Linked Parent/Guardian profiles for unified invoicing.
    *   **Lesson History:** A log of all past lessons with associated teacher notes.
    *   **Lending Status:** Real-time view of assets (PDFs, Books) currently lent to the student.
    *   **Preferences:** Preferred lesson duration, frequency, and instrument.

### C. Calendar & Scheduling
*   **Views:** Monthly Grid, Weekly Time-Slot (Primary), Daily Agenda.
*   **Event Types:**
    *   **Private Lesson:** 1-on-1 sessions linked to a specific student.
    *   **Group Class:** Multiple students, single teacher.
    *   **Non-Teaching Event:** Recitals, holidays, studio maintenance.
*   **Form Fields (Data Model):**
    *   `TeacherID`, `Visibility` (Public/Private), `Make-up Credit Eligible` (Boolean).
    *   `Online Booking Enabled`, `Attendees` (Multi-select), `Category`.
    *   `StartDateTime`, `Duration` (Minutes), `Recurrence` (Weekly, Bi-weekly, Monthly).
    *   `Pricing Mode` (Studio Base Rate vs. Override Price).
    *   `Public/Private Descriptions`.

### D. Lending Library (Digital Asset Management)
*   **Asset Catalog:** List of books, sheet music (PDFs), instruments, or video lessons.
*   **Lending Workflow:**
    *   `Title`, `Type` (PDF/Book/Hardware), `Publisher`, `Serial Number`.
    *   `AssignedToStudent`, `DateLent`, `DueDate`.
    *   `PublicNote` (Visible to student), `PrivateNote` (Studio only).
    *   `Permissions`: Allow other studio teachers to lend this item.

### E. Financials: Invoicing & Expenses
*   **Automated Billing:** System scans the calendar for "Attended" lessons and generates line items.
*   **Family Accounts:** Unified view of transactions (Charges vs. Payments).
*   **Expense Tracking:**
    *   `Payee`, `Category` (Rent, Supplies, Software), `Amount`, `Date`.
    *   `Recurrence` (Monthly rent, Yearly insurance).
    *   `Attachments`: Upload receipts (PDF/Image).
*   **Integrations:** Stripe, PayPal for direct parent payments.

### F. Business Intelligence (Reports)
*   **Priority Reports:**
    *   **Attendance:** Rate of cancellation vs. attendance.
    *   **Revenue & Expenses:** Profit/Loss statement.
    *   **Student Retention:** Tracking churn over 6-12 month periods.
    *   **Make-Up Credit Balance:** Outstanding credits owed to students.

---

## 3. Proposed Tech Stack

| Layer | Technology | Rationale |
| :--- | :--- | :--- |
| **Frontend** | **Next.js 15 (App Router)** | Performance, SSR for Dashboards, Developer Velocity. |
| **UI Library** | **Shadcn/UI + Radix UI** | Accessible, customizable components; avoids "heavy" UI frameworks. |
| **Styling** | **Tailwind CSS** | Utility-first, mobile-responsive by default. |
| **Database** | **PostgreSQL** | Relational integrity is critical for Families -> Students -> Lessons. |
| **ORM** | **Prisma** | Type-safe queries and easy migrations. |
| **Auth** | **Clerk** or **Auth.js** | Secure multi-tenant login (Studio Owners, Teachers, Parents). |
| **Payments** | **Stripe Connect** | Automated payouts and subscription billing. |
| **File Storage** | **Uploadthing / AWS S3** | Handling Lending Library assets and receipt uploads. |

---

## 4. Key Data Entities (Schema Preview)

```prisma
model Student {
  id            String    @id @default(cuid())
  firstName     String
  lastName      String
  status        Status    @default(ACTIVE)
  familyId      String
  family        Family    @relation(fields: [familyId], references: [id])
  lessons       Event[]
  lendingItems  LendingRecord[]
  createdAt     DateTime  @default(now())
}

model Event {
  id            String    @id @default(cuid())
  title         String?
  start         DateTime
  duration      Int       // Minutes
  isRecurring   Boolean   @default(false)
  attendance    Attendance?
  students      Student[]
  price         Decimal
}

model Invoice {
  id            String    @id @default(cuid())
  familyId      String
  amount        Decimal
  status        InvoiceStatus @default(DRAFT)
  dueDate       DateTime
}
```

---

## 5. Competitive Edge (UX/UI Directions)
1.  **"One-Click" Everything:** Minimize the number of clicks to complete common tasks (e.g., taking attendance should be a swipe or a single tap).
2.  **Parent Portal:** A dedicated, clean mobile app/web view for parents to pay bills and see lesson notes without the clutter.
3.  **Real-Time Sync:** Use WebSockets or Pusher for live calendar updates across different teacher devices.
4.  **Integrated Messaging:** Built-in chat/notices instead of relying on external email for every small update.
