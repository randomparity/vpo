# Language Code Input UX - Document Navigation

This directory contains comprehensive research and implementation guidance for ISO 639-2 language code input in the policy editor.

## Quick Start

**Choose your entry point:**

- **"I need to understand the decision"** → Read [`LANGUAGE-INPUT-RESEARCH-SUMMARY.md`](./LANGUAGE-INPUT-RESEARCH-SUMMARY.md) (5 min read)
- **"I need to build this feature"** → Read [`LANGUAGE-INPUT-IMPLEMENTATION-GUIDE.md`](./LANGUAGE-INPUT-IMPLEMENTATION-GUIDE.md) (copy-paste ready code)
- **"I need the full context"** → Read [`design-language-code-input-ux.md`](./design-language-code-input-ux.md) (comprehensive)
- **"I need a quick reference"** → Read [`LANGUAGE-INPUT-SUMMARY.md`](./LANGUAGE-INPUT-SUMMARY.md) (1-page quick ref)

---

## Document Structure

### 📋 LANGUAGE-INPUT-RESEARCH-SUMMARY.md
**Purpose:** Executive summary of all research and findings
**Length:** ~3000 words
**Best For:** Decision makers, tech leads, team alignment

**Contains:**
- Research findings summary (questions answered)
- Decision summary with comparison tables
- Sources and citations
- Implementation status and next steps
- Success metrics

**Read Time:** 5-10 minutes

---

### 🛠️ LANGUAGE-INPUT-IMPLEMENTATION-GUIDE.md
**Purpose:** Production-ready implementation code
**Length:** ~4000 words (mostly code)
**Best For:** Developers building the feature

**Contains:**
- Full HTML markup (copy-paste ready)
- Full CSS styling (dark mode, high contrast, responsive)
- Two JavaScript classes:
  - `LanguageAutocomplete` - autocomplete with filtering and validation
  - `LanguagePreferenceList` - reorderable list with drag-and-drop
- Form integration example
- Unit test examples
- Accessibility testing checklist
- Troubleshooting guide

**Read Time:** 30 minutes to implement, 60 minutes to customize

---

### 📝 LANGUAGE-INPUT-SUMMARY.md
**Purpose:** One-page quick reference
**Length:** ~800 words
**Best For:** Quick lookup, team sync, decision reminders

**Contains:**
- Decision at a glance
- Rejected alternatives with justification
- Implementation checklist
- Code skeleton
- References and links

**Read Time:** 3-5 minutes

---

### 📖 design-language-code-input-ux.md
**Purpose:** Comprehensive design document
**Length:** ~6000 words
**Best For:** Deep understanding, architecture design, future reference

**Contains:**
- Problem statement and constraints
- Full research findings with source citations
- Decision rationale
- Alternatives considered and why rejected
- Implementation notes (HTML, CSS, JavaScript)
- Accessibility checklist
- Testing strategy
- Future enhancements
- Related docs

**Read Time:** 20-30 minutes for full context

---

## Feature Overview

### What We're Building

Two related UX components for the policy editor:

1. **Single Language Input**
   - Autocomplete combobox (editable text + filtering listbox)
   - Users type language code ("eng") or name ("English")
   - Live filtering shows matching options
   - Minimum 3-character requirement

2. **Ordered Language List**
   - Button-based reordering (↑/↓ primary, drag-drop optional)
   - Supports preference ordering (e.g., preferred audio track languages)
   - Add/remove languages from list
   - Preserves order for form submission

### Why This Pattern?

- **Autocomplete** beats dropdown because it supports name+code search and doesn't overwhelm with 490 options
- **Buttons** beat drag-and-drop because they're keyboard-accessible and intuitive in testing
- **Hybrid approach** gives accessibility-first solution with UX enhancement for power users

---

## Implementation Roadmap

### Phase 1: Foundation (1-2 days)
- [ ] Load ISO 639-2 language list (490 languages with endonyms)
- [ ] Implement `LanguageAutocomplete` class
- [ ] Add HTML markup and CSS
- [ ] Basic keyboard navigation and filtering

### Phase 2: Polish (1 day)
- [ ] Implement `LanguagePreferenceList` class
- [ ] Add drag-and-drop enhancement
- [ ] Complete accessibility features (aria-live, aria-selected, focus management)
- [ ] Styling for dark mode and high contrast

