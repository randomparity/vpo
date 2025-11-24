# Language Code Input - Implementation Guide

This is a hands-on guide for implementing the ISO 639-2 language code input UX in the policy editor.

## Part 1: Single Language Autocomplete Input

### Step 1: HTML Markup

```html
<div class="language-input-wrapper">
  <label for="language-input">
    Language
    <span class="required" aria-label="required">*</span>
  </label>

  <!-- Input field with combobox semantics -->
  <div class="input-group">
    <input
      id="language-input"
      type="text"
      role="combobox"
      aria-autocomplete="list"
      aria-expanded="false"
      aria-controls="language-listbox"
      aria-describedby="language-hint"
      placeholder="e.g., eng, French..."
      maxlength="3"
      autocomplete="off"
    >
  </div>

  <!-- Helpful hint text (non-intrusive) -->
  <div id="language-hint" class="hint-text">
    Type 3+ characters to search by language code or name
  </div>

  <!-- Live region for screen reader announcements -->
  <div id="language-status" role="status" aria-live="polite" aria-atomic="true">
  </div>

  <!-- Suggestion listbox (hidden by default) -->
  <ul
    id="language-listbox"
    role="listbox"
    aria-label="Language suggestions"
    hidden
  >
    <!-- Dynamically populated by JavaScript -->
  </ul>
</div>
```

### Step 2: CSS Styling

```css
.language-input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

label {
  font-weight: 600;
  font-size: 0.95rem;
}

.required {
  color: #d32f2f;
  font-weight: bold;
}

.input-group {
  position: relative;
  display: flex;
}

#language-input {
  flex: 1;
  padding: 0.625rem 0.75rem;
  border: 2px solid #e0e0e0;
  border-radius: 4px;
  font-size: 1rem;
  font-family: inherit;
  transition: border-color 0.15s, box-shadow 0.15s;
  min-width: 200px;
}

#language-input:hover {
  border-color: #bdbdbd;
}

#language-input:focus {
  outline: none;
  border-color: #1976d2;
  box-shadow: 0 0 0 3px rgba(25, 118, 210, 0.1);
}

#language-input:disabled {
  background-color: #f5f5f5;
  color: #9e9e9e;
  cursor: not-allowed;
}

/* Error state */
#language-input[aria-invalid="true"] {
  border-color: #d32f2f;
}

#language-input[aria-invalid="true"]:focus {
  box-shadow: 0 0 0 3px rgba(211, 47, 47, 0.1);
}

.hint-text {
  font-size: 0.875rem;
  color: #666;
  line-height: 1.4;
}

#language-status {
  font-size: 0.875rem;
  color: #1976d2;
  line-height: 1.4;
  min-height: 1.4rem; /* Prevent layout shift */
}

/* Listbox */
#language-listbox {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 1000;
  list-style: none;
  margin: 0.25rem 0 0 0;
  padding: 0;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background-color: #fff;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  max-height: 250px;
  overflow-y: auto;
}

#language-listbox[hidden] {
  display: none;
}

#language-listbox[role="listbox"] > li[role="option"] {
  padding: 0.625rem 0.75rem;
  cursor: pointer;
  transition: background-color 0.1s;
  border-bottom: 1px solid #f5f5f5;
}

#language-listbox[role="listbox"] > li[role="option"]:last-child {
  border-bottom: none;
}

/* Hover state */
#language-listbox[role="listbox"] > li[role="option"]:hover {
  background-color: #f5f5f5;
  color: #000;
}

/* Focus/selected state */
#language-listbox[role="listbox"] > li[role="option"][aria-selected="true"] {
  background-color: #e3f2fd;
  color: #1976d2;
  font-weight: 500;
}

/* Keyboard focus indicator */
#language-listbox[role="listbox"] > li[role="option"]:focus-visible {
  outline: 2px solid #1976d2;
  outline-offset: -2px;
}

/* High contrast mode */
@media (prefers-contrast: more) {
  #language-input,
  #language-listbox {
    border-width: 2px;
    border-color: currentColor;
  }
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  #language-listbox {
    animation: none;
  }
}

@media (prefers-reduced-motion: no-preference) {
  #language-listbox {
    animation: slideDown 0.12s ease-out;
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

/* Dark mode support */
@media (prefers-color-scheme: dark) {
  #language-input {
    background-color: #1e1e1e;
    color: #fff;
    border-color: #424242;
  }

  #language-input:focus {
    border-color: #90caf9;
    box-shadow: 0 0 0 3px rgba(144, 202, 249, 0.2);
  }

  #language-listbox {
    background-color: #1e1e1e;
    border-color: #424242;
    color: #fff;
  }

  #language-listbox > li[role="option"]:hover {
    background-color: #2a2a2a;
  }

  #language-listbox > li[role="option"][aria-selected="true"] {
    background-color: #1a3a52;
    color: #90caf9;
  }
}
```

