# -*- coding: utf-8 -*-
"""
SBpakTool (pak_tool.py) — Starbound 资源包 (.pak) 打包 / 解包 拖拽小工具
SBpakTool (pak_tool.py) — Starbound .pak packer / unpacker (drag & drop)
================================================================================
用法 / Usage: 把「文件夹」或「.pak 文件」拖到本程序图标上（支持多选）
              Drag a FOLDER or a .pak FILE onto this program (multiple allowed)

    文件夹 / folder   →  打包 / packs into    <文件夹名>.pak
    .pak              →  解包 / unpacks into  <文件名>\\

还支持 / Also supports:
    * 界面中英双语，自动跟随系统，可用 --lang zh|en 或 PAK_TOOL_LANG 强制
      Bilingual UI (zh/en), auto-detected; force with --lang or PAK_TOOL_LANG
    * 资源管理器右键菜单：--install-menu 添加，--uninstall-menu 移除
      Explorer right-click menu: --install-menu / --uninstall-menu
    * 中文路径照样能用（临时 ASCII 目录联接，零拷贝，用完即删）
      Non-ASCII paths work (temporary ASCII junctions, zero copy, always cleaned up)
    * 打包先写临时文件再原子替换，失败不会破坏已有的 .pak
      Packing writes a temp file first and replaces atomically — never damages an
      existing .pak
    * 打包前会检查 _metadata（缺字段 / JSON 写坏 / 拖错层级 / 混进 .git 等）
      Pre-flight checks for _metadata and stray junk files

依赖同目录下的 asset_packer.exe / asset_unpacker.exe（OpenStarbound 官方工具，
本脚本只调用它们，绝不修改）。
Requires asset_packer.exe / asset_unpacker.exe (official OpenStarbound tools) in the
same folder; this script only calls them and never modifies them.

由人工智能 DeepSeek 编写，免费分享，随便用、随便改、随便再发。
Written by DeepSeek (AI). Shared freely - use it, modify it, pass it on.
================================================================================
"""

from __future__ import annotations

import atexit
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

# ============================== 配置项 ==============================
PACKER_NAME = "asset_packer.exe"
UNPACKER_NAME = "asset_unpacker.exe"

PACKER_EXTRA_ARGS: tuple = ()      # 打包附加参数，例如 ("-v",) 可逐文件输出
UNPACKER_EXTRA_ARGS: tuple = ()    # 解包附加参数

TIMEOUT_SECONDS = 1800             # 单个任务超时（秒），None = 不限时
SHOW_DIALOG = True                 # 结果窗口（成功/失败都弹一次，方便拖拽后确认）
CHECK_METADATA = True              # 打包前检查 _metadata（Mod 元数据）
CHECK_JUNK = True                  # 打包前提示 .git / *.psd 等不该进 .pak 的东西
VERBOSE = False                    # 把 asset_*.exe 的原始输出也打到控制台
KEEP_TEMP = False                  # True = 保留临时目录，方便排查问题
LOG_FILE_NAME = "pak_tool.log"     # 日志文件（与本脚本同目录）
LOG_MAX_BYTES = 2 * 1024 * 1024    # 日志超过该大小自动轮转
# ====================================================================

VERSION = "2.0"
PAK_MAGIC = b"SBAsset"             # Starbound .pak 文件头（当前版本为 SBAsset6）
WINDOW_TITLE = "pak_tool"

# 打包时不该出现的杂物（默认只提示、不自动排除，避免误删有用文件）
JUNK_DIR_NAMES = {".git", ".svn", ".hg", "__pycache__", ".idea", ".vs", "node_modules"}
JUNK_FILE_NAMES = {"thumbs.db", "desktop.ini", ".ds_store"}
JUNK_SUFFIXES = {".psd", ".xcf", ".pyc", ".pyo", ".bak", ".tmp"}
SCAN_LIMIT = 20000                 # 扫描文件数上限，避免超大目录卡住

# _metadata 字段表（参见同目录 _metadata.txt）
METADATA_FILE_NAME = "_metadata"      # 只能叫这个名字，且必须在 Mod 根目录
METADATA_JSON_NAME = "_metadata.json"  # 常见错误写法：多写了 .json 后缀，游戏不认
METADATA_WRONG_NAMES = ("_metadata.json", "_metadata.txt")   # 带扩展名 = 游戏不认
METADATA_TYPES = {
    "name": str, "friendlyName": str, "author": str, "version": str,
    "description": str, "link": str, "priority": int,
    "requires": list, "includes": list, "tags": list,
    "steamContentId": (str, int),
}
TYPE_KEYS = {str: "type_str", int: "type_int", list: "type_list"}

HELP_FLAGS = {"-h", "--help", "-?", "/?", "--usage"}
SILENT_FLAGS = {"-s", "--silent", "/silent"}
VERBOSE_FLAGS = {"--verbose", "--debug"}
KEEP_FLAGS = {"--keep-temp"}


# ============================== 多语言 / i18n ==============================
LANG = "zh"          # 运行时由 detect_language() 或 --lang 决定


