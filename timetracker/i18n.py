"""国际化模块: 中文(zh) / English(en) / Français(fr)"""

LANGS = ["zh", "en", "fr"]
LANG_DISPLAY = {"zh": "中文", "en": "English", "fr": "Français"}

_STRINGS: dict[str, dict[str, str]] = {
    # ---- 通用按钮 ----
    "ok":               {"zh": "确定",   "en": "OK",         "fr": "OK"},
    "cancel":           {"zh": "取消",   "en": "Cancel",     "fr": "Annuler"},
    "confirm":          {"zh": "确认",   "en": "Confirm",    "fr": "Confirmer"},
    "save":             {"zh": "保存",   "en": "Save",       "fr": "Enregistrer"},
    "error":            {"zh": "错误: {err}", "en": "Error: {err}", "fr": "Erreur : {err}"},

    # ---- 应用 ----
    "app_title":        {"zh": "时间追踪器", "en": "Time Tracker", "fr": "Suivi du temps"},
    "status_ready":     {"zh": "就绪. 见底部快捷键",
                         "en": "Ready. See shortcuts below.",
                         "fr": "Prêt. Voir raccourcis ci-dessous."},
    "status_no_sel":    {"zh": "请先选中一个计时器",
                         "en": "Please select a timer first.",
                         "fr": "Sélectionnez d'abord un minuteur."},
    "recovered":        {"zh": "⚠ 已恢复 {n} 个异常退出的计时器: {names}",
                         "en": "⚠ Recovered {n} timer(s): {names}",
                         "fr": "⚠ {n} minuteur(s) récupéré(s) : {names}"},
    "lang_switched":    {"zh": "语言: {lang}",
                         "en": "Language: {lang}",
                         "fr": "Langue : {lang}"},

    # ---- 计时器操作返回消息 ----
    "name_empty":       {"zh": "名称不能为空",
                         "en": "Name cannot be empty.",
                         "fr": "Le nom ne peut pas être vide."},
    "name_exists":      {"zh": "名称已存在: {name}",
                         "en": "Name already exists: {name}",
                         "fr": "Nom déjà utilisé : {name}"},
    "created":          {"zh": "已新建: {name}",  "en": "Created: {name}",  "fr": "Créé : {name}"},
    "renamed":          {"zh": "已重命名为: {name}", "en": "Renamed to: {name}", "fr": "Renommé en : {name}"},
    "deleted":          {"zh": "已删除: {name}",  "en": "Deleted: {name}",  "fr": "Supprimé : {name}"},
    "not_found":        {"zh": "计时器不存在",
                         "en": "Timer not found.",
                         "fr": "Minuteur introuvable."},
    "started":          {"zh": "已启动: {name}",  "en": "Started: {name}",  "fr": "Démarré : {name}"},
    "stopped":          {"zh": "已暂停: {name}",  "en": "Paused: {name}",   "fr": "En pause : {name}"},
    "running_n":        {"zh": "  (当前共 {n} 个计时器同时运行)",
                         "en": "  ({n} timers running simultaneously)",
                         "fr": "  ({n} minuteurs en cours simultanément)"},

    # ---- 表格列头 ----
    "col_id":           {"zh": "ID",   "en": "ID",     "fr": "ID"},
    "col_name":         {"zh": "名称", "en": "Name",   "fr": "Nom"},
    "col_status":       {"zh": "状态", "en": "Status", "fr": "État"},
    "col_today":        {"zh": "今日", "en": "Today",  "fr": "Auj."},
    "col_week":         {"zh": "本周", "en": "Week",   "fr": "Sem."},
    "col_month":        {"zh": "本月", "en": "Month",  "fr": "Mois"},
    "col_total":        {"zh": "累计", "en": "Total",  "fr": "Total"},

    # ---- 计时器状态 ----
    "running":          {"zh": "● 运行中", "en": "● Running", "fr": "● En cours"},
    "paused":           {"zh": "○ 暂停",   "en": "○ Paused",  "fr": "○ En pause"},

    # ---- 弹窗: 新建 / 重命名 / 删除 ----
    "dlg_new_title":    {"zh": "新建计时器",  "en": "New Timer",  "fr": "Nouveau minuteur"},
    "dlg_new_ph":       {"zh": "例如: 看论文", "en": "e.g. Read papers", "fr": "ex. : Lire des articles"},
    "dlg_rename_title": {"zh": "重命名",       "en": "Rename",     "fr": "Renommer"},
    "dlg_del_msg":      {"zh": "删除「{name}」?\n累计 {dur} 将一并删除",
                         "en": "Delete \"{name}\"?\nTotal {dur} will be lost.",
                         "fr": "Supprimer « {name} » ?\nTotal {dur} sera perdu."},

    # ---- 时区管理 ----
    "tz_title":         {"zh": "时区管理 (a=添加  d=删除  Esc=关闭)",
                         "en": "Timezones  (a=add  d=delete  Esc=close)",
                         "fr": "Fuseaux horaires  (a=ajouter  d=suppr.  Esc=fermer)"},
    "tz_hint":          {"zh": "第一个时区(★)作为今日/本周/本月的统计基准",
                         "en": "First timezone (★) defines Today/Week/Month boundaries.",
                         "fr": "Le premier fuseau (★) définit Auj./Sem./Mois."},
    "tz_search_title":  {"zh": "输入时区关键词",
                         "en": "Search timezone keyword",
                         "fr": "Rechercher un fuseau horaire"},
    "tz_search_ph":     {"zh": "例如 Tokyo, New_York, Shanghai",
                         "en": "e.g. Tokyo, New_York, Paris",
                         "fr": "ex. : Tokyo, New_York, Paris"},
    "tz_pick_title":    {"zh": "选择一个时区 (回车确认, Esc 取消)",
                         "en": "Select a timezone (Enter=confirm, Esc=cancel)",
                         "fr": "Sélectionner (Entrée=confirmer, Esc=annuler)"},
    "tz_added":         {"zh": "已添加: {tz}", "en": "Added: {tz}",      "fr": "Ajouté : {tz}"},
    "tz_exists":        {"zh": "已存在",        "en": "Already exists.",  "fr": "Déjà présent."},
    "tz_not_found":     {"zh": "未找到匹配的时区: {q}",
                         "en": "No timezone found: {q}",
                         "fr": "Aucun fuseau trouvé : {q}"},
    "tz_min_one":       {"zh": "至少要保留一个时区",
                         "en": "At least one timezone is required.",
                         "fr": "Au moins un fuseau horaire est requis."},

    # ---- 番茄钟状态栏 ----
    "phase_work":       {"zh": "工作",  "en": "Work",         "fr": "Travail"},
    "phase_short_break":{"zh": "短休",  "en": "Short break",  "fr": "Pause courte"},
    "phase_long_break": {"zh": "长休",  "en": "Long break",   "fr": "Pause longue"},
    "pomo_idle_bar":    {"zh": "番茄钟: 空闲   今日已完成 {n} 个工作番茄   (按 p 启动)",
                         "en": "Pomodoro: idle   {n} completed today   (p to start)",
                         "fr": "Pomodoro : inactif   {n} terminé(s) aujourd'hui   (p pour démarrer)"},
    "pomo_phase_label": {"zh": "{phase}中", "en": "{phase}", "fr": "{phase}"},
    "pomo_remaining":   {"zh": "剩余",   "en": "remaining", "fr": "restant"},
    "pomo_today_done":  {"zh": "今日完成 {n}", "en": "{n} today", "fr": "{n} auj."},
    "pomo_cancel_hint": {"zh": "(x 取消)", "en": "(x cancel)", "fr": "(x annuler)"},
    "pomo_finished":    {"zh": "🍅 [{phase}] 阶段完成! 按 p 启动下一阶段",
                         "en": "🍅 [{phase}] done! Press p for next phase.",
                         "fr": "🍅 [{phase}] terminé ! Appuyez sur p pour continuer."},
    "pomo_notify_msg":  {"zh": "番茄钟 [{phase}] 阶段完成",
                         "en": "Pomodoro [{phase}] complete",
                         "fr": "Pomodoro [{phase}] terminé"},
    "pomo_started":     {"zh": "🍅 工作番茄已启动 ({min} 分钟). 按 x 取消",
                         "en": "🍅 Pomodoro started ({min} min). Press x to cancel.",
                         "fr": "🍅 Pomodoro démarré ({min} min). x pour annuler."},
    "pomo_cancelled":   {"zh": "番茄钟已取消",
                         "en": "Pomodoro cancelled.",
                         "fr": "Pomodoro annulé."},

    # ---- 番茄钟设置弹窗 ----
    "pomo_cfg_title":   {"zh": "番茄钟设置",
                         "en": "Pomodoro Settings",
                         "fr": "Paramètres Pomodoro"},
    "pomo_cfg_work":    {"zh": "工作时长 (分钟):",
                         "en": "Work duration (min):",
                         "fr": "Durée de travail (min) :"},
    "pomo_cfg_short":   {"zh": "短休时长 (分钟):",
                         "en": "Short break (min):",
                         "fr": "Pause courte (min) :"},
    "pomo_cfg_long":    {"zh": "长休时长 (分钟):",
                         "en": "Long break (min):",
                         "fr": "Pause longue (min) :"},
    "pomo_cfg_every":   {"zh": "每几个工作番茄后长休:",
                         "en": "Long break every N pomodoros:",
                         "fr": "Pause longue tous les N pomodoros :"},
    "pomo_cfg_bell":    {"zh": "响铃: {state} (b 切换)",
                         "en": "Bell: {state} (b to toggle)",
                         "fr": "Sonnerie : {state} (b pour basculer)"},
    "pomo_cfg_bell_on": {"zh": "开",  "en": "ON",  "fr": "ON"},
    "pomo_cfg_bell_off":{"zh": "关",  "en": "OFF", "fr": "OFF"},
    "pomo_cfg_saved":   {"zh": "番茄钟设置已保存",
                         "en": "Settings saved.",
                         "fr": "Paramètres enregistrés."},
    "pomo_cfg_invalid": {"zh": "请输入正整数",
                         "en": "Please enter a positive integer.",
                         "fr": "Veuillez entrer un entier positif."},

    # ---- 排序 ----
    "sort_manual":      {"zh": "手动",    "en": "Manual",   "fr": "Manuel"},
    "sort_auto":        {"zh": "按时长↓", "en": "By time↓", "fr": "Par durée↓"},
    "sort_manual_long": {"zh": "手动排序",
                         "en": "Manual sort",
                         "fr": "Tri manuel"},
    "sort_auto_long":   {"zh": "按时长降序",
                         "en": "Sort by duration (desc)",
                         "fr": "Tri par durée (déc.)"},
    "sort_switched":    {"zh": "排序方式已切换为: {mode}  (手动排序时用 [ / ] 上下移动)",
                         "en": "Sort mode: {mode}  ([ / ] to reorder in manual mode)",
                         "fr": "Tri : {mode}  ([ / ] pour réordonner en tri manuel)"},
    "sort_no_manual":   {"zh": "当前为自动排序, 按 s 切换到手动排序后可上下移动",
                         "en": "Auto sort active. Press s to switch to manual.",
                         "fr": "Tri automatique. Appuyez sur s pour passer en manuel."},

    # ---- 导出 ----
    "export_done":      {"zh": "✓ 已导出 {n} 条记录到 {path}",
                         "en": "✓ Exported {n} record(s) to {path}",
                         "fr": "✓ {n} enregistrement(s) exporté(s) vers {path}"},

    # ---- Footer 快捷键描述 ----
    "bind_new":         {"zh": "新建",    "en": "New",          "fr": "Nouveau"},
    "bind_toggle":      {"zh": "启/停",   "en": "Start/Stop",   "fr": "Démarrer/Stop"},
    "bind_rename":      {"zh": "重命名",  "en": "Rename",       "fr": "Renommer"},
    "bind_delete":      {"zh": "删除",    "en": "Delete",       "fr": "Supprimer"},
    "bind_export":      {"zh": "导出",    "en": "Export",       "fr": "Exporter"},
    "bind_tz":          {"zh": "时区",    "en": "Timezone",     "fr": "Fuseau"},
    "bind_sort":        {"zh": "排序切换","en": "Sort mode",    "fr": "Mode tri"},
    "bind_move_up":     {"zh": "上移",    "en": "Move up",      "fr": "Monter"},
    "bind_move_down":   {"zh": "下移",    "en": "Move down",    "fr": "Descendre"},
    "bind_pomo":        {"zh": "番茄钟",  "en": "Pomodoro",     "fr": "Pomodoro"},
    "bind_pomo_cfg":    {"zh": "番茄设置","en": "Pomo settings","fr": "Config pomo"},
    "bind_pomo_cancel": {"zh": "取消番茄","en": "Cancel pomo",  "fr": "Annuler pomo"},
    "bind_lang":        {"zh": "切换语言","en": "Language",     "fr": "Langue"},
    "bind_quit":        {"zh": "退出",    "en": "Quit",         "fr": "Quitter"},
}

_lang = "zh"


def set_lang(lang: str):
    global _lang
    if lang in LANGS:
        _lang = lang


def get_lang() -> str:
    return _lang


def t(key: str, **kwargs) -> str:
    row = _STRINGS.get(key)
    if row is None:
        return key
    text = row.get(_lang) or row.get("zh") or key
    return text.format(**kwargs) if kwargs else text
