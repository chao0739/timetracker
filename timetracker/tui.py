"""
TUI 界面层
- 只负责渲染和按键, 业务逻辑全部走 TimerService
- 未来要做 Web 版, 这个文件可以整个扔掉, FastAPI 直接调 TimerService
"""
import sys
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button, DataTable, Footer, Header, Input, Label, ListItem, ListView, Static
)

from .service import TimerService, format_duration, format_mmss
from . import i18n
from .i18n import t


# ============================================================
# 输入弹窗(通用)
# ============================================================
class TextInputScreen(ModalScreen[Optional[str]]):
    BINDINGS = [Binding("escape", "cancel", "")]

    def __init__(self, title: str, default: str = "", placeholder: str = ""):
        super().__init__()
        self.title_text = title
        self.default = default
        self.placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Label(self.title_text, id="dialog-title")
            yield Input(value=self.default, placeholder=self.placeholder, id="input")
            with Horizontal(id="dialog-buttons"):
                yield Button(t("ok"), variant="primary", id="ok")
                yield Button(t("cancel"), id="cancel")

    def on_mount(self):
        self.query_one("#input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "ok":
            v = self.query_one("#input", Input).value.strip()
            if v:
                self.dismiss(v)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted):
        v = event.value.strip()
        if v:
            self.dismiss(v)

    def action_cancel(self):
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "cancel", "")]

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Label(self.message, id="dialog-title")
            with Horizontal(id="dialog-buttons"):
                yield Button(t("confirm"), variant="error", id="ok")
                yield Button(t("cancel"), id="cancel")

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(event.button.id == "ok")

    def action_cancel(self):
        self.dismiss(False)


# ============================================================
# 时区管理弹窗
# ============================================================
class TimezoneScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", ""),
        Binding("a", "add_tz", ""),
        Binding("d", "delete_tz", ""),
    ]

    def __init__(self, service: TimerService):
        super().__init__()
        self.service = service

    def compose(self) -> ComposeResult:
        with Container(id="tz-dialog"):
            yield Label(t("tz_title"), id="dialog-title")
            yield Label(t("tz_hint"), id="tz-hint")
            yield ListView(id="tz-list")

    def on_mount(self):
        self._refresh_list()

    def _refresh_list(self):
        lv = self.query_one("#tz-list", ListView)
        lv.clear()
        tzs = self.service.get_timezones()
        for i, tz in enumerate(tzs):
            prefix = "★ " if i == 0 else "  "
            lv.append(ListItem(Label(f"{prefix}{tz}"), id=f"tz-{i}"))

    def action_add_tz(self):
        def callback(query: Optional[str]):
            if not query:
                return
            matches = self.service.search_timezones(query, limit=20)
            if not matches:
                self.app.notify(t("tz_not_found", q=query), severity="warning")
                return
            if len(matches) == 1:
                ok = self.service.add_timezone(matches[0])
                self.app.notify(t("tz_added", tz=matches[0]) if ok else t("tz_exists"))
                self._refresh_list()
                return
            self.app.push_screen(
                TimezonePickerScreen(matches),
                lambda chosen: self._after_pick(chosen)
            )

        self.app.push_screen(
            TextInputScreen(t("tz_search_title"), placeholder=t("tz_search_ph")),
            callback
        )

    def _after_pick(self, chosen: Optional[str]):
        if chosen:
            ok = self.service.add_timezone(chosen)
            self.app.notify(t("tz_added", tz=chosen) if ok else t("tz_exists"))
            self._refresh_list()

    def action_delete_tz(self):
        lv = self.query_one("#tz-list", ListView)
        if lv.index is None:
            return
        tzs = self.service.get_timezones()
        if 0 <= lv.index < len(tzs):
            target = tzs[lv.index]
            if len(tzs) <= 1:
                self.app.notify(t("tz_min_one"), severity="warning")
                return
            self.service.remove_timezone(target)
            self._refresh_list()

    def action_close(self):
        self.dismiss(None)