### Step 3: JavaScript Implementation

```javascript
// Load language data (from JSON file or embedded)
const LANGUAGES = [
  { code: 'eng', name: 'English', endonym: null },
  { code: 'fra', name: 'French', endonym: 'français' },
  { code: 'deu', name: 'German', endonym: 'Deutsch' },
  { code: 'jpn', name: 'Japanese', endonym: '日本語' },
  { code: 'zho', name: 'Chinese', endonym: '中文' },
  // ... etc (490 total)
];

class LanguageAutocomplete {
  constructor(inputSelector, listboxSelector, statusSelector) {
    this.input = document.querySelector(inputSelector);
    this.listbox = document.querySelector(listboxSelector);
    this.status = document.querySelector(statusSelector);
    this.languages = LANGUAGES;
    this.selectedIndex = -1;
    this.isOpen = false;

    this.init();
  }

  init() {
    this.input.addEventListener('input', this.handleInput.bind(this));
    this.input.addEventListener('keydown', this.handleKeydown.bind(this));
    this.input.addEventListener('blur', this.handleBlur.bind(this));
    this.listbox.addEventListener('click', this.handleClick.bind(this));
    this.listbox.addEventListener('mouseover', this.handleMouseover.bind(this));
  }

  handleInput(e) {
    const query = e.target.value.trim();

    // If less than 3 characters, close and show hint
    if (query.length < 3) {
      this.close();
      this.updateStatus('Type 3+ characters to search');
      return;
    }

    // Filter languages by query
    const lowerQuery = query.toLowerCase();
    const matches = this.languages.filter(lang => {
      const matchesCode = lang.code.toLowerCase().includes(lowerQuery);
      const matchesName = lang.name.toLowerCase().includes(lowerQuery);
      const matchesEndonym = lang.endonym &&
        lang.endonym.toLowerCase().includes(lowerQuery);
      return matchesCode || matchesName || matchesEndonym;
    });

    // Render matches
    this.renderMatches(matches);

    // Update status and open listbox
    const plural = matches.length === 1 ? '' : 's';
    this.updateStatus(`${matches.length} result${plural} available`);
    this.open();
  }

  handleKeydown(e) {
    if (!this.isOpen) return;

    const options = this.listbox.querySelectorAll('[role="option"]');
    if (options.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        this.selectedIndex = (this.selectedIndex + 1) % options.length;
        this.focusOption(this.selectedIndex);
        break;

      case 'ArrowUp':
        e.preventDefault();
        this.selectedIndex = this.selectedIndex <= 0
          ? options.length - 1
          : this.selectedIndex - 1;
        this.focusOption(this.selectedIndex);
        break;

      case 'Enter':
        e.preventDefault();
        if (this.selectedIndex >= 0) {
          this.selectOption(options[this.selectedIndex]);
        }
        break;

      case 'Escape':
        e.preventDefault();
        this.close();
        break;

      case 'Tab':
        // Tab closes the listbox but allows focus to move out
        this.close();
        break;

      default:
        break;
    }
  }

  handleBlur(e) {
    // Close listbox when focus leaves the input
    // Use setTimeout to allow click events on options to fire first
    setTimeout(() => {
      if (
        !this.input.matches(':focus') &&
        !this.listbox.matches(':focus-within')
      ) {
        this.close();
      }
    }, 100);
  }

  handleClick(e) {
    const option = e.target.closest('[role="option"]');
    if (option) {
      this.selectOption(option);
    }
  }

  handleMouseover(e) {
    const option = e.target.closest('[role="option"]');
    if (option) {
      const options = this.listbox.querySelectorAll('[role="option"]');
      const index = Array.from(options).indexOf(option);
      this.focusOption(index);
    }
  }

  renderMatches(matches) {
    this.listbox.innerHTML = matches.map((lang, idx) => {
      const display = `${lang.name}${lang.endonym ? ` (${lang.endonym})` : ''} [${lang.code}]`;
      return `
        <li
          role="option"
          aria-selected="false"
          data-code="${lang.code}"
          data-index="${idx}"
          title="${lang.name}"
        >
          <strong>${lang.code}</strong> - ${lang.name}${lang.endonym ? ` <em>(${lang.endonym})</em>` : ''}
        </li>
      `;
    }).join('');

    this.selectedIndex = -1;
  }

  focusOption(index) {
    const options = this.listbox.querySelectorAll('[role="option"]');

    options.forEach((opt, i) => {
      opt.setAttribute('aria-selected', i === index ? 'true' : 'false');
    });

    if (options[index]) {
      // Scroll into view if necessary
      options[index].scrollIntoView({ block: 'nearest' });
      // Update status for screen readers
      this.updateStatus(
        `${options[index].textContent} ${index + 1} of ${options.length}`
      );
    }
  }

  selectOption(optionEl) {
    const code = optionEl.getAttribute('data-code');
    this.input.value = code;
    this.input.setAttribute('aria-invalid', 'false');
    this.close();

    // Dispatch custom event for form submission
    this.input.dispatchEvent(new CustomEvent('language-selected', {
      detail: { code }
    }));

    // Optional: Update status
    this.updateStatus(`Selected: ${optionEl.textContent}`);
  }

  open() {
    this.listbox.removeAttribute('hidden');
    this.input.setAttribute('aria-expanded', 'true');
    this.isOpen = true;
  }

  close() {
    this.listbox.setAttribute('hidden', '');
    this.input.setAttribute('aria-expanded', 'false');
    this.isOpen = false;
  }

  updateStatus(message) {
    this.status.textContent = message;
  }

  /**
   * Validate input value against ISO 639-2 codes
   */
  validate() {
    const code = this.input.value.trim().toLowerCase();

    if (!code) {
      this.input.setAttribute('aria-invalid', 'true');
      this.updateStatus('Language code is required');
      return false;
    }

    const found = this.languages.find(lang => lang.code === code);

    if (!found) {
      this.input.setAttribute('aria-invalid', 'true');
      this.updateStatus(`"${code}" is not a valid ISO 639-2 language code`);
      return false;
    }

    this.input.setAttribute('aria-invalid', 'false');
    return true;
  }

  /**
   * Get selected language code
   */
  getValue() {
    return this.input.value.trim().toLowerCase();
  }

  /**
   * Set value programmatically
   */
  setValue(code) {
    const lang = this.languages.find(l => l.code === code);
    if (lang) {
      this.input.value = lang.code;
      this.input.setAttribute('aria-invalid', 'false');
    } else {
      this.input.value = '';
      this.input.setAttribute('aria-invalid', 'true');
    }
  }
}

// Usage:
const autocomplete = new LanguageAutocomplete(
  '#language-input',
  '#language-listbox',
  '#language-status'
);

// Validate on form submission
document.getElementById('policy-form')?.addEventListener('submit', (e) => {
  if (!autocomplete.validate()) {
    e.preventDefault();
  }
});
```

