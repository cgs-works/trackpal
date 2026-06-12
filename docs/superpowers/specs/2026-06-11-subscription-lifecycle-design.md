# Subscription Lifecycle Actions — Design Spec

**Date:** 2026-06-11  
**Status:** Approved & Implemented

## Summary

Add complete CRUD lifecycle actions to the subscriptions module: Cancel (soft delete), Renew, and Reactivate. All actions include AlertDialog confirmation modals.

## Background

The subscriptions module previously only supported Create, Read (list + reveal credentials), and Update. There was no way to cancel, renew, or reactivate subscriptions from the UI, despite the backend having these endpoints available.

## Backend Endpoints Used

| Action | Endpoint | Method |
|--------|----------|--------|
| Cancel | `/subscriptions/{id}/cancel` | POST |
| Renew | `/subscriptions/{id}/renew` | POST |
| Reactivate | `/subscriptions/{id}/reactivate` | POST |

## Frontend Changes

### 1. API Layer (`subscription-api.ts`)
Added three new API functions:
- `cancelSubscription(id)` → POST cancel endpoint
- `renewSubscription(id)` → POST renew endpoint
- `reactivateSubscription(id)` → POST reactivate endpoint

### 2. New Component: `subscription-lifecycle-dialog.tsx`
A reusable AlertDialog component that handles all three lifecycle actions:
- Props: `action` (cancel/renew/reactivate), `onConfirm`, `loading`
- Displays contextual title and confirmation message per action
- Cancel button uses destructive styling; Renew/Reactivate use default styling
- Shows loading state during API call

### 3. Updated: `subscription-table.tsx`
- Added dropdown menu (⋮ More) to both desktop table rows and mobile cards
- Actions are conditionally shown based on subscription status:
  - **Active**: Renew + Cancel
  - **Expired**: Renew + Reactivate
  - **Cancelled**: Reactivate only
- Cancel action uses destructive variant styling

### 4. Updated: `subscriptions-page.tsx`
- Added lifecycle state management (open, action, subscription, loading)
- Added `openLifecycle()` and `handleLifecycleConfirm()` handlers
- Passes lifecycle callbacks to SubscriptionTable
- Renders SubscriptionLifecycleDialog at page level

### 5. i18n Keys Added
- `frontend.subscriptions.renew_confirm`
- `frontend.subscriptions.yes_renew`
- `frontend.subscriptions.reactivate_confirm`
- `frontend.subscriptions.yes_reactivate`
- `frontend.subscriptions.more_actions`

Added to both EN and ES catalogs.

## UI Behavior

### Desktop
```
[👁 Reveal] [✏️ Edit] [⋯ More]
                        ┌──────────────┐
                        │ 🔄 Renew     │
                        │ ▶️ Reactivate │
                        │──────────────│
                        │ 🚫 Cancel    │
                        └──────────────┘
```

### Mobile
Same dropdown menu appended to the action button row.

### Confirmation Dialog
```
┌─────────────────────────────────────┐
│ Cancel Subscription                 │
│                                     │
│ Are you sure you want to cancel     │
│ this subscription?                  │
│                                     │
│          [Cancel]  [Yes, Cancel]    │
└─────────────────────────────────────┘
```

## Files Modified
1. `backend/app/core/i18n/catalogs_en_frontend.py`
2. `backend/app/core/i18n/catalogs_es_frontend.py`
3. `frontend/src/features/admin/services/subscription-api.ts`
4. `frontend/src/features/admin/components/subscription-table.tsx`
5. `frontend/src/features/admin/components/subscriptions-page.tsx`

## Files Created
1. `frontend/src/features/admin/components/subscription-lifecycle-dialog.tsx`
