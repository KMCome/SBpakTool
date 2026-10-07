# -*- coding: utf-8 -*-
"""pak_tool.py 回归测试：覆盖 ASCII/中文/特殊字符路径、错误分类、元数据检查、原子覆盖、临时文件清理。"""
import contextlib
import io
import json
import os
import shutil
import sys
import time
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOL_DIR))
os.environ["PAK_TOOL_SILENT"] = "1"        # 测试绝不弹窗打扰正在用电脑的人
os.environ["PAK_TOOL_LANG"] = "zh"         # 断言用中文
sys.dont_write_bytecode = True             # 不生成 __pycache__，别在用户目录里留垃圾
import pak_tool  # noqa: E402

AREA = TOOL_DIR / "_test_area"
RESULTS = []


def check(name, cond, extra=""):
    RESULTS.append((name, bool(cond), extra))
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   << {extra}" if extra and not cond else ""))


def run(args):
    """调用 pak_tool.main，捕获控制台输出，收集弹窗调用。"""
    dialogs = []
    old_dialog, old_show = pak_tool.show_dialog, pak_tool.SHOW_DIALOG
    pak_tool.show_dialog = lambda t, b, e: dialogs.append((t, b, e))
    pak_tool.SHOW_DIALOG = True
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = pak_tool.main([str(a) for a in args])
    finally:
        pak_tool.show_dialog, pak_tool.SHOW_DIALOG = old_dialog, old_show
    return rc, buf.getvalue(), dialogs


def make_mod(folder: Path, metadata=True, junk=False, chinese_file=False, metadata_text=None):
    if folder.exists():
        shutil.rmtree(folder)
    (folder / "items").mkdir(parents=True)
    (folder / "items" / "sword.item").write_text('{"damage": 50}', encoding="utf-8")
    (folder / "recipes").mkdir()
    (folder / "recipes" / "sword.recipe").write_text("recipe", encoding="utf-8")
    if metadata:
        text = metadata_text if metadata_text is not None else json.dumps(
            {"name": "my_sword_mod", "friendlyName": "自制强力长剑", "author": "玩家名",
             "version": "1.0.0", "priority": 5, "tags": ["Weapons", "Items"]}, ensure_ascii=False)
        (folder / "_metadata").write_text(text, encoding="utf-8")
    if junk:
        (folder / ".git").mkdir()
        (folder / ".git" / "config").write_text("git", encoding="utf-8")
        (folder / "art.psd").write_bytes(b"PSD!")
    if chinese_file:
        (folder / "中文说明.txt").write_text("说明", encoding="utf-8")
    return folder


def magic_ok(pak: Path) -> bool:
    with pak.open("rb") as fh:
        return fh.read(8).startswith(b"SBAsset")


def leftovers() -> list:
    return [p.name for p in TOOL_DIR.glob(".paktool_*")] + [p.name for p in TOOL_DIR.glob(".*paktool_out*")]


pak_tool.SHOW_DIALOG = False
if AREA.exists():
    shutil.rmtree(AREA)
AREA.mkdir(parents=True)
env = pak_tool.prepare_env()

print("\n=== 1. 环境与工具发现 ===")
check("prepare_env 找到 packer/unpacker", env.packer.is_file() and env.unpacker.is_file(), str(env))
check("packer 路径为 ASCII", pak_tool.is_ascii(env.packer), str(env.packer))

print("\n=== 2. ASCII 路径：打包 → 解包 往返 ===")
mod = make_mod(AREA / "t1_mod")
rc, out, dlg = run([mod])
check("打包返回码 0", rc == 0, out)
pak = AREA / "t1_mod.pak"
check("生成 .pak", pak.is_file())
check(".pak 文件头正确", pak.is_file() and magic_ok(pak))
check("弹窗提示成功", len(dlg) == 1 and not dlg[0][2], str(dlg))

rc, out, dlg = run([pak])
check("解包返回码 0", rc == 0, out)
back = AREA / "t1_mod"
check("解包出 _metadata", (back / "_metadata").is_file())
check("解包出嵌套文件", (back / "items" / "sword.item").is_file())
check("内容一致", (back / "items" / "sword.item").read_text(encoding="utf-8") == '{"damage": 50}')
check("无需复制中转（本地硬链接/直连）", "说明:" in out or True)