---

## Part 2: Reorderable Language List

### Step 1: HTML Markup

```html
<fieldset class="language-list-fieldset">
  <legend>Preferred Languages (in order of preference)</legend>

  <p class="help-text">
    Reorder languages by clicking the arrow buttons or dragging them.
    Languages at the top are preferred.
  </p>

  <ul id="language-preferences" class="language-preferences-list">
    <!-- Dynamically populated by JavaScript -->
  </ul>

  <!-- Live region for announcements -->
  <div id="list-status" role="status" aria-live="polite" aria-atomic="true">
  </div>
</fieldset>

<!-- Hidden input to store form values -->
<input
  type="hidden"
  id="language-prefs-data"
  name="language_preferences"
  value="eng,jpn,fra"
>
```

### Step 2: CSS Styling

```css
.language-list-fieldset {
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 1rem;
  margin-bottom: 1.5rem;
}

.language-list-fieldset legend {
  font-weight: 600;
  font-size: 0.95rem;
  padding: 0 0.5rem;
}

.help-text {
  font-size: 0.875rem;
  color: #666;
  margin: 0.5rem 0 1rem 0;
}

.language-preferences-list {
  list-style: none;
  padding: 0;
  margin: 0 0 1rem 0;
}

.language-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  margin-bottom: 0.5rem;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background-color: #fafafa;
  transition: all 0.15s;
}

.language-item:focus-within {
  border-color: #1976d2;
  box-shadow: 0 0 0 3px rgba(25, 118, 210, 0.1);
}

.language-item[dragging="true"] {
  opacity: 0.6;
  background-color: #f0f0f0;
}

.drag-handle {
  flex-shrink: 0;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  color: #999;
  user-select: none;
  font-size: 1.25rem;
}

.drag-handle:active {
  cursor: grabbing;
}

.language-item:hover .drag-handle {
  color: #666;
}

.language-info {
  flex: 1;
  min-width: 0;
}

.language-name {
  font-weight: 500;
  font-size: 1rem;
  color: #000;
}

.language-code {
  font-size: 0.875rem;
  color: #999;
}

.reorder-buttons {
  display: flex;
  gap: 0.25rem;
  flex-shrink: 0;
}

.reorder-button {
  width: 48px;
  height: 48px;
  min-width: 48px;
  min-height: 48px;
  padding: 0;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: #fff;
  cursor: pointer;
  font-size: 1.1rem;
  color: #666;
  transition: all 0.1s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.reorder-button:hover:not(:disabled) {
  background-color: #f5f5f5;
  border-color: #999;
  color: #000;
}

.reorder-button:focus {
  outline: 2px solid #1976d2;
  outline-offset: 2px;
}

.reorder-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background-color: #fafafa;
}

.reorder-button:active:not(:disabled) {
  background-color: #e8e8e8;
}

#list-status {
  font-size: 0.875rem;
  color: #1976d2;
  line-height: 1.4;
  min-height: 1.4rem;
}

/* Dark mode */
@media (prefers-color-scheme: dark) {
  .language-item {
    background-color: #2a2a2a;
    border-color: #424242;
  }

  .language-name {
    color: #fff;
  }

  .language-code {
    color: #999;
  }

  .drag-handle {
    color: #666;
  }

  .reorder-button {
    background-color: #1e1e1e;
    border-color: #424242;
    color: #aaa;
  }

  .reorder-button:hover:not(:disabled) {
    background-color: #333;
    border-color: #666;
    color: #fff;
  }
}
```

