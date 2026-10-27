"""Browser-less test of the experiment dialog flow (FR-01 - FR-04, FR-13): it renders the overview,
reads the button ids as the card renders them and posts the same requests the browser sends -
set up -> create, then end -> confirmation -> ended. Temporary rows (zz_ui*) are removed again.

Run:  python tools/ui_test.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import main                                                        # noqa: E402

ok = True
DEV = None      # numeric device id of the temporary device
NAME = None     # its mqtt name


def check(label, condition, detail=""):
    global ok
    ok = ok and bool(condition)
    print(f"{'PASS' if condition else 'FAIL'}  {label}  {detail}")


def outputs():
    return [{"id": "exp-target", "property": "data"},
            {"id": "exp-modal", "property": "opened"},
            {"id": "exp-modal", "property": "title"},
            {"id": "exp-submit", "property": "children"},
            # the two forms of the dialog (FR-12 added the device one) + their visibility
            {"id": "exp-form", "property": "children"},
            {"id": "exp-form", "property": "style"},
            {"id": "dev-form", "property": "children"},
            {"id": "dev-form", "property": "style"},
            {"id": "msg", "property": "children"},
            {"id": "modal-msg", "property": "children"},
            {"id": "reload", "property": "data"},
            {"id": "download", "property": "data"}]


# a stand-in for the edit/delete icon of a table row: the tests that do not click one still have
# to send an id whose key set matches the callback pattern exactly (that is what Dash matches on)
ROW_ID = {"type": "row-btn", "exp": 0, "mode": "edit"}

# a stand-in for the settings icon of a Devices-table row (FR-12)
DEV_ID = {"type": "dev-btn", "device": 0}


# Dash builds the multi-output key itself (with leading/trailing "..") - take it from there
OUTPUT = next(spec["output"] for spec in main.app._callback_list
              if isinstance(spec["output"], str) and "exp-modal" in spec["output"])


def find_button_id(device_name, kind):
    """The button id as the card renders it - the value the browser would send back.

    The component tree mixes `to_plotly_json()` dicts with component objects, so every node is
    converted before it is inspected.
    """
    found = []

    def walk(node):
        if hasattr(node, "to_plotly_json"):
            node = node.to_plotly_json()
        if isinstance(node, dict):
            if node.get("type") == kind and node.get("device") == device_name:
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(main.ispindel_overview({}))
    return found[0] if found else None


def pattern_key_sets():
    """The key names of every wildcard Input/State of the registered callbacks.

    dash-renderer finds the callback of a click by looking up `Object.keys(id).sort().join(',')`
    in `inputPatterns` - so a rendered id must use *exactly* the pattern's keys, otherwise the
    click is silently ignored (no request, no error). This is that rule as a test.
    Dash stores wildcard ids as JSON strings like {"device":["ALL"],"slot":["ALL"],"type":...}.
    """
    keys = set()
    for spec in main.app._callback_list:
        for group in ("inputs", "state"):
            for entry in spec.get(group, []):
                cid = entry["id"]
                if isinstance(cid, str) and cid.startswith("{"):
                    try:
                        cid = json.loads(cid)
                    except ValueError:
                        continue
                if isinstance(cid, dict):
                    keys.add(tuple(sorted(cid.keys())))
    return keys


def rendered_pattern_ids():
    """Every wildcard id the device cards render (buttons and the footer times line)."""
    found = []

    def walk(node):
        if hasattr(node, "to_plotly_json"):
            node = node.to_plotly_json()
        if isinstance(node, dict):
            node_id = node.get("id")
            if isinstance(node_id, dict) and "type" in node_id:
                found.append(tuple(sorted(node_id.keys())))
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(main.ispindel_overview({}))
    # the FR-05 table renders the edit / delete icons of every row
    walk(main.experiment_table(main.experiment_rows()))
    # the FR-12 Devices table renders the settings icon of every row
    walk(main.device_table(main.device_rows()))
    return set(found)


def find_row_id(exp_id, mode):
    """The edit / delete icon id of one FR-05 table row, as the table renders it."""
    found = []

    def walk(node):
        if hasattr(node, "to_plotly_json"):
            node = node.to_plotly_json()
        if isinstance(node, dict):
            node_id = node.get("id")
            if isinstance(node_id, dict) and node_id.get("type") == "row-btn" \
                    and node_id.get("exp") == exp_id and node_id.get("mode") == mode:
                found.append(node_id)
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(main.experiment_table(main.experiment_rows()))
    return found[0] if found else None


def card_text(device_name):
    """Dumped JSON of one device card only, so a check cannot be satisfied by another card."""
    for col in main.ispindel_overview({}).children:
        dumped = json.dumps(col.to_plotly_json(), default=str)
        if device_name in dumped:
            return dumped
    return ""


def post(setup_id, end_id, changed, clicks, states, row_id=ROW_ID, dev_id=DEV_ID,
         dev_name="", dev_active=None):
    """POST one multi-output callback exactly like dash-renderer does."""
    body = {
        "output": OUTPUT,
        "outputs": outputs(),
        "inputs": [{"id": setup_id, "property": "n_clicks", "value": clicks.get("setup")},
                   {"id": end_id, "property": "n_clicks", "value": clicks.get("end")},
                   {"id": row_id, "property": "n_clicks", "value": clicks.get("row")},
                   # FR-12: the settings icon of a Devices-table row
                   {"id": dev_id, "property": "n_clicks", "value": clicks.get("dev")},
                   {"id": "exp-cancel", "property": "n_clicks", "value": clicks.get("cancel")},
                   {"id": "exp-submit", "property": "n_clicks", "value": clicks.get("submit")}],
        # the trailing states are the rendered ids of the button patterns (the callback uses them
        # to map ctx.triggered_id to its own n_clicks - see main.clicked)
        "state": states + [{"id": setup_id, "property": "id", "value": setup_id},
                           {"id": end_id, "property": "id", "value": end_id},
                           {"id": row_id, "property": "id", "value": row_id},
                           # FR-22: the time range for the CSV row action
                           {"id": "range", "property": "value", "value": "all"},
                           # FR-12: the fields of the device dialog + the settings-icon id
                           {"id": "dev-name", "property": "value", "value": dev_name},
                           {"id": "dev-active", "property": "value",
                            "value": ["on"] if dev_active is None else dev_active},
                           {"id": dev_id, "property": "id", "value": dev_id}],
        "changedPropIds": changed,
    }
    resp = main.app.server.test_client().post(
        "/_dash-update-component", json=body, headers={"Content-Type": "application/json"})
    return resp.status_code, (resp.get_json() or {}).get("response", {})


def state(target, name="", start="", style="", og="", yeast="", resp_="", notes="", reload_=0):
    return [{"id": "exp-target", "property": "data", "value": target},
            {"id": "new-name", "property": "value", "value": name},
            {"id": "new-start", "property": "value", "value": start},
            {"id": "new-style", "property": "value", "value": style},
            {"id": "new-og", "property": "value", "value": og},
            {"id": "new-yeast", "property": "value", "value": yeast},
            {"id": "new-responsible", "property": "value", "value": resp_},
            {"id": "new-notes", "property": "value", "value": notes},
            {"id": "reload", "property": "data", "value": reload_}]


def changed(btn_id):
    return [json.dumps(btn_id, separators=(",", ":")) + ".n_clicks"]


# ---- setup: a temporary device so nothing touches the real one ---------------
# a re-run starts from a clean slate: measurements first (the FK has no cascade)
main.execute("""DELETE FROM measurement WHERE device_id IN
                  (SELECT id FROM device WHERE mqtt_name LIKE 'zz_ui%%')""")
main.execute("DELETE FROM experiment WHERE name LIKE 'zz_ui%%'")
main.execute("DELETE FROM device WHERE mqtt_name LIKE 'zz_ui%%'")
main.execute("INSERT INTO device (mqtt_name) VALUES ('zz_ui_dev')")
row = main.query("SELECT id, mqtt_name FROM device WHERE mqtt_name = 'zz_ui_dev'")[0]
DEV, NAME = row["id"], row["mqtt_name"]
# one measurement, so the card has a "last measurement" and its time to show (FR-13)
main.execute("""INSERT INTO measurement (device_id, recorded_at, tilt_deg, temp_c, gravity_plato,
                                         battery_v, interval_s, rssi_dbm)
                VALUES (%s, now() - interval '5 minutes', 62, 20, 12, 3.9, 900, -55)""", (DEV,))

# the ids come from the rendered card - exactly what the browser sends back
setup_id = find_button_id(NAME, "setup-btn")
check("the card renders a setup button whose id matches the callback pattern exactly",
      setup_id is not None and sorted(setup_id.keys()) == ["device", "slot", "type"],
      str(setup_id))
check("the setup button carries the iSpindel name", setup_id and setup_id.get("device") == NAME,
      str(setup_id))
setup_card = card_text(NAME)
check("a card without an experiment says so", "no experiment yet" in setup_card)
check("the setup button is grey and has a hover colour change",
      "bg-slate-100" in setup_card and "hover:bg-slate-200" in setup_card)
check("no end button while nothing runs", "end-btn" not in setup_card)
check("an idle card has the brand-blue outline", "border-brand" in setup_card
      and "border-2" not in setup_card,
      [c for c in setup_card.split('"') if "border-" in c][:2])

# ---- FR-13: the card shows the time of the last measurement ------------------
latest = main.query("SELECT recorded_at FROM v_device_latest WHERE mqtt_name = %s",
                    (NAME,))[0]["recorded_at"]
stamp = f"{main.local(latest):%d.%m. %H:%M:%S}"
check("FR-13 the footer shows the time of the last measurement (local time), not only its age",
      f"last: {stamp} (" in setup_card and "ago)" in setup_card,
      f"expected 'last: {stamp} (' in the footer")
check("FR-13/FR-14 the same line still counts down to the next transmission",
      "upcoming:" in setup_card, setup_card[-120:])

# ---- 1. click "Set up experiment" -> the dialog opens ------------------------
# a browser sends one value per matching card (a list); a single card can arrive as a scalar
for shape, value in (("list (browser)", [1]), ("scalar (single card)", 1)):
    status, resp = post(setup_id, setup_id, changed(setup_id),
                        {"setup": value, "end": None, "cancel": None, "submit": None},
                        state(None))
    check(f"setup click opens the dialog for that device - {shape}",
          status == 200 and resp.get("exp-target", {}).get("data") == {"mode": "create",
                                                                      "device": NAME}
          and resp.get("exp-modal", {}).get("opened") is True,
          f"http={status} {str(resp)[:110]}")

# ---- 2. submit without a name -> dialog stays open, error inside -------------
status, resp = post(setup_id, setup_id, ["exp-submit.n_clicks"],
                    {"setup": [1], "end": None, "cancel": None, "submit": 1},
                    state({"device": NAME}))
check("validation error keeps the dialog open with a message inside",
      resp.get("exp-modal", {}).get("opened") is True
      and "required" in str(resp.get("modal-msg", {}).get("children")),
      str(resp.get("modal-msg", {}).get("children"))[:60])

# ---- 3. submit with the details -> created, dialog closes --------------------
status, resp = post(setup_id, setup_id, ["exp-submit.n_clicks"],
                    {"setup": [1], "end": None, "cancel": None, "submit": 2},
                    state({"device": NAME}, name="zz_ui_exp", style="IPA", og="14.5",
                          yeast="US-05", resp_="Tester", notes="from the dialog"))
stored = main.query("""SELECT beer_style, og_plato, yeast, responsible, notes
                       FROM experiment WHERE name = 'zz_ui_exp'""")
check("dialog submit creates the experiment on that device",
      stored and stored[0]["beer_style"] == "IPA" and float(stored[0]["og_plato"]) == 14.5
      and stored[0]["notes"] == "from the dialog", str(stored))
check("dialog closes, the page reports it and the grid reloads",
      resp.get("exp-modal", {}).get("opened") is False
      and "started" in str(resp.get("msg", {}).get("children"))
      and resp.get("reload", {}).get("data") == 1,
      f"opened={resp.get('exp-modal')} reload={resp.get('reload')}")

# ---- 4. the card now shows the running experiment + red end button ----------
end_id = find_button_id(NAME, "end-btn")
running_card = card_text(NAME)
check("the card renders an end button whose id matches the callback pattern exactly",
      end_id is not None and sorted(end_id.keys()) == ["device", "slot", "type"], str(end_id))
# FR-04: while an experiment runs the header carries the experiment name instead of the
# iSpindel name, and the card gets a stronger outline (`border-2 border-brand ring-2 ring-page`).
# The experiment name only exists in the header: the footer names the device instead.
check("a running experiment puts the experiment name in the card header (FR-04)",
      "zz_ui_exp" in running_card and "end-btn" in running_card
      and "running experiment" not in running_card
      and running_card.index("zz_ui_exp") < running_card.index("iSpindel:"),
      [c for c in running_card.split(",") if "zz_ui_exp" in c][:2])
check("the iSpindel name moves to the card footer and stays in the tooltip (FR-15)",
      "iSpindel:" in running_card and NAME in running_card
      and f"iSpindel {NAME}" in running_card,
      [c for c in running_card.split(",") if "iSpindel" in c][:2])
check("a running experiment gives the card a stronger outline (FR-04)",
      "border-2" in running_card and "border-brand" in running_card
      and "ring-2 ring-page" in running_card
      and "border-2" not in setup_card and "border-brand" in setup_card,
      [c for c in running_card.split('"') if "border-" in c][:2])
check("the setup button is gone while an experiment runs", "setup-btn" not in running_card)
check("the end button is red with a hover colour change",
      "bg-red-600" in running_card and "hover:bg-red-500" in running_card)

# ---- 4b. a rebuild that merely adds the end button must not end the experiment -------
# The grid is rebuilt on every refresh and the red button then shows up with n_clicks = 0.
# Dash fires this callback for that change too, and acting on it ended an experiment
# seconds after it was created - the reported bug: 0 measurements in the table, nothing to
# select in the fermentation chart and "this iSpindel has no running experiment".
status, resp = post(setup_id, end_id, changed(end_id),
                    {"setup": None, "end": [0], "cancel": None, "submit": 2},
                    state(None, name="zz_ui_exp", reload_=1))
still_running = main.query(
    "SELECT ended_at FROM experiment WHERE name = 'zz_ui_exp'")[0]["ended_at"]
check("a spurious end event (n_clicks 0) leaves the experiment running (FR-04)",
      still_running is None, f"ended_at={still_running}")


# ---- 5. a second experiment on the same device is rejected (FR-03) ----------
alert, delta = main.create_experiment("zz_ui_second", DEV, "", "", "", "", "", "")
check("FR-03 second experiment on the same iSpindel rejected",
      "already runs" in str(alert) and delta == 0, str(alert)[:60])

# ---- 6. "End experiment" - confirmation in the same dialog, then the end (FR-04) -----
# 6a: the red button no longer ends anything by itself - it opens the shared dialog in the
# "end" mode (read-only fields, warning, submit = "End experiment").
status, resp = post(setup_id, end_id, changed(end_id),
                    {"setup": None, "end": [1], "cancel": None, "submit": 2},
                    state(None, name="zz_ui_exp", reload_=1))
check("the end button asks for confirmation in the same dialog (FR-04)",
      resp.get("exp-modal", {}).get("opened") is True
      and resp.get("exp-modal", {}).get("title") == "End experiment"
      and resp.get("exp-submit", {}).get("children") == "End experiment"
      and resp.get("exp-target", {}).get("data") == {"mode": "end", "device": NAME},
      f"opened={resp.get('exp-modal')} target={resp.get('exp-target', {}).get('data')}")
check("the confirmation says what it ends and that assignment stops (FR-04)",
      "zz_ui_exp" in str(resp.get("modal-msg", {}).get("children"))
      and "no longer assigned" in str(resp.get("modal-msg", {}).get("children")),
      str(resp.get("modal-msg", {}).get("children"))[:80])
check("the confirmation shows the experiment read-only (fields disabled)",
      '"disabled": true' in json.dumps(resp.get("exp-form", {}).get("children"), default=str),
      json.dumps(resp.get("exp-form", {}).get("children"), default=str)[:80])
still_running = main.query(
    "SELECT ended_at FROM experiment WHERE name = 'zz_ui_exp'")[0]["ended_at"]
check("nothing is ended before the confirmation (FR-04)", still_running is None,
      f"ended_at={still_running}")

# 6b: confirming in the dialog ends it (and the dialog closes)
status, resp = post(setup_id, end_id, ["exp-submit.n_clicks"],
                    {"setup": None, "end": None, "cancel": None, "submit": 1},
                    state({"mode": "end", "device": NAME}, reload_=1))
ended = main.query("SELECT ended_at FROM experiment WHERE name = 'zz_ui_exp'")[0]["ended_at"]
check("confirming in the dialog ends the experiment of that card (FR-04)",
      ended is not None and "ended" in str(resp.get("msg", {}).get("children"))
      and resp.get("exp-modal", {}).get("opened") is False,
      f"ended_at={ended}")
# the reported bug: ending by iSpindel name must work as well, never a 500
main.create_experiment("zz_ui_exp2", DEV, "", "", "", "", "", "")
alert, delta = main.end_experiment(NAME)
ended2 = main.query("SELECT ended_at FROM experiment WHERE name = 'zz_ui_exp2'")[0]["ended_at"]
check("ending by iSpindel name works (the bug that was reported)",
      ended2 is not None and delta == 1, f"{ended2} delta={delta}")
alert, delta = main.end_experiment("does_not_exist")
check("an unknown iSpindel gives a message instead of a database error",
      "unknown" in str(alert) and delta == 0, str(alert)[:50])
# the dialog is rebuilt from the database, so it always shows the experiment that is running
# *now* (FR-03: at most one active experiment per iSpindel), never a stale one
main.execute("UPDATE experiment SET ended_at = now() WHERE name = 'zz_ui_exp2'")
main.create_experiment("zz_ui_exp3", DEV, "", "", "", "", "", "")
status, resp = post(setup_id, end_id, changed(end_id),
                    {"setup": None, "end": [1], "cancel": None, "submit": 2},
                    state(None, reload_=1))
check("the end confirmation names the experiment that is running now (FR-03/FR-04)",
      resp.get("exp-modal", {}).get("title") == "End experiment"
      and "zz_ui_exp3" in str(resp.get("modal-msg", {}).get("children")),
      str(resp.get("modal-msg", {}).get("children"))[:80])
main.end_experiment(DEV)

# ---- 7. cancel and a rebuilt grid do not create anything --------------------
status, resp = post(setup_id, end_id, ["exp-cancel.n_clicks"],
                    {"setup": None, "end": [1], "cancel": 1, "submit": 2},
                    state({"device": NAME}, name="zz_ui_exp", reload_=2))
check("cancel closes the dialog without creating anything",
      resp.get("exp-modal", {}).get("opened") is False
      and resp.get("exp-target", {}).get("data") is None, str(resp.get("exp-modal")))
status, resp = post(setup_id, end_id, changed(setup_id),
                    {"setup": [None], "end": [None], "cancel": 1, "submit": 2},
                    state(None, reload_=2))
check("a rebuilt grid (all clicks empty) does not reopen the dialog",
      resp.get("exp-modal", {}).get("opened") in (None, "no_update")
      and resp.get("exp-target", {}).get("data") in (None, "no_update"),
      f"opened={resp.get('exp-modal')}")

# ---- 9. every rendered pattern id must match a callback pattern's keys ------
# (this is the bug that made the red End button do nothing: the id had an extra key)
patterns = pattern_key_sets()
rendered = rendered_pattern_ids()
missing = sorted(k for k in rendered if k not in patterns)
check("every rendered wildcard id matches a callback pattern exactly",
      not missing, f"rendered={sorted(rendered)} patterns={sorted(patterns)} unmatched={missing}")

# ---- 10. FR-06: edit and delete from a table row -----------------------------
exp_id = main.query("SELECT id FROM experiment WHERE name = 'zz_ui_exp'")[0]["id"]
edit_id, del_id = find_row_id(exp_id, "edit"), find_row_id(exp_id, "delete")
check("the table row renders edit and delete icon buttons",
      edit_id == {"type": "row-btn", "exp": exp_id, "mode": "edit"} and del_id is not None,
      f"edit={edit_id} delete={del_id}")

status, resp = post(setup_id, end_id, changed(edit_id),
                    {"row": [1], "cancel": 1, "submit": 2},
                    state(None, reload_=1), row_id=edit_id)
form = json.dumps(resp.get("exp-form", {}).get("children"), default=str)
check("the edit icon opens the dialog prefilled with that experiment (FR-06)",
      resp.get("exp-modal", {}).get("title") == "Edit experiment"
      and "zz_ui_exp" in form and "US-05" in form and "from the dialog" in form,
      f"title={resp.get('exp-modal', {}).get('title')!r}")

# a name that is already taken must be refused, like in the create dialog (FR-02)
status, resp = post(setup_id, end_id, ["exp-submit.n_clicks"],
                    {"row": [1], "cancel": 1, "submit": 1},
                    state({"mode": "edit", "id": exp_id}, name="zz_ui_exp2", reload_=1),
                    row_id=edit_id)
check("editing refuses a duplicate name (FR-02)",
      "unique" in str(resp.get("modal-msg", {}).get("children"))
      and resp.get("exp-modal", {}).get("opened") is True,
      str(resp.get("modal-msg", {}).get("children"))[:60])

# saving the edited fields updates the row in place
status, resp = post(setup_id, end_id, ["exp-submit.n_clicks"],
                    {"row": [1], "cancel": 1, "submit": 1},
                    state({"mode": "edit", "id": exp_id}, name="zz_ui_edited", yeast="S-04",
                          reload_=1), row_id=edit_id)
updated = main.query("SELECT yeast FROM experiment WHERE id = %s", (exp_id,))
check("saving the edited fields updates the experiment (FR-06)",
      updated and updated[0]["yeast"] == "S-04"
      and resp.get("exp-modal", {}).get("opened") is False,
      f"yeast={updated[0]['yeast'] if updated else None}")

# the trash icon asks before deleting; confirming removes the experiment and its measurements
main.execute("""INSERT INTO measurement (device_id, experiment_id, recorded_at, tilt_deg)
                VALUES (%s, %s, now(), 60)""", (DEV, exp_id))
status, resp = post(setup_id, end_id, changed(del_id),
                    {"row": [1], "cancel": 1, "submit": 2},
                    state(None, reload_=1), row_id=del_id)
check("the delete icon asks for confirmation in the same dialog",
      resp.get("exp-modal", {}).get("title") == "Delete experiment"
      and "cannot be undone" in str(resp.get("modal-msg", {}).get("children")),
      str(resp.get("modal-msg", {}).get("children"))[:60])
status, resp = post(setup_id, end_id, ["exp-submit.n_clicks"],
                    {"row": [1], "cancel": 1, "submit": 1},
                    state({"mode": "delete", "id": exp_id}, reload_=1), row_id=del_id)
check("confirming deletes the experiment and its measurements",
      not main.query("SELECT 1 FROM experiment WHERE id = %s", (exp_id,))
      and not main.query("SELECT 1 FROM measurement WHERE experiment_id = %s", (exp_id,))
      and resp.get("exp-modal", {}).get("opened") is False,
      str(resp.get("msg", {}).get("children"))[:60])

# ---- 11. FR-04 / FR-06 / FR-17 / FR-21: the actions of a running row ---------
# A running experiment carries the FR-06 pencil (it can be corrected while it runs - the edit
# never touches the end time), the FR-04 end button (the red stop icon opens the same confirmation
# popup as the card button) and the two analysis actions FR-17 (chart) / FR-21 (csv). **Delete**
# stays a completed-only action.
main.create_experiment("zz_ui_running", DEV, "", "", "", "", "", "")
running_id = main.query("SELECT id FROM experiment WHERE name = 'zz_ui_running'")[0]["id"]
run_end = find_row_id(running_id, "end")
run_edit = find_row_id(running_id, "edit")
run_chart = find_row_id(running_id, "chart")
run_csv = find_row_id(running_id, "csv")
check("a running row offers edit + end + chart + csv, but no delete (FR-04 / FR-06 / FR-17 / FR-21)",
      run_end == {"type": "row-btn", "exp": running_id, "mode": "end"}
      and run_edit == {"type": "row-btn", "exp": running_id, "mode": "edit"}
      and find_row_id(running_id, "delete") is None
      and run_chart == {"type": "row-btn", "exp": running_id, "mode": "chart"}
      and run_csv == {"type": "row-btn", "exp": running_id, "mode": "csv"},
      f"end={run_end} edit={run_edit} delete={find_row_id(running_id, 'delete')} "
      f"chart={run_chart} csv={run_csv}")

# FR-06 on a running row: the pencil opens the edit dialog prefilled with the running experiment
status, resp = post(setup_id, end_id, changed(run_edit),
                    {"row": [1], "cancel": 1, "submit": 2}, state(None, reload_=1),
                    row_id=run_edit)
check("the pencil of a running row opens the edit dialog prefilled (FR-06)",
      resp.get("exp-modal", {}).get("title") == "Edit experiment"
      and "zz_ui_running" in json.dumps(resp.get("exp-form", {}).get("children"), default=str),
      f"title={resp.get('exp-modal', {}).get('title')!r}")

# FR-21: the csv icon of a running row exports that experiment and reports in the toast
main.execute("""INSERT INTO measurement (device_id, experiment_id, recorded_at, tilt_deg, temp_c,
                                         gravity_plato, battery_v, interval_s, rssi_dbm)
                VALUES (%s, %s, now(), 62, 20, 12, 3.9, 900, -55)""", (DEV, running_id))
status, resp = post(setup_id, end_id, changed(run_csv),
                    {"row": [1], "cancel": 1, "submit": 2}, state(None, reload_=1),
                    row_id=run_csv)
check("the csv icon exports the running experiment (FR-21)",
      status == 200 and "zz_ui_running" in str(resp.get("msg", {}).get("children")),
      str(resp.get("msg", {}).get("children"))[:80])

status, resp = post(setup_id, end_id, changed(run_end),
                    {"row": [1], "cancel": 1, "submit": 2}, state(None, reload_=1),
                    row_id=run_end)
check("the end icon of a running row opens the same confirmation popup (FR-04)",
      resp.get("exp-modal", {}).get("title") == "End experiment"
      and resp.get("exp-submit", {}).get("children") == "End experiment"
      and resp.get("exp-target", {}).get("data") == {"mode": "end", "device": NAME}
      and "zz_ui_running" in str(resp.get("modal-msg", {}).get("children")),
      f"target={resp.get('exp-target', {}).get('data')}")
check("nothing is ended before the confirmation (FR-04)",
      main.query("SELECT ended_at FROM experiment WHERE id = %s",
                 (running_id,))[0]["ended_at"] is None)

status, resp = post(setup_id, end_id, ["exp-submit.n_clicks"],
                    {"row": [1], "cancel": 1, "submit": 1},
                    state({"mode": "end", "device": NAME}, reload_=1), row_id=run_end)
run_ended = main.query("SELECT ended_at FROM experiment WHERE id = %s", (running_id,))[0]
check("confirming that popup ends the experiment (FR-04)",
      run_ended["ended_at"] is not None
      and "ended" in str(resp.get("msg", {}).get("children"))
      and resp.get("exp-modal", {}).get("opened") is False,
      f"ended_at={run_ended['ended_at']}")

# ---- 8. the page layout ------------------------------------------------------
def find_modal():
    found = []

    def walk(node):
        if hasattr(node, "to_plotly_json"):
            node = node.to_plotly_json()
        if isinstance(node, dict):
            if node.get("id") == "exp-modal" or node.get("type") == "Modal":
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(main.app.layout)
    return found[0] if found else None


layout = json.dumps(main.app.layout.to_plotly_json(), default=str)
check("the old start/end card is gone", "Start / end an experiment" not in layout)
check("the experiment table panel carries no heading line any more",
      "Experiments (FR-05)" not in layout)
check("the dialog lives outside the rebuilt grid (typing survives a refresh)",
      "exp-modal" in layout and "Set up experiment" in layout and "Start experiment" in layout)
# FR-17 / FR-16 / FR-21: the experiment multi-select and the CSV button left the chart card -
# the selection moved into the row actions (chart-select store), the export onto the rows.
check("the chart card has no experiment multi-select / CSV button any more",
      "exp-select" not in layout and "csv-btn" not in layout and "chart-select" in layout)
def component_order(root, ids):
    """The ids of `ids` in document order (depth-first), so a layout check can assert that the
    figure really comes before the controls under it - a plain substring search over the JSON is
    unreliable because to_plotly_json leaves some subtrees as repr strings."""
    order = []

    def walk(node):
        if hasattr(node, "to_plotly_json"):
            node = node.to_plotly_json()
        if isinstance(node, dict):
            node_id = node.get("id")
            if isinstance(node_id, str) and node_id in ids:
                order.append(node_id)
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(root)
    return order


# FR-16 / FR-18: both controls sit **under** the figure now (the time axis bottom-left, the time
# range bottom-right) - in document order the graph comes first, then the axis, then the range.
order = component_order(main.app.layout, {"chart", "relative", "range"})
check("the time axis / time range controls moved below the chart",
      order == ["chart", "relative", "range"], f"order={order}")
modal_props = (find_modal() or {}).get("props", {})
check("the dialog cannot close itself out of sync (no X / outside / Esc)",
      modal_props.get("withCloseButton") is False and modal_props.get("closeOnClickOutside") is False
      and modal_props.get("closeOnEscape") is False and modal_props.get("opened") is False,
      str({k: modal_props.get(k) for k in
           ("opened", "withCloseButton", "closeOnClickOutside", "closeOnEscape")}))

# ---- 12. FR-12: the Devices table + its settings dialog ----------------------
# The Devices table manages the `device` master data (the values the ingest created on the first
# message). The dialog reuses the experiment modal with a different form, so the same `post()` works.
dev_row = main.query("SELECT id FROM device WHERE mqtt_name = %s", (NAME,))[0]["id"]
dev_btn = {"type": "dev-btn", "device": dev_row}
dev_table = json.dumps(main.device_table(main.device_rows()).to_plotly_json(), default=str)
check("the Devices table lists the iSpindel with its interval and a settings action (FR-12)",
      main.DEVICE_HEADERS[0] == "Name (MQTT topic)" and "Interval" in main.DEVICE_HEADERS
      and NAME in dev_table and "dev-btn" in dev_table,
      str(main.DEVICE_HEADERS))

status, resp = post(setup_id, end_id, changed(dev_btn), {"dev": 1}, state(None, reload_=1),
                    dev_id=dev_btn)
check("the Devices settings icon opens the device dialog (FR-12)",
      resp.get("exp-modal", {}).get("title") == "Device settings"
      and resp.get("exp-target", {}).get("data") == {"mode": "device", "id": dev_row}
      and NAME in json.dumps(resp.get("dev-form", {}).get("children"), default=str)
      and resp.get("dev-form", {}).get("style") == {"display": "block"}
      and resp.get("exp-form", {}).get("style") == {"display": "none"},
      f"title={resp.get('exp-modal', {}).get('title')!r}")

status, resp = post(setup_id, end_id, ["exp-submit.n_clicks"], {"submit": 1},
                    state({"mode": "device", "id": dev_row}, reload_=1),
                    dev_id=dev_btn, dev_name="ui test keg", dev_active=[])
saved = main.query("SELECT display_name, is_active FROM device WHERE id = %s", (dev_row,))[0]
check("saving the device dialog stores the display name + the in-use flag (FR-12)",
      saved["display_name"] == "ui test keg" and saved["is_active"] is False
      and "saved" in str(resp.get("msg", {}).get("children")), str(saved))
check("an ignored iSpindel disappears from the overview (FR-13)",
      NAME not in json.dumps(main.ispindel_overview({}).to_plotly_json(), default=str))

# ---- cleanup ----------------------------------------------------------------
# measurements first: the FK has no cascade (the FR-13 test inserts one for its device)
main.execute("""DELETE FROM measurement WHERE device_id IN
                  (SELECT id FROM device WHERE mqtt_name LIKE 'zz_ui%%')""")
main.execute("DELETE FROM experiment WHERE name LIKE 'zz_ui%%'")
main.execute("DELETE FROM device WHERE mqtt_name LIKE 'zz_ui%%'")
left = main.query("""SELECT (SELECT count(*) FROM experiment WHERE name LIKE 'zz_ui%%') e,
                            (SELECT count(*) FROM device WHERE mqtt_name LIKE 'zz_ui%%') d,
                            (SELECT count(*) FROM measurement m JOIN device d ON d.id = m.device_id
                              WHERE d.mqtt_name LIKE 'zz_ui%%') m""")[0]
print(f"cleanup: {left['e']} experiments, {left['d']} devices and {left['m']} measurements left")
print("\nRESULT:", "ALL PASS" if ok else "FAILURES - see above")
sys.exit(0 if ok else 1)