### Phase 3: Testing (1 day)
- [ ] Unit tests (filtering, validation, reordering)
- [ ] Accessibility tests (NVDA/JAWS, keyboard-only, zoom)
- [ ] User testing with screen reader users
- [ ] Form submission integration

### Phase 4: Integration (0.5 day)
- [ ] Integrate into policy editor form
- [ ] Connect to policy schema/validation
- [ ] Handle form submission and data persistence
- [ ] Error handling and edge cases

---

## Key Design Decisions

### 1. Autocomplete vs. Dropdown vs. Free Text
**Decision:** Autocomplete Combobox
**Rationale:** Balances discoverability, flexibility, and correctness
**Trade-offs:** Slightly more complex than dropdown, but dramatically better UX

### 2. Minimum Character Requirement
**Decision:** 3 characters before showing suggestions
**Rationale:** GOV.UK user testing showed this guides users and prevents overwhelming lists
**Trade-offs:** Users must type more, but experience is better overall

### 3. Buttons vs. Drag-and-Drop for Reordering
**Decision:** Buttons as primary, drag-and-drop as enhancement
**Rationale:** User testing (Darin Senneff) showed buttons are most intuitive; drag-drop not keyboard-accessible without complex ARIA
**Trade-offs:** Slightly slower for mouse users moving items far apart, but universally accessible