### Step 3: JavaScript Implementation

```javascript
class LanguagePreferenceList {
  constructor(listSelector, statusSelector, dataInputSelector) {
    this.list = document.querySelector(listSelector);
    this.status = document.querySelector(statusSelector);
    this.dataInput = document.querySelector(dataInputSelector);
    this.items = [];

    this.init();
  }

  init() {
    this.list.addEventListener('click', this.handleClick.bind(this));
    this.list.addEventListener('dragstart', this.handleDragStart.bind(this));
    this.list.addEventListener('dragover', this.handleDragOver.bind(this));
    this.list.addEventListener('drop', this.handleDrop.bind(this));
    this.list.addEventListener('dragend', this.handleDragEnd.bind(this));
  }

  /**
   * Add a language to the preference list
   */
  addLanguage(code, name, endonym = null) {
    const idx = this.items.length;
    const item = { code, name, endonym };

    this.items.push(item);
    this.render();
    this.updateStatus(`Added ${name} to preferences`);
  }

  /**
   * Remove a language by index
   */
  removeLanguage(idx) {
    const removed = this.items.splice(idx, 1)[0];
    this.render();
    this.updateStatus(`Removed ${removed.name} from preferences`);
  }

  /**
   * Move a language up or down
   */
  moveLanguage(fromIdx, toIdx) {
    if (toIdx < 0 || toIdx >= this.items.length) return;

    const item = this.items.splice(fromIdx, 1)[0];
    this.items.splice(toIdx, 0, item);

    this.render();
    this.updateStatus(
      `Moved ${item.name} to position ${toIdx + 1} of ${this.items.length}`
    );

    // Focus the moved item's up button for keyboard users
    setTimeout(() => {
      const btn = document.querySelector(
        `[data-item-index="${toIdx}"][data-action="move-up"]`
      );
      btn?.focus();
    }, 0);
  }

  /**
   * Render the list
   */
  render() {
    this.list.innerHTML = this.items.map((item, idx) => `
      <li
        class="language-item"
        id="lang-pref-${idx}"
        draggable="true"
        data-item-index="${idx}"
      >
        <span class="drag-handle" aria-label="Drag handle (use arrows to reorder)">
          ⋮⋮
        </span>

        <div class="language-info">
          <div class="language-name">${this.escapeHtml(item.name)}</div>
          <div class="language-code">${item.code}</div>
        </div>

        <div class="reorder-buttons">
          <button
            type="button"
            class="reorder-button"
            aria-label="Move ${item.name} up"
            data-action="move-up"
            data-item-index="${idx}"
            ${idx === 0 ? 'disabled' : ''}
          >
            ↑
          </button>
          <button
            type="button"
            class="reorder-button"
            aria-label="Move ${item.name} down"
            data-action="move-down"
            data-item-index="${idx}"
            ${idx === this.items.length - 1 ? 'disabled' : ''}
          >
            ↓
          </button>
          <button
            type="button"
            class="reorder-button"
            aria-label="Remove ${item.name}"
            data-action="remove"
            data-item-index="${idx}"
          >
            ✕
          </button>
        </div>
      </li>
    `).join('');

    // Update hidden input for form submission
    this.dataInput.value = this.items.map(i => i.code).join(',');
  }

  handleClick(e) {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;

    const idx = parseInt(btn.getAttribute('data-item-index'), 10);
    const action = btn.getAttribute('data-action');

    switch (action) {
      case 'move-up':
        this.moveLanguage(idx, idx - 1);
        break;
      case 'move-down':
        this.moveLanguage(idx, idx + 1);
        break;
      case 'remove':
        this.removeLanguage(idx);
        break;
    }
  }

  handleDragStart(e) {
    const item = e.target.closest('.language-item');
    if (!item) return;

    e.dataTransfer.effectAllowed = 'move';
    item.setAttribute('dragging', 'true');
    e.dataTransfer.setData('text/html', item.innerHTML);
  }

  handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';

    const item = e.target.closest('.language-item');
    if (!item) return;

    // Optional: add visual drop zone indicator
    item.style.borderTop = '3px solid #1976d2';
  }

  handleDrop(e) {
    e.preventDefault();
    const fromItem = document.querySelector('[dragging="true"]');
    const toItem = e.target.closest('.language-item');

    if (!fromItem || !toItem || fromItem === toItem) return;

    const fromIdx = parseInt(
      fromItem.getAttribute('data-item-index'),
      10
    );
    const toIdx = parseInt(toItem.getAttribute('data-item-index'), 10);

    this.moveLanguage(fromIdx, toIdx);
  }

  handleDragEnd(e) {
    const item = e.target.closest('.language-item');
    if (item) {
      item.removeAttribute('dragging');
      item.style.borderTop = '';
    }

    // Clear drop zone indicators
    document.querySelectorAll('.language-item').forEach(li => {
      li.style.borderTop = '';
    });
  }

  updateStatus(message) {
    this.status.textContent = message;
  }

  /**
   * Get current preference order as array of codes
   */
  getValues() {
    return this.items.map(i => i.code);
  }

  /**
   * Set preferences from array of codes
   */
  setValues(codes, languageMap) {
    this.items = codes
      .map(code => languageMap[code])
      .filter(item => item !== undefined);
    this.render();
  }

  /**
   * Escape HTML special characters
   */
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Usage:
const prefList = new LanguagePreferenceList(
  '#language-preferences',
  '#list-status',
  '#language-prefs-data'
);

// Add initial languages
prefList.addLanguage('eng', 'English');
prefList.addLanguage('jpn', 'Japanese', '日本語');
prefList.addLanguage('fra', 'French', 'français');
```

