# Discovery & Strategy Interview Log

This document tracks the evolving vision for Musico based on stakeholder interviews.

---

## 1. Business Model & Onboarding
**Question:** When you move to a full release, do you envision a "Self-Service SaaS" model where any studio owner can sign up, or will it remain "Managed"?

**Answer:**
- **Short Term (Alpha/Beta):** Managed service. The platform owner will provision new studios manually.
- **Goal for Alpha:** Get feedback from specific users (wife and others) to identify "must-have" vs. "unused" features.
- **Long Term:** Transition to a "Self-Service SaaS" with immediate, automatic tenant creation.
- **Speculative Future:** Potential for advanced features like a drag-and-drop editor for studio sites.

---

## 2. Feature Parity & Mobile Usage
**Question:** Do you expect users to do everything from their phones, or is there a split between desktop "Management" and mobile "Operations"?

**Answer:**
- **Mobile-First Mandate:** The platform must be mobile-first.
- **Mobile Use Cases:** Daily operations like checking the schedule and marking attendance must be seamless on phones.
- **Desktop Use Cases:** "Heavy work" (complex management, reporting, large-scale data entry) will likely happen on desktop.

---

## 3. Student Progress & Growth
**Question:** How central is Progress Tracking (practice logs, shared notes, repertoire) to the platform?

**Answer:**
- **Resource Management:** Highly central. Teachers distribute many handouts.
- **Digital Handouts:** The platform must allow easy uploading and distribution of "common sheets" (PDFs, images, etc.).
- **Printing:** Students and parents must be able to view and print these from home.
- **User Personas:** We must support "Adult Learners" (students who manage themselves) as well as the "Student-Parent" pair. Roles should be flexible enough for a student to be their own account manager.

---

## 4. Communication & Notifications
**Question:** How "loud" should the system be regarding updates (lesson changes, new handouts)?

**Answer:**
- **Hybrid Control:** Urgent changes (lesson time shifts) should ideally trigger immediate alerts.
- **Manual Overrides:** Teachers need "Send" or "Send to All" buttons to control the flow.
- **Notification Fatigue:** There is a concern that parents might ignore purely automatic messages. 
- **Future Task:** Need to "iron out" specific triggers and message types before building the full engine to ensure high signal-to-noise ratio.

---

## 5. Payment Workflows & Attendance Policies
**Question:** How do you want to handle "Missed Lessons" and the billing cycle (Pre-paid vs Post-paid)?

**Answer:**
- **Studio Sovereignty:** It is critical that each studio defines its own policies (cancellation windows, makeup credit logic, etc.).
- **Validation:** Billing functionality should potentially be disabled until a studio owner has explicitly configured their "Studio Policy."
- **Future Task:** Design a "Policy Engine" that governs how attendance status (Absent, Cancelled, Makeup) translates into line items on an invoice.

---

## 6. The "Teacher-Studio" Relationship
**Question:** Can a teacher work for multiple studios, and how should their settings (like language) behave across them?

**Answer:**
- **Security First:** Security and data isolation take precedence.
- **Context Separation:** Multi-school users should likely be treated as separate "contexts" for each school.
- **Switching UI:** The platform must allow for very easy switching between schools (Tenant Switcher).
- **Future Task:** Need to refine the boundary between "Global User" settings (email, password) and "Local Membership" settings (role, school-specific preferences).

---

## 7. Data Ownership & Portability
**Question:** If a student leaves a studio, who "owns" the data (lesson notes, repertoire, etc.)?

**Answer:**
- **Deferred Decision:** Need to weigh user expectations (portability) against legal simplicity (ownership).
- **UX Consideration:** What do students/parents actually want?
- **Legal Consideration:** What are the easiest/safest data ownership models for a multi-tenant SaaS (GDPR/CCPA implications)?

---

## 8. Multi-Teacher Studios & Collaboration
**Question:** In a studio with multiple teachers, how much should they share (students, resources)?

**Answer:**
- **Role-Based Privacy:** Admins and Owners have studio-wide visibility.
- **Siloed Teachers:** Staff/Teachers should primarily see their own assigned roster.
- **Permission Tiers:** Need to ensure the `PortalScope` service and template logic strictly enforce these boundaries as we scale.

---

## 9. Student Onboarding & Registration
**Question:** How do new students enter a studio (Manual vs. Public Form)?

**Answer:**
- **Managed Invitation Flow:** Prefer a system where admins "Invite to sign up" rather than a public "Join" form.
- **Role-Specific Invites:** Admins should be able to send dedicated links for "Parent" vs. "Student" roles.
- **Auto-Assignment:** Once a user signs up via an invite link, they should be automatically associated with that school.
- **Future Task:** Design the invitation lifecycle (Invite -> Token -> Sign up -> Membership Activation).

---

## 10. Platform Scope & Integrations
**Question:** Is Musico an "All-in-One" system or a "Hub" for other tools (Google Drive, Zoom, etc.)?

**Answer:**
- **Hub Strategy:** Prefer connecting to external storage (Dropbox, Google Drive) rather than hosting files.
- **Cost Efficiency:** This avoids high storage/bandwidth costs for the platform, which can be passed as savings to the studio owner.
- **Future Task:** Explore OAuth integrations for the "Big Three" storage providers to allow teachers to "attach" existing documents to student profiles.

---

## 11. Money Flow & Stripe Integration
**Question:** In a multi-teacher studio, how does the money flow (Studio-level vs. Direct-to-Teacher)?

**Answer:**
- **Studio-Level Collection:** The studio/owner collects all family payments.
- **Reporting:** Musico should provide the reports needed for the owner to then pay individual teachers outside the platform.
- **Solo Teachers:** For single-teacher studios, the owner and teacher are the same, so "Direct-to-Teacher" is effectively "Studio-Level."

---

## 12. Invitation Lifecycle
**Question:** What are the constraints and requirements for the managed invitation flow?

**Answer:**
- **Simplicity Priority:** Since this is a transitionary feature toward a self-service model, we will build the simplest version possible to minimize future tech debt.
- **Minimal Logic:** Role assignment during invite creation, simple token validation, and one-time use consumption.

---

## 13. Branding & Customization
**Question:** Do you want studio domains to be brandable (logos/colors) or standardized?

**Answer:**
- **Standardized for MVP:** Focus on the Musico brand for the initial release and Alpha.
- **Future Task:** Revisit per-studio branding (colors, logos) once the core product is stable and users are onboarded.

---

## 14. Public Studio Pages
**Question:** Does each studio need its own public landing page, or is their domain strictly a private portal?

**Answer:**
- **Strictly Private:** For the current phase, tenant domains will immediately show a login screen.
- **Future Task:** Revisit the possibility of a "Public Landing Page" or "Website Creator" in a much later release.

---

## 15. Messaging & Conversation Flow
**Question:** Is communication "One-Way" (Announcements/Handouts) or "Two-Way" (Built-in Chat)?

**Answer:**
- **One-Way for Alpha:** Initial communication will be announcements and handouts sent from the teacher to the student/parent.
- **Off-Platform Replies:** Users can respond via existing channels (Email, SMS, WhatsApp) if they need a dialogue.
- **Future Task:** Monitor user feedback to see if built-in two-way chat is a high-demand feature for later releases.

---

**End of Initial Discovery Session (March 2026)**
*This log will be updated as new requirements emerge during development and testing.*
