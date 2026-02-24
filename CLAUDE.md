# Rain Assistant — Project Guidelines

## Frontend UI/UX Rules

These rules are **mandatory** for all frontend work in `frontend/src/`.

### Colors
- **ONLY** use semantic theme tokens: `bg-surface`, `text-text`, `text-blue`, `bg-red/10`, `text-primary`, etc.
- **NEVER** use Tailwind's static palette: `text-blue-400`, `bg-red-500/10`, `text-green-600`, etc.
- Exception: brand colors for external providers (e.g., `bg-[#d97706]` for Anthropic).
- Available tokens: `bg`, `surface`, `surface2`, `overlay`, `text`, `text2`, `subtext`, `blue`, `green`, `red`, `yellow`, `mauve`, `cyan`, `magenta`, `primary`, `primary-light`, `primary-dark`, `on-primary`.

### Typography
- Only standard Tailwind sizes: `text-xs` (12px), `text-sm` (14px), `text-base` (16px), `text-lg` (18px), `text-xl`+.
- **No** arbitrary pixel sizes (`text-[9px]`, `text-[11px]`, `text-[13px]`).
- For monospace, use `font-mono` (mapped to JetBrains Mono). Not `font-[family-name:var(--font-jetbrains)]`.

### Spacing
- Section gaps: `space-y-3` or `space-y-4`.
- Card padding: `p-4`. Compact blocks: `px-3 py-2`.
- Consistent empty state padding: `py-8`.

### Focus Rings
- Always use the `.focus-ring` CSS utility class.
- **Never** inline `focus:outline-none focus:ring-1 focus:ring-primary`.

### Loading States
- Use `<Skeleton>` and `<SkeletonList>` from `@/components/Skeleton`.
- Always use `shimmer-bg`. Never `animate-pulse` for loading skeletons.

### Empty States
- Use `<EmptyState>` from `@/components/EmptyState`.
- Props: `icon`, `title`, `hint?`.

### Popovers / Dropdowns
- Use `usePopover()` hook from `@/hooks/usePopover`.
- **Never** manually implement click-outside + Escape key logic.

### Inline Styles
- Only for truly dynamic values (computed heights, random animation delays).
- **Never** for static properties expressible in Tailwind (`resize-none`, `min-h-[44px]`).

### Internationalization (i18n)
- **ALL** user-facing strings must go through `t()` from `useTranslation`.
- No hardcoded English or Spanish text in JSX.
- Translation keys go in `frontend/src/lib/translations.ts` (both `en` and `es`).

### Component Patterns
- Prefer editing existing components over creating new files.
- Co-locate sub-components in the same file when they're only used there.
- Use `React.memo` for message-related components rendered in lists.
