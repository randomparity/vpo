# Language Code Input UX - Quick Reference

## Decision: Autocomplete Combobox + Button-Based Reordering

### Single Language Input

**Pattern:** Accessible autocomplete combobox (editable input + filtering listbox)

**Why:**
- Users can type language names ("English") or codes ("eng")
- Filters 490 languages down without overwhelming users
- Accessible to keyboard and screen reader users
- Supports international users with endonym search

**Key features:**
- Min 3 characters before showing suggestions
- Case-insensitive partial matching
- Live region announces result count
- Arrow keys navigate, Enter selects, Escape closes
- Data attribute for endonyms (e.g., "français" for French)

### Ordered List Input

**Pattern:** Buttons (Up/Down/Remove) + optional drag-and-drop

**Why:**
- User testing shows buttons are most intuitive
- Keyboard-accessible without complex ARIA
- Works on all devices (mobile, keyboard-only)
- Drag-and-drop available as bonus for power users

**Key features:**
- 48×48px minimum button size
- Live region announces moves: "Moved English down 1 position"
- Tab to move focus between items
- Arrow keys reorder (Shift+Arrow for larger moves)
- Drag handle (`⋮⋮`) optional, not required

---

## Rejected Alternatives

| Pattern | Why Rejected |
|---------|-------------|
| Closed dropdown (select) | Can't search/filter 490 items; poor mobile |
| Free text (no validation) | Allows invalid codes; no discoverability |
| Multi-select dropdown | Doesn't preserve order |
| Numeric input for reordering | Confusing UX in testing; numbers are counterintuitive |
| Drag-and-drop only | Not keyboard-accessible; doesn't work on touch |

---

## Implementation Checklist

### HTML
- [ ] Use `<input role="combobox" aria-autocomplete="list" aria-controls="[listbox-id]">`
- [ ] Create `<ul role="listbox">` for suggestions
- [ ] Add `<li role="option">` for each language
- [ ] Include `<div role="status" aria-live="polite">` for announcements
- [ ] Buttons use `aria-label` (not just icons)

### JavaScript
- [ ] Filter on `input` event (3+ chars)
- [ ] Handle arrow keys (Up/Down/Enter/Escape) in keydown handler
- [ ] Show/hide listbox with `hidden` attribute
- [ ] Update `aria-expanded` on input
- [ ] Update `aria-selected` on focused option
- [ ] Announce results in live region

### CSS
- [ ] Input focus: 2-3px blue outline or shadow
- [ ] Options hover/selected: different background color
- [ ] Buttons: 48×48px minimum, visible focus indicator
- [ ] Respect `prefers-reduced-motion` (disable animations)

### Accessibility Testing
- [ ] Keyboard-only navigation works (Tab, arrows, Enter)
- [ ] Screen reader reads suggestions and status updates
- [ ] High contrast mode visible (no color-only indicators)
- [ ] Touch targets are 48×48px minimum
- [ ] Focus indicators clear (3:1 contrast minimum)

---

## Code Skeleton (Vanilla JS)

```javascript
// Autocomplete
class LanguageAutocomplete {
  constructor(inputEl, listboxEl, statusEl) { /*...*/ }
  handleInput(e) {
    const query = e.target.value.toLowerCase();
    if (query.length < 3) return;
    const matches = this.languages.filter(/* search name/code/endonym */);
    this.updateStatus(`${matches.length} results available`);
  }
  handleKeydown(e) {
    // Arrow Up/Down: navigate options
    // Enter: select current
    // Escape: close listbox
  }
}

// Reorderable list
class LanguagePreferenceList {
  constructor(listEl, statusEl) { /*...*/ }
  moveItem(fromIdx, toIdx) {
    [this.items[fromIdx], this.items[toIdx]] =
      [this.items[toIdx], this.items[fromIdx]];
    this.updateStatus(`Moved to position ${toIdx + 1}`);
  }
}
```

---

## Data Requirements

Need ISO 639-2 language list with:
```json
[
  {
    "code": "eng",
    "name": "English",
    "endonym": null
  },
  {
    "code": "fra",
    "name": "French",
    "endonym": "français"
  },
  // ... 490 total
]
```

Source: [Library of Congress](https://www.loc.gov/standards/iso639-2/php/code_list.php)

---

## References

- **Full design doc:** `/docs/design/design-language-code-input-ux.md`
- **W3C Combobox Pattern:** https://www.w3.org/WAI/ARIA/apg/patterns/combobox/
- **GOV.UK Accessible Autocomplete:** https://alphagov.github.io/accessible-autocomplete/
- **Reorderable List Patterns:** https://www.darins.page/articles/designing-a-reorderable-list-component

## Related docs

- [Language Input UX Design](design-language-code-input-ux.md) - Full design document
- [Language Input Research Summary](LANGUAGE-INPUT-RESEARCH-SUMMARY.md) - Research findings
- [Policy Editor](../usage/policy-editor.md) - Policy editor user guide
