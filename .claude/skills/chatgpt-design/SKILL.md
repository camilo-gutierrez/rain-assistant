# ChatGPT Design System — Rain UI Improvement Guide

You are a UI designer and frontend developer. Your goal is to improve Rain Assistant's frontend to achieve a design aesthetic **very similar to ChatGPT's interface** while respecting Rain's existing theme system and CLAUDE.md rules.

Use this guide as your **definitive design reference** when the user asks to improve, redesign, or polish any frontend component.

---

## 1. COLOR PALETTE (Dark Theme Reference)

ChatGPT uses a **warm, neutral dark palette** — NOT cool/blue-tinted like Rain's current dark theme.

| Element | ChatGPT Hex | Closest Rain Token | Notes |
|---------|-------------|-------------------|-------|
| Page background | `#212121` | `--bg` | Warm charcoal, NOT blue-black |
| Surface / Cards | `#2f2f2f` | `--surface` | Slight warm lift |
| Surface hover | `#3a3a3a` | `--surface2` | Subtle hover differentiation |
| Input field bg | `#303030` | `--surface2` | Rounded pill, slightly raised |
| Sidebar bg | `#171717` | `--bg` (darker variant) | Darker than main content |
| Text primary | `#ECECEC` | `--text` | Near-white, not pure white |
| Text secondary | `#B4B4B4` | `--text2` | Muted but readable |
| Text placeholder | `#8E8E8E` | `--subtext` | "Ask anything" placeholder |
| Accent / Send | `#0084FF` | `--primary` | Blue circle send button |
| Borders | `rgba(255,255,255,0.06)` | `--overlay` | Nearly invisible, very subtle |
| Menu separator | `rgba(255,255,255,0.08)` | `--overlay` | Thin 1px lines |

**When adjusting Rain's dark theme**, shift the palette from cool/purple-tinted to warm/neutral grays:
- Current `--bg: #0B0B10` → aim for `#212121` range (warmer)
- Current `--surface: #15151E` → aim for `#2f2f2f` range (warmer)
- Keep `--primary` as brand accent (can stay indigo or shift to blue)

**Light theme**: ChatGPT uses `#FFFFFF` bg with `#F7F7F8` surfaces — clean, minimal, no colored tints.

---

## 2. TYPOGRAPHY

### Font Stack
- **Primary**: System sans-serif (ChatGPT uses their own "Söhne" font, but Inter/system-ui is the closest match — Rain already uses Inter, which is perfect)
- **Mono**: Söhne Mono → Rain's JetBrains Mono is excellent, keep it
- **Display/Hero**: The "Ready when you are." text uses a **serif display font** — this is optional brand flourish

### Scale & Weights
| Usage | Size | Weight | Rain Class |
|-------|------|--------|------------|
| Hero greeting | 28-32px | 300 (light) | `text-2xl` or `text-3xl font-light` |
| Page titles | 20px | 600 (semibold) | `text-xl font-semibold` |
| Nav items | 14-15px | 400 (regular) | `text-sm` |
| Body / Messages | 15-16px | 400 | `text-base` |
| Secondary text | 13-14px | 400 | `text-sm` |
| Labels / Hints | 12px | 400 | `text-xs` |
| Input placeholder | 16px | 400 | `text-base` |

### Key Typography Rules
- **NO bold abuse**: ChatGPT is very restrained with bold. Headers use semibold, body is regular
- **Generous line-height**: `leading-relaxed` (1.625) for body text
- **Letter-spacing**: Normal, never tight. Slightly wide for all-caps labels if used
- Menu items: `text-sm` with `py-2.5 px-3` spacing — easy touch targets

---

## 3. SPACING & LAYOUT

### Overall Layout
```
┌──────────────────────────────────────────────────┐
│ (no visible top bar — model selector is minimal) │
├─────────┬────────────────────────────────────────┤
│         │                                        │
│ Sidebar │        Centered content area           │
│ ~260px  │        max-w-2xl to max-w-3xl          │
│         │                                        │
│         │     "Ready when you are."              │
│         │                                        │
│         │     ┌──────────────────────────┐       │
│         │     │  Ask anything...    🎤 ⬆ │       │
│         │     └──────────────────────────┘       │
│         │                                        │
└─────────┴────────────────────────────────────────┘
```