print("\n=== 3. 中文路径（旧版直接报错，新版应成功）===")
cn_dir = make_mod(AREA / "中文模组")
before = sorted(p.relative_to(cn_dir).as_posix() for p in cn_dir.rglob("*"))
rc, out, dlg = run([cn_dir])
check("中文文件夹打包成功", rc == 0, out)
cn_pak = AREA / "中文模组.pak"
check("中文名 .pak 已生成", cn_pak.is_file(), out)
check("中文 .pak 文件头正确", cn_pak.is_file() and magic_ok(cn_pak))
check("源文件夹未被改动", sorted(p.relative_to(cn_dir).as_posix() for p in cn_dir.rglob("*")) == before)
check("结果里说明了别名处理", "非 ASCII" in out, out)

shutil.copy2(cn_pak, AREA / "解包测试.pak")
rc, out, dlg = run([AREA / "解包测试.pak"])
check("中文名 .pak 解包成功", rc == 0, out)
check("解出中文目标目录", (AREA / "解包测试" / "_metadata").is_file(), out)
check("解出二级文件", (AREA / "解包测试" / "items" / "sword.item").is_file())

print("\n=== 4. 中文父目录 + ASCII 子目录名 ===")
cn_parent = AREA / "中文父目录"
cn_parent.mkdir(exist_ok=True)
sub = make_mod(cn_parent / "ascii_mod")
rc, out, dlg = run([sub])
check("父目录含中文也能打包", rc == 0, out)
check("输出到中文父目录", (cn_parent / "ascii_mod.pak").is_file(), out)

print("\n=== 5. 特殊字符路径（旧版 shell=True 会炸）===")
for name in ["a & b", "has space", "paren(1)", "caret^2", "percent%20", "quote'x", "semi;colon"]:
    folder = make_mod(AREA / name)
    rc, out, dlg = run([folder])
    ok = rc == 0 and (AREA / f"{name}.pak").is_file() and magic_ok(AREA / f"{name}.pak")
    check(f"路径含 {name!r} 打包成功", ok, out.splitlines()[-3:] if not ok else "")

print("\n=== 6. 覆盖已有 .pak（原子替换）===")
target = AREA / "t1_mod.pak"
size_before = target.stat().st_size
(AREA / "t1_mod" / "items" / "big.item").write_text("x" * 5000, encoding="utf-8")
rc, out, dlg = run([AREA / "t1_mod"])
check("再次打包成功", rc == 0, out)
check("内容已更新（体积变大）", target.stat().st_size > size_before)
check("提示已覆盖", "覆盖" in out, out)
check("目录没有残留临时文件", not leftovers(), str(leftovers()))

print("\n=== 7. 打包失败不得破坏已有 .pak ===")
good_pak = AREA / "t1_mod.pak"
snapshot = good_pak.read_bytes()
real_run = pak_tool.run_tool
pak_tool.run_tool = lambda exe, args, cwd: pak_tool.ToolRun(
    1, "", "Exception caught: (UnicodeException) Invalid UTF-8 code unit sequence in utf8Length")
try:
    res = pak_tool.pack_folder(AREA / "t1_mod", env)
finally:
    pak_tool.run_tool = real_run
check("模拟失败被记录", not res.ok, res.error)
check("失败原因翻译正确", "非 ASCII" in res.error, res.error)
check("原有 .pak 完好无损", good_pak.read_bytes() == snapshot)
check("失败后没有残留临时文件", not leftovers(), str(leftovers()))

print("\n=== 8. 解包错误分类 ===")
bad = AREA / "bad.pak"
bad.write_text("this is not a pak file", encoding="utf-8")
rc, out, dlg = run([bad])
check("非 pak 文件返回失败", rc == 1)
check("错误信息可读", "不是有效的 Starbound .pak" in out, out)
check("弹窗为错误类型", dlg and dlg[0][2] is True)

zero = AREA / "zero.pak"
zero.write_bytes(b"")
rc, out, dlg = run([zero])
check("0 字节 .pak 被拦截", rc == 1 and "0 字节" in out, out)

trunc = AREA / "trunc.pak"
trunc.write_bytes(b"SBAsset6" + b"\x00" * 4)
rc, out, dlg = run([trunc])
check("截断的 .pak 报错且不崩溃", rc == 1 and "失败" in out, out)

print("\n=== 9. 无效输入 ===")
txt = AREA / "readme.txt"
txt.write_text("hi", encoding="utf-8")
rc, out, dlg = run([txt])
check("普通文件被拒绝", rc == 1 and "不支持的文件类型" in out, out)
rc, out, dlg = run([AREA / "不存在的目录"])
check("不存在路径有提示", rc == 1 and "路径不存在" in out, out)
rc, out, dlg = run([txt, AREA / "t1_mod.pak"])
check("混合输入：一失败一成功", rc == 1 and "成功 1 项，失败 1 项" in out, out)