def detect_language() -> str:
    """中文系统用中文，其它一律英文；可用 PAK_TOOL_LANG=zh|en 强制指定。"""
    forced = (os.environ.get("PAK_TOOL_LANG") or "").strip().lower()
    if forced.startswith("zh") or forced in ("cn", "chinese"):
        return "zh"
    if forced.startswith("en") or forced in ("english",):
        return "en"
    if os.name == "nt":
        try:
            import ctypes
            if (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x04:
                return "zh"          # LANG_CHINESE
            return "en"
        except Exception:
            pass
    try:
        import locale
        return "zh" if (locale.getlocale()[0] or "").lower().startswith("zh") else "en"
    except Exception:
        return "en"


# key: (中文, English)   —— {0} {1} 为位置参数
MSG = {
    # --- 运行环境 ---
    "tool_missing": ("找不到 {0} / {1}。\n请把本程序和这两个 exe 放在同一个目录下。",
                     "Cannot find {0} / {1}.\nKeep this program and those two exe files in the same folder."),
    "tool_dir_nonascii": ("工具所在路径含非 ASCII 字符（{0}），又找不到可用的 ASCII 临时目录。\n请把本程序和两个 exe 放到纯英文路径下。",
                          "The tool path contains non-ASCII characters ({0}) and no usable ASCII temp folder was found.\nPlease move this program and the two exe files to a pure-ASCII path."),
    "tool_copy_failed": ("工具路径含非 ASCII 字符，且无法建立 ASCII 运行副本：{0}",
                         "The tool path contains non-ASCII characters and no ASCII working copy could be created: {0}"),
    # --- 调用 asset_*.exe ---
    "timeout": ("{0} 运行超过 {1} 秒仍未结束，已中止", "{0} did not finish within {1} seconds and was aborted"),
    "launch_failed": ("无法启动 {0}：{1}", "Failed to start {0}: {1}"),
    "err_utf8": ("路径含非 ASCII 字符，asset_*.exe 无法处理（本工具会先用 ASCII 别名绕过；若仍报错，请检查源目录里的文件名）",
                 "The path contains non-ASCII characters that asset_*.exe cannot handle (this tool works around it with an ASCII alias; if it still fails, check the file names inside the source folder)"),
    "err_format": ("不是有效的 Starbound .pak 文件", "Not a valid Starbound .pak file"),
    "err_eof": (".pak 文件不完整或已损坏（可能上次打包/下载中断）",
                "The .pak file is incomplete or corrupted (a previous pack or download may have been interrupted)"),
    "err_config": ("找不到配置文件", "Configuration file not found"),
    "err_args": ("传给 asset_*.exe 的参数数量不对", "Wrong number of arguments passed to asset_*.exe"),
    "err_json": ("JSON 语法错误，打包被中止（多半是 _metadata 写错了）",
                 "JSON syntax error, packing aborted (usually a mistake in _metadata)"),
    "err_jsonex": ("JSON 格式错误（多半是 _metadata 写错了）", "JSON format error (usually a mistake in _metadata)"),
    "err_meta_load": ("无法解析 _metadata（内容必须是 JSON 对象 {{...}}）",
                      "Cannot parse _metadata (its content must be a JSON object {{...}})"),
    "err_longpath_tool": ("路径太长（Windows 260 字符限制），请把 Mod 移到更浅的目录再试",
                          "Path too long (Windows 260-character limit). Move the mod to a shallower folder and retry"),
    "err_openfile": ("文件不存在、被占用或无权限", "File missing, in use, or no permission"),
    "err_access": ("文件被其它程序占用或无访问权限（关掉游戏/资源管理器预览后重试）",
                   "The file is in use by another program or access was denied (close the game / Explorer preview and retry)"),
    "err_denied": ("没有写入权限，无法创建 {0}\n（Windows 拒绝访问）请把 Mod 文件夹换个位置，或检查该目录是否被安全软件/受控文件夹访问保护",
                   "No write permission: cannot create {0}\n(Windows access denied) Move the mod folder elsewhere, or check whether security software / Controlled Folder Access protects that folder"),
    "err_raw": ("（asset 工具原始报错：{0}）", "(raw error from the asset tool: {0})"),
    "err_exit": ("asset_*.exe 退出码 {0}", "asset_*.exe exited with code {0}"),
    # --- 临时目录 / 别名 ---
    "copy_dir_wait": ("      （路径含非 ASCII 字符，正在复制一份到临时目录，大文件夹请稍候…）",
                      "      (non-ASCII path: copying to a temp folder, please wait for large folders...)"),
    "copy_file_wait": ("      （路径含非 ASCII 字符，正在复制 .pak 到临时目录…）",
                       "      (non-ASCII path: copying the .pak to a temp folder...)"),
    "keep_temp": ("      (KEEP_TEMP) 临时目录未清理：{0}", "      (KEEP_TEMP) temp folder kept: {0}"),
    # --- _metadata ---
    "meta_not_utf8": ("_metadata 不是 UTF-8 编码（{0}），打包工具和游戏都会读取失败",
                      "_metadata is not UTF-8 encoded ({0}); both the packer and the game will fail to read it"),
    "meta_read_fail": ("_metadata 读取失败：{0}", "Failed to read _metadata: {0}"),
    "meta_bad_json": ("_metadata 不是合法 JSON：第 {0} 行第 {1} 列 — {2}",
                      "_metadata is not valid JSON: line {0}, column {1} — {2}"),
    "meta_not_object": ("_metadata 顶层必须是 JSON 对象 {{...}}，当前是 {0}",
                        "The top level of _metadata must be a JSON object {{...}}, but it is {0}"),
    "meta_no_name": ("缺少必填字段 \"name\"（Mod 唯一标识），游戏可能无法加载该 Mod",
                     "Missing required field \"name\" (the mod's unique id); the game may fail to load this mod"),
    "meta_bad_type": ("字段 \"{0}\" 应为{1}，当前是 {2}", "Field \"{0}\" should be {1}, but is {2}"),
    "meta_bad_list": ("字段 \"{0}\" 里应全部是字符串，发现 {1}",
                      "Field \"{0}\" should contain only strings; found {1}"),
    "meta_unknown": ("含未知字段（游戏会忽略）：{0}", "Contains unknown fields (the game ignores them): {0}"),
    "type_str": ("字符串", "a string"),
    "type_int": ("整数", "an integer"),
    "type_list": ("数组", "an array"),
    "junk_found": ("源目录里有 {0}，它们会被一起打包进 .pak（上传工坊前建议清理）",
                   "The source folder contains {0}; they will be packed into the .pak (consider cleaning up before uploading to the Workshop)"),
    "pack_empty": ("源文件夹是空的，打出来的 .pak 不包含任何文件",
                   "The source folder is empty; the resulting .pak will contain no files"),
    "path_too_long": ("路径太长（{0} 字符），超过 Windows 260 字符限制，{1} 会直接失败。\n请把 Mod 移到更浅的目录（例如 D:\\mods\\）后重试",
                      "Path too long ({0} characters), over the Windows 260-character limit; {1} will fail.\nMove the mod to a shallower folder (e.g. D:\\mods\\) and retry"),
    "meta_missing": ("本层没有 _metadata 文件，游戏/工坊可能不认这个 .pak（覆盖类补丁可以忽略）",
                     "No _metadata here; the game/Workshop may not recognise this .pak (ignore this for override patches)"),
    "meta_wrong_name": ("只找到了 {0}：Starbound 只认根目录下名为 {1}（没有扩展名）的文件，请把扩展名去掉",
                        "Only {0} was found: Starbound accepts only a file named exactly {1} (no extension) in the root - remove the extension"),
    "meta_wrong_level": ("本层没有 _metadata，但子文件夹 \"{0}\" 里有 —— 你可能选错了层级，要打包的应该是 \"{0}\"（.pak 根目录需要 _metadata，游戏才认）",
                         "No _metadata here, but subfolder \"{0}\" has one — you probably picked the wrong level; pack \"{0}\" instead (a .pak needs _metadata at its root)"),
    "meta_fatal": ("打包无法进行：{0}\n（asset_packer.exe 必须能解析 _metadata，修好后再试）",
                   "Cannot pack: {0}\n(asset_packer.exe must be able to parse _metadata; fix it and try again)"),
    "meta_multi_sub": ("本层没有 _metadata，子文件夹 {0} 里有 —— 请把它们分别处理",
                       "No _metadata here, but subfolders {0} have one — please process them one by one"),
    "exe_inside": ("源文件夹里混进了本工具的 {0}，会被一起打包",
                   "The source folder contains this tool's {0}; it will be packed too"),
    # --- 打包 ---
    "drive_root": ("不能直接打包驱动器根目录或当前目录，请选择里面的具体文件夹",
                   "Cannot pack a drive root or the current folder; please pick a folder inside it"),
    "no_write_dir": ("没有写入权限，无法在 {0} 创建文件\n请把 Mod 文件夹换个位置再试",
                     "No write permission: cannot create files in {0}\nPlease move the mod folder elsewhere"),
    "saved_elsewhere": ("{0} 没有写入权限，.pak 改存到：{1}", "{0} is not writable; the .pak was saved to: {1}"),
    "target_is_dir": ("输出位置有一个同名文件夹：{0}\n请先给它改名或删掉，再重新打包",
                      "A folder with the same name occupies the output path: {0}\nRename or remove it, then pack again"),
    "target_readonly": ("已有的 .pak 是只读的：{0}\n右键 → 属性 → 取消勾选「只读」后重试",
                        "The existing .pak is read-only: {0}\nRight-click → Properties → clear the Read-only box, then retry"),
    "alias_pack": ("路径含非 ASCII 字符，已通过临时 ASCII 别名完成打包（源文件未被修改）",
                   "Non-ASCII path: packing used a temporary ASCII alias (your files were not modified)"),
    "alias_unpack": ("路径含非 ASCII 字符，已通过临时 ASCII 别名完成解包",
                     "Non-ASCII path: unpacking used a temporary ASCII alias"),
    "alias_fail": ("路径含非 ASCII 字符，且无法建立 ASCII 别名：\n{0}\n（非 ASCII 字符：{1}）\n请把文件夹改成英文名，或确认临时目录可用",
                   "Non-ASCII path and no ASCII alias could be created:\n{0}\n(non-ASCII characters: {1})\nRename it to ASCII, or make sure a temp folder is available"),
    "no_tmp_output": ("无法准备临时输出文件，请把 Mod 移到纯英文路径后重试：{0}",
                      "Cannot prepare a temporary output file; move the mod to a pure-ASCII path: {0}"),
    "retry_temp": ("目标目录不允许 asset_packer.exe 写入，已改在临时目录打包后再放入",
                   "The target folder does not allow asset_packer.exe to write; packing was done in a temp folder and then moved"),
    "retry_temp_unpack": ("目标目录不允许 asset_unpacker.exe 写入，已改在临时目录解包后由本程序放入",
                          "The target folder does not allow asset_unpacker.exe to write; unpacking was done in a temp folder and then moved in"),
    "moved_elsewhere": ("无法放到 {0}（{1}），已改存到：{2}",
                        "Could not place the file at {0} ({1}); it was saved to: {2}"),
    "place_failed": ("打包已完成，但放不到 {0}：{1}\n文件已保留为：{2}",
                     "Packing finished, but the file could not be placed at {0}: {1}\nThe file was kept at: {2}"),
    "pack_no_output": ("asset_packer.exe 报告成功，但没有生成有效的 .pak 文件",
                       "asset_packer.exe reported success but produced no valid .pak file"),
    "overwrote": ("已覆盖原有的同名 .pak", "Overwrote the existing .pak"),
    # --- 解包 ---
    "unpack_longpath": ("路径太长（{0} 字符），超过 Windows 260 字符限制，asset_unpacker.exe 会直接失败。\n请把 .pak 移到更浅的目录后重试",
                        "Path too long ({0} characters), over the Windows 260-character limit; asset_unpacker.exe will fail.\nMove the .pak to a shallower folder and retry"),
    "read_fail": ("无法读取文件：{0}", "Cannot read the file: {0}"),
    "zero_pak": (".pak 文件是 0 字节（复制/下载中断），无法解包",
                 "The .pak file is 0 bytes (an interrupted copy/download); cannot unpack"),
    "bad_magic": ("不是有效的 Starbound .pak 文件（文件头是 \"{0}\"，应为 SBAsset6）",
                  "Not a valid Starbound .pak file (header is \"{0}\", expected SBAsset6)"),
    "out_is_file": ("输出位置已存在同名文件（不是文件夹）：{0}",
                    "A file with the same name already exists at the output path (not a folder): {0}"),
    "target_exists": ("目标文件夹已存在，同名文件会被覆盖，多余文件不会被删除",
                      "The output folder already exists; same-named files will be overwritten, extra files will not be deleted"),
    "mkdir_fail": ("无法创建输出文件夹 {0}：{1}", "Cannot create the output folder {0}: {1}"),
    "moveback_fail": ("解包完成，但搬回目标文件夹失败：{0}", "Unpacking finished, but moving files back failed: {0}"),
    "moveback_ok": ("已通过临时目录中转完成解包", "Unpacking completed via a temp folder"),
    "no_outdir": ("asset_unpacker.exe 报告成功，但没有生成输出文件夹",
                  "asset_unpacker.exe reported success but created no output folder"),
    "pak_empty": ("这个 .pak 里没有任何文件", "This .pak contains no files"),
    "detail_files": ("{0} 个文件 / {1}", "{0} file(s) / {1}"),
    "unnamed": ("未命名", "unnamed"),
    "mod_meta": ("Mod 元数据：{0}（{1}）", "Mod metadata: {0} ({1})"),
    "mod_meta_json": ("包里的元数据叫 {0}，游戏只认 {1}", "The metadata inside is named {0}, but the game accepts only {1}"),
    "unpack_no_write": ("没有写入权限，无法在 {0} 创建文件夹\n请把 .pak 换个位置再试",
                        "No write permission: cannot create a folder in {0}\nPlease move the .pak elsewhere"),
    "unpack_saved": ("{0} 没有写入权限，解包结果改存到：{1}", "{0} is not writable; the unpacked result was saved to: {1}"),
    # --- 输入判定 / 报告 ---
    "path_missing": ("路径不存在（可能已被移动或删除）", "Path does not exist (it may have been moved or deleted)"),
    "unsupported": ("不支持的文件类型：只能选择「文件夹」（打包）或「.pak 文件」（解包）\n当前是：{0}",
                    "Unsupported item: only folders (pack) or .pak files (unpack) are supported\nThis one is: {0}"),
    "no_ext": ("无扩展名", "no extension"),
    "action_pack": ("打包", "Pack"),
    "action_unpack": ("解包", "Unpack"),
    "action_invalid": ("无效", "Invalid"),
    "label_note": ("      说明: ", "      note: "),
    "label_warn": ("      提示: ", "      warning: "),
    "label_fail": ("      失败: ", "      FAILED: "),
    "label_ok": ("      OK  → ", "      OK  → "),
    "summary_line": ("\n成功 {0} 项，失败 {1} 项", "\n{0} succeeded, {1} failed"),
    "log_hint": ("详细日志：{0}", "Log file: {0}"),
    "dlg_all_ok": ("已完成 {0} 项", "Done: {0} item(s)"),
    "dlg_mixed": ("完成 {0} 项，失败 {1} 项", "{0} succeeded, {1} failed"),
    "dlg_all_fail": ("失败 {0} 项", "{0} failed"),
    "dlg_fail_item": ("■ 失败：{0}", "■ FAILED: {0}"),
    "dlg_ok_item": ("■ {0}：{1}", "■ {0}: {1}"),
    "fatal": ("错误：{0}", "Error: {0}"),
    "title_cannot_run": ("无法运行", "Cannot run"),
    "title_internal": ("内部错误", "Internal error"),
    "title_usage": ("使用方法", "How to use"),
    "target_busy": ("（目标可能只读或被占用）", " (the target may be read-only or in use)"),
    "truncated": ("\n…（内容过长，完整信息见日志）", "\n... (too long — see the log for details)"),
    "internal_err": ("内部错误：{0}（详情见日志）", "Internal error: {0} (see the log)"),
    "action_process": ("处理", "Process"),
    # --- 选择窗口 ---
    "gui_hint": ("选择要处理的文件夹或 .pak 文件\n（也可以直接把文件拖到本程序图标上）",
                 "Choose a folder or a .pak file\n(you can also drag files onto this program)"),
    "gui_dir": ("① 选择文件夹 → 打包成 .pak", "1) Choose a folder  →  pack into .pak"),
    "gui_pak": ("② 选择 .pak → 解包成文件夹", "2) Choose a .pak  →  unpack into a folder"),
    "gui_quit": ("退出", "Quit"),
    "gui_dir_title": ("选择要打包的文件夹", "Choose the folder to pack"),
    "gui_pak_title": ("选择要解包的 .pak", "Choose the .pak to unpack"),
    "gui_filter_pak": ("Starbound 资源包", "Starbound package"),
    "gui_filter_all": ("所有文件", "All files"),
    # --- 右键菜单 ---
    "menu_label_pack": ("SBpakTool 打包", "SBpakTool Pack"),
    "menu_label_unpack": ("SBpakTool 解包", "SBpakTool Unpack"),
    "menu_installed": ("已添加右键菜单：\n  文件夹上 → “SBpakTool 打包”\n  文件上   → “SBpakTool 解包”\n\n只写入当前用户注册表，不需要管理员权限。\n重新打开一次右键菜单就能看到。\n（以后把整个文件夹挪了位置，随便运行一次本程序，菜单会自动指向新位置）",
                       "Right-click menu installed:\n  on folders → \"SBpakTool Pack\"\n  on files   → \"SBpakTool Unpack\"\n\nPer-user registry only, no admin rights needed.\nReopen the context menu to see it.\n(If you move this folder later, just run the program once and the menu\nwill be pointed at the new location automatically.)"),
    "menu_removed": ("已移除右键菜单，重新打开右键菜单即可生效。",
                     "Right-click menu removed. Reopen the context menu to see the change."),
    "menu_failed": ("写入注册表失败：{0}\n请用普通方式运行本程序（双击 / 在资源管理器里运行）后再试；\n如果是在受限环境或沙箱里执行的，注册表会被拒绝写入。",
                    "Failed to write the registry: {0}\nRun this program normally (double-click it or run it from Explorer) and retry;\nsandboxed or restricted environments are not allowed to write the registry."),
    "menu_windows_only": ("右键菜单功能只在 Windows 上可用。", "The right-click menu is only available on Windows."),
}


def tr(key: str, *args) -> str:
    pair = MSG.get(key)
    if pair is None:
        return key
    text = pair[0] if LANG == "zh" else pair[1]
    return text.format(*args) if args else text


class PakToolError(Exception):
    """可直接展示给用户的错误。"""


# ============================== 基础工具 ==============================
def is_ascii(path) -> bool:
    """路径是否纯 ASCII（asset_*.exe 只接受 ASCII 命令行参数）。"""
    try:
        return str(path).isascii()
    except Exception:
        return False


def non_ascii_chars(path, limit: int = 8) -> str:
    """列出路径里的非 ASCII 字符，便于用户定位要改名的位置。"""
    bad = sorted({ch for ch in str(path) if not ch.isascii()})
    if not bad:
        return ""
    shown = "".join(bad[:limit])
    return shown + ("…" if len(bad) > limit else "")


def human_size(num: float) -> str:
    num = float(num)
    for unit in ("B", "KB", "MB"):
        if num < 1024:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} GB"


