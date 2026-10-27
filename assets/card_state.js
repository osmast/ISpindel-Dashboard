/* Remembers which accordion cards are open.
 *
 * The cards are plain <details> elements, but update_dashboard() rebuilds the card tree every
 * refresh - a remounted <details> loses its `open` attribute. On every toggle the current open
 * set is written to the `open_cards` store, and main.py renders `open` from it again.
 */
(function () {
    "use strict";

    function publish() {
        var open = {};
        var cards = document.querySelectorAll("details[data-card]");
        for (var i = 0; i < cards.length; i++) {
            open[cards[i].dataset.card] = cards[i].open;
        }
        if (window.dash_clientside && window.dash_clientside.set_props) {
            window.dash_clientside.set_props("open_cards", {data: open});
        }
    }

    // `toggle` does not bubble, so listen in the capture phase
    document.addEventListener("toggle", function (event) {
        var target = event.target;
        if (target && target.dataset && target.dataset.card !== undefined) {
            publish();
        }
    }, true);
})();
