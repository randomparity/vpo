# Language Code Input UX Research - Complete Summary

**Deliverables Created:** 2025-11-24

This research synthesizes UX patterns for ISO 639-2 language code input in web forms, with a focus on the policy editor's needs.

---

## Three-Document Structure

### 1. **design-language-code-input-ux.md** (26 KB)
The comprehensive research and design decision document. Includes:
- Problem statement and user challenges
- Research findings from W3C, GOV.UK, and user testing
- Decision (autocomplete combobox + button-based reordering)
- Rationale and alternatives considered
- Implementation notes with HTML, JavaScript, and CSS sketches
- Accessibility checklist and testing strategy

**Start here for:** Decision-making, architectural understanding, and justification

### 2. **LANGUAGE-INPUT-SUMMARY.md** (4.3 KB)
Quick reference guide for developers. Includes:
- One-page summary of decision
- Why/rejected alternatives comparison table
- Implementation checklist
- Code skeleton
- Data requirements

**Start here for:** Quick lookup, team alignment, and implementation kickoff

### 3. **LANGUAGE-INPUT-IMPLEMENTATION-GUIDE.md** (26 KB)
Hands-on implementation guide with production-ready code. Includes:
- Full HTML/CSS/JavaScript for autocomplete
- Full HTML/CSS/JavaScript for reorderable list
- Form integration example
- Unit and accessibility tests
- Troubleshooting guide
- Data source info

**Start here for:** Building the feature, copy-paste code, styling reference

---

## Research Findings Summary

### Key Question 1: Text Input vs. Dropdown vs. Autocomplete?

**Answer: Autocomplete Combobox (Editable input + filtered listbox)**

| Aspect | Autocomplete | Dropdown | Free Text |
|--------|-------------|----------|-----------|
| User can type code | ✓ Yes | ✗ Must scroll | ✓ Yes |
| User can type name | ✓ Yes (filters) | ✗ Must scroll | ✓ Yes |
| Validates codes | ✓ Yes | ✓ Yes | ✗ No |
| Keyboard accessible | ✓ Yes | ✓ Yes | ✓ Yes (limited) |
| Non-intrusive | ✓ Yes | ✗ 490 options visible | ✓ Yes |
| Screen reader friendly | ✓ Yes (live regions) | ~ Depends | ✗ No context |

**Why autocomplete wins:**
- Users don't memorize ISO 639-2 codes; autocomplete helps them discover
- Supports both code ("eng") and name ("English") input
- Live filtering prevents overwhelming users with 490 options
- WAI-ARIA patterns (from W3C) provide proven accessibility guidance

### Key Question 2: How to Help Users Without Overwhelming?

**Answer: Minimum 3-Character Requirement + Live Result Count**

From GOV.UK user testing:
- "Type 3+ characters" gives users actionable guidance
- Announcing "13 results available" manages expectations
- Live feedback prevents confusion

### Key Question 3: How to Handle Preference Ordering?

**Answer: Button-Based UI (↑/↓) with Optional Drag-and-Drop**

User testing (Darin Senneff) showed:
- **Button-based (↑/↓):** Users "picked it up fastest—all ignored instructions"
- **Drag-and-drop:** Intuitive for mouse users but not keyboard-accessible by default
- **Numeric input:** Confusing, users don't expect text input
- **Grab toggles:** Poor affordance, users didn't know what they did

**Recommended hybrid approach:**
1. Buttons as primary (keyboard-accessible, always works)
2. Drag-and-drop as optional enhancement
3. Both in one UI for flexibility

### Key Question 4: Accessibility Approach?

**Answer: W3C ARIA Combobox Pattern with Live Regions**

W3C, GOV.UK, and Orange Digital Accessibility guidelines converge on:
- `role="combobox"` with `aria-autocomplete="list"`
- `role="listbox"` with `role="option"` items
- `aria-expanded`, `aria-selected`, `aria-controls` for state
- `role="status" aria-live="polite"` for announcements
- Focus management (keep DOM focus on input, use `aria-activedescendant` or `focus()`)
- 48×48px minimum touch targets
- Clear keyboard navigation (Arrow ↑↓, Enter, Escape, Tab)

**Note:** GOV.UK's approach (focus options directly) tested more robust on mobile than W3C's `aria-activedescendant` approach.

---

## Decision Details

### For Single Language Input

```
INPUT: Text field with role="combobox"
       aria-autocomplete="list"
       aria-expanded="false"
       aria-controls="[listbox]"

BEHAVIOR: On keystroke, filter languages by:
         - Code match (case-insensitive)
         - Name match (case-insensitive)
         - Endonym match (e.g., "français" finds French)

         Show only if ≥3 characters typed

DISPLAY: Listbox with role="listbox", options with role="option"
         Each option shows: "[CODE] Name (endonym if exists)"

KEYBOARD: ↓ next, ↑ prev, Enter select, Esc close, Tab moves focus

LIVE REGION: Announces "3+ required", result count, current selection
             Updates screen readers without visual changes
```

### For Ordered List Input

```
ITEM STRUCTURE: [Drag Handle] [Name] [↑ Button] [↓ Button] [✕ Button]

PRIMARY INTERACTION: Up/Down buttons move item one position
                     Up disabled if first, Down disabled if last
                     Remove button deletes from list

SECONDARY INTERACTION: Drag handle allows mouse drag-and-drop
                       (optional enhancement)

KEYBOARD: Tab between items, Arrow keys move within buttons
          Shift+Arrow for larger moves (5 positions)
          Space/Enter to activate focused button

LIVE REGION: "Moved English down 1 position. Order: 1. English, 2. Japanese"

ACCESSIBILITY: All text in aria-label on buttons, not just icons
               Focus ring on buttons and items
               High contrast support (borders not color)
```