# ============================== 日志 / 输出 ==============================
_log_path: Path | None = None


def setup_log(tool_dir: Path) -> None:
    global _log_path
    try:
        tool_dir.mkdir(parents=True, exist_ok=True)
        path = tool_dir / LOG_FILE_NAME
        if path.exists() and path.stat().st_size > LOG_MAX_BYTES:
            try:
                path.replace(path.with_suffix(path.suffix + ".1"))
            except OSError:
                pass
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} pak_tool v{VERSION} =====\n")
        _log_path = path
    except Exception:
        _log_path = None


def emit(text: str = "") -> None:
    """安全打印：pythonw.exe / PyInstaller --noconsole 下 stdout 可能为 None。"""
    stream = sys.stdout
    if stream is None:
        return
    try:
        stream.write(text + "\n")
        stream.flush()
    except Exception:
        pass


def log(message: str, echo: bool = False) -> None:
    if echo:
        emit(message)
    if _log_path is None:
        return
    try:
        with _log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"[{time.strftime('%H:%M:%S')}] {message}\n")
    except Exception:
        pass


# ============================== 子进程调用 ==============================
def _no_window_flags() -> int:
    """子进程不弹黑框（输出走管道，不需要控制台）。"""
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def clean_tool_output(text: str, limit: int = 900) -> str:
    """去掉 asset_*.exe 崩溃时的十六进制调用栈，只留有用信息。"""
    keep = []
    for line in (text or "").replace("\r", "").splitlines():
        line = line.strip()
        if not line:
            continue
        if re.fullmatch(r"\[?\d+\]?\s*0x[0-9a-fA-F]+.*", line):      # [03] 0x7ff6...
            continue
        if re.fullmatch(r"[0-9a-fA-F]{2}(\s+[0-9a-fA-F]{2}){3,}.*", line):  # 内存转储
            continue
        keep.append(line)
    joined = "\n".join(keep)
    if len(joined) > limit:
        joined = joined[:limit] + " …"
    return joined


KNOWN_ERRORS = (
    ("utf8Length", "err_utf8"),
    ("format unrecognized", "err_format"),
    ("EofException", "err_eof"),
    ("Could not open specified configFile", "err_config"),
    ("Too few positional arguments", "err_args"),
    ("JsonParsingException", "err_json"),
    ("JsonException", "err_jsonex"),
    ("Could not load metadata", "err_meta_load"),
    ("GetFullPathName", "err_longpath_tool"),
    ("Could not open file", "err_openfile"),
    ("Access is denied", "err_access"),
)


def is_access_denied(run: "ToolRun") -> bool:
    """asset 工具是不是因为「拒绝访问」（Win32 错误码 5）而失败的。"""
    raw = f"{run.stderr}\n{run.stdout}"
    return bool(re.search(r"could not (?:open file|create directory) '[^']*'\s*,?\s*5\b", raw, re.I))