class TimezonePickerScreen(ModalScreen[Optional[str]]):
    """时区搜索结果选择"""
    BINDINGS = [Binding("escape", "cancel", "")]

    def __init__(self, candidates: list[str]):
        super().__init__()
        self.candidates = candidates

    def compose(self) -> ComposeResult:
        with Container(id="tz-dialog"):
            yield Label(t("tz_pick_title"), id="dialog-title")
            lv = ListView(id="picker-list")
            yield lv

    def on_mount(self):
        lv = self.query_one("#picker-list", ListView)
        for i, tz in enumerate(self.candidates):
            lv.append(ListItem(Label(tz), id=f"pick-{i}"))
        lv.focus()

    def on_list_view_selected(self, event: ListView.Selected):
        idx = self.query_one("#picker-list", ListView).index
        if idx is not None and 0 <= idx < len(self.candidates):
            self.dismiss(self.candidates[idx])

    def action_cancel(self):
        self.dismiss(None)


# ============================================================
# 番茄钟设置弹窗
# ============================================================
class PomodoroConfigScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "cancel", "")]

    def __init__(self, service: TimerService):
        super().__init__()
        self.service = service

    def compose(self) -> ComposeResult:
        cfg = self.service.get_pomodoro_config()
        bell_state = t("pomo_cfg_bell_on") if cfg["bell_enabled"] else t("pomo_cfg_bell_off")
        with Container(id="pomo-config-dialog"):
            yield Label(t("pomo_cfg_title"), id="dialog-title")
            yield Label(t("pomo_cfg_work"))
            yield Input(value=str(cfg["work_minutes"]), id="work-min")
            yield Label(t("pomo_cfg_short"))
            yield Input(value=str(cfg["short_break_minutes"]), id="short-min")
            yield Label(t("pomo_cfg_long"))
            yield Input(value=str(cfg["long_break_minutes"]), id="long-min")
            yield Label(t("pomo_cfg_every"))
            yield Input(value=str(cfg["long_break_every"]), id="every")
            yield Label(t("pomo_cfg_bell", state=bell_state), id="bell-label")
            with Horizontal(id="dialog-buttons"):
                yield Button(t("save"), variant="primary", id="save")
                yield Button(t("cancel"), id="cancel")

    def on_mount(self):
        self._bell_enabled = self.service.get_pomodoro_config()["bell_enabled"]

    def on_key(self, event):
        if event.key == "b":
            focused = self.focused
            if not isinstance(focused, Input):
                self._bell_enabled = not self._bell_enabled
                bell_state = t("pomo_cfg_bell_on") if self._bell_enabled else t("pomo_cfg_bell_off")
                self.query_one("#bell-label", Label).update(t("pomo_cfg_bell", state=bell_state))

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "save":
            try:
                w = max(1, int(self.query_one("#work-min", Input).value))
                s = max(1, int(self.query_one("#short-min", Input).value))
                l = max(1, int(self.query_one("#long-min", Input).value))
                e = max(1, int(self.query_one("#every", Input).value))
            except ValueError:
                self.app.notify(t("pomo_cfg_invalid"), severity="error")
                return
            self.service.set_pomodoro_config(
                work_minutes=w, short_break_minutes=s, long_break_minutes=l,
                long_break_every=e, bell_enabled=self._bell_enabled
            )
            self.app.notify(t("pomo_cfg_saved"))
            self.dismiss(None)
        else:
            self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


