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


# ============================================================
# 输入弹窗(通用)
# ============================================================
class TextInputScreen(ModalScreen[Optional[str]]):
    BINDINGS = [Binding("escape", "cancel", "取消")]

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
                yield Button("确定", variant="primary", id="ok")
                yield Button("取消", id="cancel")

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
    BINDINGS = [Binding("escape", "cancel", "取消")]

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Label(self.message, id="dialog-title")
            with Horizontal(id="dialog-buttons"):
                yield Button("确认", variant="error", id="ok")
                yield Button("取消", id="cancel")

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(event.button.id == "ok")

    def action_cancel(self):
        self.dismiss(False)


# ============================================================
# 时区管理弹窗
# ============================================================
class TimezoneScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "关闭"),
        Binding("a", "add_tz", "添加"),
        Binding("d", "delete_tz", "删除"),
    ]

    def __init__(self, service: TimerService):
        super().__init__()
        self.service = service

    def compose(self) -> ComposeResult:
        with Container(id="tz-dialog"):
            yield Label("时区管理 (a=添加 d=删除当前选中 Esc=关闭)", id="dialog-title")
            yield Label("第一个时区会作为统计周期(今日/本周/本月)的基准", id="tz-hint")
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
                self.app.notify(f"未找到匹配的时区: {query}", severity="warning")
                return
            # 如果只有一个完全匹配, 直接添加
            if len(matches) == 1:
                ok = self.service.add_timezone(matches[0])
                self.app.notify("已添加: " + matches[0] if ok else "已存在")
                self._refresh_list()
                return
            # 多个匹配, 让用户从列表选
            self.app.push_screen(
                TimezonePickerScreen(matches),
                lambda chosen: self._after_pick(chosen)
            )

        self.app.push_screen(
            TextInputScreen("输入时区关键词", placeholder="例如 Tokyo, New_York, Shanghai"),
            callback
        )

    def _after_pick(self, chosen: Optional[str]):
        if chosen:
            ok = self.service.add_timezone(chosen)
            self.app.notify("已添加: " + chosen if ok else "已存在")
            self._refresh_list()

    def action_delete_tz(self):
        lv = self.query_one("#tz-list", ListView)
        if lv.index is None:
            return
        tzs = self.service.get_timezones()
        if 0 <= lv.index < len(tzs):
            target = tzs[lv.index]
            if len(tzs) <= 1:
                self.app.notify("至少要保留一个时区", severity="warning")
                return
            self.service.remove_timezone(target)
            self._refresh_list()

    def action_close(self):
        self.dismiss(None)