def diagnose(rc: int, stderr: str, stdout: str) -> str:
    """把 asset_*.exe 的报错翻译成用户看得懂的一句话（必要时附上原始报错行）。"""
    raw = f"{stderr}\n{stdout}"
    low = raw.lower()
    tail = clean_tool_output(stderr) or clean_tool_output(stdout)
    first = tail.splitlines()[0].strip() if tail else ""
    # 写不进去（Win32 错误码 5 = 拒绝访问）：直接指出是权限问题，并给出解决办法
    denied = re.search(r"could not (?:open file|create directory) '([^']*)'\s*,?\s*5", raw, re.I)
    if denied:
        return tr("err_denied", denied.group(1))
    for key, msg_key in KNOWN_ERRORS:
        if key.lower() in low:
            friendly = tr(msg_key)
            if first and first not in friendly and len(first) <= 220:
                return f"{friendly}\n{tr('err_raw', first)}"
            return friendly
    return first or tr("err_exit", rc)


@dataclass
class ToolRun:
    rc: int
    stdout: str = ""
    stderr: str = ""


def run_tool(exe: Path, args: list, cwd: Path) -> ToolRun:
    """以列表方式传参（不用 shell），彻底避开 & ^ % 空格等特殊字符的转义问题。"""
    cmd = [str(exe)] + [str(a) for a in args]
    log("执行: " + subprocess.list2cmdline(cmd))
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",      # 固定 UTF-8，避免中文系统 cp936 解码崩溃
            errors="replace",
            creationflags=_no_window_flags(),
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise PakToolError(tr("timeout", exe.name, TIMEOUT_SECONDS))
    except OSError as exc:
        raise PakToolError(tr("launch_failed", exe.name, exc))
    if proc.stdout.strip():
        log("stdout: " + clean_tool_output(proc.stdout, 4000))
    if proc.stderr.strip():
        log("stderr: " + clean_tool_output(proc.stderr, 4000))
    return ToolRun(proc.returncode, proc.stdout, proc.stderr)


def ensure_ok(run: ToolRun) -> None:
    if run.rc != 0:
        raise PakToolError(diagnose(run.rc, run.stderr, run.stdout))
    if VERBOSE:
        for line in clean_tool_output(run.stdout or run.stderr, 4000).splitlines():
            emit("      | " + line)


def dir_stats(path: Path) -> tuple:
    """返回 (文件数, 总字节数)。"""
    count = 0
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for name in filenames:
            count += 1
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                pass
    return count, total


# ============================== 运行环境 ==============================
@dataclass
class Env:
    tool_dir: Path                 # 原始工具目录
    bin_dir: Path                  # 实际调用 exe 的目录（必要时是 ASCII 副本）
    work_root: Path | None         # 临时/别名根目录（保证 ASCII）
    packer: Path = None
    unpacker: Path = None
    temp_bin: bool = False         # bin_dir 是否是我们创建的临时副本


def candidate_tool_dirs() -> list:
    dirs = []
    env_dir = os.environ.get("PAK_TOOL_DIR")
    if env_dir:
        dirs.append(Path(env_dir))
    if getattr(sys, "frozen", False):                       # PyInstaller 打包后
        dirs.append(Path(sys.executable).resolve().parent)
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            dirs.append(Path(meipass))
    try:
        dirs.append(Path(__file__).resolve().parent)        # 直接跑 .py
    except NameError:
        pass
    dirs.append(Path.cwd())
    unique = []
    for d in dirs:
        if d not in unique:
            unique.append(d)
    return unique


def writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".paktool_probe_{os.getpid()}"
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except Exception:
        return False


def can_write_into(dirpath: Path) -> bool:
    """目录里能不能新建文件（只探测，不留下东西）。"""
    probe = dirpath / f".paktool_probe_{os.getpid()}"
    try:
        probe.write_bytes(b"")
    except Exception:
        return False
    try:
        probe.unlink()
    except OSError:
        pass
    return True


def work_root_candidates(tool_dir: Path) -> list:
    raw = [tool_dir,
           Path(os.environ.get("TEMP") or "") if os.environ.get("TEMP") else None,
           Path(os.environ["LOCALAPPDATA"]) / "Temp" if os.environ.get("LOCALAPPDATA") else None,
           Path(os.environ["ProgramData"]) if os.environ.get("ProgramData") else None,
           Path.home()]
    out = []
    for item in raw:
        if item and str(item) not in ("", ".") and item not in out:
            out.append(item)
    return out


def prepare_env() -> Env:
    tool_dir = None
    for d in candidate_tool_dirs():
        if (d / PACKER_NAME).is_file() and (d / UNPACKER_NAME).is_file():
            tool_dir = d
            break
    if tool_dir is None:
        raise PakToolError(tr("tool_missing", PACKER_NAME, UNPACKER_NAME))

    env = Env(tool_dir=tool_dir, bin_dir=tool_dir, work_root=None)
    if is_ascii(tool_dir):
        env.packer = tool_dir / PACKER_NAME
        env.unpacker = tool_dir / UNPACKER_NAME
    else:
        # 工具目录本身带中文 → 连 exe 路径都传不进去，先把两个 exe 复制到 ASCII 目录
        bin_root = None
        for cand in work_root_candidates(tool_dir):
            if is_ascii(cand) and writable_dir(cand):
                bin_root = cand
                break
        if bin_root is None:
            raise PakToolError(tr("tool_dir_nonascii", tool_dir))
        bin_dir = bin_root / f".paktool_bin_{os.getpid()}"
        try:
            bin_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tool_dir / PACKER_NAME, bin_dir / PACKER_NAME)
            shutil.copy2(tool_dir / UNPACKER_NAME, bin_dir / UNPACKER_NAME)
        except OSError as exc:
            raise PakToolError(tr("tool_copy_failed", exc))
        log(f"工具目录含非 ASCII 字符，已复制 exe 到：{bin_dir}")
        env.bin_dir = bin_dir
        env.temp_bin = True
        env.packer = bin_dir / PACKER_NAME
        env.unpacker = bin_dir / UNPACKER_NAME

    for cand in work_root_candidates(tool_dir):
        if is_ascii(cand) and writable_dir(cand):
            env.work_root = cand
            break
    gc_stale_workspaces(env.work_root)
    log(f"工具目录: {tool_dir} | 运行目录: {env.bin_dir} | 临时根目录: {env.work_root}")
    return env