# ============================================================
# 主应用
# ============================================================
class TimeTrackerApp(App):
    CSS = """
    Screen { background: $surface; }

    #clock-bar {
        height: 5;
        background: $boost;
        border: tall $primary;
        padding: 0 1;
    }
    .clock {
        width: 1fr;
        content-align: center middle;
        text-style: bold;
    }

    #pomo-bar {
        height: 3;
        background: $boost;
        border: tall $secondary;
        padding: 0 2;
        content-align: center middle;
    }

    DataTable { height: 1fr; }

    #status-bar {
        height: 3;
        background: $boost;
        padding: 0 2;
        content-align: center middle;
    }

    #dialog, #tz-dialog, #pomo-config-dialog {
        align: center middle;
        background: $panel;
        border: thick $primary;
        padding: 1 2;
        width: 70;
        height: auto;
    }
    #tz-dialog, #pomo-config-dialog { height: 25; }

    #dialog-title { text-style: bold; margin-bottom: 1; }
    #dialog-buttons { align: center middle; height: auto; margin-top: 1; }
    #dialog-buttons Button { margin: 0 1; }
    #tz-hint { color: $text-muted; margin-bottom: 1; }
    """

    BINDINGS = [
        Binding("n", "new_timer", "新建"),
        Binding("space", "toggle_timer", "启动/暂停"),
        Binding("r", "rename_timer", "重命名"),
        Binding("d", "delete_timer", "删除"),
        Binding("e", "export_csv", "导出"),
        Binding("t", "manage_tz", "时区"),
        Binding("s", "toggle_sort", "排序切换"),
        Binding("[", "move_up", "上移"),
        Binding("]", "move_down", "下移"),
        Binding("p", "start_pomodoro", "番茄钟"),
        Binding("c", "config_pomodoro", "番茄设置"),
        Binding("x", "cancel_pomodoro", "取消番茄"),
        Binding("l", "cycle_lang", "切换语言"),
        Binding("q", "quit_app", "退出"),
    ]

    AUTOSAVE_INTERVAL = 10

    def __init__(self, service: TimerService):
        super().__init__()
        self.service = service

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Horizontal(id="clock-bar")
        yield Static("", id="pomo-bar")
        yield DataTable(id="timer-table", cursor_type="row", zebra_stripes=True)
        yield Static("", id="status-bar")
        yield Footer()

    def on_mount(self):
        self.title = t("app_title")
        self._rebuild_bindings()
        self._rebuild_table_columns()
        self._update_subtitle()
        self._rebuild_clock_bar()

        recovered = self.service.recover_on_startup()
        if recovered:
            self.set_status(t("recovered", n=len(recovered), names=", ".join(recovered)))
        else:
            self.set_status(t("status_ready"))

        self.set_interval(1.0, self.tick)
        self.set_interval(self.AUTOSAVE_INTERVAL, self.autosave)

        self.refresh_table()
        self.refresh_pomo_bar(self.service.tick_pomodoro())

    def set_status(self, msg: str):
        self.query_one("#status-bar", Static).update(msg)

    def _rebuild_bindings(self):
        from textual.binding import BindingsMap
        # 直接替换实例级 _bindings 缓存, Textual active_bindings 读的就是这个
        self._bindings = BindingsMap([
            Binding("n", "new_timer", t("bind_new")),
            Binding("space", "toggle_timer", t("bind_toggle")),
            Binding("r", "rename_timer", t("bind_rename")),
            Binding("d", "delete_timer", t("bind_delete")),
            Binding("e", "export_csv", t("bind_export")),
            Binding("t", "manage_tz", t("bind_tz")),
            Binding("s", "toggle_sort", t("bind_sort")),
            Binding("[", "move_up", t("bind_move_up")),
            Binding("]", "move_down", t("bind_move_down")),
            Binding("p", "start_pomodoro", t("bind_pomo")),
            Binding("c", "config_pomodoro", t("bind_pomo_cfg")),
            Binding("x", "cancel_pomodoro", t("bind_pomo_cancel")),
            Binding("l", "cycle_lang", t("bind_lang")),
            Binding("q", "quit_app", t("bind_quit")),
        ])
        self.refresh_bindings()

    def _rebuild_table_columns(self):
        table = self.query_one("#timer-table", DataTable)
        table.clear(columns=True)
        table.add_columns(
            t("col_id"), t("col_name"), t("col_status"),
            t("col_today"), t("col_week"), t("col_month"), t("col_total")
        )

    # ---------- 时钟栏 ----------
    def _rebuild_clock_bar(self):
        bar = self.query_one("#clock-bar", Horizontal)
        bar.remove_children()
        for tz in self.service.get_timezones():
            bar.mount(Static("", classes="clock", id=f"clock-{tz.replace('/', '_').replace('-', '_')}"))

    def _update_clocks(self):
        lang = i18n.get_lang()
        weekdays_zh = ["一", "二", "三", "四", "五", "六", "日"]
        tzs = self.service.get_timezones()
        for i, tz in enumerate(tzs):
            try:
                z = ZoneInfo(tz)
                now = datetime.now(z)
            except Exception:
                continue
            label = tz.split("/")[-1].replace("_", " ")
            prefix = "★ " if i == 0 else ""
            day_str = f"周{weekdays_zh[now.weekday()]}" if lang == "zh" else now.strftime("%a")
            text = (
                f"[bold cyan]{prefix}{label}[/]\n"
                f"{now.strftime('%Y-%m-%d')} {day_str}\n"
                f"[bold yellow]{now.strftime('%H:%M:%S')}[/]"
            )
            wid = f"clock-{tz.replace('/', '_').replace('-', '_')}"
            try:
                self.query_one(f"#{wid}", Static).update(text)
            except Exception:
                pass

    # ---------- 主循环 ----------
    def tick(self):
        self._update_clocks()
        pomo_state = self.service.tick_pomodoro()
        self.refresh_pomo_bar(pomo_state)
        if pomo_state.just_finished:
            self._on_pomodoro_finished(pomo_state.finished_phase)
        self.refresh_table()

    def autosave(self):
        self.service.checkpoint_all_running()

    def refresh_table(self, focus_timer_id: Optional[int] = None):
        table = self.query_one("#timer-table", DataTable)
        cursor_row = table.cursor_row if table.row_count > 0 else 0
        table.clear()

        views = self.service.list_timer_views()
        focus_row = cursor_row
        for i, v in enumerate(views):
            status = f"[bold green]{t('running')}[/]" if v.is_running else f"[dim]{t('paused')}[/]"
            name = f"[bold]{v.name}[/]" if v.is_running else v.name
            table.add_row(
                str(v.id), name, status,
                format_duration(v.today_seconds),
                format_duration(v.week_seconds),
                format_duration(v.month_seconds),
                format_duration(v.total_seconds),
                key=str(v.id),
            )
            if focus_timer_id is not None and v.id == focus_timer_id:
                focus_row = i
        if table.row_count > 0:
            table.move_cursor(row=min(focus_row, table.row_count - 1))

    def refresh_pomo_bar(self, state):
        bar = self.query_one("#pomo-bar", Static)
        if not state.is_active:
            bar.update(f"[dim]{t('pomo_idle_bar', n=state.completed_works_today)}[/]")
            return
        phase_key = {
            "work": "phase_work",
            "short_break": "phase_short_break",
            "long_break": "phase_long_break",
        }.get(state.phase, "phase_work")
        phase_name = t(phase_key)
        color = {"work": "red", "short_break": "green", "long_break": "blue"}.get(state.phase, "white")
        bar.update(
            f"[bold {color}]🍅 {t('pomo_phase_label', phase=phase_name)}[/]   "
            f"{t('pomo_remaining')} [bold yellow]{format_mmss(state.remaining_seconds)}[/]   "
            f"{format_mmss(state.elapsed_seconds)}/{format_mmss(state.planned_seconds)}   "
            f"{t('pomo_today_done', n=state.completed_works_today)}   [dim]{t('pomo_cancel_hint')}[/]"
        )

    def _on_pomodoro_finished(self, phase: Optional[str]):
        cfg = self.service.get_pomodoro_config()
        phase_key = {
            "work": "phase_work",
            "short_break": "phase_short_break",
            "long_break": "phase_long_break",
        }.get(phase or "", "phase_work")
        phase_name = t(phase_key)
        if cfg["bell_enabled"]:
            try:
                from plyer import notification
                notification.notify(
                    title=t("app_title"),
                    message=t("pomo_notify_msg", phase=phase_name),
                    timeout=10,
                )
            except Exception:
                sys.stdout.write("\a\a\a")
                sys.stdout.flush()
        self.set_status(t("pomo_finished", phase=phase_name))
        self.notify(t("pomo_notify_msg", phase=phase_name), severity="information", timeout=8)

    # ---------- 计时器操作 ----------
    def _selected_timer_id(self) -> Optional[int]:
        table = self.query_one("#timer-table", DataTable)
        if table.row_count == 0:
            return None
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            return int(row_key.value)
        except Exception:
            return None

    def action_new_timer(self):
        def cb(name: Optional[str]):
            if name:
                ok, msg = self.service.create_timer(name)
                self.set_status(("✓ " if ok else "✗ ") + msg)
                if ok:
                    self.refresh_table()
        self.push_screen(TextInputScreen(t("dlg_new_title"), placeholder=t("dlg_new_ph")), cb)

    def action_toggle_timer(self):
        tid = self._selected_timer_id()
        if tid is None:
            self.set_status(t("status_no_sel"))
            return
        ok, msg, running = self.service.toggle_timer(tid)
        if ok and running > 1:
            timer = self.service.db.get_timer(self.service.user_id, tid)
            if timer and timer["is_running"]:
                msg += t("running_n", n=running)
        self.set_status(("✓ " if ok else "✗ ") + msg)
        self.refresh_table()

    def action_rename_timer(self):
        tid = self._selected_timer_id()
        if tid is None:
            self.set_status(t("status_no_sel"))
            return
        timer = self.service.db.get_timer(self.service.user_id, tid)
        if not timer:
            return

        def cb(name: Optional[str]):
            if name:
                ok, msg = self.service.rename_timer(tid, name)
                self.set_status(("✓ " if ok else "✗ ") + msg)
                if ok:
                    self.refresh_table()
        self.push_screen(TextInputScreen(t("dlg_rename_title"), default=timer["name"]), cb)

    def action_delete_timer(self):
        tid = self._selected_timer_id()
        if tid is None:
            self.set_status(t("status_no_sel"))
            return
        timer = self.service.db.get_timer(self.service.user_id, tid)
        if not timer:
            return

        def cb(yes: bool):
            if yes:
                ok, msg = self.service.delete_timer(tid)
                self.set_status(("✓ " if ok else "✗ ") + msg)
                if ok:
                    self.refresh_table()
        self.push_screen(
            ConfirmScreen(t("dlg_del_msg", name=timer["name"], dur=format_duration(timer["total_seconds"]))),
            cb
        )

    def action_export_csv(self):
        from pathlib import Path
        path = Path.home() / f"timetracker_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        n = self.service.export_sessions_csv(path)
        self.set_status(t("export_done", n=n, path=path))

    # ---------- 时区 ----------
    def action_manage_tz(self):
        def cb(_):
            self._rebuild_clock_bar()
            self._update_clocks()
            self.refresh_table()
        self.push_screen(TimezoneScreen(self.service), cb)

    # ---------- 番茄钟 ----------
    def action_start_pomodoro(self):
        self.service.start_pomodoro("work")
        cfg = self.service.get_pomodoro_config()
        self.set_status(t("pomo_started", min=cfg["work_minutes"]))
        self.refresh_pomo_bar(self.service.tick_pomodoro())

    def action_cancel_pomodoro(self):
        self.service.cancel_pomodoro()
        self.set_status(t("pomo_cancelled"))
        self.refresh_pomo_bar(self.service.tick_pomodoro())

    def action_config_pomodoro(self):
        self.push_screen(PomodoroConfigScreen(self.service), lambda _: None)

    # ---------- 排序 ----------
    def _update_subtitle(self):
        mode = self.service.get_sort_mode()
        mode_label = t("sort_auto_long") if mode == "auto_total_desc" else t("sort_manual_long")
        lang_display = i18n.LANG_DISPLAY.get(i18n.get_lang(), "")
        self.sub_title = f"{mode_label} | {lang_display} (l)"

    def action_toggle_sort(self):
        mode = self.service.get_sort_mode()
        new_mode = "auto_total_desc" if mode == "manual" else "manual"
        self.service.set_sort_mode(new_mode)
        mode_label = t("sort_auto_long") if new_mode == "auto_total_desc" else t("sort_manual_long")
        self.set_status(t("sort_switched", mode=mode_label))
        self._update_subtitle()
        self.refresh_table()

    def action_move_up(self):
        if self.service.get_sort_mode() != "manual":
            self.set_status(t("sort_no_manual"))
            return
        tid = self._selected_timer_id()
        if tid is None:
            return
        if self.service.move_timer(tid, -1):
            self.refresh_table(focus_timer_id=tid)

    def action_move_down(self):
        if self.service.get_sort_mode() != "manual":
            self.set_status(t("sort_no_manual"))
            return
        tid = self._selected_timer_id()
        if tid is None:
            return
        if self.service.move_timer(tid, +1):
            self.refresh_table(focus_timer_id=tid)

    # ---------- 语言 ----------
    def action_cycle_lang(self):
        langs = i18n.LANGS
        current = i18n.get_lang()
        idx = langs.index(current) if current in langs else 0
        new_lang = langs[(idx + 1) % len(langs)]
        self.service.set_language(new_lang)
        i18n.set_lang(new_lang)
        self.title = t("app_title")
        self._rebuild_bindings()
        self._rebuild_table_columns()
        self._update_subtitle()
        self.refresh_table()
        self.refresh_pomo_bar(self.service.tick_pomodoro())
        self.set_status(t("lang_switched", lang=i18n.LANG_DISPLAY[new_lang]))

    # ---------- 退出 ----------
    def action_quit_app(self):
        self.service.checkpoint_all_running()
        self.service.db.close()
        self.exit()