class TimezonePickerScreen(ModalScreen[Optional[str]]):
    """时区搜索结果选择"""
    BINDINGS = [Binding("escape", "cancel", "取消")]

    def __init__(self, candidates: list[str]):
        super().__init__()
        self.candidates = candidates

    def compose(self) -> ComposeResult:
        with Container(id="tz-dialog"):
            yield Label("选择一个时区 (回车确认, Esc 取消)", id="dialog-title")
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
    BINDINGS = [Binding("escape", "cancel", "取消")]

    def __init__(self, service: TimerService):
        super().__init__()
        self.service = service

    def compose(self) -> ComposeResult:
        cfg = self.service.get_pomodoro_config()
        with Container(id="pomo-config-dialog"):
            yield Label("番茄钟设置", id="dialog-title")
            yield Label("工作时长 (分钟):")
            yield Input(value=str(cfg["work_minutes"]), id="work-min")
            yield Label("短休时长 (分钟):")
            yield Input(value=str(cfg["short_break_minutes"]), id="short-min")
            yield Label("长休时长 (分钟):")
            yield Input(value=str(cfg["long_break_minutes"]), id="long-min")
            yield Label("每几个工作番茄后长休:")
            yield Input(value=str(cfg["long_break_every"]), id="every")
            yield Label(f"响铃: {'开' if cfg['bell_enabled'] else '关'} (b 切换)", id="bell-label")
            with Horizontal(id="dialog-buttons"):
                yield Button("保存", variant="primary", id="save")
                yield Button("取消", id="cancel")

    BINDINGS_RUNTIME = [Binding("b", "toggle_bell", "响铃")]

    def on_mount(self):
        self._bell_enabled = self.service.get_pomodoro_config()["bell_enabled"]

    def on_key(self, event):
        if event.key == "b":
            # 检查焦点不在 input 上
            focused = self.focused
            if not isinstance(focused, Input):
                self._bell_enabled = not self._bell_enabled
                self.query_one("#bell-label", Label).update(
                    f"响铃: {'开' if self._bell_enabled else '关'} (b 切换)"
                )

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "save":
            try:
                w = max(1, int(self.query_one("#work-min", Input).value))
                s = max(1, int(self.query_one("#short-min", Input).value))
                l = max(1, int(self.query_one("#long-min", Input).value))
                e = max(1, int(self.query_one("#every", Input).value))
            except ValueError:
                self.app.notify("请输入正整数", severity="error")
                return
            self.service.set_pomodoro_config(
                work_minutes=w, short_break_minutes=s, long_break_minutes=l,
                long_break_every=e, bell_enabled=self._bell_enabled
            )
            self.app.notify("番茄钟设置已保存")
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
        self.title = "时间追踪器"
        self._update_subtitle()

        table = self.query_one("#timer-table", DataTable)
        table.add_columns("ID", "名称", "状态", "今日", "本周", "本月", "累计")

        self._rebuild_clock_bar()

        recovered = self.service.recover_on_startup()
        if recovered:
            self.set_status(f"⚠ 已恢复 {len(recovered)} 个异常退出的计时器: {', '.join(recovered)}")
        else:
            self.set_status("就绪. 按 ? 或看底部快捷键栏")

        # 定时任务
        self.set_interval(1.0, self.tick)
        self.set_interval(self.AUTOSAVE_INTERVAL, self.autosave)

        self.refresh_table()
        self.refresh_pomo_bar(self.service.tick_pomodoro())

    def set_status(self, msg: str):
        self.query_one("#status-bar", Static).update(msg)

    # ---------- 时钟栏 ----------
    def _rebuild_clock_bar(self):
        """根据当前用户的时区配置动态重建时钟栏"""
        bar = self.query_one("#clock-bar", Horizontal)
        bar.remove_children()
        for tz in self.service.get_timezones():
            bar.mount(Static("", classes="clock", id=f"clock-{tz.replace('/', '_').replace('-', '_')}"))

    def _update_clocks(self):
        weekdays = ["一", "二", "三", "四", "五", "六", "日"]
        tzs = self.service.get_timezones()
        for i, tz in enumerate(tzs):
            try:
                z = ZoneInfo(tz)
                now = datetime.now(z)
            except Exception:
                continue
            label = tz.split("/")[-1].replace("_", " ")
            prefix = "★ " if i == 0 else ""
            text = (
                f"[bold cyan]{prefix}{label}[/]\n"
                f"{now.strftime('%Y-%m-%d')} 周{weekdays[now.weekday()]}\n"
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
            status = "[bold green]● 运行中[/]" if v.is_running else "[dim]○ 暂停[/]"
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
            bar.update(
                f"[dim]番茄钟: 空闲[/]   今日已完成 [bold]{state.completed_works_today}[/] 个工作番茄"
                f"   [dim](按 p 启动)[/]"
            )
            return
        phase_name = {"work": "工作", "short_break": "短休", "long_break": "长休"}.get(state.phase, state.phase)
        color = {"work": "red", "short_break": "green", "long_break": "blue"}.get(state.phase, "white")
        bar.update(
            f"[bold {color}]🍅 {phase_name}中[/]   "
            f"剩余 [bold yellow]{format_mmss(state.remaining_seconds)}[/]   "
            f"已用 {format_mmss(state.elapsed_seconds)} / {format_mmss(state.planned_seconds)}   "
            f"今日完成 {state.completed_works_today}   [dim](x 取消)[/]"
        )

    def _on_pomodoro_finished(self, phase: Optional[str]):
        cfg = self.service.get_pomodoro_config()
        phase_cn = {"work": "工作", "short_break": "短休", "long_break": "长休"}.get(phase or "", phase or "")
        if cfg["bell_enabled"]:
            # 终端响铃 (\a), SSH 也支持. 多响几下更明显
            sys.stdout.write("\a\a\a")
            sys.stdout.flush()
        self.set_status(f"🍅 [{phase_cn}] 阶段完成! 按 p 启动下一阶段")
        self.notify(f"番茄钟 [{phase_cn}] 阶段完成", severity="information", timeout=8)

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
        self.push_screen(TextInputScreen("新建计时器", placeholder="例如: 看论文"), cb)

    def action_toggle_timer(self):
        tid = self._selected_timer_id()
        if tid is None:
            self.set_status("请先选中一个计时器")
            return
        ok, msg, running = self.service.toggle_timer(tid)
        if ok and running > 1 and "已启动" in msg:
            msg += f"  (当前共 {running} 个计时器同时运行)"
        self.set_status(("✓ " if ok else "✗ ") + msg)
        self.refresh_table()

    def action_rename_timer(self):
        tid = self._selected_timer_id()
        if tid is None:
            return
        t = self.service.db.get_timer(self.service.user_id, tid)
        if not t:
            return

        def cb(name: Optional[str]):
            if name:
                ok, msg = self.service.rename_timer(tid, name)
                self.set_status(("✓ " if ok else "✗ ") + msg)
                if ok:
                    self.refresh_table()
        self.push_screen(TextInputScreen("重命名", default=t["name"]), cb)

    def action_delete_timer(self):
        tid = self._selected_timer_id()
        if tid is None:
            return
        t = self.service.db.get_timer(self.service.user_id, tid)
        if not t:
            return

        def cb(yes: bool):
            if yes:
                ok, msg = self.service.delete_timer(tid)
                self.set_status(("✓ " if ok else "✗ ") + msg)
                if ok:
                    self.refresh_table()
        self.push_screen(
            ConfirmScreen(f"删除「{t['name']}」?\n累计 {format_duration(t['total_seconds'])} 将一并删除"),
            cb
        )

    def action_export_csv(self):
        from pathlib import Path
        path = Path.home() / f"timetracker_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        n = self.service.export_sessions_csv(path)
        self.set_status(f"✓ 已导出 {n} 条记录到 {path}")

    # ---------- 时区 ----------
    def action_manage_tz(self):
        def cb(_):
            self._rebuild_clock_bar()
            self._update_clocks()
            self.refresh_table()
        self.push_screen(TimezoneScreen(self.service), cb)

    # ---------- 番茄钟 ----------
    def action_start_pomodoro(self):
        # 简单策略: 总是启动 work; 想做完整循环可以再扩展
        self.service.start_pomodoro("work")
        cfg = self.service.get_pomodoro_config()
        self.set_status(f"🍅 工作番茄已启动 ({cfg['work_minutes']} 分钟). 按 x 取消")
        self.refresh_pomo_bar(self.service.tick_pomodoro())

    def action_cancel_pomodoro(self):
        self.service.cancel_pomodoro()
        self.set_status("番茄钟已取消")
        self.refresh_pomo_bar(self.service.tick_pomodoro())

    def action_config_pomodoro(self):
        self.push_screen(PomodoroConfigScreen(self.service), lambda _: None)

    # ---------- 排序 ----------
    def _update_subtitle(self):
        mode = self.service.get_sort_mode()
        mode_cn = "手动" if mode == "manual" else "按时长↓"
        self.sub_title = (
            f"n=新建 空格=启停 s=排序({mode_cn}) [/]=上下移  "
            "p=番茄钟 t=时区 c=番茄设置 q=退出"
        )

    def action_toggle_sort(self):
        mode = self.service.get_sort_mode()
        new_mode = "auto_total_desc" if mode == "manual" else "manual"
        self.service.set_sort_mode(new_mode)
        mode_cn = "按时长降序" if new_mode == "auto_total_desc" else "手动排序"
        self.set_status(f"排序方式已切换为: {mode_cn}  (手动排序时用 [ / ] 上下移动)")
        self._update_subtitle()
        self.refresh_table()

    def action_move_up(self):
        if self.service.get_sort_mode() != "manual":
            self.set_status("当前为自动排序, 按 s 切换到手动排序后可上下移动")
            return
        tid = self._selected_timer_id()
        if tid is None:
            return
        if self.service.move_timer(tid, -1):
            self.refresh_table(focus_timer_id=tid)

    def action_move_down(self):
        if self.service.get_sort_mode() != "manual":
            self.set_status("当前为自动排序, 按 s 切换到手动排序后可上下移动")
            return
        tid = self._selected_timer_id()
        if tid is None:
            return
        if self.service.move_timer(tid, +1):
            self.refresh_table(focus_timer_id=tid)

    # ---------- 退出 ----------
    def action_quit_app(self):
        self.service.checkpoint_all_running()
        self.service.db.close()
        self.exit()
