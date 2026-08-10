---
name: frontend-design-system
description: Use whenever building, redesigning, or extending any screen/component in frontend/ — new pages, new CrudTable lookups, new dialogs, new form layouts — so the visual design (colors, typography, spacing, component look) stays consistent with what's already shipped. Load before writing JSX/CSS for a new frontend screen, not for backend work.
---

# Frontend Design System

This documents the **visual design language** actually implemented in `frontend/` as of Phase 0 — the look, not the architecture. `CLAUDE.md` §3 remains the authority on folder structure, layering, and code shape (pages → containers → components → hooks → services); this skill is the companion doc for *how it should look* so new screens in later phases (catalog, purchasing, cargo, inventory, sales, payments, expenses, reporting) match rather than drift.

Stack this design sits on: **shadcn/ui** (Radix primitives + Tailwind v4, CSS-first config — no `tailwind.config.js`), **lucide-react** icons, **react-hot-toast**, Geist Variable font. If a new primitive is needed, install it via `npx shadcn@latest add <name>` from `frontend/` — don't hand-roll what shadcn already provides — then strip its unused `import * as React from "react"` (React 19's JSX transform doesn't need it; every existing primitive has already had this removed) and match its styling to the conventions below.

## Design direction & rationale

Researched against 2026 B2B/wholesale admin-dashboard and SaaS-login design trends before implementing (not guessed) — chromatic, purposeful color over generic flat grays; a branded split-screen login over a bare centered form; card-based, icon-labeled sections over plain unstyled tables. The business is a China↔Pakistan mobile-accessories trading operation, so the palette leans **trust + trade**: a deep indigo/blue primary (professionalism, finance) with a warm gold accent (currency/exchange), not the generic default shadcn neutral gray-on-gray.

## Color tokens

Defined in `frontend/src/index.css`, OKLCH throughout, full light + dark pairs (never add a color with only one mode defined). Semantic tokens (`--primary`, `--muted`, `--accent`, etc.) follow shadcn's standard naming — don't invent parallel ad hoc color variables for things a semantic token already covers.