# ============================== 中文路径：ASCII 别名 ==============================
def is_reparse_point(path: Path) -> bool:
    """是否是联接/符号链接（junction 也算）。"""
    try:
        return bool(os.lstat(path).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except Exception:
        return False


def make_junction(link: Path, target: Path) -> bool:
    """
    建立目录联接（junction，无需管理员权限、零拷贝）。

    坑点：建联接只能靠 cmd 的 mklink，而 cmd 会「二次解析」命令行：
      - subprocess 的列表写法只在参数含空格时才加引号，路径里的 & ^ ( ) 会被 cmd
        当成命令分隔符，结果 mklink 只拿到半截路径（可能建出一个指向别处的联接）；
      - %VAR% 即使加了引号也会被 cmd 展开。
    所以这里手工加引号，并且在建完之后用 realpath 复核「联接确实指向目标」，
    对不上宁可作废改用复制，绝不冒险拿错目录去打包。失败返回 False。
    """
    if os.name != "nt":
        return False
    link_s = str(link).rstrip("\\/")
    target_s = str(target).rstrip("\\/") or str(target)
    if any(ch in link_s or ch in target_s for ch in '%"'):
        return False
    try:
        proc = subprocess.run(
            f'cmd /c mklink /J "{link_s}" "{target_s}"',
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            creationflags=_no_window_flags(), timeout=60,
        )
    except Exception:
        return False
    if not link.exists():
        return False
    try:
        if os.path.realpath(link).lower() == os.path.realpath(target).lower():
            return True
        log(f"mklink 建出的联接没有指向预期目标，已弃用：{link} -> {os.path.realpath(link)}")
    except OSError as exc:
        log(f"无法校验联接目标（{exc}），已弃用：{link}")
    return False


class TempWorkspace:
    """
    为「命令行参数必须是 ASCII」的限制提供临时别名。

    - 目录：优先用 junction（零拷贝、瞬间完成），失败则整体复制一份
    - 文件：优先用硬链接（零拷贝），失败则复制
    所有临时产物都记录在案，退出时按类型精确删除（junction 只删联接本身，绝不碰真实数据）。
    """

    _serial = 0

    def __init__(self, env: Env, tag: str):
        self.env = env
        self.tag = tag
        self.enabled = env.work_root is not None
        self.dir: Path | None = None
        self.created: list = []      # (path, kind)

    def __enter__(self) -> "TempWorkspace":
        if self.enabled:
            TempWorkspace._serial += 1
            self.dir = self.env.work_root / (
                f".paktool_tmp_{os.getpid()}_{self.tag}_{TempWorkspace._serial}"
            )
            try:
                self.dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                log(f"无法创建临时目录 {self.dir}: {exc}")
                self.enabled = False
                self.dir = None
        return self

    def __exit__(self, *exc_info) -> bool:
        self.cleanup()
        return False

    def _new_path(self, name: str) -> Path:
        return self.dir / f"{len(self.created)}_{name}"

    def dir_alias(self, real: Path, allow_copy: bool = True) -> Path | None:
        """返回引用 real 目录的 ASCII 路径；无法建立时返回 None。"""
        if is_ascii(real):
            return real
        if not self.enabled:
            return None
        link = self._new_path("d")
        if make_junction(link, real):
            self.created.append((link, "junction"))
            log(f"ASCII 别名(junction): {link} -> {real}")
            return link
        # mklink 可能留下一个没建对/指向别处的联接，必须登记以便清理（并且绝不递归删除）
        if is_reparse_point(link):
            self.created.append((link, "junction"))
            log(f"登记待清理的联接残留：{link}")
        if not allow_copy:
            return None
        mirror = self._new_path("mirror")
        emit(tr("copy_dir_wait"))
        try:
            shutil.copytree(real, mirror)
        except OSError as exc:
            log(f"复制到 ASCII 临时目录失败: {exc}")
            return None
        self.created.append((mirror, "copydir"))
        log(f"ASCII 别名(复制): {mirror} <- {real}")
        return mirror

    def file_alias(self, real: Path) -> Path | None:
        """返回引用 real 文件的 ASCII 路径；无法建立时返回 None。"""
        if is_ascii(real):
            return real
        if not self.enabled:
            return None
        suffix = real.suffix if real.suffix.isascii() else ""
        link = self._new_path(f"f{suffix}")
        try:
            os.link(real, link)                     # 硬链接：同盘瞬间完成
        except OSError:
            emit(tr("copy_file_wait"))
            try:
                shutil.copy2(real, link)
            except OSError as exc:
                log(f"复制到 ASCII 临时目录失败: {exc}")
                return None
            self.created.append((link, "copyfile"))
            log(f"ASCII 别名(复制): {link} <- {real}")
        else:
            self.created.append((link, "hardlink"))
            log(f"ASCII 别名(硬链接): {link} -> {real}")
        return link

    def cleanup(self) -> None:
        if KEEP_TEMP and self.created:
            emit(tr("keep_temp", self.dir))
            return
        for path, kind in reversed(self.created):
            # 保险：只允许删除本工作区内的东西，任何情况下都不碰用户真实文件
            if self.dir is None or not str(path).startswith(str(self.dir)):
                log(f"跳过非法清理路径: {path}")
                continue
            try:
                if kind == "junction":
                    os.rmdir(path)                  # 只删除联接本身，目标数据不受影响
                elif kind == "copydir":
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    os.unlink(path)
            except OSError as exc:
                log(f"清理临时项失败 {path}: {exc}")
        self.created.clear()
        if self.dir is not None:
            try:
                os.rmdir(self.dir)
            except OSError as exc:
                # 绝不递归强删（防止误删 junction 指向的真实数据），只记下来让用户能手动处理
                log(f"临时目录未能清空，可手动删除：{self.dir}（{exc}）")
            self.dir = None


def remove_workspace(env: Env) -> None:
    """退出时清理我们创建的临时运行目录（只删自己建的那一层）。"""
    if not env.temp_bin:
        return
    try:
        shutil.rmtree(env.bin_dir, ignore_errors=True)
    except OSError:
        pass


def place_file_atomically(src: Path, dst: Path, staging_name: str) -> None:
    """
    把 src 放到 dst 的位置。
    同分区走 os.replace（原子，旧文件要么完整保留要么被完整替换）；
    跨分区先复制到 dst 同目录的临时名，再原子替换 —— 绝不直接用 shutil.move 覆盖，
    否则复制中途失败会把用户原有的 .pak 弄成半截。
    """
    try:
        os.replace(src, dst)
        return
    except OSError as exc:
        if str(src.parent) == str(dst.parent):
            raise OSError(f"{exc}{tr('target_busy')}") from exc
    staging = dst.parent / staging_name
    try:
        shutil.copy2(src, staging)
        os.replace(staging, dst)
    finally:
        try:
            if staging.exists():
                staging.unlink()
        except OSError:
            pass


def merge_tree(src: Path, dst: Path) -> None:
    """
    把 src 目录里的内容合并进 dst（同名文件覆盖、同名目录递归合并）。
    不能直接用 shutil.move —— 当 dst 里已存在同名目录时，它会变成 dst/name/name 这种嵌套。
    """
    dst.mkdir(parents=True, exist_ok=True)
    for entry in list(src.iterdir()):
        dest = dst / entry.name
        if entry.is_dir() and not entry.is_symlink():
            merge_tree(entry, dest)
        else:
            if dest.is_dir():
                if is_reparse_point(dest):
                    os.rmdir(dest)              # 万一是联接，只删联接本身，绝不递归跟进
                else:
                    shutil.rmtree(dest, ignore_errors=True)
            shutil.move(str(entry), str(dest))


def gc_stale_workspaces(work_root: Path | None) -> None:
    """清理上次异常退出（被强杀）留下的临时目录；只碰自己的 .paktool_tmp_* 命名空间。"""
    if work_root is None:
        return
    now = time.time()
    try:
        candidates = list(work_root.glob(".paktool_tmp_*"))
    except OSError:
        return
    for path in candidates:
        try:
            if not path.is_dir() or now - path.stat().st_mtime < 24 * 3600:
                continue
        except OSError:
            continue
        try:
            for entry in list(os.scandir(path)):
                item = Path(entry.path)
                if is_reparse_point(item):          # 联接：只删联接本身
                    os.rmdir(item)
                elif entry.is_dir(follow_symlinks=False):
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    os.unlink(item)
            os.rmdir(path)
            log(f"已清理上次残留的临时目录：{path}")
        except OSError:
            pass


# ============================== 打包前检查 ==============================
def read_metadata(folder: Path) -> tuple:
    """
    读取 Mod 根目录的 _metadata。
    返回 (数据, 错误说明, 是否致命)；asset_packer.exe 自己也会解析它，
    所以 JSON 语法错误必然导致打包失败，可以提前拦下。
    """
    path = folder / METADATA_FILE_NAME
    if not path.is_file():
        return None, "", False
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        return None, tr("meta_not_utf8", exc), True
    except OSError as exc:
        return None, tr("meta_read_fail", exc), True
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, tr("meta_bad_json", exc.lineno, exc.colno, exc.msg), True
    if not isinstance(data, dict):
        # 光有合法 JSON 不够：asset_packer.exe 还要能当成对象读取，否则一样打包失败
        return None, tr("meta_not_object", type(data).__name__), True
    return data, "", False


def validate_metadata(data: dict) -> list:
    """按 _metadata.txt 的字段表检查，返回提示列表（只提示、不阻止）。"""
    warns = []
    if not isinstance(data.get("name"), str) or not data.get("name", "").strip():
        warns.append(tr("meta_no_name"))
    for key, value in data.items():
        expect = METADATA_TYPES.get(key)
        if expect is None:
            continue
        if isinstance(value, bool) or not isinstance(value, expect):
            names = expect if isinstance(expect, tuple) else (expect,)
            want = " / ".join(tr(TYPE_KEYS.get(t, "type_str")) for t in names)
            warns.append(tr("meta_bad_type", key, want, type(value).__name__))
        if key in ("requires", "includes", "tags") and isinstance(value, list):
            bad = [v for v in value if not isinstance(v, str)]
            if bad:
                warns.append(tr("meta_bad_list", key, bad[:3]))
    unknown = [k for k in data if k not in METADATA_TYPES]
    if unknown:
        warns.append(tr("meta_unknown", ", ".join(unknown[:5])))
    return warns


def check_junk(root: Path) -> list:
    """找出会被一起打进 .pak 的杂物。"""
    found: dict = {}
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(root):
        for name in list(dirnames):
            if name.lower() in JUNK_DIR_NAMES:
                found[name] = found.get(name, 0) + 1
                dirnames.remove(name)          # 不深入，避免统计几万个文件
        for name in filenames:
            low = name.lower()
            if low in JUNK_FILE_NAMES:
                found[name] = found.get(name, 0) + 1
            elif Path(low).suffix in JUNK_SUFFIXES:
                found[Path(low).suffix] = found.get(Path(low).suffix, 0) + 1
        scanned += len(filenames) + len(dirnames)
        if scanned > SCAN_LIMIT:
            break
    if not found:
        return []
    sep = "、" if LANG == "zh" else ", "
    items = sep.join(f"{k} ×{v}" for k, v in sorted(found.items(), key=lambda kv: -kv[1])[:6])
    return [tr("junk_found", items)]


def preflight_pack(src: Path) -> tuple:
    """打包前检查。返回 (提示列表, 致命错误)；致命错误非空时不必再调用 asset_packer。"""
    warns = []
    try:
        entries = list(src.iterdir())
    except OSError as exc:
        return warns, f"无法读取源文件夹：{exc}"
    if not entries:
        warns.append(tr("pack_empty"))

    target = src.parent / (src.name + ".pak")
    if len(str(src)) >= 260 or len(str(target)) >= 260:
        return warns, tr("path_too_long", len(str(target)), PACKER_NAME)

    fatal = ""
    if CHECK_METADATA:
        data, err, is_fatal = read_metadata(src)
        if err:
            if is_fatal:
                fatal = tr("meta_fatal", err)
            else:
                warns.append(err)
        elif data is None:
            wrong = next((n for n in METADATA_WRONG_NAMES if (src / n).is_file()), "")
            if wrong:
                warns.append(tr("meta_wrong_name", wrong, METADATA_FILE_NAME))
            subs = [d.name for d in entries if d.is_dir() and (d / METADATA_FILE_NAME).is_file()]
            if len(subs) == 1:
                warns.append(tr("meta_wrong_level", subs[0]))
            elif len(subs) > 1:
                warns.append(tr("meta_multi_sub", ", ".join(subs[:3])))
            elif not wrong:
                warns.append(tr("meta_missing"))
        else:
            warns.extend(validate_metadata(data))

    if CHECK_JUNK:
        warns.extend(check_junk(src))

    for exe in (PACKER_NAME, UNPACKER_NAME):
        if (src / exe).exists():
            warns.append(tr("exe_inside", exe))
            break
    return warns, fatal


def preflight_unpack(pak: Path) -> str:
    """解包前的检查；返回错误说明（空串表示可以通过）。"""
    if len(str(pak)) >= 260:
        return tr("unpack_longpath", len(str(pak)))
    try:
        size = pak.stat().st_size
    except OSError as exc:
        return tr("read_fail", exc)
    if size == 0:
        return tr("zero_pak")
    try:
        with pak.open("rb") as fh:
            head = fh.read(8)
    except OSError as exc:
        return tr("read_fail", exc)
    if not head.startswith(PAK_MAGIC):
        shown = head[:8].decode("latin-1").replace("\n", "\\n")
        return tr("bad_magic", shown)
    return ""


# ============================== 处理结果 ==============================
@dataclass
class ItemResult:
    source: Path
    action: str
    ok: bool = False
    output: Path | None = None
    error: str = ""
    detail: str = ""
    warnings: list = field(default_factory=list)
    notes: list = field(default_factory=list)


# ============================== 打包 ==============================
def pack_folder(src: Path, env: Env) -> ItemResult:
    if not src.name:
        raise PakToolError(tr("drive_root"))
    target = src.parent / (src.name + ".pak")
    result = ItemResult(source=src, action=tr("action_pack"), output=target)
    warnings, fatal = preflight_pack(src)
    result.warnings = warnings
    if fatal:
        result.error = fatal
        return result

    # 放 .pak 的目录如果没有写权限（安全软件、受控文件夹访问、受限环境），
    # 不要等打完包才失败 —— 直接改存到工具目录，并明确告诉用户
    if not can_write_into(target.parent):
        fallback = env.tool_dir / target.name
        if str(fallback) != str(target) and can_write_into(fallback.parent):
            result.notes.append(tr("saved_elsewhere", target.parent, fallback))
            target = fallback
            result.output = target
        else:
            result.error = tr("no_write_dir", target.parent)
            return result

    existed = target.exists()
    if existed and target.is_dir():
        result.error = tr("target_is_dir", target)
        return result
    if existed and not os.access(target, os.W_OK):
        result.error = tr("target_readonly", target)
        return result

    try:
        with TempWorkspace(env, "pack") as ws:
            src_arg = ws.dir_alias(src)
            if src_arg is None:
                raise PakToolError(tr("alias_fail", src, non_ascii_chars(src)))
            if str(src_arg) != str(src):
                result.notes.append(tr("alias_pack"))

            # 优先把临时 .pak 打在「目标目录」里：同盘、零拷贝、最后一步是原子替换。
            # 目标目录前面已经探测过可写；写不进去的情况早在那时改存工具目录了。
            tmp_name = f".paktool_out_{os.getpid()}.pak"
            if is_ascii(target.parent):
                final_arg = target.parent / tmp_name
            else:
                out_dir = ws.dir_alias(target.parent, allow_copy=False)
                if out_dir is not None:
                    final_arg = out_dir / tmp_name          # 借联接写进目标目录，同样是同盘
                elif ws.dir is not None:
                    final_arg = ws.dir / tmp_name           # 退路：先放临时目录，最后再搬过去
                else:
                    raise PakToolError(tr("no_tmp_output", src))
            keep_output = False          # 放置失败时把成果留在旁边，不能让 finally 又删掉
            try:
                run = run_tool(env.packer, [*PACKER_EXTRA_ARGS, src_arg, final_arg], env.bin_dir)
                if run.rc != 0 and is_access_denied(run) and ws.dir is not None \
                        and final_arg.parent != ws.dir:
                    # asset_packer.exe 没权限往目标目录写（安全软件/受限环境）：
                    # 改到临时目录重打一次，最后再由本程序搬过去
                    log(f"目标目录写不进去，改用临时目录重试：{final_arg.parent}")
                    final_arg = ws.dir / tmp_name
                    run = run_tool(env.packer, [*PACKER_EXTRA_ARGS, src_arg, final_arg], env.bin_dir)
                    result.notes.append(tr("retry_temp"))
                ensure_ok(run)
                if not final_arg.is_file() or final_arg.stat().st_size == 0:
                    raise PakToolError(tr("pack_no_output"))
                try:
                    place_file_atomically(final_arg, target, tmp_name)
                except OSError as exc:
                    # 打包本身成功了，只是放不过去：换个地方放，别让用户白等一场
                    for candidate in (target.parent / (target.name + ".new"),
                                      env.tool_dir / target.name):
                        if candidate == target:
                            continue
                        try:
                            os.replace(final_arg, candidate)
                        except OSError:
                            continue
                        result.notes.append(tr("moved_elsewhere", target, exc, candidate))
                        target = candidate
                        result.output = candidate
                        existed = False
                        break
                    else:
                        keep_output = True
                        raise PakToolError(tr("place_failed", target, exc, final_arg))
            finally:
                try:
                    if not keep_output and final_arg != target and final_arg.exists():
                        final_arg.unlink()
                except OSError:
                    pass
    except PakToolError as exc:
        result.error = str(exc)
        return result

    result.ok = True
    if existed:
        result.notes.append(tr("overwrote"))
    result.detail = human_size(target.stat().st_size)
    return result


# ============================== 解包 ==============================
def unpack_pak(pak: Path, env: Env) -> ItemResult:
    target = pak.parent / pak.stem
    result = ItemResult(source=pak, action=tr("action_unpack"), output=target)
    err = preflight_unpack(pak)
    if err:
        result.error = err
        return result

    # 与打包同理：解包目标目录写不进去时，改存到工具目录并告诉用户
    if not can_write_into(pak.parent):
        fallback = env.tool_dir / pak.stem
        if str(fallback) != str(target) and can_write_into(fallback.parent):
            result.notes.append(tr("unpack_saved", pak.parent, fallback))
            target = fallback
            result.output = target
        else:
            result.error = tr("unpack_no_write", pak.parent)
            return result

    created_target = False
    try:
        if target.exists():
            if target.is_file():
                raise PakToolError(tr("out_is_file", target))
            try:
                if any(target.iterdir()):
                    result.notes.append(tr("target_exists"))
            except OSError:
                pass

        with TempWorkspace(env, "unpack") as ws:
            pak_arg = ws.file_alias(pak)
            if pak_arg is None:
                raise PakToolError(tr("alias_fail", pak, non_ascii_chars(pak)))
            if str(pak_arg) != str(pak):
                result.notes.append(tr("alias_unpack"))

            out_arg = target
            move_back = False
            if not is_ascii(target):
                if not target.exists():
                    try:
                        target.mkdir(parents=True, exist_ok=True)
                        created_target = True
                    except OSError as exc:
                        raise PakToolError(tr("mkdir_fail", target, exc))
                alias = ws.dir_alias(target, allow_copy=False)
                if alias is not None:
                    out_arg = alias
                else:
                    out_arg = ws.dir / "unpacked"       # 建不了联接 → 先解到临时目录再搬回去
                    ws.created.append((out_arg, "copydir"))    # 登记，确保临时目录一定会被清掉
                    move_back = True

            run = run_tool(env.unpacker, [*UNPACKER_EXTRA_ARGS, pak_arg, out_arg], env.bin_dir)
            if run.rc != 0 and is_access_denied(run) and ws.dir is not None and not move_back:
                # 解包器没权限往目标目录写（安全软件/受限环境）：先解到临时目录，
                # 再由本程序合并过去 —— 和打包一样的兜底，不然就成了「能打包不能解包」
                fallback_out = ws.dir / "unpacked"
                ws.created.append((fallback_out, "copydir"))
                log(f"目标目录写不进去，改用临时目录重试解包：{out_arg}")
                retry = run_tool(env.unpacker,
                                 [*UNPACKER_EXTRA_ARGS, pak_arg, fallback_out], env.bin_dir)
                run = retry                      # 不管成败都以重试结果为准
                if retry.rc == 0:
                    out_arg, move_back = fallback_out, True
                    result.notes.append(tr("retry_temp_unpack"))
            ensure_ok(run)

            if move_back:
                try:
                    out_arg.mkdir(parents=True, exist_ok=True)
                    merge_tree(out_arg, target)         # 递归合并，不能直接搬目录（会出现 x/x 嵌套）
                except OSError as exc:
                    raise PakToolError(tr("moveback_fail", exc))
                result.notes.append(tr("moveback_ok"))
    except PakToolError as exc:
        result.error = str(exc)
        if created_target and target.is_dir():
            try:
                target.rmdir()                          # 只删我们刚建的空目录
            except OSError:
                pass
        return result

    if not target.exists():
        result.error = tr("no_outdir")
        return result
    files, total = dir_stats(target)
    if files == 0:
        result.notes.append(tr("pak_empty"))
    result.detail = tr("detail_files", files, human_size(total))
    if CHECK_METADATA:
        data, merr, _fatal = read_metadata(target)
        if merr:
            result.warnings.append(merr)
        elif isinstance(data, dict):
            name = data.get("friendlyName") or data.get("name") or "?"
            result.notes.append(tr("mod_meta", name, data.get("name") or tr("unnamed")))
        elif any((target / n).is_file() for n in METADATA_WRONG_NAMES):
            wrong = next(n for n in METADATA_WRONG_NAMES if (target / n).is_file())
            result.warnings.append(tr("meta_wrong_name", wrong, METADATA_FILE_NAME))
    result.ok = True
    return result


# ============================== 主流程 ==============================
@dataclass
class Options:
    paths: list = field(default_factory=list)
    silent: bool = False
    verbose: bool = False
    keep_temp: bool = False
    help: bool = False
    lang: str = ""              # zh / en / 空 = 跟随系统
    install_menu: bool = False
    uninstall_menu: bool = False
    from_menu: bool = False     # 由右键菜单启动（会合并同一批的多个实例）


def parse_args(argv: list) -> Options:
    opts = Options()
    pending_lang = False
    for arg in argv:
        low = arg.lower()
        if pending_lang:
            opts.lang, pending_lang = low, False
            continue
        if low.startswith("--lang="):
            opts.lang = low.split("=", 1)[1]
        elif low == "--lang":
            pending_lang = True
        elif low in HELP_FLAGS:
            opts.help = True
        elif low in SILENT_FLAGS:
            opts.silent = True
        elif low in VERBOSE_FLAGS:
            opts.verbose = True
        elif low in KEEP_FLAGS:
            opts.keep_temp = True
        elif low in ("--install-menu", "--install", "/install"):
            opts.install_menu = True
        elif low in ("--uninstall-menu", "--uninstall", "/uninstall"):
            opts.uninstall_menu = True
        elif low == "--from-menu":
            opts.from_menu = True
        else:
            opts.paths.append(arg)      # 其余一律当路径，兼容各种奇怪文件名
    return opts


def normalize_path(raw: str) -> Path:
    text = (raw or "").strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1].strip()
    return Path(os.path.abspath(text)) if text else Path(text)