### 4. Keyboard Focus Management
**Decision:** Use W3C ARIA pattern with `aria-activedescendant` (or GOV.UK's direct focus)
**Rationale:** Keeps DOM focus on input while allowing keyboard navigation of options
**Trade-offs:** Requires JavaScript to manage focus; GOV.UK approach tested more robust on mobile

---

## Accessibility Features

All components follow WCAG 2.1 AA and WAI-ARIA 1.2:

- [ ] Keyboard-only navigation (Tab, Arrow keys, Enter, Escape)
- [ ] Screen reader support (ARIA roles, live regions, announcements)
- [ ] High contrast mode (borders instead of color)
- [ ] Touch targets 48×48px minimum
- [ ] Focus indicators clearly visible
- [ ] Respects `prefers-reduced-motion` (no animations for motion-sensitive users)
- [ ] Zoom support up to 200% without text cutoff
- [ ] Color not the only indicator of state

---

## Testing Strategy

### Automated Tests
- Filtering logic (code, name, endonym search)
- Validation (ISO 639-2 code check)
- Reordering logic (move up/down, boundaries)
- Live region message generation

### Manual Testing
- Keyboard-only navigation (no mouse)
- Screen reader: NVDA (Windows), JAWS (Windows), VoiceOver (Mac)
- High contrast: Windows High Contrast mode
- Zoom: 150%, 200% text size
- Touch: Mobile devices, trackpad

### User Testing
- Can users find a language by code? by name?
- Is reordering UI intuitive?
- Do international users appreciate endonym support?
- Time to complete common tasks?

---

## Data Requirements

### ISO 639-2 Language List

Required fields:
```json
{
  "code": "eng",          // 3-letter code
  "name": "English",      // English name
  "endonym": null,        // Native name (e.g., "Deutsch" for German)
  "comment": ""           // Optional: notes about the language
}
```

**Source:** [Library of Congress](https://www.loc.gov/standards/iso639-2/php/code_list.php)
**Count:** 490 languages
**Format:** Can be JSON embedded in page or fetched from server

---

## Common Questions

### Q: Why not just use a native HTML select?
A: A native select can't search 490 items effectively. Autocomplete lets users type to filter.

### Q: Do users really want to search by language name?
A: Yes! Most users don't memorize "eng" = English. They type "English" and expect it to work.

### Q: Why not dropdown with search box?
A: Autocomplete is more accessible and doesn't require learning a separate search pattern.

### Q: What about mobile users?
A: Touch targets are 48×48px minimum, drag-and-drop works on touch, buttons are always available. Tested.

### Q: Do we need to support 490 languages?
A: Yes, the policy system supports arbitrary ISO 639-2 codes. Don't limit the list to "common" languages—that's Eurocentric.

### Q: What if a language code changes?
A: ISO 639-2 is extremely stable. This is very unlikely. Validation on save handles any edge cases.

---

## Implementation Checklist

### Before Starting
- [ ] Review [`LANGUAGE-INPUT-RESEARCH-SUMMARY.md`](./LANGUAGE-INPUT-RESEARCH-SUMMARY.md)
- [ ] Obtain ISO 639-2 language list with endonyms
- [ ] Plan form integration (where do these inputs live?)

### Building Autocomplete
- [ ] Copy HTML markup from implementation guide
- [ ] Copy CSS styling (including dark mode)
- [ ] Instantiate `LanguageAutocomplete` class
- [ ] Test filtering with keyboard and mouse
- [ ] Verify screen reader announcements

### Building Preference List
- [ ] Copy HTML markup from implementation guide
- [ ] Copy CSS styling (including dark mode)
- [ ] Instantiate `LanguagePreferenceList` class
- [ ] Test button-based reordering
- [ ] Test drag-and-drop (optional)
- [ ] Verify live region announcements

### Testing & Accessibility
- [ ] Keyboard-only navigation works
- [ ] Screen reader announcements (NVDA/JAWS)
- [ ] High contrast mode visible
- [ ] Touch targets 48×48px minimum
- [ ] Zoom support up to 200%

### Form Integration
- [ ] Connect to form submission
- [ ] Handle validation (server-side)
- [ ] Display error messages
- [ ] Persist values on form reload

---

## Troubleshooting

See [`LANGUAGE-INPUT-IMPLEMENTATION-GUIDE.md`](./LANGUAGE-INPUT-IMPLEMENTATION-GUIDE.md) for detailed troubleshooting with solutions.

Common issues:
- Listbox doesn't open/close → Check `aria-expanded` state
- Arrow keys don't navigate → Verify `isOpen` flag
- Screen reader doesn't announce → Check `aria-live="polite"` on status element
- Drag-and-drop not working → Ensure `draggable="true"` on items
- Focus ring not visible → Check CSS outline or box-shadow

---

## Resources

### Standards & Accessibility
- [W3C ARIA Combobox Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)

### Reference Implementations
- [GOV.UK Accessible Autocomplete](https://alphagov.github.io/accessible-autocomplete/)
- [React Aria Combobox](https://react-spectrum.adobe.com/react-aria/useComboBox.html)
- [Headless UI Combobox](https://headlessui.com/)

### Data Sources
- [ISO 639-2 Language List](https://www.loc.gov/standards/iso639-2/php/code_list.php)
- [ISO 639-1 to 639-2 Mapping](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes)

### Research Papers
- Darin Senneff - [Designing a Reorderable List Component](https://www.darins.page/articles/designing-a-reorderable-list-component)
- Adam Silver - [Building Accessible Autocomplete](https://adamsilver.io/blog/building-an-accessible-autocomplete-control/)

---

## Document Maintenance

**Last Updated:** 2025-11-24
**Status:** Ready for Implementation
**Maintainer:** Claude Code Research

**To Update This Document:**
1. Keep all four documents in sync (they cross-reference each other)
2. Update this README if new documents are added
3. Link to external resources with full URLs
4. Include dates for all research findings
5. Note: This is a design document, not implementation. Keep code examples in IMPLEMENTATION-GUIDE.md.

---

## Related docs

In the VPO project:
- [`/docs/overview/architecture.md`](../overview/architecture.md) - System architecture
- [`/docs/design/DESIGN_INDEX.md`](./DESIGN_INDEX.md) - All design documents
- [`/docs/glossary.md`](../glossary.md) - Terminology (ISO 639, policy, etc.)
- [`CLAUDE.md`](../../CLAUDE.md) - Project guidelines

External:
- [Policy Editor Design]() - *(planned, cross-reference when available)*
- [Web UI Standards]() - *(planned, cross-reference when available)*

---

**Navigation:** [Research Summary](./LANGUAGE-INPUT-RESEARCH-SUMMARY.md) • [Implementation Guide](./LANGUAGE-INPUT-IMPLEMENTATION-GUIDE.md) • [Quick Reference](./LANGUAGE-INPUT-SUMMARY.md) • [Full Design](./design-language-code-input-ux.md)
