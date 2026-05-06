"""
业务逻辑层 (Service Layer)
- 不依赖任何 UI, 纯 Python 调用
- 未来上云时, FastAPI 路由直接调用同一个 Service, 逻辑零重写
- 时间一律用 UTC 存储, 展示层负责转换时区
"""
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, available_timezones

from .db import Database, LOCAL_USER_ID


# ============================================================
# 偏好默认值
# ============================================================
DEFAULT_TIMEZONES = ["Europe/Paris", "Asia/Shanghai"]
DEFAULT_POMODORO = {
    "work_minutes": 25,
    "short_break_minutes": 5,
    "long_break_minutes": 15,
    "long_break_every": 4,
    "bell_enabled": True,
}


@dataclass
class TimerView:
    """给 UI 用的计时器视图对象"""
    id: int
    name: str
    is_running: bool
    total_seconds: int      # 含运行中实时部分
    today_seconds: int
    week_seconds: int
    month_seconds: int


@dataclass
class PomodoroState:
    """番茄钟当前状态快照"""
    is_active: bool             # 是否有番茄钟在跑
    phase: str                  # work / short_break / long_break / idle
    planned_seconds: int        # 当前阶段计划时长
    elapsed_seconds: int        # 当前阶段已过秒数
    remaining_seconds: int      # 剩余秒数 (可能 <0 表示超时)
    completed_works_today: int  # 今日完成的工作番茄数
    work_count_in_cycle: int    # 当前循环内完成的工作番茄数 (用于决定下次是短休还是长休)
    just_finished: bool         # 这一帧是否刚好结束 (UI 用来触发响铃)
    finished_phase: Optional[str]  # 刚结束的阶段名