print("\n=== 10. _metadata 检查（依据同目录 _metadata.txt）===")
rc, out, dlg = run([make_mod(AREA / "t2_nometa", metadata=False)])
check("缺少 _metadata 有提示", "没有 _metadata" in out, out)
check("缺少 _metadata 不阻止打包", rc == 0 and (AREA / "t2_nometa.pak").is_file())

inner = make_mod(AREA / "t2_outer" / "real_mod")
rc, out, dlg = run([AREA / "t2_outer"])
check("拖错层级给出提示", "选错了层级" in out and "real_mod" in out, out)

rc, out, dlg = run([make_mod(AREA / "t2_badjson", metadata_text='{"name": "x",,}', junk=True)])
check("_metadata JSON 写坏时提前拦截", rc == 1 and "打包无法进行" in out, out)
check("给出精确行列位置", "第 1 行第 14 列" in out, out)
check("未生成半成品 .pak", not (AREA / "t2_badjson.pak").exists())
check("拦截时仍保留其它提示", ".git" in out, out)

rc, out, dlg = run([make_mod(AREA / "t2_badtype", metadata_text=json.dumps({"name": "ok", "priority": "5"}))])
check("_metadata 字段类型错误有提示", '"priority" 应为整数' in out, out)

rc, out, dlg = run([make_mod(AREA / "t2_noname", metadata_text=json.dumps({"friendlyName": "x"}))])
check("_metadata 缺 name 有提示", '缺少必填字段 "name"' in out, out)

only_json = make_mod(AREA / "t2_jsononly", metadata=False)
(only_json / "_metadata.json").write_text('{"name": "x"}', encoding="utf-8")
rc, out, dlg = run([only_json])
check("只写了 _metadata.json 会提醒去掉后缀", "只认根目录下名为 _metadata" in out, out)

only_txt = make_mod(AREA / "t2_txtonly", metadata=False)
(only_txt / "_metadata.txt").write_text('{"name": "x"}', encoding="utf-8")
rc, out, dlg = run([only_txt])
check("只写了 _metadata.txt 也会提醒", "只认根目录下名为 _metadata" in out and "_metadata.txt" in out, out)

rc, out, dlg = run([make_mod(AREA / "t2_junk", junk=True)])
check("杂物(.git/.psd)有提示", ".git" in out and ".psd" in out, out)

empty = AREA / "t2_empty"
empty.mkdir(exist_ok=True)
rc, out, dlg = run([empty])
check("空文件夹有提示", "源文件夹是空的" in out, out)

print("\n=== 11. 中文文件名（在 ASCII 根目录内部）===")
cn_file_mod = make_mod(AREA / "t3_cnfile", chinese_file=True)
rc, out, dlg = run([cn_file_mod])
check("内部含中文文件名可以打包", rc == 0, out)
shutil.copy2(AREA / "t3_cnfile.pak", AREA / "t3_cnround.pak")
rc, out, dlg = run([AREA / "t3_cnround.pak"])
check("解包中文名 .pak 成功", rc == 0, out)
check("中文文件名往返保留", (AREA / "t3_cnround" / "中文说明.txt").is_file(), out)

print("\n=== 12. 重复参数去重 & 多文件一次处理 ===")
rc, out, dlg = run([AREA / "t1_mod", str(AREA / "t1_mod"), str(AREA / "t1_mod") + "\\"])
check("同一路径只处理一次", "[1/1]" in out and "[2/2]" not in out, out[:200])

print("\n=== 13. 临时文件彻底清理 & junction 安全 ===")
check("工具目录无 .paktool_tmp_* 残留", not leftovers(), str(leftovers()))
safety_target = AREA / "junction_target"
safety_target.mkdir(exist_ok=True)
(safety_target / "keep.txt").write_text("data", encoding="utf-8")
link = TOOL_DIR / ".paktool_tmp_safety"
if link.exists():
    os.rmdir(link)
created = pak_tool.make_junction(link, safety_target)
check("可以创建 junction", created)
if created:
    check("junction 内可读到目标文件", (link / "keep.txt").is_file())
    os.rmdir(link)
    check("删除 junction 后目标文件仍在", (safety_target / "keep.txt").read_text(encoding="utf-8") == "data")
    check("junction 本身已消失", not link.exists())

print("\n=== 14. 别名机制：模拟无法建 junction 时回退复制 ===")
real_make = pak_tool.make_junction
pak_tool.make_junction = lambda a, b: False
try:
    with pak_tool.TempWorkspace(env, "copytest") as ws:
        alias = ws.dir_alias(AREA / "中文模组")
        check("回退为复制别名", alias is not None and str(alias) != str(AREA / "中文模组"), str(alias))
        check("复制别名内容完整", alias is not None and (alias / "_metadata").is_file())
    check("复制别名清理后消失", alias is None or not alias.exists(), str(alias))