---

## What to Avoid

1. **Closed dropdown only** - Can't search 490 items
2. **Free text with validation only** - Users don't know valid codes exist
3. **Drag-and-drop only** - Not keyboard-accessible
4. **Numeric input for reordering** - Confusing and error-prone
5. **Endonym search without English support** - International users want both
6. **Color-only indicators** - High contrast and color-blind users can't perceive
7. **Small touch targets** - Mobile users need 48×48px minimum

---

## Implementation Status

### Files Created
1. `/docs/design/design-language-code-input-ux.md` - Comprehensive research and design
2. `/docs/design/LANGUAGE-INPUT-SUMMARY.md` - Quick reference
3. `/docs/design/LANGUAGE-INPUT-IMPLEMENTATION-GUIDE.md` - Production-ready code
4. `/docs/INDEX.md` - Updated with design doc link

### Files Ready for Use
- HTML markup examples (copy-paste ready)
- CSS styling (includes dark mode and high contrast)
- Vanilla JavaScript classes:
  - `LanguageAutocomplete` - Full autocomplete with validation
  - `LanguagePreferenceList` - Reorderable list with drag-and-drop
- Unit test examples (Jest-compatible)
- Accessibility test checklist
- Integration examples (form submission)

### Next Steps for Implementation
1. Load ISO 639-2 language list (490 languages)
   - Source: [Library of Congress](https://www.loc.gov/standards/iso639-2/php/code_list.php)
   - Include endonyms for internationalization
2. Integrate JavaScript classes into policy editor
3. Add unit tests and accessibility tests
4. Test with screen reader (NVDA, JAWS, VoiceOver)
5. User testing with international users

---

## Research Sources

All research sourced from authoritative accessibility and UX guidelines:

1. **W3C ARIA Authoring Practices Guide (APG)**
   - Combobox Pattern: https://www.w3.org/WAI/ARIA/apg/patterns/combobox/
   - Editable Combobox with List Autocomplete Example

2. **GOV.UK Accessible Autocomplete**
   - https://alphagov.github.io/accessible-autocomplete/
   - User-tested component built to WCAG 2.1 AA
   - Superior to W3C reference implementation in testing

3. **Orange Digital Accessibility Guidelines**
   - Best practices for autocomplete components
   - Focus management recommendations (direct focus > aria-activedescendant)
   - Live region messaging patterns

4. **Adam Silver on Accessible Autocomplete**
   - https://adamsilver.io/blog/building-an-accessible-autocomplete-control/
   - Foundational structure (progressive enhancement from native select)
   - Keyboard navigation and screen reader support

5. **Darin Senneff on Reorderable Lists**
   - https://www.darins.page/articles/designing-a-reorderable-list-component
   - User testing results comparing reordering patterns
   - Buttons outperformed drag handles, grab toggles, text input

6. **ISO 639-2 Standards**
   - Library of Congress: https://www.loc.gov/standards/iso639-2/
   - 490 languages with both bibliographic (B) and terminology (T) codes
   - Some overlap with ISO 639-1 (2-letter codes)

---

## Key Metrics for Success

When implementing, measure:

1. **Usability**
   - Users can find a language by typing code OR name
   - Time to reorder 3 languages < 30 seconds
   - Success rate without instructions > 80%

2. **Accessibility**
   - Keyboard navigation works end-to-end
   - Screen reader announces all states and changes
   - 48×48px minimum touch targets met
   - High contrast mode passes WCAG AA

3. **Correctness**
   - Only valid ISO 639-2 codes accepted
   - Preference order preserved correctly
   - Duplicate languages prevented

4. **Performance**
   - Filtering 490 items < 50ms
   - No visual jank on reordering

---

## Questions Answered

### 1. What are common UX patterns for language code input?

**Autocomplete combobox** (editable input + filtered listbox) is the standard from:
- W3C ARIA Authoring Practices Guide
- GOV.UK accessibility team (user-tested)
- Orange Digital Accessibility Guidelines
- Modern accessible components (React Aria, Headless UI)

### 2. Should we use free text + validation, dropdown, or autocomplete?

**Autocomplete** is best because:
- Supports both code ("eng") and name ("English") input
- Non-overwhelming (filters 490 → ~10 results)
- Accessible (live regions for screen readers)
- Progressive enhancement (works without JavaScript)
- Typo-tolerant (case-insensitive, partial match)

### 3. How can we help users discover valid codes?

Three strategies:
1. **Autocomplete filtering** - Type to narrow down
2. **Live announcements** - "13 results available"
3. **Endonym support** - Search by local name ("français" finds French)
4. **Minimum character requirement** - Guides users ("Type 3+ characters")

### 4. What's the balance between flexibility and correctness?

- **Flexibility:** Accept code OR name input, support typos and case variations
- **Correctness:** Validate against official ISO 639-2 list before saving
- **Result:** Users get autocomplete help during input; server validates on save

---

## Additional Resources

### For Policy Editor Team
- Review `/docs/design/design-language-code-input-ux.md` for architectural context
- Use `/docs/design/LANGUAGE-INPUT-SUMMARY.md` for team alignment
- Implement with `/docs/design/LANGUAGE-INPUT-IMPLEMENTATION-GUIDE.md`

### For Accessibility Review
- Checklist in design-language-code-input-ux.md (§ Accessibility Checklist)
- W3C ARIA Pattern reference implementation
- GOV.UK accessible-autocomplete source code

### For Future Enhancement
- Document discusses drag-and-drop optional enhancement
- Future section covers recently-used languages, language families, favorites
- User testing recommended for international users (endonym support)

---

**Document Version:** 1.0
**Last Updated:** 2025-11-24
**Maintainer:** Claude Code Research
**Status:** Ready for Implementation
