/* Custom AG Grid cell renderers for the measurement grid in the experiment edit dialog (FR-06).
 *
 * Dash AG Grid looks up a `cellRenderer` name in `window.dashAgGridComponentFunctions`. The renderer
 * returns a React element (AG Grid bundles React as the global `React`). The ✕ is a plain span, not
 * a <button>: it keeps the cell's click event bubbling so Dash AG Grid reports it as `cellClicked`
 * with `colId="actions"` - the server callback (`meas_grid_event`) does the deletion.
 *
 * If React is not on the page for some reason, the renderer falls back to the same ✕ as text, so
 * the column still exists and the callback still works.
 */
(function () {
    "use strict";

    var fns = window.dashAgGridComponentFunctions =
        window.dashAgGridComponentFunctions || {};

    fns.measDeleteRenderer = function () {
        if (typeof React === "undefined") {
            return "\u2715";
        }
        return React.createElement("span", {
            role: "button",
            title: "delete this measurement",
            style: {
                color: "#dc2626",
                cursor: "pointer",
                fontSize: "14px",
                fontWeight: "600",
                lineHeight: "1",
                padding: "2px 6px",
                userSelect: "none"
            }
        }, "\u2715");
    };
})();