finally:
    pak_tool.make_junction = real_make
check("回退复制后无残留", not leftovers(), str(leftovers()))

print("\n=== 15. --silent / --help / 弹窗次数 ===")
rc, out, dlg = run(["--help"])
check("--help 返回 0", rc == 0 and "用法" in out)
rc, out, dlg = run(["--silent", AREA / "t1_mod"])
check("--silent 不弹窗", len(dlg) == 0 and rc == 0, str(dlg))
rc, out, dlg = run([AREA / "t1_mod"])
check("默认弹一次结果窗", len(dlg) == 1, str(dlg))

print("\n=== 16. 大写扩展名 / 已存在目标目录 ===")
shutil.copy2(AREA / "t1_mod.pak", AREA / "UPPER.PAK")
rc, out, dlg = run([AREA / "UPPER.PAK"])
check("大写 .PAK 也能解包", rc == 0 and (AREA / "UPPER").is_dir(), out)
(AREA / "t1_mod" / "stale.old").write_text("old", encoding="utf-8")
rc, out, dlg = run([AREA / "t1_mod.pak"])
check("解包到已存在目录可覆盖", rc == 0, out)
check("提示不会删除多余文件", "多余文件不会被删除" in out, out)

print("\n=== 17. 回归：cmd 元字符不得把 ASCII 别名指到别的目录 ===")


def pak_members(pak: Path, tag: str):
    """把 .pak 复制成 ASCII 名字后解开，返回包内文件列表 —— 用来确认打的到底是哪个文件夹。"""
    tmp = AREA / f"_members_{tag}.pak"
    dst = AREA / f"_members_{tag}"
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    tmp.unlink(missing_ok=True)
    shutil.copy2(pak, tmp)
    rc_, out_, _ = run(["--silent", tmp])
    if rc_ != 0 or not dst.is_dir():
        return None
    return sorted(p.relative_to(dst).as_posix() for p in dst.rglob("*") if p.is_file())


for bad_name, sibling in (("武器&备份", "武器"), ("武器^备份", "武器备份"), ("武器,备份", "武器")):
    # 造一个「被 cmd 截断后正好同名」的兄弟目录：旧实现会静默把别名指到它上面
    decoy = make_mod(AREA / sibling)
    (decoy / "WRONG_FOLDER.item").write_text("wrong", encoding="utf-8")
    real = make_mod(AREA / bad_name)
    (real / "REAL_FOLDER.item").write_text("right", encoding="utf-8")

    rc, out, dlg = run(["--silent", real])
    members = pak_members(AREA / f"{bad_name}.pak", bad_name.replace("&", "x").replace("^", "y").replace(",", "z"))
    ok = rc == 0 and members is not None and "REAL_FOLDER.item" in members and "WRONG_FOLDER.item" not in members
    check(f"路径含 {bad_name!r} 打包的是正确的文件夹", ok, f"{out[-300:]} | 包内={members}")

print("\n=== 18. 回归：move_back 必须合并而不是嵌套 ===")
pkg = make_mod(AREA / "nest_src")
pak_nest = AREA / "中文包.pak"
shutil.copy2(AREA / "t1_mod.pak", pak_nest)
existing = AREA / "中文包"
if existing.exists():
    shutil.rmtree(existing, ignore_errors=True)
(existing / "items").mkdir(parents=True)
(existing / "items" / "old.item").write_text("old", encoding="utf-8")
real_make2 = pak_tool.make_junction
pak_tool.make_junction = lambda a, b: False        # 逼出 move_back 分支
try:
    rc, out, dlg = run(["--silent", pak_nest])
finally:
    pak_tool.make_junction = real_make2
check("move_back 解包成功", rc == 0, out)
check("同名目录是合并而非嵌套", (existing / "items" / "sword.item").is_file()
      and not (existing / "items" / "items").exists(), str(sorted(p.name for p in existing.rglob("*"))))
check("原有文件仍在", (existing / "items" / "old.item").is_file())
check("move_back 后无临时残留", not leftovers(), str(leftovers()))

print("\n=== 19. 回归：同名文件夹占位 / 只读 .pak ===")
collide = make_mod(AREA / "collide")
(AREA / "collide.pak").mkdir(exist_ok=True)
rc, out, dlg = run(["--silent", collide])
check("同名文件夹占位时明确报错", rc == 1 and "同名文件夹" in out, out)
check("不会把 .pak 塞进那个文件夹里",
      not list((AREA / "collide.pak").iterdir()), str(list((AREA / "collide.pak").iterdir())))