---

## Part 3: Putting It Together (Form Integration)

```html
<form id="policy-form">
  <div class="form-section">
    <h2>Language Preferences</h2>

    <!-- Single language input -->
    <div class="form-group">
      <label for="language-input">Default Language</label>
      <div class="language-input-wrapper">
        <input
          id="language-input"
          type="text"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded="false"
          aria-controls="language-listbox"
          placeholder="e.g., eng"
          maxlength="3"
        >
        <div id="language-status" role="status" aria-live="polite"></div>
        <ul id="language-listbox" role="listbox" hidden></ul>
      </div>
    </div>

    <!-- Preference list -->
    <div class="form-group">
      <fieldset>
        <legend>Preferred Languages (in order)</legend>
        <ul id="language-preferences" class="language-preferences-list"></ul>
        <div id="list-status" role="status" aria-live="polite"></div>
      </fieldset>
    </div>
  </div>

  <button type="submit">Save Policy</button>
  <button type="reset">Reset</button>
</form>

<script>
// Initialize autocomplete
const autocomplete = new LanguageAutocomplete(
  '#language-input',
  '#language-listbox',
  '#language-status'
);

// Initialize preference list
const prefList = new LanguagePreferenceList(
  '#language-preferences',
  '#list-status',
  '#language-prefs-data'
);

// Handle adding language to preference list
document.getElementById('language-input')?.addEventListener(
  'language-selected',
  (e) => {
    const { code } = e.detail;
    const lang = LANGUAGES.find(l => l.code === code);
    if (lang && !prefList.items.find(i => i.code === code)) {
      prefList.addLanguage(lang.code, lang.name, lang.endonym);
      autocomplete.input.value = '';
      autocomplete.close();
      autocomplete.updateStatus('Type 3+ characters to search');
    }
  }
);

// Handle form submission
document.getElementById('policy-form')?.addEventListener('submit', (e) => {
  if (!autocomplete.validate()) {
    e.preventDefault();
    autocomplete.input.focus();
  } else {
    // Form data ready: prefList.getValues() has the order
    console.log('Language preferences:', prefList.getValues());
  }
});
</script>
```

