/* Reloads an open dashboard when the server's callback map changed.
 *
 * Dash keys every request by the **outputs** of the page it was loaded with. After a deploy that
 * adds, removes or moves an output (e.g. the AG Grid removal), an open tab keeps sending the old
 * key; the server answers 500 ("Callback function not found") and the page looks frozen until it
 * is reloaded by hand. The index carries the build id of the page
 * (`<meta name="ispindel-build">`), `/build` answers with the id of the running process - a
 * mismatch reloads the tab. The checkout is no-store, so the reload really gets the new page.
 *
 * Deliberately tiny: one request every 15 s, no DOM work, nothing on a page that has no meta tag.
 */
(function () {
    "use strict";

    var meta = document.querySelector('meta[name="ispindel-build"]');
    if (!meta || !window.fetch) {
        return;
    }
    var mine = meta.getAttribute("content");
    var timer = null;

    function check() {
        fetch("/build", {cache: "no-store"}).then(function (response) {
            return response.ok ? response.text() : null;
        }).then(function (theirs) {
            theirs = theirs ? theirs.trim() : "";
            if (!theirs || theirs === mine) {
                return;
            }
            if (timer) {
                window.clearInterval(timer);
            }
            window.location.reload();       // the new page carries the new meta id
        }).catch(function () {
            /* offline or restarting - retry on the next interval, never break the page */
        });
    }

    timer = window.setInterval(check, 15000);
    check();
})();