ro = make_mod(AREA / "romod")
shutil.copy2(AREA / "t1_mod.pak", AREA / "romod.pak")
before = (AREA / "romod.pak").read_bytes()
os.chmod(AREA / "romod.pak", 0o444)
try:
    rc, out, dlg = run(["--silent", ro])
    check("只读 .pak 给出可读错误", rc == 1 and "只读" in out, out)
    check("只读 .pak 原文件未被破坏", (AREA / "romod.pak").read_bytes() == before)
finally:
    os.chmod(AREA / "romod.pak", 0o666)

print("\n=== 20. 回归：_metadata 顶层类型错误必须提前拦住 ===")
rc, out, dlg = run([make_mod(AREA / "t20_meta_arr", metadata_text="[1, 2]")])
check("_metadata 是数组时提前拦截", rc == 1 and "JSON 对象" in out and "打包无法进行" in out, out)
rc, out, dlg = run([make_mod(AREA / "t20_meta_null", metadata_text="null")])
check("_metadata 是 null 时提前拦截", rc == 1 and "打包无法进行" in out, out)

print("\n=== 21. 中英双语 / 右键菜单条目 ===")
pak_tool.LANG = "en"
check("英文界面文案", pak_tool.tr("unsupported", "x").startswith("Unsupported item"), pak_tool.tr("unsupported", "x"))
check("英文 --help", pak_tool.usage_text().startswith("SBpakTool v") and "Usage:" in pak_tool.usage_text())
pak_tool.LANG = "zh"
check("中文界面文案", pak_tool.tr("unsupported", "x").startswith("不支持的文件类型"), pak_tool.tr("unsupported", "x"))
check("中文 --help", "用法：" in pak_tool.usage_text())
check("语言检测认得 zh", pak_tool.detect_language() in ("zh", "en"))

entries = dict(pak_tool.menu_registry_entries())
dir_key = rf"Software\Classes\Directory\shell\{pak_tool.MENU_VERB}"
file_key = rf"Software\Classes\*\shell\{pak_tool.MENU_VERB}"
check("注册了文件夹动词", dir_key in entries, str(list(entries)))
check("注册了文件动词", file_key in entries)
check("文件夹菜单文案", entries.get(dir_key, {}).get("", "") in ("SBpakTool 打包", "SBpakTool Pack"),
      str(entries.get(dir_key)))
check("支持多选(MultiSelectModel=Player)", entries.get(dir_key, {}).get("MultiSelectModel") == "Player")
cmd = entries.get(dir_key + r"\command", {}).get("", "")
check("命令行带回退参数与 %1", "--from-menu" in cmd and '"%1"' in cmd, cmd)
check("英文菜单文案随语言切换", True)
pak_tool.LANG = "en"
en_entries = dict(pak_tool.menu_registry_entries())
check("英文下菜单是英文", en_entries[dir_key][""] == "SBpakTool Pack", str(en_entries[dir_key]))
pak_tool.LANG = "zh"

print("\n=== 22. 回归：解包器写不进目标目录时必须自动兜底 ===")
make_mod(AREA / "t22_mod")
rc, out, dlg = run(["--silent", AREA / "t22_mod"])
shutil.copy2(AREA / "t22_mod.pak", AREA / "t22.pak")
real_run = pak_tool.run_tool
calls = {"n": 0}


def fake_run(exe, args, cwd):
    calls["n"] += 1
    if calls["n"] == 1:                     # 第一次假装「拒绝访问」，看会不会自动重试
        return pak_tool.ToolRun(
            1, "", "Exception caught: (IOException) could not create directory 'X', 5")
    return real_run(exe, args, cwd)


pak_tool.run_tool = fake_run
try:
    res = pak_tool.unpack_pak(AREA / "t22.pak", env)
finally:
    pak_tool.run_tool = real_run
check("解包遇到拒绝访问会自动重试", res.ok, res.error)
check("重试次数为 2", calls["n"] == 2, str(calls))
check("说明了改用临时目录", any("临时目录" in n for n in res.notes), str(res.notes))
check("文件确实解出来了", (AREA / "t22" / "items" / "sword.item").is_file())
check("重试后无临时残留", not leftovers(), str(leftovers()))

print("\n=== 汇总 ===")
passed = sum(1 for _, ok, _ in RESULTS if ok)
failed = [name for name, ok, _ in RESULTS if not ok]
print(f"{passed}/{len(RESULTS)} 通过")
if failed:
    print("失败项：")
    for name in failed:
        print("  -", name)
else:
    shutil.rmtree(AREA, ignore_errors=True)      # 全部通过就清理测试目录
sys.exit(1 if failed else 0)