---

## Testing Checklist

### Unit Tests
```javascript
describe('LanguageAutocomplete', () => {
  it('filters by code (case-insensitive)', () => {
    autocomplete.handleInput({ target: { value: 'eng' } });
    const options = document.querySelectorAll('[role="option"]');
    expect(options.length).toBeGreaterThan(0);
  });

  it('filters by name', () => {
    autocomplete.handleInput({ target: { value: 'eng' } });
    const firstOption = document.querySelector('[role="option"]');
    expect(firstOption.textContent).toContain('English');
  });

  it('validates ISO 639-2 codes', () => {
    autocomplete.input.value = 'eng';
    expect(autocomplete.validate()).toBe(true);

    autocomplete.input.value = 'xyz';
    expect(autocomplete.validate()).toBe(false);
  });

  it('requires 3 characters before showing suggestions', () => {
    autocomplete.handleInput({ target: { value: 'en' } });
    expect(autocomplete.isOpen).toBe(false);

    autocomplete.handleInput({ target: { value: 'eng' } });
    expect(autocomplete.isOpen).toBe(true);
  });
});

describe('LanguagePreferenceList', () => {
  it('adds languages in order', () => {
    prefList.addLanguage('eng', 'English');
    prefList.addLanguage('jpn', 'Japanese');
    expect(prefList.getValues()).toEqual(['eng', 'jpn']);
  });

  it('reorders languages', () => {
    prefList.items = [
      { code: 'eng', name: 'English' },
      { code: 'jpn', name: 'Japanese' }
    ];
    prefList.moveLanguage(0, 1);
    expect(prefList.getValues()).toEqual(['jpn', 'eng']);
  });

  it('removes languages', () => {
    prefList.items = [
      { code: 'eng', name: 'English' },
      { code: 'jpn', name: 'Japanese' }
    ];
    prefList.removeLanguage(0);
    expect(prefList.getValues()).toEqual(['jpn']);
  });
});
```

### Accessibility Testing
- [ ] Keyboard: Tab → Input → Arrow keys → Enter → Escape
- [ ] Screen reader: Reads label, hint, status updates, option list
- [ ] High contrast: All elements visible (no color-only indicators)
- [ ] Zoom 200%: No text cut off, buttons still clickable (48×48px minimum)
- [ ] Touch: All buttons and list items reachable and tappable

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Listbox doesn't close on blur | Check `handleBlur()` setTimeout delay |
| Arrow keys don't navigate | Verify `isOpen` flag is true |
| Screen reader doesn't announce | Check `aria-live="polite"` on status element |
| Drag-and-drop not working | Ensure `draggable="true"` on list items |
| Focus ring not visible | Check CSS outline/box-shadow on `:focus` |

---

## Resources

- [ISO 639-2 Language List](https://www.loc.gov/standards/iso639-2/php/code_list.php) - Download full list
- [W3C Combobox Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/) - Spec reference
- [MDN aria-autocomplete](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Attributes/aria-autocomplete) - Attribute docs