| Token | Light | Role |
|---|---|---|
| `--primary` | `oklch(0.47 0.19 264)` — deep indigo-blue | Brand color: primary buttons, links, active nav state, logo badge, hero gradient |
| `--gold` / `--gold-foreground` | `oklch(0.78 0.15 75)` | **Custom token, not a shadcn default** — sparing accent use only: hero-panel highlight dot, radial gradient blob. Not used for hover states or general UI (that's what `--accent` is for) |
| `--accent` / `--accent-foreground` | `oklch(0.945 0.02 264)` | Subtle neutral-ish hover/active background (nav item hover, active tab) — stays close to neutral so it doesn't compete with `--primary` |
| `--destructive` | unchanged from shadcn default (`oklch(0.577 0.245 27.325)`) | Destructive actions/errors only |
| `--radius` | `0.75rem` (bumped from shadcn's default `0.625rem`) | Slightly softer/friendlier corners app-wide |

`--gold` is exposed as a Tailwind utility via `@theme inline`'s `--color-gold`/`--color-gold-foreground` mapping, so it's usable as `bg-gold`, `text-gold-foreground`, etc. Any new one-off brand color follows this same pattern (define in `:root`/`.dark`, map through `@theme inline`) rather than inlining a raw `oklch(...)` value in a component.

**When extending the palette** (e.g. a status color for a future "PO status" badge): pick an OKLCH hue that reads as intentional against the indigo/gold pair — don't drop in an arbitrary saturated color per PLAN.md's later-phase entities without checking it against this pair first.

## Typography

Geist Variable (`@fontsource-variable/geist`), loaded once in `index.css`. Headings use `font-heading` (mapped to the same font — no separate display face). Don't introduce a second typeface.

## Brand identity

- **Name**: "Trading System" — used verbatim in `index.html`'s `<title>`, `Navbar.jsx`, `Footer.jsx`, and the auth split-panel. Keep this consistent; don't rename in one place without the others.
- **Logo mark**: `ArrowLeftRight` (lucide-react) in a rounded-square colored badge — represents the RMB↔PKR exchange at the center of the business. Used in: `Navbar.jsx` (bg-primary badge), `AuthLayout.jsx` (white/15 badge on the gradient panel, primary badge on the mobile fallback header), and `public/favicon.svg` (hand-drawn as static SVG paths matching lucide's `arrow-left-right` glyph, on a `#4338ca` rounded-square background — the closest hex approximation of `--primary` for a context where CSS variables aren't available).
- Don't introduce a second icon as "the" logo elsewhere — `ArrowLeftRight` is it.

## Layout patterns

### Auth pages — split screen (`components/auth/AuthLayout.jsx`)

Left panel (`hidden lg:flex`, mobile-first — hidden by default, shown at `lg:`): full-bleed `bg-linear-to-br from-primary to-[oklch(0.3_0.14_264)]` gradient, a decorative radial-gradient overlay (white blob top-left, `var(--gold)` blob bottom-right, low opacity), logo mark + wordmark, a headline + 2–3 bullet highlights (gold dot markers), a tagline footer. Right panel: centered card (`rounded-xl border bg-card p-6 shadow-sm sm:p-8`), `title` + optional `description`, form content, optional `footer` slot below the card for "Forgot password? / Back to sign in"-style links. On mobile, the left panel disappears entirely and a small inline logo+wordmark row appears above the card instead — never show a placeholder or truncated version of the hero panel.

Every one of `SignIn`/`SignUp`/`ForgotPassword`/`ResetPassword` follows this exact shape: `<AuthLayout title=... description=... footer={<Link .../>}>`. A new auth-adjacent screen (if one is ever added) should too.

### App shell — self-hiding chrome (`components/Navbar.jsx`, `components/Footer.jsx`)

Both `Navbar` and `Footer` call `useAuth()` and `return null` when `status !== 'authenticated'` — they simply don't render on the auth pages, so the split-screen login stays full-bleed with no competing chrome. This is deliberate: don't wrap them in a route-based conditional in `App.jsx` instead — keep the self-hiding logic in the component itself, matching the existing pattern.

`Navbar` is `sticky top-0 z-40 bg-background/95 backdrop-blur-sm`, with: logo badge + wordmark on the left, centered nav links using `NavLink` (active state = `bg-accent text-accent-foreground`, inactive = `text-muted-foreground hover:bg-accent hover:text-accent-foreground`), and on the right an account menu — a circular `Avatar`/`AvatarFallback` showing the signed-in user's initials (`utils/stringUtils.js`'s `getInitials`), wrapped in a `DropdownMenu` (`DropdownMenuTrigger asChild` around a bare focus-ringed `<button>`, never the `Avatar` itself as the trigger). The menu opens with a `DropdownMenuLabel` ("Signed in as {username}") and a `DropdownMenuItem` for Sign out, which opens the existing `ConfirmDialog` rather than signing out directly. This avatar menu is visible at every breakpoint — it is not part of what collapses on mobile. Below `md`, only the nav *links* collapse into a panel toggled by a separate `Menu`/`X` icon button next to the avatar (per CLAUDE.md §3.7's non-negotiable mobile nav collapse); don't fold sign-out into that links panel — the avatar menu already covers it at every width.

`main` in `App.jsx` carries `bg-muted/30` — a faint tint so white `Card`s (see below) have visible separation from the page background. Don't remove this or cards will look like they're floating on an identical white background.

### Content pages — header + Card sections (`containers/SettingsContainer.jsx` pattern)

Every authenticated page follows: a plain page header (`text-2xl font-semibold tracking-tight` title + `text-sm text-muted-foreground` one-line description, no card around the header itself), then the actual content inside one or more `Card`s. For a tabbed page, `TabsTrigger`s carry a small leading icon (`size-4`) alongside the label — don't ship a text-only tab if the page has more than one.

## Component conventions

### CrudTable (`components/common/CrudTable.jsx`) — the pattern every lookup/list screen follows

A `Card` with:
- `CardHeader` (bordered bottom): an icon badge (`size-9 rounded-lg bg-primary/10 text-primary`, icon `size-4.5`) + `CardTitle`/`CardDescription`, and a `CardAction` slot holding the primary "Add" button (`<Plus />` + label, default button size).
- `CardContent`: the table itself inside `overflow-x-auto rounded-lg border` (CLAUDE.md §3.7 non-negotiable — every table gets this, even a 2-column one, on principle), header row `bg-muted/50`, body rows `hover:bg-muted/40`. Row actions are **icon-only ghost buttons** (`variant="ghost" size="icon-sm"`, `Pencil`/`Trash2`, `Trash2` tinted `text-destructive`) — always with an `aria-label` describing the action + entity (e.g. `Edit exchange rate`), never a bare icon with no accessible name. Below the table: `PaginationControls`.
- Three explicit states, each spanning the full row width (`h-32 text-center`, not left-aligned filler text): **loading** (`Loader2` spinning + "Loading…"), **error** (destructive-colored text), **empty** (`Inbox` icon dimmed + "No records yet — add the first one above."). A new list screen must implement all three, not just the happy path.

Config-driven: `CrudTable` takes `{config, title, description, icon, addLabel, entityLabel}` — `entityLabel` is the *singular* lowercase form ("exchange rate", not "Exchange Rates") used to build action labels, the drawer heading, and the delete-confirm wording. Always pass it; don't let it fall back to the generic "record" default for a real screen.

### Dialogs — one generic primitive, two named wrappers

`components/common/ConfirmDialog.jsx` is the base: `title`, `description`, `confirmLabel`/`pendingLabel`, `confirmVariant` ('default' | 'destructive'). When `confirmVariant="destructive"`, it automatically renders a `TriangleAlert` icon in a `bg-destructive/10` circle next to the title — don't pass an icon explicitly, it's derived from the variant.

`ConfirmDeleteDialog.jsx` wraps it for the delete case (destructive, "This soft-deletes the record..." copy). Any other confirm-before-action need (sign-out is the existing example, in `Navbar.jsx`) should call `ConfirmDialog` directly with its own title/description — **don't** create a third named wrapper unless the wording is reused in more than one place, and **always** close the dialog's own `open` state inside the confirm handler before/alongside triggering the action itself (a handler that only calls the action and never sets `open` false will leave the dialog "open" in component state — if the triggering component conditionally returns `null` rather than unmounting, as `Navbar` does, the dialog reappears next time that component renders real content again; this exact bug happened once with sign-out and was fixed by closing the dialog inside the confirm handler).

### Add/edit drawers (`components/common/CrudDrawer.jsx`)

A `Sheet` (not a `Dialog`) for add/edit — reserve `Dialog` for confirmations. Heading is `Add {entityLabel}` / `Edit {entityLabel}` with a one-line `SheetDescription`. Footer is `Cancel` (outline) + `Save` (default, shows "Saving…" while pending) side by side, right-aligned. A field marked `editableOnUpdate: false` in its config renders `disabled` in edit mode via the `Controller`'s `disabled` prop — this is also what keeps that field out of the submitted payload (RHF drops disabled fields from `handleSubmit`'s output), which matters when the backend's `Update` schema doesn't accept that field at all.

### Buttons

- Primary form-submit CTAs (sign in, sign up, etc.): `size="lg" className="w-full"` — full-width, prominent.
- Card-header "Add" actions: default size, icon + label (`<Plus />` then text).
- Table row actions: `variant="ghost" size="icon-sm"`, icon only, `aria-label` required.
- Dialog/drawer secondary actions ("Cancel"): `variant="outline"`.
- Destructive confirm ("Delete"): `variant="destructive"`.

### Icons

lucide-react throughout, no other icon set. Default inline icon size is whatever the primitive already sets (buttons auto-size their child `svg` via `[&_svg:not([class*='size-'])]:size-4`) — only add an explicit `size-*` class when the icon sits outside a styled primitive (e.g. inside a colored badge span) or needs to be larger/smaller than that default.

### Toasts

`react-hot-toast`'s `<Toaster/>` (mounted once, in `main.jsx`) is themed via `toastOptions` to match the app rather than left at its plain default: background/color/border pull from the `--card`/`--card-foreground`/`--border` tokens, `border-radius: var(--radius-md)`, a soft shadow, and success/error icon colors tied to `--primary`/`--destructive`. If `<Toaster/>` is ever re-mounted or reconfigured, keep this `toastOptions` block — a plain-white default toast next to the rest of this palette looks broken, not neutral.

## Responsive rules

Inherited from CLAUDE.md §3.7 and not repeated in full here — the short version, as actually implemented: mobile-first classes everywhere (base class = smallest screen, `md:`/`lg:` layer up, never the reverse), every table wrapped in `overflow-x-auto`, the nav collapses below `md`, and the auth split-panel only appears at `lg:`+.

## Checklist for a new screen

1. Page header: title + one-line description, no card wrapper around the header itself.
2. Wrap actual content in `Card` (or reuse `CrudTable` if it's a lookup list).
3. Icon badge in any `CardHeader` that represents a distinct domain concept (`bg-primary/10 text-primary`, `size-9` badge / `size-4.5` icon).
4. Loading / error / empty states, all three, styled per the CrudTable pattern above if it's a list.
5. Row/item actions are icon-only ghost buttons with `aria-label` if space is tight (tables); labeled buttons if there's room (card-level actions).
6. Any destructive action goes through `ConfirmDialog`/`ConfirmDeleteDialog` with `confirmVariant="destructive"`.
7. Mobile-first classes, table horizontal scroll containment, checked at ~375/768/1280px before calling it done.
