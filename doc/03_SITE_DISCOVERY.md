# Discovery Notes from MyMusicStaff

Date of live exploration: 2026-03-06

## Observed top-level modules

1. Home
2. Teachers & Staff
3. Students
4. Calendar
5. Repertoire
6. Lending Library
7. Online Resources
8. Families & Invoices
9. Expenses & Other Revenue
10. Mileage Log
11. Website
12. News & Blog Posts
13. Business Reports

## Observed workflow characteristics

1. Students: multi-step onboarding wizard.
2. Calendar: very dense event form (many controls and options).
3. Families/Invoices: tabbed finance workflow.
4. Lending Library: detailed inventory + lending form; high complexity for many users.
5. Posts: rich editor with many controls.
6. Expenses: manual entry and PDF/photo intake options.

## UX pain points (used for product positioning)

1. Overly broad nav for early-stage users.
2. Form-heavy interactions where quick actions are preferable.
3. Some modules likely overbuilt for solo/small studios.
4. Mobile efficiency likely weaker for high-frequency actions.

## Technical fingerprints observed

1. Frontend appears Angular (ng-version observed as 18.2.14).
2. API traffic to `api.mymusicstaff.com/v1/*`.
3. Legacy endpoints present (`.ashx` handlers).
4. Backend response headers indicate IIS/ASP.NET stack.

## Relevant endpoints seen (for concept only)

1. `/v1/profile/`
2. `/v1/school/`
3. `/v1/membership`
4. `/v1/search/news`

Note: do not replicate endpoint design blindly; define cleaner domain-driven endpoints in Musico Teach.