### Spacing Tokens
| Usage | Value | Tailwind |
|-------|-------|----------|
| Sidebar width | 260px | `w-[260px]` |
| Sidebar padding | 12px horizontal | `px-3` |
| Nav item height | 40-44px | `h-10` or `h-11` |
| Nav item padding | 10px 12px | `px-3 py-2.5` |
| Nav item gap (icon-text) | 12px | `gap-3` |
| Nav item border-radius | 10px | `rounded-[10px]` |
| Content max-width | 768px | `max-w-3xl` |
| Content padding | 16-24px horizontal | `px-4 md:px-6` |
| Input bar margin from edges | ~16px | `mx-4` |
| Input bar padding | 12-16px | `p-3 md:p-4` |
| Input bar border-radius | 24-28px | `rounded-3xl` |
| Card/section gap | 4-8px | `gap-1` to `gap-2` |
| Menu item spacing | 2px between | `gap-0.5` |
| Section dividers | 8px margin + 1px line | `my-2 border-overlay` |

### Critical Layout Principles
1. **Center the content**: Chat messages and input are in a centered column (`mx-auto max-w-3xl`)
2. **Breathing room**: Generous padding around content, never cramped
3. **Minimal chrome**: Very little visible UI "furniture" — the content is the interface
4. **Bottom input**: Input sits at the bottom with clear space, not stuck to edges

---

## 4. COMPONENTS