def usage_text() -> str:
    if LANG == "zh":
        return (
            f"SBpakTool v{VERSION} — Starbound .pak 打包 / 解包\n"
            f"\n"
            f"用法：把「文件夹」或「.pak 文件」拖到本程序上（可多选）\n"
            f"      文件夹 → 打包成同级的 <文件夹名>.pak\n"
            f"      .pak   → 解包到同级的 <文件名>\\\n"
            f"\n"
            f"右键菜单：SBpakTool 打包 / SBpakTool 解包（--install-menu 添加，--uninstall-menu 移除）\n"
            f"\n"
            f"命令行：SBpakTool [选项] <路径 ...>\n"
            f"  -h, --help          显示本帮助\n"
            f"  -s, --silent        不弹结果窗口，只写日志\n"
            f"      --lang zh|en    强制界面语言（默认跟随系统）\n"
            f"      --verbose       额外打印 asset_*.exe 的原始输出\n"
            f"      --keep-temp     保留临时目录（排查问题用）\n"
            f"      --install-menu  添加资源管理器右键菜单\n"
            f"      --uninstall-menu 移除右键菜单\n"
            f"  不带参数运行        打开选择窗口\n"
            f"\n"
            f"日志：{LOG_FILE_NAME}（与本程序同目录）\n"
            f"由人工智能 DeepSeek 编写，免费分享，随便用、随便改、随便再发。"
        )
    return (
        f"SBpakTool v{VERSION} — Starbound .pak packer / unpacker\n"
        f"\n"
        f"Usage: drag a FOLDER or a .pak FILE onto this program (multiple allowed)\n"
        f"      folder → packs into  <folder name>.pak  next to it\n"
        f"      .pak   → unpacks into <file name>\\      next to it\n"
        f"\n"
        f"Right-click menu: \"SBpakTool Pack\" / \"SBpakTool Unpack\"\n"
        f"      (add with --install-menu, remove with --uninstall-menu)\n"
        f"\n"
        f"Command line: SBpakTool [options] <paths ...>\n"
        f"  -h, --help          show this help\n"
        f"  -s, --silent        no result dialog, log only\n"
        f"      --lang zh|en    force UI language (default: follow the system)\n"
        f"      --verbose       also print the raw asset_*.exe output\n"
        f"      --keep-temp     keep temp folders (for troubleshooting)\n"
        f"      --install-menu  add the Explorer right-click menu\n"
        f"      --uninstall-menu remove the right-click menu\n"
        f"  run without arguments  opens a picker window\n"
        f"\n"
        f"Log file: {LOG_FILE_NAME} (next to this program)\n"
        f"Written by DeepSeek (AI). Free to use, modify and share."
    )


