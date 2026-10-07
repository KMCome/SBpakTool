# -*- coding: utf-8 -*-
"""端到端测试：真正以子进程方式启动 pak_tool.py（模拟资源管理器拖拽），检查退出码与产物。"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent
SCRIPT = TOOL / "pak_tool.py"
AREA = TOOL / "_e2e_area"
RESULTS = []
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"     # 子进程也别生成 __pycache__


def check(name, cond, extra=""):
    RESULTS.append((name, bool(cond)))
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   << {extra}" if extra and not cond else ""))


def run_cli(args, cwd=None):
    # PAK_TOOL_SILENT=1：彻底禁止弹窗，测试绝不能打扰正在用电脑的人
    env = dict(os.environ, PAK_TOOL_SILENT="1", PAK_TOOL_LANG="zh")
    proc = subprocess.run([sys.executable, str(SCRIPT), *[str(a) for a in args]],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          cwd=str(cwd or TOOL), env=env)
    return proc.returncode, proc.stdout, proc.stderr


def make_mod(folder: Path):
    (folder / "items").mkdir(parents=True, exist_ok=True)
    (folder / "items" / "a.item").write_text("{}", encoding="utf-8")
    (folder / "_metadata").write_text('{"name":"e2e","friendlyName":"E2E"}', encoding="utf-8")
    return folder


if AREA.exists():
    shutil.rmtree(AREA)
AREA.mkdir(parents=True)

print("=== E2E：以子进程方式调用（--silent，避免弹窗阻塞）===")
cn = make_mod(AREA / "中文模组")
rc, out, err = run_cli(["--silent", cn])
check("中文文件夹打包 exit=0", rc == 0, f"rc={rc}\n{out}\n{err}")
check("生成中文名 .pak", (AREA / "中文模组.pak").is_file())

rc, out, err = run_cli(["--silent", AREA / "中文模组.pak"])
check("中文 .pak 解包 exit=0", rc == 0, f"rc={rc}\n{out}\n{err}")
check("解包产物存在", (AREA / "中文模组" / "items" / "a.item").is_file())

rc, out, err = run_cli(["--silent", AREA / "中文模组", AREA / "中文模组"])
check("重复参数去重后成功", rc == 0 and "[1/1]" in out and "[2/2]" not in out, out)

# 相对路径 + 从别的目录启动
rel = os.path.relpath(AREA / "中文模组", TOOL)
rc, out, err = run_cli(["--silent", rel], cwd=TOOL)
check("相对路径可用", rc == 0, out)

rc, out, err = run_cli(["--silent", AREA / "中文模组"], cwd="C:\\")
check("从其它工作目录启动可用", rc == 0, out)

rc, out, err = run_cli(["--verbose", "--silent", AREA / "中文模组"])
check("--verbose 打印 asset 工具输出", rc == 0 and "Output packed assets" in out, out)

print("\n=== E2E：错误路径 ===")
bad = AREA / "bad.pak"
bad.write_text("nope", encoding="utf-8")
rc, out, err = run_cli(["--silent", bad])
check("坏 .pak exit=1", rc == 1 and "不是有效的 Starbound .pak" in out, out)
rc, out, err = run_cli(["--silent", AREA / "missing_dir"])
check("不存在路径 exit=1", rc == 1 and "路径不存在" in out, out)
rc, out, err = run_cli(["--help"])
check("--help exit=0", rc == 0 and "用法" in out, out)

print("\n=== E2E：PAK_TOOL_SILENT=1 时即使不加 --silent 也不弹窗 ===")
rc, out, err = run_cli([AREA / "中文模组"])          # 故意不加 --silent
check("环境变量能抑制弹窗（否则这里会一直卡住等人关窗）", rc == 0, f"rc={rc}\n{out}\n{err}")

print("\n=== E2E：中英双语 ===")
rc, out, err = run_cli(["--silent", "--lang", "en", AREA / "中文模组"])
check("--lang en 输出英文", rc == 0 and "Pack" in out and "succeeded" in out, out)
rc, out, err = run_cli(["--silent", "--lang", "zh", AREA / "中文模组"])
check("--lang zh 输出中文", rc == 0 and "打包" in out and "成功" in out, out)
env_en = dict(os.environ, PAK_TOOL_SILENT="1", PAK_TOOL_LANG="en")
proc = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True,
                      encoding="utf-8", errors="replace", cwd=str(TOOL), env=env_en)
check("PAK_TOOL_LANG=en 的 --help 是英文", "Usage:" in proc.stdout and "用法" not in proc.stdout,
      proc.stdout[:200])

print("\n=== E2E：工具自身放在中文路径下 ===")
cn_tool_dir = AREA / "中文工具目录"
cn_tool_dir.mkdir(parents=True, exist_ok=True)
for name in ("asset_packer.exe", "asset_unpacker.exe", "pak_tool.py"):
    shutil.copy2(TOOL / name, cn_tool_dir / name)
cn_mod = cn_tool_dir / "测试模组"
cn_mod.mkdir(exist_ok=True)
(cn_mod / "_metadata").write_text('{"name":"cn_tool"}', encoding="utf-8")
(cn_mod / "a.item").write_text("{}", encoding="utf-8")
env2 = dict(os.environ, PAK_TOOL_SILENT="1", PAK_TOOL_LANG="zh")
proc = subprocess.run([sys.executable, str(cn_tool_dir / "pak_tool.py"), "--silent", str(cn_mod)],
                      capture_output=True, text=True, encoding="utf-8", errors="replace",
                      cwd=str(cn_tool_dir), env=env2)
check("工具在中文目录下也能打包", proc.returncode == 0 and (cn_tool_dir / "测试模组.pak").is_file(),
      f"rc={proc.returncode}\n{proc.stdout[-400:]}\n{proc.stderr[-300:]}")
if (cn_tool_dir / "测试模组.pak").is_file():
    proc = subprocess.run([sys.executable, str(cn_tool_dir / "pak_tool.py"), "--silent",
                           str(cn_tool_dir / "测试模组.pak")],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          cwd=str(cn_tool_dir), env=env2)
    check("工具在中文目录下也能解包",
          proc.returncode == 0 and (cn_tool_dir / "测试模组" / "a.item").is_file(),
          f"rc={proc.returncode}\n{proc.stdout[-300:]}")
    check("中文工具目录下无临时残留",
          not list(cn_tool_dir.glob(".paktool_*")) and not list(cn_tool_dir.glob(".paktool_bin_*")),
          str([p.name for p in cn_tool_dir.iterdir()]))

print("\n=== E2E：无残留 / 日志 ===")
leftovers = [p.name for p in TOOL.glob(".paktool_*")]
check("工作目录无临时残留", not leftovers, str(leftovers))
check("源文件夹未被改动", (cn / "_metadata").is_file() and (cn / "items" / "a.item").is_file())
log_file = TOOL / "pak_tool.log"
check("生成了日志文件", log_file.is_file())
if log_file.is_file():
    text = log_file.read_text(encoding="utf-8", errors="replace")
    check("日志记录了执行命令", "asset_packer.exe" in text)
    check("日志记录了 junction 别名", "junction" in text or "ASCII" in text)

print("\n=== E2E：tkinter 可用性（只建窗口不 mainloop）===")
try:
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    root.destroy()
    check("tkinter 可创建窗口", True)
except Exception as exc:
    check("tkinter 可创建窗口", False, repr(exc))

passed = sum(1 for _, ok in RESULTS if ok)
failed = [n for n, ok in RESULTS if not ok]
print(f"\n{passed}/{len(RESULTS)} 通过")
for name in failed:
    print("  -", name)
if not failed:
    shutil.rmtree(AREA, ignore_errors=True)
sys.exit(1 if failed else 0)