### 4.1 Input Bar (Most Important Component)
The input bar is ChatGPT's signature element:

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│  Ask anything                              🎤  (●)  │
│                                                      │
│  ⊕  Extended thinking ∨                              │
└──────────────────────────────────────────────────────┘
```

**Design specs:**
- **Shape**: Large pill / rounded rectangle (`rounded-3xl` or `rounded-[26px]`)
- **Background**: Slightly lighter than page bg (`bg-surface2`)
- **Border**: Very subtle or none. No harsh outlines
- **Shadow**: Subtle shadow to lift it: `shadow-sm` or custom `0 2px 6px rgba(0,0,0,0.15)`
- **Placeholder**: "Ask anything" in `text-subtext`, `text-base`
- **Min height**: ~52px, grows with content
- **Max height**: ~200px before scroll
- **Send button**: Circular, 32px, `bg-primary` when has content, `bg-overlay` when empty
- **Mic button**: Same size, ghost/transparent style
- **Attachments (+)**: Bottom-left, subtle icon button
- **Model selector**: Bottom-left, text button with chevron ("Extended thinking ∨")

**Key differences from current Rain input:**
- Much larger border-radius (pill shape vs current rectangular)
- Padding is more generous
- Input field and action buttons are in the SAME container (not separated)
- Send button is a **circle**, not a rectangular button

### 4.2 Sidebar Navigation

```
┌─────────────────────┐
│  (logo)        (□)  │  ← Toggle collapse button
│                     │
│  📝 New chat        │  ← Ghost/subtle button, not filled
│                     │
│  🔍 Search chats    │
│  🖼 Images          │
│  88 Apps            │
│  ✨ Deep research   │
│  ⏱ Codex           │
│                     │
│  ── GPTs ────────── │  ← Section header, muted
│                     │
│  ⊕ GCP Developer    │
│  ⊕ Integracion...   │
│                     │
│  ⊕ Explore GPTs     │
│                     │
│─────────────────────│
│  👤 Camilo Gutierrez│  ← User profile at bottom
│     Plus            │
└─────────────────────┘
```

**Design specs:**
- **Background**: Slightly darker than main content or same
- **Nav items**: Icon + text, `text-sm`, `rounded-[10px]` on hover
- **Hover state**: Very subtle background change (`bg-surface2/50`)
- **Active state**: Slightly more visible bg (`bg-surface2`)
- **No active accent bar**: ChatGPT doesn't use colored left borders. Active = subtle bg change only
- **Section headers**: ALL CAPS or small muted text, `text-xs text-subtext font-medium`
- **User avatar**: Bottom of sidebar, circular, with name + plan badge
- **Collapse button**: Top-right of sidebar, toggles between expanded/icon-only
- **Scrollable**: Middle section scrolls if needed, header and footer stay fixed

### 4.3 Dropdowns / Menus

```
┌────────────────────────┐
│  👤 camiloms           │  ← Profile header
│     @camiloms          │
│                        │
│  ⊕ Upgrade plan        │
│  ⏱ Personalization     │
│  ⚙ Settings            │
│  ❓ Help            ▸  │  ← Submenu arrow
│  ↪ Log out             │
└────────────────────────┘
```

**Design specs:**
- **Border-radius**: 16px (`rounded-2xl`)
- **Background**: `bg-surface` with subtle border
- **Shadow**: Medium: `shadow-lg` or `0 4px 24px rgba(0,0,0,0.25)`
- **Padding**: 8px internal padding, items have `px-3 py-2.5`
- **Dividers**: 1px lines with `my-1` margin
- **Icons**: 20px, `text-text2`, left-aligned
- **Text**: `text-sm text-text`
- **Hover**: `bg-surface2/60` rounded
- **Submenu arrow**: `▸` or ChevronRight for expandable items
- **Width**: 240-280px for user menus
- **Animation**: `scale-in` + `fade-in` on open, 150ms

### 4.4 Settings Modal

```
┌──────────────────────────────────────────────┐
│  ✕                                           │
│                                              │
│  ┌──────────┐  ┌──────────────────────────┐  │
│  │ General  │  │  Setting Title           │  │
│  │ Notif    │  │  Description text...     │  │
│  │ Person.. │  │                          │  │
│  │ Apps     │  │  Option        Default ∨ │  │
│  │ Schedule │  │  Option        Default ∨ │  │
│  │ Data     │  │  Option        Default ∨ │  │
│  │ Security │  │                          │  │
│  │ Account  │  │  Custom instructions     │  │
│  │          │  │  ┌──────────────────┐    │  │
│  │          │  │  │ Text area...     │    │  │
│  │          │  │  └──────────────────┘    │  │
│  └──────────┘  └──────────────────────────┘  │
│                                              │
└──────────────────────────────────────────────┘
```

**Design specs:**
- **Type**: Full overlay modal (centered, not drawer)
- **Backdrop**: `bg-black/60` with `backdrop-blur-sm`
- **Modal bg**: `bg-surface` with `rounded-2xl`
- **Size**: Max ~700px wide, ~500px tall
- **Close button**: Top-left `✕`, ghost button
- **Internal layout**: Left sidebar nav (180px) + right content area
- **Nav items**: `text-sm`, vertical list, active = `bg-surface2` + `font-medium`
- **Content**: Settings rows with label left, control right
- **Controls**: Dropdown selects styled as ghost buttons with chevron
- **Sections**: Clean headers (`text-lg font-semibold`) + description (`text-sm text-text2`)

### 4.5 Message Bubbles

**User messages:**
- **Background**: `bg-surface2` rounded pill/blob (`rounded-3xl`)
- **Alignment**: Right-aligned
- **Padding**: `px-4 py-2.5`
- **Max width**: ~70% of container
- **Text**: `text-base text-text`

**Assistant messages:**
- **No background**: Just text, left-aligned
- **No bubble**: Clean, unbounded text (this is a KEY difference)
- **Avatar**: Small circular icon at top-left (optional)
- **Markdown**: Rendered with proper heading sizes, code blocks with bg
- **Code blocks**: `bg-surface2` with `rounded-xl`, monospace, copy button top-right

### 4.6 Empty State / Greeting

The "Ready when you are." centered text:
- **Centered** both horizontally and vertically in the content area
- **Font**: Display/serif OR light sans-serif, `text-2xl` to `text-3xl`
- **Weight**: Light (300) or regular
- **Color**: `text-text` or slightly muted
- **No icon**: Just text, minimal
- **Disappears** when first message is sent

---

## 5. INTERACTIVE STATES

### Hover
- Menu items: Very subtle bg shift (`bg-surface2/40` → `bg-surface2/60`)
- Buttons: Slight brightness increase
- Links: No underline change, slight color shift
- **Duration**: 150ms ease

### Focus
- Use Rain's `.focus-ring` utility (2px primary shadow)
- Input fields: No visible border change, just the focus ring
- Buttons: Focus ring only on keyboard navigation (`:focus-visible`)

### Active / Pressed
- Buttons: Slight scale down (`active:scale-[0.98]`) + darker bg
- Menu items: Instant bg change, no animation

### Transitions
- Background/color transitions: `150ms ease`
- Transform transitions: `100ms ease`
- Modal/dropdown appear: `200ms ease-out` with scale + fade
- Sidebar collapse: `300ms ease` width transition

---

## 6. ICONS

- **Style**: Line/outline icons, NOT filled (Lucide icons are perfect)
- **Size**: 20px for nav items, 16px for inline/small, 24px for primary actions
- **Color**: `text-text2` default, `text-text` on hover/active
- **Stroke width**: 1.5-2px (Lucide default)

---

## 7. SHADOWS & ELEVATION

| Level | Usage | Value |
|-------|-------|-------|
| 0 | Flat elements | None |
| 1 | Cards, input bar | `0 2px 6px rgba(0,0,0,0.1)` |
| 2 | Dropdowns, tooltips | `0 4px 16px rgba(0,0,0,0.2)` |
| 3 | Modals | `0 8px 32px rgba(0,0,0,0.3)` |

In dark mode, shadows are less visible — rely more on subtle border + bg differences.

---

## 8. BORDER RADIUS

| Element | Radius | Tailwind |
|---------|--------|----------|
| Input bar | 26px | `rounded-3xl` |
| Buttons (pill) | 20px | `rounded-2xl` |
| Cards | 16px | `rounded-2xl` |
| Dropdowns/Menus | 16px | `rounded-2xl` |
| Nav items (hover) | 10px | `rounded-[10px]` |
| Avatars | 50% | `rounded-full` |
| Code blocks | 12px | `rounded-xl` |
| Badges | 9999px | `rounded-full` |
| Send button | 50% | `rounded-full` |

**Pattern**: ChatGPT uses **very generous border-radius** everywhere. Nothing is sharp-cornered.

---

## 9. ANIMATIONS & MICRO-INTERACTIONS

- **Message appear**: Fade in + slight slide up (Rain's `animate-msg-appear` is good)
- **Dropdown open**: Scale from 95% + fade in, 200ms (`animate-scale-in`)
- **Send button**: Subtle pulse when ready, smooth color transition
- **Typing indicator**: Three dots with staggered bounce animation
- **Scroll to bottom**: Smooth scroll behavior
- **Sidebar toggle**: Width transition 300ms with content fade
- **Theme switch**: 300ms crossfade (Rain already has this)

---

## 10. RESPONSIVE BEHAVIOR

### Desktop (≥768px)
- Sidebar always visible (260px), collapsible to icon-only (~68px)
- Content centered with max-width
- Input bar has max-width matching content

### Mobile (<768px)
- Sidebar as overlay drawer (slide from left)
- Full-width content
- Input bar stretches full width with side padding
- Bottom safe area padding for iOS
- Touch targets minimum 44px

---

## 11. IMPLEMENTATION CHECKLIST

When improving a Rain component toward ChatGPT design, check:

- [ ] **Colors**: Using warm neutral grays, not cool/blue-tinted?
- [ ] **Border radius**: Generously rounded? (`rounded-2xl` or `rounded-3xl`)
- [ ] **Spacing**: Comfortable padding? Not cramped?
- [ ] **Typography**: Clean hierarchy? Not over-bold?
- [ ] **Shadows**: Subtle and appropriate for elevation level?
- [ ] **Borders**: Nearly invisible? Using bg difference instead of harsh lines?
- [ ] **Icons**: Line-style, consistent 20px size?
- [ ] **Hover states**: Subtle, not dramatic?
- [ ] **Focus**: Using `.focus-ring` utility?
- [ ] **i18n**: All strings through `t()`?
- [ ] **Semantic tokens**: Using Rain's theme tokens, NOT hardcoded colors?
- [ ] **No arbitrary sizes**: Standard Tailwind only per CLAUDE.md?
- [ ] **Minimal chrome**: Removed unnecessary visual noise?
- [ ] **Content-first**: Is the content the hero, not the UI frame?

---

## 12. QUICK REFERENCE — "Make it look like ChatGPT"

**TL;DR transformations to apply:**

1. **Increase border-radius** on everything (cards, inputs, menus → `rounded-2xl`+)
2. **Soften borders** — replace visible borders with bg color differences
3. **Warm up dark theme** — shift from blue-black to warm charcoal grays
4. **Generous padding** — when in doubt, add more space
5. **Pill-shaped input** — the signature element, big rounded container
6. **Circular send button** — replace rectangular send with a circle
7. **Minimal sidebar** — icon + text, subtle hover, no colored accent bars
8. **No bubble for assistant** — just clean text, left-aligned
9. **Centered content** — max-w-3xl mx-auto for the main area
10. **Subtle everything** — less contrast in borders, shadows, hover states

$ARGUMENTS