def process_one(path: Path, env: Env) -> ItemResult:
    if path.is_dir():
        return pack_folder(path, env)
    if path.is_file() and path.suffix.lower() == ".pak":
        return unpack_pak(path, env)
    if not path.exists():
        return ItemResult(path, tr("action_invalid"), error=tr("path_missing"))
    return ItemResult(
        path, tr("action_invalid"),
        error=tr("unsupported", path.suffix or tr("no_ext")),
    )


def format_report(results: list) -> str:
    lines = []
    for index, res in enumerate(results, 1):
        head = f"[{index}/{len(results)}] {res.action} {res.source}"
        if res.ok:
            lines.append(f"{head}\n{tr('label_ok')}{res.output}"
                         + (f"  ({res.detail})" if res.detail else ""))
            for note in res.notes:
                lines.append(f"{tr('label_note')}{note}")
            for warn in res.warnings:
                lines.append(f"{tr('label_warn')}{warn}")
        else:
            lines.append(f"{head}\n{tr('label_fail')}{res.error}")
            for warn in res.warnings:
                lines.append(f"{tr('label_warn')}{warn}")
    return "\n".join(lines)


def dialog_title_and_body(results: list) -> tuple:
    ok_count = sum(1 for r in results if r.ok)
    fail_count = len(results) - ok_count
    if fail_count and ok_count:
        head = tr("dlg_mixed", ok_count, fail_count)
    elif fail_count:
        head = tr("dlg_all_fail", fail_count)
    else:
        head = tr("dlg_all_ok", ok_count)
    body_lines = [head, ""]
    for res in results:
        if res.ok:
            body_lines.append(tr("dlg_ok_item", res.action, res.source.name))
            body_lines.append(f"   → {res.output}")
            if res.detail:
                body_lines.append(f"   {res.detail}")
        else:
            body_lines.append(tr("dlg_fail_item", res.source))
            body_lines.append(f"   {res.error}")
        for note in res.notes:
            body_lines.append(f"   · {note}")
        for warn in res.warnings:
            body_lines.append(f"   ⚠ {warn}")
        body_lines.append("")
    if _log_path is not None:
        body_lines.append(tr("log_hint", _log_path))
    body = "\n".join(body_lines).strip()
    if len(body) > 1800:
        body = body[:1800] + tr("truncated")
    return head, body


def win_message_box(title: str, body: str, is_error: bool) -> bool:
    """没有 tkinter 时的兜底弹窗（打包成 exe 后至少不会「什么都没发生」）。"""
    if os.name != "nt":
        return False
    try:
        import ctypes
        flags = 0x00000010 if is_error else 0x00000040      # MB_ICONERROR / MB_ICONINFORMATION
        ctypes.windll.user32.MessageBoxW(None, str(body), str(title), flags | 0x00040000)
        return True
    except Exception:
        return False


def dialogs_enabled() -> bool:
    """
    设了环境变量 PAK_TOOL_SILENT=1 就彻底不弹窗。
    给自动化/脚本调用用 —— 免得测试的时候在别人屏幕上蹦出窗口要手动关。
    """
    return not os.environ.get("PAK_TOOL_SILENT")


def show_dialog(title: str, body: str, is_error: bool) -> None:
    if not dialogs_enabled():
        return
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        try:
            root.withdraw()
            root.attributes("-topmost", True)
            if is_error:
                messagebox.showerror(title, body, parent=root)
            else:
                messagebox.showinfo(title, body, parent=root)
        finally:
            try:
                root.destroy()
            except Exception:
                pass
        return
    except Exception:
        pass
    win_message_box(title, body, is_error)


