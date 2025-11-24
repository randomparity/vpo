# Language Code Input UX: ISO 639-2 Form Patterns

**Status:** Research & Design Decision
**Date:** 2025-11-24
**Context:** Policy editor needs user-friendly input for ISO 639-2 language codes
**Applies To:** Policy editor form, language preference lists

---

## Executive Summary

For ISO 639-2 language code input in the policy editor, we recommend an **accessible autocomplete combobox** pattern with reorderable list support. This balances discoverability, validation, and usability while maintaining accessibility for all users, including those using assistive technologies.

The pattern combines:
- **Free text input with autocomplete** (not strict dropdown) to support typed codes
- **Live filtering** showing matching language names and codes
- **Reorderable list UI** with button-based up/down controls as the primary mechanism
- **Drag-and-drop** as optional enhancement for power users
- **WAI-ARIA accessibility** with proper focus management and screen reader support

---

## Problem Statement

The policy editor requires users to specify language codes in two scenarios:

1. **Single language input:** Simple field for a single ISO 639-2 code
2. **Ordered list input:** Preference list where order matters (e.g., preferred audio tracks)

**User challenges:**
- ISO 639-2 codes are cryptic (eng, jpn, fra) and users rarely memorize them
- Codes must be validated against the official ISO 639-2 standard (~490 languages)
- Users may know language names (English, Japanese) but not the codes
- Support for endonyms (local names) would improve international usability
- Preference ordering requires clear, discoverable reordering UI

**Constraints:**
- Must work in vanilla JavaScript (no framework-specific components)
- Must be accessible (WCAG 2.1 AA, WAI-ARIA compliant)
- Must support keyboard-only navigation
- Must not overwhelm users with 490 options at once

---

## Research Findings

### 1. Language Code Challenges

ISO 639-2 defines three-letter codes for languages, with some variants:
- **Primary set (ISO 639-2/B):** Traditional bibliographic codes
- **Terminology set (ISO 639-2/T):** Preferred codes for terminology
- ~490 total languages supported

**Users rarely know codes by heart.** Even polyglots struggle to recall "jpn" vs "jap" or which code represents their target language. Support for language *names* is critical.

### 2. Autocomplete Pattern Research

Research from W3C WAI-ARIA, GOV.UK, and Orange Digital Accessibility shows that **editable combobox with list autocomplete** is the optimal pattern for language selection and similar controlled vocabularies.

#### Why Autocomplete > Dropdown

| Aspect | Autocomplete Combobox | Closed Dropdown |
|--------|----------------------|-----------------|
| **Typing codes** | Users can type "eng" directly | Requires scrolling through 490 items |
| **Discovering names** | Type "eng" to find "English (eng)" | Must scroll or search for endonym |
| **Typo tolerance** | Case-insensitive partial matching | Exact match only |
| **Mixed input** | Users can mix codes and names | One-way lookup only |
| **Accessibility** | Live regions announce matches | Dropdown closed until opened |

#### Key Accessibility Features

**W3C ARIA Authoring Practices recommend:**

1. **Focus Management**
   - Keep DOM focus on input, use `aria-activedescendant` to manage listbox focus (W3C approach)
   - OR use `focus()` on listbox options (GOV.UK/Orange approach—more robust on mobile)
   - JavaScript must ensure focused options scroll into view
   - Users never lose context of what they typed

2. **ARIA Attributes**
   ```
   role="combobox" on input
   aria-autocomplete="list"
   aria-controls="[id of listbox]"
   aria-expanded="true|false"

   role="listbox" on suggestion container
   role="option" on each suggestion
   aria-selected="true|false" (visual state indicator)
   aria-posinset and aria-setsize (position in list)
   ```

3. **Live Regions for Context**
   - Announce minimum character requirement ("Type at least 2 characters to see suggestions")
   - Announce result count ("13 results available")
   - Announce current selection status ("English 1 of 13")
   - Use `role="status"` with `aria-live="polite"` for non-intrusive updates

4. **Keyboard Navigation**
   ```
   In input:
   - Arrow Down: Open list and move focus to first match
   - Arrow Up: Move to previous option
   - Arrow Down/Up: Cycle through matches (wraps around)
   - Enter: Select focused option
   - Escape: Close list, keep typed value
   - Tab: Close list, move focus out of component

   Text editing keys work normally (Backspace, Delete, etc.)
   ```

