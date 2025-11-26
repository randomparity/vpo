# Vanilla JavaScript State Management Research Report

## Executive Summary

This report evaluates state management patterns for a policy editor web UI in the Video Policy Orchestrator (VPO) project. The UI must handle complex form state across multiple sections (track order, languages, flags, patterns) with real-time YAML preview, using only vanilla JavaScript without frameworks.

## Context

- **Project**: Video Policy Orchestrator (VPO)
- **Component**: Policy Editor Web UI
- **Constraints**: Vanilla JavaScript only (no React/Vue/Angular)
- **Requirements**:
  - Manage state across 5-8 form sections
  - Different field types: lists, toggles, ordered lists, text inputs
  - Real-time YAML preview that updates as form changes
  - Maintain consistency with existing VPO web UI patterns
- **Existing Stack**: aiohttp, Jinja2 templates, plain JavaScript with ES6+ modules

## Research Findings

### 1. Modern Vanilla JavaScript State Management Patterns

Based on 2024-2025 trends, the most effective patterns for vanilla JavaScript state management are:

#### A. Proxy-Based Reactive State (Recommended)

JavaScript's `Proxy` object enables automatic change detection and reactive updates similar to Vue.js internals.

**Advantages:**
- Native browser support (IE11+)
- Automatic tracking of property changes
- Clean, declarative code
- No dependencies
- Minimal overhead (~100-150 lines of code)

**Pattern:**
```javascript
function createReactiveState(initialState, onChange) {
    return new Proxy(initialState, {
        set(target, property, value) {
            const oldValue = target[property];
            target[property] = value;
            if (oldValue !== value) {
                onChange(property, value, oldValue);
            }
            return true;
        }
    });
}

// Usage
const state = createReactiveState({
    track_order: [],
    languages: {},
    flags: {}
}, (property, newValue, oldValue) => {
    updateYamlPreview();
    syncFormField(property, newValue);
});
```

#### B. Observer Pattern with Event Emitters

Traditional but effective pattern using custom event emission for state changes.

**Advantages:**
- Well-understood pattern
- Explicit control over notifications
- Easy to debug

**Disadvantages:**
- More boilerplate code
- Manual notification required
- Tighter coupling between components

#### C. Pub/Sub Pattern

Decoupled messaging pattern with a central event bus.

**Advantages:**
- Complete decoupling of publishers and subscribers
- Many-to-many relationships
- Easy to add new subscribers

**Disadvantages:**
- More complex than needed for single-page forms
- Harder to track data flow
- Potential memory leaks if not cleaned up

### 2. Lightweight Libraries (Optional)

If building from scratch is not preferred, these ultra-lightweight libraries are compatible with vanilla JavaScript:

