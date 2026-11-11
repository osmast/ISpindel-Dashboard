/* Accordion cards are native <details> elements - the browser opens and closes them itself, with no
 * JavaScript involved.
 *
 * The former custom open-state script was removed: it wrote the set to localStorage and re-applied
 * it on every DOM mutation, which could close a card immediately after a click (the rebuild's
 * MutationObserver raced the native toggle). Keeping <details> standard is both simpler and
 * snappier: the state is handled by the browser, not by React or Dash.
 *
 * This file intentionally does nothing. It stays in the repository (and in the Dockerfile COPY
 * list) so an old deployment that still references it does not 404.
 */
