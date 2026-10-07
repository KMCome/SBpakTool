# -*- coding: utf-8 -*-
"""模拟测试：PyInstaller 冻结环境、无控制台（pythonw/--noconsole）环境。"""
import os
import shutil
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOL))
os.environ["PAK_TOOL_SILENT"] = "1"        # 测试绝不弹窗打扰正在用电脑的人
os.environ["PAK_TOOL_LANG"] = "zh"
sys.dont_write_bytecode = True             # 不生成 __pycache__
import pak_tool  # noqa: E402

AREA = TOOL / "_sim_area"
RESULTS = []


def check(name, cond, extra=""):
    RESULTS.append((name, bool(cond)))
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   << {extra}" if extra and not cond else ""))


if AREA.exists():
    shutil.rmtree(AREA)
(AREA / "mod").mkdir(parents=True)
(AREA / "mod" / "_metadata").write_text('{"name":"sim"}', encoding="utf-8")
(AREA / "mod" / "a.item").write_text("{}", encoding="utf-8")

print("=== 1. 冻结环境下的工具发现 ===")
fake_exe_dir = AREA / "fake_dist"
fake_exe_dir.mkdir(exist_ok=True)
saved = (getattr(sys, "frozen", None), sys.executable, getattr(sys, "_MEIPASS", None))
sys.frozen = True
sys.executable = str(fake_exe_dir / "pak_tool.exe")
sys._MEIPASS = str(AREA / "fake_meipass")
try:
    dirs = pak_tool.candidate_tool_dirs()
    check("冻结时优先使用 exe 所在目录", str(dirs[0]) == str(fake_exe_dir), str(dirs[:3]))
    check("冻结时也考虑 _MEIPASS", str(AREA / "fake_meipass") in [str(d) for d in dirs], str(dirs))
finally:
    if saved[0] is None:
        del sys.frozen
    else:
        sys.frozen = saved[0]
    sys.executable = saved[1]
    if saved[2] is None:
        del sys._MEIPASS
    else:
        sys._MEIPASS = saved[2]

print("\n=== 2. 无控制台（sys.stdout = None）也能正常工作 ===")
real_stdout = sys.stdout
sys.stdout = None
try:
    rc = pak_tool.main(["--silent", str(AREA / "mod")])
    crashed = False
    err = ""
except BaseException as exc:            # noqa: BLE001
    rc, crashed, err = None, True, repr(exc)
finally:
    sys.stdout = real_stdout
check("无 stdout 不崩溃", not crashed, err)
check("无 stdout 仍返回 0", rc == 0, str(rc))
check("无 stdout 仍产出 .pak", (AREA / "mod.pak").is_file())

print("\n=== 3. 无 stdout 时弹窗逻辑被 silent 抑制 ===")
calls = []
real_show = pak_tool.show_dialog
pak_tool.show_dialog = lambda t, b, e: calls.append((t, e))
sys.stdout = None
try:
    pak_tool.main(["--silent", str(AREA / "mod")])
finally:
    sys.stdout = real_stdout
    pak_tool.show_dialog = real_show
check("--silent 下无弹窗调用", calls == [], str(calls))

print("\n=== 4. 别名清理后的安全性 ===")
check("工具目录无残留", not list(TOOL.glob(".paktool_*")), str(list(TOOL.glob(".paktool_*"))))
check("源文件仍在", (AREA / "mod" / "_metadata").is_file())

passed = sum(1 for _, ok in RESULTS if ok)
failed = [n for n, ok in RESULTS if not ok]
print(f"\n{passed}/{len(RESULTS)} 通过")
for n in failed:
    print("  -", n)
if not failed:
    shutil.rmtree(AREA, ignore_errors=True)
sys.exit(1 if failed else 0)