#### VanJS (1.0kB)
- Reactive UI framework
- No JSX, no build tools
- 50-100x smaller than React
- Based on pure vanilla JavaScript
- **Source:** [VanJS](https://vanjs.org/)

#### ArrowJS (2kB)
- Reactive interfaces with native JavaScript
- No build tools, no virtual DOM
- Blazing fast performance
- **Source:** [ArrowJS](https://www.arrow-js.com/)

#### Reef (2.6kB)
- Reactive state-based UI
- Zero dependencies
- Simple API
- **Source:** [Reef](https://reefjs.com/)

#### Tiny Signals
- Inspired by Preact's Signals API
- Minimal state management
- Efficient synchronization
- **Source:** [Tiny Signals](https://www.cssscript.com/state-management-tiny-signals/)

### 3. Form State Synchronization Best Practices

#### Two-Way Data Binding

Modern approach using Proxy for automatic synchronization between form inputs and state object:

```javascript
// Form -> State binding
formElement.addEventListener('input', (e) => {
    state[e.target.name] = e.target.value;
});

// State -> Form binding (via Proxy)
const state = new Proxy(initialState, {
    set(target, property, value) {
        target[property] = value;
        // Update corresponding form field
        const field = document.querySelector(`[name="${property}"]`);
        if (field && field.value !== value) {
            field.value = value;
        }
        // Update YAML preview
        updateYamlPreview();
        return true;
    }
});
```

**Key Patterns from Research:**
- Use event delegation for dynamic form fields
- Debounce text inputs (300ms standard)
- Validate on blur, not on every keystroke
- Progressive enhancement: HTML form submission fallback

### 4. YAML Generation

For real-time YAML preview, the standard library is **js-yaml**:

```javascript
import yaml from 'js-yaml';

function updateYamlPreview() {
    const yamlString = yaml.dump(state);
    previewElement.textContent = yamlString;
}
```

**Alternatives:**
- Build YAML manually (for simpler schemas)
- Use template literals with proper indentation
- Server-side generation via API endpoint

### 5. Analysis of Existing VPO Patterns

From `/home/dave/src/vpo/src/video_policy_orchestrator/server/static/js/library.js`:

**Current Patterns:**
- IIFE modules for encapsulation
- Plain object for state (`currentFilters`)
- Direct DOM manipulation
- Event delegation for dynamic content
- URL synchronization via `history.replaceState`
- Debouncing for search inputs (300ms)

**Architecture:**
```javascript
(function() {
    'use strict';

    // State
    let currentFilters = {
        status: '',
        search: '',
        resolution: '',
        audio_lang: [],
        subtitles: ''
    };

    // DOM refs
    const searchInputEl = document.getElementById('filter-search');

    // Event handlers
    searchInputEl.addEventListener('input', debounce(() => {
        currentFilters.search = searchInputEl.value;
        handleFilterChange();
    }, 300));
})();
```

**Observations:**
- No reactive layer currently used
- State updates are manual
- DOM updates triggered explicitly
- Works well for simple list/filter UIs
- May become unwieldy with complex nested state

## Decision: Recommended State Management Pattern

### Primary Recommendation: Proxy-Based Reactive State with Centralized Store

**Rationale:**

1. **Consistency with Modern JavaScript**: Leverages native Proxy API available in all modern browsers
2. **Minimal Dependencies**: No external libraries required
3. **Reactive Updates**: Automatic synchronization between state, form, and YAML preview
4. **Maintainability**: Clean separation of concerns, easy to understand
5. **Scalability**: Can handle complex nested state (track order lists, language objects)
6. **Debugging**: Simple to log state changes via Proxy trap
7. **Fits VPO Patterns**: Extends existing IIFE module pattern without major refactoring

### Implementation Architecture

```javascript
// state-manager.js
(function() {
    'use strict';

    // Create reactive state store
    function createStateStore(initialState) {
        const subscribers = new Set();

        const handler = {
            set(target, property, value) {
                const oldValue = target[property];
                target[property] = value;

                if (oldValue !== value) {
                    // Notify subscribers
                    subscribers.forEach(fn => fn(property, value, oldValue));
                }

                return true;
            },

            // Deep reactivity for nested objects
            get(target, property) {
                const value = target[property];
                if (typeof value === 'object' && value !== null) {
                    return new Proxy(value, handler);
                }
                return value;
            }
        };

        const proxy = new Proxy(initialState, handler);

        return {
            state: proxy,
            subscribe(fn) {
                subscribers.add(fn);
                return () => subscribers.delete(fn); // Unsubscribe function
            }
        };
    }

    // Initialize policy editor state
    const initialState = {
        name: '',
        description: '',
        track_order: {
            video: [],
            audio: [],
            subtitles: []
        },
        languages: {
            primary_audio: '',
            subtitle_languages: []
        },
        flags: {
            default_audio: false,
            forced_subtitles: false
        },
        patterns: []
    };

    const store = createStateStore(initialState);

    // Subscribe to state changes for YAML preview
    store.subscribe((property, newValue, oldValue) => {
        console.log(`State changed: ${property}`, newValue);
        updateYamlPreview(store.state);
    });

    // Export for use in other modules
    window.policyEditorState = store;
})();
```

### Form Binding

```javascript
// policy-editor.js
(function() {
    'use strict';

    const state = window.policyEditorState.state;

    // Bind form inputs to state (Form -> State)
    function bindFormToState() {
        document.querySelectorAll('[data-state-field]').forEach(input => {
            const field = input.dataset.stateField;

            input.addEventListener('input', (e) => {
                setNestedProperty(state, field, e.target.value);
            });
        });
    }

    // Bind state to form updates (State -> Form)
    window.policyEditorState.subscribe((property, value) => {
        const input = document.querySelector(`[data-state-field="${property}"]`);
        if (input && input.value !== value) {
            input.value = value;
        }
    });

    // Helper to set nested properties (e.g., "languages.primary_audio")
    function setNestedProperty(obj, path, value) {
        const keys = path.split('.');
        const lastKey = keys.pop();
        const target = keys.reduce((o, k) => o[k], obj);
        target[lastKey] = value;
    }

    // Initialize
    document.addEventListener('DOMContentLoaded', () => {
        bindFormToState();
    });
})();
```

### YAML Preview

```javascript
// yaml-preview.js
(function() {
    'use strict';

    const previewEl = document.getElementById('yaml-preview');
    let updateTimer = null;

    function updateYamlPreview(state) {
        // Debounce updates
        if (updateTimer) clearTimeout(updateTimer);

        updateTimer = setTimeout(() => {
            // Option 1: Use js-yaml library (requires CDN or build step)
            // const yamlString = yaml.dump(state);

            // Option 2: Manual YAML generation (for simple schemas)
            const yamlString = generateYaml(state);

            previewEl.textContent = yamlString;
        }, 150);
    }

    // Simple YAML generator (no dependencies)
    function generateYaml(obj, indent = 0) {
        const spaces = '  '.repeat(indent);
        let yaml = '';

        for (const [key, value] of Object.entries(obj)) {
            if (value === null || value === undefined) continue;

            if (Array.isArray(value)) {
                yaml += `${spaces}${key}:\n`;
                value.forEach(item => {
                    if (typeof item === 'object') {
                        yaml += `${spaces}  - ${generateYaml(item, indent + 2).trim()}\n`;
                    } else {
                        yaml += `${spaces}  - ${item}\n`;
                    }
                });
            } else if (typeof value === 'object') {
                yaml += `${spaces}${key}:\n`;
                yaml += generateYaml(value, indent + 1);
            } else {
                yaml += `${spaces}${key}: ${value}\n`;
            }
        }

        return yaml;
    }

    // Subscribe to state changes
    window.policyEditorState.subscribe(() => {
        updateYamlPreview(window.policyEditorState.state);
    });

    // Initial render
    document.addEventListener('DOMContentLoaded', () => {
        updateYamlPreview(window.policyEditorState.state);
    });
})();
```

## Alternatives Considered

### Alternative 1: Plain Object with Manual Updates (Current VPO Pattern)

**Pros:**
- Simple, no magic
- Easy to debug
- Consistent with existing code

**Cons:**
- Requires manual DOM updates after every state change
- Easy to forget to update preview
- More boilerplate for complex nested state
- No automatic synchronization

**Verdict:** Good for simple list UIs, insufficient for complex form editor

### Alternative 2: Lightweight Library (VanJS, ArrowJS, Reef)

**Pros:**
- Battle-tested reactivity
- Rich feature set
- Good documentation
- Still very small (1-3kB)

**Cons:**
- External dependency
- Learning curve for team
- May be overkill for single-page editor
- Requires build step or CDN

**Verdict:** Viable if team prefers not to maintain custom reactivity code

### Alternative 3: Observer Pattern (Manual Event Emitters)

**Pros:**
- Explicit, easy to trace
- No modern API dependencies
- Full control

**Cons:**
- More boilerplate than Proxy
- Easy to miss notifications
- Manual tracking of dependencies
- Less elegant than Proxy solution

**Verdict:** Workable but more verbose, Proxy is cleaner

### Alternative 4: Pub/Sub with Message Bus

**Pros:**
- Complete decoupling
- Flexible many-to-many

**Cons:**
- Overcomplicated for single-page form
- Harder to debug
- Memory leak risks
- No direct property access

**Verdict:** Too complex for this use case

## Implementation Notes

### Key Considerations

1. **Nested Reactivity**: Use recursive Proxy wrapping for deep objects
2. **Array Operations**: Proxy Array mutations (push, pop, splice) properly
3. **Performance**: Debounce rapid updates (150-300ms)
4. **Validation**: Validate on blur or state change, not on every keystroke
5. **Error Handling**: Gracefully handle invalid state transitions
6. **Undo/Redo**: Consider adding state history for better UX
7. **Dirty State Tracking**: Track whether form has unsaved changes

### Code Structure

```text
static/js/
├── policy-editor/
│   ├── state-manager.js        # Reactive state store
│   ├── form-bindings.js        # Form <-> State synchronization
│   ├── yaml-preview.js         # YAML generation and preview
│   ├── validation.js           # Form validation logic
│   └── editor.js               # Main initialization
```

### Testing Strategy

1. **Unit Tests**: Test state store in isolation
2. **Integration Tests**: Test form bindings with jsdom
3. **Manual Tests**: Browser testing for edge cases
4. **Performance Tests**: Measure update latency with large forms

### Migration Path

1. **Phase 1**: Implement reactive state store (no UI changes)
2. **Phase 2**: Migrate simple fields to reactive bindings
3. **Phase 3**: Add complex field types (lists, ordered lists)
4. **Phase 4**: Implement YAML preview
5. **Phase 5**: Add validation and error handling
6. **Phase 6**: Polish UX (undo/redo, dirty state)

### Browser Compatibility

- **Proxy**: Supported in all modern browsers (Chrome 49+, Firefox 18+, Safari 10+)
- **No IE11 Support**: IE11 does not support Proxy (cannot be polyfilled)
- **Fallback**: For IE11, use plain object with manual updates (Alternative 1)

### Dependencies

**Minimal Approach (Recommended):**
- Zero dependencies for state management
- Optional: js-yaml (10kB) for YAML generation via CDN

**With Library Approach:**
- VanJS (1kB) or ArrowJS (2kB) + js-yaml (10kB)

### Code Size Estimate

- State manager: ~150 lines
- Form bindings: ~100 lines
- YAML preview: ~80 lines (manual) or ~20 lines (with js-yaml)
- Validation: ~100 lines
- **Total**: ~430 lines or ~270 lines with js-yaml

## Conclusion

**Recommended Pattern:** Proxy-based reactive state management with centralized store.

**Key Benefits:**
- Modern, native JavaScript solution
- Automatic synchronization between form, state, and preview
- Maintainable and debuggable
- Extends existing VPO patterns cleanly
- No external dependencies for core functionality
- Scalable to complex nested state

**Next Steps:**
1. Implement state-manager.js with Proxy-based store
2. Create form binding utilities
3. Implement YAML preview with debouncing
4. Add validation layer
5. Build UI components for policy editor sections
6. Test thoroughly with various policy schemas

## References and Sources

### State Management Patterns
- [State Management in Vanilla JS: 2026 Trends](https://medium.com/@chirag.dave/state-management-in-vanilla-js-2026-trends-f9baed7599de)
- [Back to Basics: Mastering State Management in Vanilla JavaScript](https://medium.com/@asierr/back-to-basics-mastering-state-management-in-vanilla-javascript-e3be7377ac46)
- [Modern State Management in Vanilla JavaScript: 2026 Patterns and Beyond](https://medium.com/@orami98/modern-state-management-in-vanilla-javascript-2026-patterns-and-beyond-ce00425f7ac5)
- [Managing Complex State in Vanilla JavaScript: A Comprehensive Guide](https://www.javacodegeeks.com/2024/11/managing-complex-state-in-vanilla-javascript-a-comprehensive-guide.html)
- [Build a state management system with vanilla JavaScript](https://css-tricks.com/build-a-state-management-system-with-vanilla-javascript/)
- [State Management Strategies Without Frameworks: Vanilla Patterns That Scale](https://namastedev.com/blog/state-management-strategies-without-frameworks-vanilla-patterns-that-scale/)

### Reactive Programming
- [Reactive State Management using Proxy and Reflect in JavaScript](https://medium.com/@rahul.jindal57/reactive-state-management-using-proxy-and-reflect-in-javascript-1cbdcb79d017)
- [How to create a reactive state-based UI component with vanilla JS Proxies](https://gomakethings.com/how-to-create-a-reactive-state-based-ui-component-with-vanilla-js-proxies/)
- [Build a light and global state system](https://piccalil.li/blog/build-a-light-and-global-state-system/)
- [Simple reactive data stores with vanilla JavaScript and Proxies](https://gomakethings.com/simple-reactive-data-stores-with-vanilla-javascript-and-proxies/)
- [CSS { In Real Life } | Reactivity in Vanilla Javascript](https://css-irl.info/reactivity-in-vanilla-javascript/)
- [Reactive UI's with VanillaJS - Part 1: Pure Functional Style](https://css-tricks.com/reactive-uis-vanillajs-part-1-pure-functional-style/)

### Two-Way Data Binding
- [Two-way data binding and reactivity with 15 lines of vanilla JavaScript](https://gomakethings.com/two-way-data-binding-and-reactivity-with-15-lines-of-vanilla-javascript/)
- [Two-way data binding with vanilla JavaScript](https://gomakethings.com/two-way-data-binding-with-vanilla-javascript/)
- [2 way data binding in JavaScript - Stack Overflow](https://stackoverflow.com/questions/45490004/2-way-data-binding-in-javascript)
- [2 Way Data Binding in Plain Vanilla JavaScript](http://namitamalik.github.io/2-way-data-binding-in-Plain-Vanilla-JavaScript/)
- [Two-way data binding in vanilla JS (POC)](https://dev.to/phoinixi/two-way-data-binding-in-vanilla-js-poc-4e06)

### Form State Management
- [Vanilla JavaScript Form Handling: No Framework Guide](https://strapi.io/blog/vanilla-javascript-form-handling-guide)
- [Simple state management with vanilla JavaScript](https://medium.com/@novosibcool/simple-state-management-with-vanilla-javascript-66fcd79380d4)
- [Binding User Interfaces and Application State with Vanilla JavaScript](https://matswainson.com/binding-user-interfaces-application-state-with-vanilla-javascript)

### Observer vs Pub/Sub
- [Observer and Pub-Sub Patterns for reactive behaviours in JavaScript](https://dionarodrigues.dev/blog/observer-and-pub-sub-patterns-for-reactive-behaviours-in-javascript)
- [Observer vs Pub-Sub pattern](https://hackernoon.com/observer-vs-pub-sub-pattern-50d3b27f838c)
- [Difference between Observer, Pub/Sub, and Data Binding](https://stackoverflow.com/questions/15594905/difference-between-observer-pub-sub-and-data-binding)
- [Comparison between different Observer Pattern implementations](https://github.com/millermedeiros/js-signals/wiki/Comparison-between-different-Observer-Pattern-implementations)

### Lightweight Libraries
- [VanJS - A 1.0kB No-JSX Framework](https://vanjs.org/)
- [ArrowJS - Reactive interfaces with native JavaScript](https://www.arrow-js.com/)
- [Reef - Reactive state-based UI](https://reefjs.com/)
- [Minimal State Management for Vanilla JavaScript - Tiny Signals](https://www.cssscript.com/state-management-tiny-signals/)
- [Kel - Event driven state management library](https://github.com/vijitail/Kel)

### YAML Conversion
- [js-yaml - npm](https://www.npmjs.com/package/js-yaml)
- [YAML parser for JavaScript - JS-YAML](https://nodeca.github.io/js-yaml/)
- [How to convert JSON to YAML in javascript - Stack Overflow](https://stackoverflow.com/questions/38781929/how-to-convert-json-to-yaml-in-javascript)
- [Converting JSON to YAML in JavaScript](https://umeey.medium.com/converting-json-to-yaml-in-javascript-8a752fc8f87e)

---

**Document Version**: 1.0
**Last Updated**: 2025-11-24
**Author**: Research Report (AI-Generated)
**Related Docs**: CLAUDE.md, plugin-author-guide.md