# ============================================================
# Service
# ============================================================
class TimerService:
    def __init__(self, db: Database, user_id: int = LOCAL_USER_ID):
        self.db = db
        self.user_id = user_id

        # 番茄钟运行时状态 (内存中, 不入库; 入库的只有完成的 pomodoro 记录)
        # 上云后这部分要么放 Redis, 要么客户端本地保存
        self._pomo_phase: str = "idle"
        self._pomo_start_utc: Optional[datetime] = None
        self._pomo_planned: int = 0
        self._pomo_work_count_in_cycle: int = 0
        self._pomo_just_finished_phase: Optional[str] = None  # 给 UI 消费一次的标志

    # ============================================================
    # 偏好: 时区
    # ============================================================
    def get_timezones(self) -> list[str]:
        raw = self.db.get_pref(self.user_id, "timezones")
        if not raw:
            return DEFAULT_TIMEZONES.copy()
        try:
            tzs = json.loads(raw)
            if isinstance(tzs, list) and all(isinstance(x, str) for x in tzs):
                return tzs
        except json.JSONDecodeError:
            pass
        return DEFAULT_TIMEZONES.copy()

    def set_timezones(self, tzs: list[str]):
        # 校验
        valid = available_timezones()
        cleaned = []
        for tz in tzs:
            if tz in valid and tz not in cleaned:
                cleaned.append(tz)
        if not cleaned:
            cleaned = DEFAULT_TIMEZONES.copy()
        self.db.set_pref(self.user_id, "timezones", json.dumps(cleaned))

    def add_timezone(self, tz: str) -> bool:
        if tz not in available_timezones():
            return False
        tzs = self.get_timezones()
        if tz in tzs:
            return False
        tzs.append(tz)
        self.set_timezones(tzs)
        return True

    def remove_timezone(self, tz: str):
        tzs = self.get_timezones()
        if tz in tzs:
            tzs.remove(tz)
            self.set_timezones(tzs)

    def get_primary_timezone(self) -> str:
        """统计周期(今日/本周/本月)按第一个时区界定边界"""
        tzs = self.get_timezones()
        return tzs[0] if tzs else "UTC"

    def search_timezones(self, query: str, limit: int = 30) -> list[str]:
        q = query.lower().strip()
        if not q:
            return sorted(available_timezones())[:limit]
        return sorted(tz for tz in available_timezones() if q in tz.lower())[:limit]

    # ============================================================
    # 偏好: 番茄钟
    # ============================================================
    def get_pomodoro_config(self) -> dict:
        raw = self.db.get_pref(self.user_id, "pomodoro_config")
        if not raw:
            return DEFAULT_POMODORO.copy()
        try:
            cfg = json.loads(raw)
            merged = DEFAULT_POMODORO.copy()
            merged.update({k: v for k, v in cfg.items() if k in DEFAULT_POMODORO})
            return merged
        except json.JSONDecodeError:
            return DEFAULT_POMODORO.copy()

    def set_pomodoro_config(self, **kwargs):
        cfg = self.get_pomodoro_config()
        for k, v in kwargs.items():
            if k in DEFAULT_POMODORO:
                cfg[k] = v
        self.db.set_pref(self.user_id, "pomodoro_config", json.dumps(cfg))

    # ============================================================
    # 启动时恢复
    # ============================================================
    def recover_on_startup(self) -> list[str]:
        """把异常退出时还在运行的计时器, 截断到 last_checkpoint 并写入会话日志"""
        rows = self.db.list_running_timers(self.user_id)
        recovered = []
        for row in rows:
            if not row["last_start_ts"] or not row["last_checkpoint_ts"]:
                self.db.mark_timer_stopped(row["id"], 0)
                continue
            last_start = datetime.fromisoformat(row["last_start_ts"])
            last_cp = datetime.fromisoformat(row["last_checkpoint_ts"])
            session_seconds = max(0, int((last_cp - last_start).total_seconds()))
            self.db.add_session(
                self.user_id, row["id"],
                last_start.isoformat(), last_cp.isoformat(),
                session_seconds
            )
            self.db.mark_timer_stopped(row["id"], 0)  # checkpoint 之前的进度已在 total_seconds
            recovered.append(row["name"])
        return recovered

    # ============================================================
    # 计时器 CRUD
    # ============================================================
    def create_timer(self, name: str) -> tuple[bool, str]:
        name = name.strip()
        if not name:
            return False, "名称不能为空"
        try:
            self.db.add_timer(self.user_id, name)
            return True, f"已新建: {name}"
        except Exception as e:
            if "UNIQUE" in str(e):
                return False, f"名称已存在: {name}"
            return False, f"错误: {e}"

    def rename_timer(self, timer_id: int, new_name: str) -> tuple[bool, str]:
        new_name = new_name.strip()
        if not new_name:
            return False, "名称不能为空"
        try:
            self.db.rename_timer(self.user_id, timer_id, new_name)
            return True, f"已重命名为: {new_name}"
        except Exception as e:
            if "UNIQUE" in str(e):
                return False, f"名称已存在: {new_name}"
            return False, f"错误: {e}"

    def delete_timer(self, timer_id: int) -> tuple[bool, str]:
        t = self.db.get_timer(self.user_id, timer_id)
        if not t:
            return False, "计时器不存在"
        if t["is_running"]:
            self.stop_timer(timer_id)
        self.db.delete_timer(self.user_id, timer_id)
        return True, f"已删除: {t['name']}"

    def toggle_timer(self, timer_id: int) -> tuple[bool, str, int]:
        """
        启动/暂停切换. 返回 (success, message, running_count_after).
        running_count_after 用于 UI 提示"现在有 N 个在跑"
        """
        t = self.db.get_timer(self.user_id, timer_id)
        if not t:
            return False, "计时器不存在", 0
        if t["is_running"]:
            self.stop_timer(timer_id)
            running = len(self.db.list_running_timers(self.user_id))
            return True, f"已暂停: {t['name']}", running
        else:
            self.start_timer(timer_id)
            running = len(self.db.list_running_timers(self.user_id))
            return True, f"已启动: {t['name']}", running

    def start_timer(self, timer_id: int):
        now_iso = datetime.now(timezone.utc).isoformat()
        self.db.mark_timer_running(timer_id, now_iso)

    def stop_timer(self, timer_id: int):
        t = self.db.get_timer(self.user_id, timer_id)
        if not t or not t["is_running"]:
            return
        last_start = datetime.fromisoformat(t["last_start_ts"])
        last_cp = datetime.fromisoformat(t["last_checkpoint_ts"])
        now = datetime.now(timezone.utc)
        delta = max(0, int((now - last_cp).total_seconds()))
        session_seconds = max(0, int((now - last_start).total_seconds()))
        self.db.mark_timer_stopped(timer_id, delta)
        self.db.add_session(self.user_id, timer_id, last_start.isoformat(), now.isoformat(), session_seconds)

    def checkpoint_all_running(self):
        """每隔 N 秒把所有运行中计时器的进度落盘"""
        rows = self.db.list_running_timers(self.user_id)
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        for row in rows:
            if not row["last_checkpoint_ts"]:
                continue
            last_cp = datetime.fromisoformat(row["last_checkpoint_ts"])
            delta = int((now - last_cp).total_seconds())
            if delta > 0:
                self.db.update_timer_progress(row["id"], delta, now_iso)

    # ============================================================
    # 时段统计
    # ============================================================
    def _period_bounds_utc(self, period: str) -> tuple[datetime, datetime]:
        tz = ZoneInfo(self.get_primary_timezone())
        now_local = datetime.now(tz)
        if period == "today":
            start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start = (now_local - timedelta(days=now_local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "month":
            start = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError(period)
        return start.astimezone(timezone.utc), now_local.astimezone(timezone.utc)

    def _seconds_in_period(self, timer_id: int, start_utc: datetime, end_utc: datetime) -> int:
        rows = self.db.query_sessions(self.user_id, timer_id, start_utc.isoformat(), end_utc.isoformat())
        total = 0
        for row in rows:
            s = datetime.fromisoformat(row["start_ts"])
            e = datetime.fromisoformat(row["end_ts"])
            if s < start_utc:
                s = start_utc
            if e > end_utc:
                e = end_utc
            seg = int((e - s).total_seconds())
            if seg > 0:
                total += seg
        # 如果正在运行, 把"上次启动到现在"的部分截断到时段内加上
        t = self.db.get_timer(self.user_id, timer_id)
        if t and t["is_running"] and t["last_start_ts"]:
            ls = datetime.fromisoformat(t["last_start_ts"])
            now = datetime.now(timezone.utc)
            s = max(ls, start_utc)
            e = min(now, end_utc)
            if e > s:
                total += int((e - s).total_seconds())
        return total

    def list_timer_views(self) -> list[TimerView]:
        timers = self.db.list_timers(self.user_id)
        today_s, now_utc = self._period_bounds_utc("today")
        week_s, _ = self._period_bounds_utc("week")
        month_s, _ = self._period_bounds_utc("month")
        result = []
        for t in timers:
            total = t["total_seconds"]
            if t["is_running"] and t["last_checkpoint_ts"]:
                last_cp = datetime.fromisoformat(t["last_checkpoint_ts"])
                total += max(0, int((datetime.now(timezone.utc) - last_cp).total_seconds()))
            result.append(TimerView(
                id=t["id"],
                name=t["name"],
                is_running=bool(t["is_running"]),
                total_seconds=total,
                today_seconds=self._seconds_in_period(t["id"], today_s, now_utc),
                week_seconds=self._seconds_in_period(t["id"], week_s, now_utc),
                month_seconds=self._seconds_in_period(t["id"], month_s, now_utc),
            ))
        return result

    # ============================================================
    # 番茄钟
    # ============================================================
    def start_pomodoro(self, phase: str = "work"):
        """phase: work / short_break / long_break"""
        cfg = self.get_pomodoro_config()
        if phase == "work":
            planned = cfg["work_minutes"] * 60
        elif phase == "short_break":
            planned = cfg["short_break_minutes"] * 60
        elif phase == "long_break":
            planned = cfg["long_break_minutes"] * 60
        else:
            return
        self._pomo_phase = phase
        self._pomo_start_utc = datetime.now(timezone.utc)
        self._pomo_planned = planned

    def cancel_pomodoro(self):
        """中途取消, 记录为未完成"""
        if self._pomo_phase == "idle" or self._pomo_start_utc is None:
            return
        now = datetime.now(timezone.utc)
        actual = max(0, int((now - self._pomo_start_utc).total_seconds()))
        self.db.add_pomodoro(
            self.user_id, self._pomo_phase,
            self._pomo_start_utc.isoformat(), now.isoformat(),
            self._pomo_planned, actual, completed=False
        )
        self._pomo_phase = "idle"
        self._pomo_start_utc = None
        self._pomo_planned = 0

    def tick_pomodoro(self) -> PomodoroState:
        """
        每秒由 UI 调一次. 如果时间到, 自动完成当前阶段并记账.
        下一阶段不会自动启动, 由 UI 决定/提示用户.
        """
        cfg = self.get_pomodoro_config()
        just_finished_phase = None

        if self._pomo_phase != "idle" and self._pomo_start_utc is not None:
            elapsed = int((datetime.now(timezone.utc) - self._pomo_start_utc).total_seconds())
            if elapsed >= self._pomo_planned:
                # 阶段完成
                end_utc = self._pomo_start_utc + timedelta(seconds=self._pomo_planned)
                self.db.add_pomodoro(
                    self.user_id, self._pomo_phase,
                    self._pomo_start_utc.isoformat(), end_utc.isoformat(),
                    self._pomo_planned, self._pomo_planned, completed=True
                )
                if self._pomo_phase == "work":
                    self._pomo_work_count_in_cycle += 1
                    if self._pomo_work_count_in_cycle >= cfg["long_break_every"]:
                        self._pomo_work_count_in_cycle = 0
                just_finished_phase = self._pomo_phase
                self._pomo_phase = "idle"
                self._pomo_start_utc = None
                self._pomo_planned = 0

        # 构造状态快照
        if self._pomo_phase != "idle" and self._pomo_start_utc is not None:
            elapsed = int((datetime.now(timezone.utc) - self._pomo_start_utc).total_seconds())
            remaining = self._pomo_planned - elapsed
            is_active = True
            phase = self._pomo_phase
            planned = self._pomo_planned
        else:
            elapsed = 0
            remaining = 0
            is_active = False
            phase = "idle"
            planned = 0

        # 今日完成的工作番茄数
        tz = ZoneInfo(self.get_primary_timezone())
        now_local = datetime.now(tz)
        day_start_utc = now_local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        today_count = self.db.count_completed_work_pomodoros_today(
            self.user_id, day_start_utc.isoformat(), datetime.now(timezone.utc).isoformat()
        )

        return PomodoroState(
            is_active=is_active,
            phase=phase,
            planned_seconds=planned,
            elapsed_seconds=elapsed,
            remaining_seconds=remaining,
            completed_works_today=today_count,
            work_count_in_cycle=self._pomo_work_count_in_cycle,
            just_finished=just_finished_phase is not None,
            finished_phase=just_finished_phase,
        )

    def suggest_next_phase(self) -> str:
        """根据循环计数建议下一阶段是什么"""
        cfg = self.get_pomodoro_config()
        if self._pomo_work_count_in_cycle == 0:
            # 刚做完长休, 或刚启动 -> 下一个是 work
            return "work"
        # 实际逻辑: tick 完成 work 后 cycle 计数 +1, 所以这里看的是上次完成 work 后的状态
        # 简单起见: cycle == 0 表示刚长休完, 否则下一个非 work 阶段
        return "work"

    # ============================================================
    # 导出
    # ============================================================
    def export_sessions_csv(self, path) -> int:
        import csv
        rows = self.db.export_all_sessions(self.user_id)
        primary_tz = ZoneInfo(self.get_primary_timezone())
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["timer_name", "start_utc", "end_utc",
                        f"start_{self.get_primary_timezone()}",
                        f"end_{self.get_primary_timezone()}",
                        "duration_seconds", "duration_hms"])
            for r in rows:
                s_utc = datetime.fromisoformat(r["start_ts"])
                e_utc = datetime.fromisoformat(r["end_ts"])
                w.writerow([
                    r["name"],
                    r["start_ts"],
                    r["end_ts"],
                    s_utc.astimezone(primary_tz).strftime("%Y-%m-%d %H:%M:%S"),
                    e_utc.astimezone(primary_tz).strftime("%Y-%m-%d %H:%M:%S"),
                    r["duration_seconds"],
                    format_duration(r["duration_seconds"]),
                ])
        return len(rows)


# ============================================================
# 工具函数
# ============================================================
def format_duration(seconds: int) -> str:
    if seconds < 0:
        seconds = 0
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    elif m > 0:
        return f"{m}m {s:02d}s"
    else:
        return f"{s}s"


def format_mmss(seconds: int) -> str:
    """番茄钟用的 MM:SS 格式, 支持负数(超时)"""
    sign = "-" if seconds < 0 else ""
    s = abs(seconds)
    m = s // 60
    s = s % 60
    return f"{sign}{m:02d}:{s:02d}"