5. **Inclusive Design Considerations**
   - Support **endonyms** (local names): Users in France expect to type "français"
   - Store endonym in data attribute: `data-endonym="français"`
   - Filter by both name and endonym when user types
   - Display both in suggestions: "French (français) [fra]"

### 3. Reorderable List Patterns

For language preference lists, **button-based up/down controls significantly outperform alternatives** in user testing (per Darin Senneff's design research).

#### Pattern Comparison

| Pattern | Strengths | Weaknesses | When to Use |
|---------|-----------|-----------|------------|
| **Buttons (Up/Down)** | Intuitive, keyboard-accessible, fast learning | Slower for large lists, limited icon space | ✓ Primary for 2–10 items |
| **Drag & Drop** | Intuitive for mouse users, visual feedback | Not keyboard-accessible by default, scrolling issues | Optional enhancement |
| **Number Input** | Precise positioning | Confusing UX, users don't expect text input in lists | Avoid |
| **Grab Toggles** | Minimal space | Poor affordance, users don't know what they do | Avoid |

#### Recommended Pattern: Hybrid Approach

**Primary (keyboard & mouse accessible):**
- Pair up/down arrow buttons for each list item (48×48px minimum)
- Single-tap/click to move one position
- Visual focus indicator (4px border)
- Support Shift+Arrow for larger moves (e.g., 5 positions)

**Enhancement (drag & drop for power users):**
- Add drag handle icon (`⋮⋮` or `☰`) at item start
- Indicate draggable with cursor change on hover
- Show insertion marker or drop zone
- Respect `prefers-reduced-motion` by disabling animations for users with motion sensitivity

**Accessibility features:**
- All operations keyboard-navigable (Tab to move focus between items, arrow keys to reorder)
- Live region announces changes: "Moved English down 1 position"
- Skip the grab toggle if using buttons—it's redundant

### 4. Minimum Character Requirement

GOV.UK user testing found that **indicating minimum characters (2–3) improves usability.**

Users prefer seeing "Type 2 more characters to see suggestions" rather than an overwhelming list or empty state. This:
- Reduces cognitive load (not 490 options to see)
- Gives users actionable feedback
- Prevents accidental selection

For 490 languages, 3 characters is optimal:
- "eng" uniquely identifies English (among other 3-char matches)
- "jp" or "ja" still needs refinement; "jpn" is clear
- Matches typical autocomplete pattern (3 chars for reasonable filtering)

---

## Decision: Recommended UX Pattern

### For Single Language Input

Use an **accessible autocomplete combobox** with these features:

```html
<div class="language-input">
  <label for="lang-input">Language</label>

  <input
    id="lang-input"
    type="text"
    role="combobox"
    aria-autocomplete="list"
    aria-expanded="false"
    aria-controls="lang-listbox"
    placeholder="e.g., eng, French..."
    maxlength="3"
  >

  <div id="lang-status" role="status" aria-live="polite"></div>

  <ul
    id="lang-listbox"
    role="listbox"
    hidden
  >
    <!-- Dynamically populated options -->
    <li role="option" aria-selected="false" data-code="eng">
      English (eng)
    </li>
  </ul>
</div>
```

**Features:**
- **Min 3 characters** before showing suggestions (configurable)
- **Case-insensitive partial matching** on name and code
- **Endonym support** (search "français" to find French)
- **Live feedback:** "3 results available. French 1 of 3"
- **Keyboard:** ↓↑ to navigate, Enter to select, Esc to close
- **Tab behavior:** Closes list, preserves typed value if valid code exists

### For Ordered List Input

Use a **button-based reorderable list** with optional drag-and-drop:

```html
<div class="language-list">
  <label>Preferred Languages (in order)</label>

  <ul id="lang-prefs" class="language-preference-list">
    <li id="lang-item-0" class="language-item" tabindex="0">
      <span class="drag-handle" aria-label="Drag handle"></span>
      <span class="language-name">English (eng)</span>

      <div class="reorder-buttons">
        <button
          aria-label="Move English up"
          data-action="move-up"
          data-index="0"
        >
          ↑
        </button>
        <button
          aria-label="Move English down"
          data-action="move-down"
          data-index="0"
        >
          ↓
        </button>
        <button
          aria-label="Remove English"
          data-action="remove"
          data-index="0"
        >
          ✕
        </button>
      </div>
    </li>
  </ul>

  <div id="list-status" role="status" aria-live="polite"></div>
</div>
```

**Features:**
- **Up/Down buttons** as primary interaction (48×48px minimum)
- **Drag handle** optional (for mouse users)
- **Remove button** for deleting from list
- **Live announcements:** "Moved English down 1 position. Order: 1. English, 2. Japanese"
- **Keyboard navigation:** Tab between items, arrow keys to reorder
- **Focus management:** Clear focus ring (4px) on hovered/focused button
- **Motion-safe:** Animations respect `prefers-reduced-motion`

---

## Rationale

### Why Autocomplete Over Dropdown

1. **Discoverability:** Users can search by language name or code without scrolling 490 items
2. **Flexibility:** Supports both "eng" (code) and "English" (name) input
3. **Validation:** Can validate that typed code exists in ISO 639-2 standard
4. **Accessibility:** Live regions and focus management work better than scrollable dropdowns
5. **International:** Endonym support (French speakers can type "français") improves usability

### Why Buttons Over Drag-and-Drop

1. **Accessibility:** Buttons are keyboard-navigable by default; drag-and-drop requires complex ARIA
2. **Reliability:** Works on all devices (mobile, touch, keyboard-only)
3. **Clarity:** Users understand button labels ("Move up") better than grabby affordances
4. **Testing:** User testing shows buttons are consistently more intuitive (pick up fastest, ignore instructions)

### Why Hybrid for Lists

1. **Progressive enhancement:** Lists work without JavaScript (fallback: text inputs)
2. **Power users:** Drag-and-drop is faster for reordering 5+ items
3. **Accessibility:** Buttons remain primary; drag is bonus
4. **Assistive tech:** Screen readers announce button actions; drag-and-drop is more complex

---

## Alternatives Considered & Rejected

### 1. Closed Dropdown (Select Element)

**Why rejected:**
- Forces users to scroll 490 items to find a language
- No search/filter; must click to open, then arrow down to find match
- Poor mobile experience (native select is tiny)
- Hard to support endonyms without complex option grouping

**When acceptable:** Only if you filter languages to a small subset (e.g., 10 most common)

### 2. Free Text Input (No Validation)

**Why rejected:**
- Allows invalid codes ("Eng", "ENGLISH", "xyz123")
- No discoverability—users must know codes or language names
- Leads to data errors in policies
- No feedback if user misspells

**When acceptable:** Only with strong backend validation and error messaging

### 3. Multi-Select Dropdown

**Why rejected:**
- Doesn't preserve order (important for language preference)
- Difficult to reorder selections without custom UI
- Smaller click targets for reordering
- Less discoverable than autocomplete

### 4. Drag-and-Drop Only (No Buttons)

**Why rejected:**
- Not keyboard-accessible without complex ARIA (`aria-grab`, etc.)
- Doesn't work for touch users on some devices
- Scrolling while dragging is difficult
- Less discoverable—users may not realize list is reorderable

### 5. Numeric Input for Reordering

**Why rejected:**
- User testing shows confusion and errors
- Users expect to type numbering but UI resets/reorders unexpectedly
- Counterintuitive compared to move buttons
- Harder to preview changes before committing

---

## Implementation Notes

### HTML Structure

```html
<!-- Single language input -->
<fieldset>
  <legend>Add Language Preference</legend>

  <div class="language-input-group">
    <label for="lang-new">Language:</label>
    <input
      id="lang-new"
      type="text"
      role="combobox"
      aria-autocomplete="list"
      aria-expanded="false"
      aria-controls="lang-suggestions"
      placeholder="Type 3+ characters..."
    >
    <div id="lang-hint" role="status" aria-live="polite">
      Type 3+ characters to search
    </div>
    <ul id="lang-suggestions" role="listbox" hidden></ul>
  </div>

  <button type="button" id="add-lang">Add Language</button>
</fieldset>

<!-- Ordered language list -->
<fieldset>
  <legend>Language Preferences</legend>
  <ul id="language-prefs" class="language-prefs-list">
    <!-- Items dynamically added -->
  </ul>
  <div id="list-status" role="status" aria-live="polite"></div>
</fieldset>
```

### Vanilla JavaScript Implementation Sketch

```javascript
class LanguageAutocomplete {
  constructor(inputEl, listboxEl, statusEl) {
    this.input = inputEl;
    this.listbox = listboxEl;
    this.status = statusEl;
    this.languages = []; // ISO 639-2 list loaded from data
    this.selectedIndex = -1;

    this.init();
  }

  init() {
    this.input.addEventListener('input', (e) => this.handleInput(e));
    this.input.addEventListener('keydown', (e) => this.handleKeydown(e));
    this.listbox.addEventListener('click', (e) => this.handleSelect(e));
  }

  handleInput(e) {
    const query = e.target.value.trim().toLowerCase();

    if (query.length < 3) {
      this.closeListbox();
      this.updateStatus(`Type 3+ characters to search`);
      return;
    }

    const matches = this.languages.filter(lang =>
      lang.name.toLowerCase().includes(query) ||
      lang.code.toLowerCase().includes(query) ||
      (lang.endonym && lang.endonym.toLowerCase().includes(query))
    );

    this.renderMatches(matches);
    this.updateStatus(
      `${matches.length} result${matches.length === 1 ? '' : 's'} available`
    );
    this.openListbox();
  }

  handleKeydown(e) {
    if (!this.isOpen()) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        this.selectNext();
        break;
      case 'ArrowUp':
        e.preventDefault();
        this.selectPrevious();
        break;
      case 'Enter':
        e.preventDefault();
        this.selectCurrent();
        break;
      case 'Escape':
        e.preventDefault();
        this.closeListbox();
        break;
    }
  }

  renderMatches(matches) {
    this.listbox.innerHTML = matches.map((lang, idx) => `
      <li
        role="option"
        aria-selected="false"
        data-code="${lang.code}"
        data-index="${idx}"
      >
        ${lang.name} (${lang.code})
      </li>
    `).join('');

    this.selectedIndex = -1;
  }

  openListbox() {
    this.listbox.hidden = false;
    this.input.setAttribute('aria-expanded', 'true');
  }

  closeListbox() {
    this.listbox.hidden = true;
    this.input.setAttribute('aria-expanded', 'false');
  }

  selectNext() {
    const options = this.listbox.querySelectorAll('[role="option"]');
    this.selectedIndex = (this.selectedIndex + 1) % options.length;
    this.focusOption(this.selectedIndex);
  }

  focusOption(idx) {
    const options = this.listbox.querySelectorAll('[role="option"]');
    options.forEach((opt, i) => {
      opt.setAttribute('aria-selected', i === idx ? 'true' : 'false');
    });
    const focused = options[idx];
    if (focused) {
      focused.scrollIntoView({ block: 'nearest' });
    }
  }

  selectCurrent() {
    const focused = this.listbox.querySelector('[aria-selected="true"]');
    if (focused) {
      this.input.value = focused.getAttribute('data-code');
      this.closeListbox();
      this.input.dispatchEvent(
        new CustomEvent('language-selected', {
          detail: { code: focused.getAttribute('data-code') }
        })
      );
    }
  }

  updateStatus(message) {
    this.status.textContent = message;
  }

  isOpen() {
    return !this.listbox.hidden;
  }
}

// Usage:
const autocomplete = new LanguageAutocomplete(
  document.getElementById('lang-new'),
  document.getElementById('lang-suggestions'),
  document.getElementById('lang-hint')
);
```

### Reorderable List (Button-Based)

```javascript
class LanguagePreferenceList {
  constructor(listEl, statusEl) {
    this.list = listEl;
    this.status = statusEl;
    this.items = [];

    this.list.addEventListener('click', (e) => this.handleClick(e));
    this.list.addEventListener('keydown', (e) => this.handleKeydown(e));
  }

  addItem(code, name) {
    const idx = this.items.length;
    const li = document.createElement('li');
    li.className = 'language-item';
    li.id = `lang-item-${idx}`;
    li.tabIndex = 0;
    li.innerHTML = `
      <span class="drag-handle" aria-label="Drag handle"></span>
      <span class="language-name">${name}</span>
      <div class="reorder-buttons">
        <button
          aria-label="Move ${name} up"
          data-action="move-up"
          ${idx === 0 ? 'disabled' : ''}
        >↑</button>
        <button
          aria-label="Move ${name} down"
          data-action="move-down"
          ${idx === this.items.length - 1 ? 'disabled' : ''}
        >↓</button>
        <button
          aria-label="Remove ${name}"
          data-action="remove"
        >✕</button>
      </div>
    `;

    this.list.appendChild(li);
    this.items.push({ code, name });
    this.updateButtonStates();
  }

  handleClick(e) {
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;

    const li = btn.closest('li');
    const idx = Array.from(this.list.children).indexOf(li);
    const action = btn.getAttribute('data-action');

    switch (action) {
      case 'move-up':
        this.moveItem(idx, idx - 1);
        break;
      case 'move-down':
        this.moveItem(idx, idx + 1);
        break;
      case 'remove':
        this.removeItem(idx);
        break;
    }
  }

  moveItem(fromIdx, toIdx) {
    if (toIdx < 0 || toIdx >= this.items.length) return;

    [this.items[fromIdx], this.items[toIdx]] =
      [this.items[toIdx], this.items[fromIdx]];

    this.render();
    this.updateStatus(
      `Moved ${this.items[toIdx].name} to position ${toIdx + 1}`
    );
  }

  removeItem(idx) {
    const removed = this.items.splice(idx, 1)[0];
    this.render();
    this.updateStatus(`Removed ${removed.name}`);
  }

  render() {
    this.list.innerHTML = this.items.map((item, idx) => `
      <li class="language-item" id="lang-item-${idx}" tabindex="0">
        <span class="drag-handle"></span>
        <span class="language-name">${item.name}</span>
        <div class="reorder-buttons">
          <button
            aria-label="Move ${item.name} up"
            data-action="move-up"
            ${idx === 0 ? 'disabled' : ''}
          >↑</button>
          <button
            aria-label="Move ${item.name} down"
            data-action="move-down"
            ${idx === this.items.length - 1 ? 'disabled' : ''}
          >↓</button>
          <button
            aria-label="Remove ${item.name}"
            data-action="remove"
          >✕</button>
        </div>
      </li>
    `).join('');

    this.updateButtonStates();
  }

  updateButtonStates() {
    this.list.querySelectorAll('[data-action="move-up"]').forEach((btn, idx) => {
      btn.disabled = idx === 0;
    });

    this.list.querySelectorAll('[data-action="move-down"]').forEach((btn, idx) => {
      btn.disabled = idx === this.items.length - 1;
    });
  }

  updateStatus(message) {
    this.status.textContent = message;
  }

  getValues() {
    return this.items.map(item => item.code);
  }
}
```

### CSS Considerations

```css
/* Autocomplete Input */
[role="combobox"] {
  padding: 0.5rem 0.75rem;
  border: 2px solid #ccc;
  border-radius: 4px;
  font-size: 1rem;
  min-width: 200px;
}

[role="combobox"]:focus {
  outline: none;
  border-color: #0066cc;
  box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.1);
}

/* Listbox */
[role="listbox"] {
  list-style: none;
  padding: 0;
  margin: 0.25rem 0 0 0;
  border: 1px solid #ccc;
  border-radius: 4px;
  max-height: 200px;
  overflow-y: auto;
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

[role="option"] {
  padding: 0.5rem 0.75rem;
  cursor: pointer;
}

[role="option"]:hover,
[role="option"][aria-selected="true"] {
  background-color: #f0f0f0;
  color: #000;
}

/* Status text (live region) */
[role="status"] {
  font-size: 0.875rem;
  color: #666;
  margin-top: 0.25rem;
}

/* Reorderable list */
.language-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  margin-bottom: 0.5rem;
  list-style: none;
}

.language-item:focus {
  outline: 4px solid #0066cc;
  outline-offset: 2px;
}

.drag-handle {
  cursor: grab;
  color: #999;
  font-size: 1.25rem;
  flex-shrink: 0;
}

.language-name {
  flex-grow: 1;
  font-weight: 500;
}

.reorder-buttons {
  display: flex;
  gap: 0.25rem;
  flex-shrink: 0;
}

.reorder-buttons button {
  min-width: 48px;
  min-height: 48px;
  padding: 0.5rem;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  font-size: 1rem;
}

.reorder-buttons button:hover:not(:disabled) {
  background-color: #f5f5f5;
  border-color: #999;
}

.reorder-buttons button:focus {
  outline: 2px solid #0066cc;
  outline-offset: 2px;
}

.reorder-buttons button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* High contrast support */
@media (prefers-contrast: more) {
  [role="combobox"],
  [role="listbox"],
  .language-item,
  .reorder-buttons button {
    border-color: currentColor;
    border-width: 2px;
  }
}

/* Motion-safe animations */
@media (prefers-reduced-motion: no-preference) {
  [role="listbox"] {
    animation: slideDown 0.15s ease-out;
  }

  @keyframes slideDown {
    from {
      opacity: 0;
      transform: translateY(-4px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
}
```

### Data Structure (ISO 639-2 Languages)

Store language data in a JSON file or embedded in the page:

```json
[
  {
    "code": "eng",
    "name": "English",
    "endonym": null,
    "comment": ""
  },
  {
    "code": "fra",
    "name": "French",
    "endonym": "français",
    "comment": ""
  },
  {
    "code": "jpn",
    "name": "Japanese",
    "endonym": "日本語",
    "comment": ""
  },
  {
    "code": "deu",
    "name": "German",
    "endonym": "Deutsch",
    "comment": ""
  }
]
```

Source: [Library of Congress ISO 639-2 Code List](https://www.loc.gov/standards/iso639-2/php/code_list.php)

### Validation

**Client-side:**
- Check that input is a valid ISO 639-2 code
- Only accept 3-character alphanumeric codes

**Server-side:**
- Validate against authoritative ISO 639-2 list before saving
- Reject policies with invalid language codes
- Log validation errors for debugging

---

## Accessibility Checklist

- [ ] Input has `role="combobox"`, `aria-autocomplete="list"`, `aria-expanded`, `aria-controls`
- [ ] Listbox has `role="listbox"`, options have `role="option"`, `aria-selected`
- [ ] Focus indicator visible and meets contrast requirements (3:1 minimum, 4px for composite controls)
- [ ] Keyboard navigation works: Arrow keys, Enter, Escape, Tab
- [ ] Live region (`role="status"`) announces results and actions
- [ ] All buttons have descriptive `aria-label` (e.g., "Move English up")
- [ ] Disabled buttons are properly marked (`disabled` attribute or `aria-disabled="true"`)
- [ ] Color is not the only indicator of state (use underline, border, text change)
- [ ] Component works with screen readers (NVDA, JAWS, VoiceOver tested)
- [ ] Touch targets are 48×48px minimum (buttons, draggable items)
- [ ] Respects `prefers-reduced-motion` (animations disabled if set)
- [ ] High contrast mode works (borders/text remain visible)

---

## Testing Strategy

### Unit Tests
- Language code validation (valid/invalid codes)
- Filtering logic (case-insensitive, partial match, endonym search)
- Reordering logic (move up/down, remove, boundary cases)
- Live region message generation

### Integration Tests
- Keyboard navigation (arrow keys, Enter, Escape, Tab)
- Mouse interaction (click, hover, drag-drop if implemented)
- Form submission with valid/invalid codes
- Persistence of preference order

### Accessibility Testing
- NVDA/JAWS with screen reader
- Keyboard-only navigation (no mouse)
- High contrast mode (Windows High Contrast)
- Motion sensitivity (`prefers-reduced-motion`)
- Zoom/magnification (200%+ text size)

### User Testing
- Can users find a language by typing code?
- Can users find a language by typing name?
- Is the reordering UI clear and intuitive?
- Do international users appreciate endonym support?

---

## Future Enhancements

1. **Drag-and-drop** (if testing shows demand from power users)
2. **Recently used languages** (most common selections at top)
3. **Language families** (group by language family for discovery)
4. **Favorite/star languages** (pin frequently used languages)
5. **Import/export** (save/load language preference lists)
6. **Custom aliases** (let users define shortcuts like "en" → "eng")

---

## Related Docs

- [Design: Policy Editor](/docs/design/design-policy-editor.md) *(planned)*
- [Usage: Policy Authoring](/docs/usage/policy-authoring.md) *(planned)*
- [Glossary: ISO 639](/docs/glossary.md) (language codes)
- [W3C ARIA Combobox Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/)
- [GOV.UK Accessible Autocomplete](https://alphagov.github.io/accessible-autocomplete/)