def gui_pick() -> list:
    """不带参数运行时的手动选择窗口。"""
    try:
        import tkinter as tk
        from tkinter import filedialog
        chosen: list = []
        root = tk.Tk()
    except Exception as exc:                     # 没有图形环境 / 没装 tkinter
        log(f"无法打开选择窗口：{exc!r}")
        emit(usage_text())
        if dialogs_enabled():
            win_message_box(f"{WINDOW_TITLE} v{VERSION} — {tr('title_usage')}", usage_text(), False)
        return []
    try:
        root.title(f"{WINDOW_TITLE} v{VERSION}")
        root.geometry("400x190")
        root.attributes("-topmost", True)
        try:
            ico = Path(__file__).resolve().parent / "icon.ico"
            if ico.is_file():
                root.iconbitmap(default=str(ico))
        except Exception:
            pass
        tk.Label(root, text=tr("gui_hint"), justify="center", pady=12).pack()

        def pick_dir():
            path = filedialog.askdirectory(title=tr("gui_dir_title"), parent=root)
            if path:
                chosen.append(path)
                root.destroy()

        def pick_pak():
            path = filedialog.askopenfilename(
                title=tr("gui_pak_title"), parent=root,
                filetypes=[(tr("gui_filter_pak"), "*.pak"), (tr("gui_filter_all"), "*.*")])
            if path:
                chosen.append(path)
                root.destroy()

        tk.Button(root, text=tr("gui_dir"), width=34, command=pick_dir).pack(pady=3)
        tk.Button(root, text=tr("gui_pak"), width=34, command=pick_pak).pack(pady=3)
        tk.Button(root, text=tr("gui_quit"), width=34, command=root.destroy).pack(pady=3)
        root.mainloop()
    except Exception:
        log(traceback.format_exc())
    finally:
        try:
            root.destroy()
        except Exception:
            pass
    return chosen


# ============================== 资源管理器右键菜单 ==============================
MENU_VERB = "SBpakTool"        # 注册表里用的动词名（保持 ASCII）
SPOOL_NAME = ".paktool_spool"
MENU_BATCH_SECONDS = 0.5       # 合并同一批右键启动的多个实例，等这么久
SPOOL_MAX_AGE = 15             # 只收集这么新以内的暂存文件，避免处理上一次的残留


def launcher_command() -> str:
    """右键菜单里要执行的命令行前缀（打包成 exe 就用 exe，否则用 pythonw + 脚本）。"""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}"'
    script = Path(__file__).resolve()
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")          # pythonw 不会闪黑框
    return f'"{pyw if pyw.is_file() else py}" "{script}"'


def menu_registry_entries() -> list:
    """返回 [(键, {值名: 值})]，方便安装、卸载和测试。"""
    icon = Path(__file__).resolve().parent / "icon.ico"
    command = menu_command_value()
    labels = ((r"Directory\shell", "menu_label_pack"), (r"*\shell", "menu_label_unpack"))
    entries = []
    for base, label_key in labels:
        key = rf"Software\Classes\{base}\{MENU_VERB}"
        values = {"": tr(label_key), "MultiSelectModel": "Player"}
        if icon.is_file():
            values["Icon"] = str(icon)
        entries.append((key, values))
        entries.append((key + r"\command", {"": command}))
    return entries


def menu_command_value() -> str:
    """当前这份程序应该写进菜单的命令行。"""
    return f'{launcher_command()} --from-menu "%1"'


def context_menu_needs_repair() -> bool:
    """右键菜单装了、但指向的是旧位置（工具被移动过）→ 需要修。"""
    if os.name != "nt":
        return False
    import winreg
    key = rf"Software\Classes\Directory\shell\{MENU_VERB}\command"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
            current = winreg.QueryValueEx(handle, "")[0]
    except OSError:
        return False                       # 没装菜单，不用管
    return str(current) != menu_command_value()


def repair_context_menu() -> None:
    """
    工具被移到别的目录后，注册表里记的还是旧路径，右键菜单会失效。
    这里静默重装一次，把它指回当前位置。失败就算了（不影响正常使用）。
    """
    try:
        if context_menu_needs_repair():
            if set_context_menu(False, quiet=True) == 0:
                log("检测到工具被移动过，已自动把右键菜单指向新位置")
    except Exception:
        pass


def set_context_menu(remove: bool, quiet: bool = False) -> int:
    """添加/移除右键菜单（只写 HKCU，不需要管理员权限）。"""
    if os.name != "nt":
        emit(tr("menu_windows_only"))
        return 1
    import winreg
    if remove:
        for key, _ in menu_registry_entries():
            if key.endswith(r"\command"):
                continue
            for sub in (key + r"\command", key):
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
                except OSError:
                    pass
        message, failed = tr("menu_removed"), False
    else:
        try:
            for key, values in menu_registry_entries():
                with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_WRITE) as handle:
                    for name, value in values.items():
                        winreg.SetValueEx(handle, name, 0, winreg.REG_SZ, value)
            message, failed = tr("menu_installed"), False
        except OSError as exc:
            message, failed = tr("menu_failed", exc), True
    emit(message)
    log(message.replace("\n", " "))
    if not quiet and dialogs_enabled() and SHOW_DIALOG:
        show_dialog(f"{WINDOW_TITLE} v{VERSION}", message, failed)
    return 1 if failed else 0


def collect_menu_batch(paths: list, env: Env) -> list | None:
    """
    资源管理器对多选是「每个选中项启动一次进程」，这里把同一批启动的调用合并成一次处理。
    返回要处理的路径；返回 None 表示自己不是收集者（本次不用做事，直接退出）。
    """
    spool = env.tool_dir / SPOOL_NAME
    lock = spool / "collector.lock"
    try:
        spool.mkdir(exist_ok=True)
        (spool / f"{os.getpid()}_{time.time_ns()}.txt").write_text(
            "\n".join(str(p) for p in paths), encoding="utf-8")
    except OSError:
        return paths                        # 暂存不了就自己处理，绝不吞掉用户的请求
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        try:
            if time.time() - lock.stat().st_mtime <= 30:
                return None                 # 已经有收集者在干活，交给它
            lock.unlink()                   # 收集者像是死掉了，抢过来
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except OSError:
            return paths
    except OSError:
        return paths
    try:
        time.sleep(MENU_BATCH_SECONDS)      # 等同批的其它实例把参数写完
        batch, now = [], time.time()
        for item in sorted(spool.glob("*.txt")):
            try:
                if now - item.stat().st_mtime > SPOOL_MAX_AGE:
                    item.unlink()           # 上次的残留，不要误处理
                    continue
                batch += [line for line in item.read_text(encoding="utf-8").splitlines() if line.strip()]
                item.unlink()
            except OSError:
                pass
        return batch or paths
    finally:
        try:
            lock.unlink()
        except OSError:
            pass
        try:
            spool.rmdir()
        except OSError:
            pass


def main(argv: list) -> int:
    global VERBOSE, KEEP_TEMP, LANG
    opts = parse_args(argv)
    VERBOSE = VERBOSE or opts.verbose
    KEEP_TEMP = KEEP_TEMP or opts.keep_temp
    if opts.lang.startswith("zh"):
        LANG = "zh"
    elif opts.lang.startswith("en"):
        LANG = "en"
    else:
        LANG = detect_language()          # 跟随系统（PAK_TOOL_LANG 环境变量也认）

    if opts.install_menu or opts.uninstall_menu:
        return set_context_menu(opts.uninstall_menu)

    if not opts.help:
        repair_context_menu()      # 工具被挪过目录的话，自动把右键菜单指回自己

    if opts.help:
        emit(usage_text())
        if SHOW_DIALOG and not opts.silent:
            show_dialog(f"{WINDOW_TITLE} v{VERSION} — {tr('title_usage')}", usage_text(), False)
        return 0

    paths = opts.paths
    if not paths:
        paths = gui_pick()
        if not paths:
            return 0

    env = prepare_env()
    setup_log(env.tool_dir)
    atexit.register(remove_workspace, env)

    if opts.from_menu and len(paths) == 1:
        batch = collect_menu_batch(paths, env)      # 多选时合并成一次，只弹一个结果窗
        if batch is None:
            return 0
        paths = batch

    emit(f"{WINDOW_TITLE} v{VERSION}")
    results = []
    seen = set()
    for raw in paths:
        path = normalize_path(raw)
        key = os.path.normcase(str(path))
        if key in seen:
            continue
        seen.add(key)
        try:
            results.append(process_one(path, env))
        except PakToolError as exc:
            results.append(ItemResult(path, tr("action_process"), error=str(exc)))
        except Exception as exc:                       # 兜底，绝不让窗口一闪而过
            log(traceback.format_exc())
            results.append(ItemResult(path, tr("action_process"), error=tr("internal_err", repr(exc))))

    report = format_report(results)
    emit(report)
    log("结果:\n" + report)

    ok_count = sum(1 for r in results if r.ok)
    emit(tr("summary_line", ok_count, len(results) - ok_count))
    if _log_path is not None:
        emit(tr("log_hint", _log_path))

    if SHOW_DIALOG and not opts.silent:
        title, body = dialog_title_and_body(results)
        show_dialog(f"{WINDOW_TITLE} — {title}", body, any(not r.ok for r in results))
    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except PakToolError as exc:
        emit(tr("fatal", exc))
        log(f"致命错误：{exc}")
        show_dialog(f"{WINDOW_TITLE} — {tr('title_cannot_run')}", str(exc), True)
        raise SystemExit(2)
    except BaseException:                              # noqa: BLE001
        detail = traceback.format_exc()
        emit(detail)
        log(detail)
        show_dialog(f"{WINDOW_TITLE} — {tr('title_internal')}", detail[-1500:], True)
        raise SystemExit(3)
