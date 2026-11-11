/* Keeps every Plotly chart as wide as its container.
 *
 * `dcc.Graph(config={"responsive": true})` only listens to **window** resize events. The chart also
 * has to follow its *container*: a tab switch, a modal, the mobile breakpoint re-render, or a
 * details card opening/closing can change the available width without a window resize, and Plotly
 * then keeps its old pixel width (the chart overflows or leaves a gap on a phone).
 *
 * A ResizeObserver on the plot's parent calls `Plotly.Plots.resize` whenever that box changes.
 * Work is coalesced into one animation frame, so dragging a window edge does not thrash Plotly.
 * Every `.js-plotly-plot` is watched, and a MutationObserver picks up the ones remounted by the
 * 15 s dashboard refresh.
 */
(function () {
    "use strict";

    if (!window.ResizeObserver || !window.MutationObserver) {
        return;
    }

    var watched = new WeakSet();
    var queued = false;
    var pending = null;

    function resize() {
        queued = false;
        var plots = pending;
        pending = null;
        if (!window.Plotly || !window.Plotly.Plots || !plots) {
            return;
        }
        for (var i = 0; i < plots.length; i++) {
            var plot = plots[i];
            if (plot.isConnected && plot._fullLayout) {
                window.Plotly.Plots.resize(plot);
            }
        }
    }

    function schedule(plot) {
        pending = pending || [];
        if (pending.indexOf(plot) === -1) {
            pending.push(plot);
        }
        if (!queued) {
            queued = true;
            window.requestAnimationFrame(resize);
        }
    }

    function watch(plot) {
        if (watched.has(plot) || !plot.parentElement) {
            return;
        }
        watched.add(plot);
        var observer = new ResizeObserver(function () {
            schedule(plot);
        });
        observer.observe(plot.parentElement);
    }

    var scanQueued = false;

    function scan() {
        scanQueued = false;
        var plots = document.querySelectorAll(".js-plotly-plot");
        for (var i = 0; i < plots.length; i++) {
            watch(plots[i]);
        }
    }

    function scheduleScan() {
        if (scanQueued) {
            return;
        }
        scanQueued = true;
        window.requestAnimationFrame(scan);
    }

    function start() {
        scan();
        // the countdown rebuilds text every second, so coalesce the rescans into one frame
        new MutationObserver(scheduleScan).observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();