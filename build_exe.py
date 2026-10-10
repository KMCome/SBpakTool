# -*- coding: utf-8 -*-
"""
把 pak_tool.py 打包成带图标的 EXE（双击本文件即可运行）。

只打【文件夹版】：
    pak_tool\\  ── pak_tool.exe + _internal\\ 运行库
    SBpakTool-release\\  ── 可直接压缩发人的完整套装

为什么不用单文件版：
  ・单文件版每次运行都要把自己解压到 %TEMP%，系统临时目录不可写时会直接
    报 "Could not create temporary directory!"；
  ・自解压这个行为本身就是杀毒软件最敏感的特征，误报明显更多；
  ・启动还更慢。

用 Python 而不是 .bat 来做这件事，是为了避开 cmd 对中文/UTF-8 的编码坑。
"""

import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STALE_ONEFILE = HERE / "pak_tool.exe"      # 旧版单文件产物，构建时清掉
LEGACY_DIST = HERE / "pak_tool"            # 旧版会在根目录留这个中间文件夹，构建时清掉
DIST_DIR = HERE / "build" / "dist" / "pak_tool"   # PyInstaller 的输出（最后会改名成发布文件夹）
RELEASE_DIR = HERE / "SBpakTool-release"


def pause() -> None:
    try:
        input("\n按回车键关闭窗口 ...")
    except Exception:
        pass


def main() -> int:
    print("=" * 50)
    print("  把 pak_tool.py 打包成 pak_tool.exe（文件夹版，带图标）")
    print("=" * 50)
    print(f"  目录：{HERE}")
    print(f"  Python：{sys.version.split()[0]}")

    if not (HERE / "pak_tool.py").is_file():
        print("[错误] 同目录下找不到 pak_tool.py")
        pause()
        return 1

    # 发布包里必须带着这两个官方工具，否则别人拿到手根本没法用。
    # GitHub 仓库只放源码、没放它们，所以这里要拦住，不能默不做声地生成残包。
    missing_tools = [n for n in ("asset_packer.exe", "asset_unpacker.exe")
                     if not (HERE / n).is_file()]
    if missing_tools:
        print("\n[错误] 缺少官方工具，无法生成完整的发布包：")
        for name in missing_tools:
            print(f"         {name}")
        print("\n       它们是 OpenStarbound 项目的命令行工具，打包时会被复制进发布文件夹。")
        print("       本项目的 GitHub 仓库【只放源码，没有上传这两个 exe】。")
        print("       请用下面任一方式拿到它们，放到本文件旁边，然后重新运行：")
        print("         1) 从本项目的 Releases 页面下载 zip，解压后把这两个 exe 复制过来")
        print("         2) 或从 OpenStarbound 项目获取：")
        print("            https://github.com/OpenStarbound/OpenStarbound")
        print("\n       （少任何一个都不会出发布包，避免你发给别人一个用不了的文件夹）")
        pause()
        return 1

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("\n[提示] 没有安装 PyInstaller，正在自动安装 ...")
        code = subprocess.call([sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"])
        if code != 0:
            print("[错误] 自动安装失败，请手动执行：python -m pip install pyinstaller")
            pause()
            return 1

    if STALE_ONEFILE.exists():                   # 清掉以前留下的单文件版，免得混淆
        try:
            STALE_ONEFILE.unlink()
            print("  已删除旧版单文件 pak_tool.exe（现在只出文件夹版）")
        except OSError:
            print("[警告] 旧的单文件 pak_tool.exe 被占用，删不掉，请手动删除")

    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--onedir",
           "--name", "pak_tool"]
    icon = HERE / "icon.ico"
    if icon.is_file():
        cmd += ["--icon", str(icon)]
        print("  图标：icon.ico")
    version_file = write_version_file()          # 写入版本信息，能明显减少杀软误报
    if version_file:
        cmd += ["--version-file", str(version_file)]
        print("  版本信息：已写入（ProductName / FileVersion / Copyright）")
    cmd += ["--distpath", str(HERE / "build" / "dist"),
            "--workpath", str(HERE / "build" / "tmp"),
            "--specpath", str(HERE / "build"),
            str(HERE / "pak_tool.py")]

    print("\n[1/2] 正在打包，通常几秒到一分钟，请稍候 ...\n")
    started = time.time()
    code = subprocess.call(cmd, cwd=str(HERE))
    ok = code == 0 and (DIST_DIR / "pak_tool.exe").is_file()
    if not ok:
        print("\n[错误] 打包失败。build 目录已保留，可查看 build\\tmp\\pak_tool\\warn-pak_tool.txt")
        pause()
        return 1

    # 直接把构建产物搬成 SBpakTool-release（同盘是秒级改名，不再留中间副本），
    # 然后才清理 build 目录。
    release = make_release_folder()
    if release is None:
        print("\n[错误] 发布文件夹生成失败，build 目录已保留以便排查")
        pause()
        return 1
    shutil.rmtree(HERE / "build", ignore_errors=True)

    print(f"\n[2/2] 完成，用时 {time.time() - started:.0f} 秒")
    print(f"\n[发布] 要发给别人的东西已经在这儿了：\n      {release}")
    print("      把这个文件夹整个压缩（建议 zip）发给别人即可 —— 对方【不需要安装 Python】。")
    print(f"      程序本体：{release}\\pak_tool.exe（旁边的 _internal 是运行库，要一起保留）")

    print("\n      提示：以后改了 pak_tool.py，重新运行一次本文件即可重新打包。")
    print("\n      【关于杀毒软件报毒 / Windows 提示「已保护你的电脑」】")
    print("        · 已用文件夹版（不自解压）+ 写入版本信息，误报已经压到最低")
    print("        · 若仍被拦，用下面两步处理，不是真的有病毒：")
    print("            1) 右键 pak_tool.exe → 属性 → 勾选「解除锁定」")
    print("            2) 杀毒软件里把这个文件夹加进信任区")
    print("        · 程序不需要管理员权限（内嵌 manifest 是 asInvoker），也不会写系统目录")
    pause()
    return 0


def write_version_file():
    """
    生成 PyInstaller 的版本资源文件。
    没有版本信息的 exe 是杀毒软件眼里的高危特征，写进去能少挨不少误报。
    """
    content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(2, 0, 0, 0),
    prodvers=(2, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('080404B0', [
        StringStruct('CompanyName', 'SBpakTool'),
        StringStruct('FileDescription', 'SBpakTool - Starbound .pak packer / unpacker'),
        StringStruct('FileVersion', '2.0.0.0'),
        StringStruct('InternalName', 'pak_tool'),
        StringStruct('LegalCopyright', 'MIT License. Written by DeepSeek (AI).'),
        StringStruct('OriginalFilename', 'pak_tool.exe'),
        StringStruct('ProductName', 'SBpakTool'),
        StringStruct('ProductVersion', '2.0.0.0'),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
"""
    try:
        path = HERE / "build" / "version_info.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path
    except OSError:
        return None


def make_release_folder():
    """
    把构建产物变成「别人拿去就能用」的发布文件夹。
    关键是【改名】而不是复制：同盘改名是秒级的，也不会留下 pak_tool\\ 中间副本。
    """
    src = DIST_DIR
    if not (src / "pak_tool.exe").is_file():
        return None
    out = RELEASE_DIR
    try:
        if out.exists():
            shutil.rmtree(out, ignore_errors=True)
        if LEGACY_DIST.exists():                    # 旧版留在根目录的中间产物，顺手清掉
            shutil.rmtree(LEGACY_DIST, ignore_errors=True)

        try:
            shutil.move(str(src), str(out))         # 同盘 → 秒级改名
        except OSError:
            shutil.copytree(src, out)               # 跨盘等罕见情况才真复制
            shutil.rmtree(src, ignore_errors=True)

        for name in ("asset_packer.exe", "asset_unpacker.exe"):
            if (HERE / name).is_file():
                shutil.copy2(HERE / name, out / name)
        for name in ("README.md", "README.txt"):
            if (HERE / name).is_file():
                shutil.copy2(HERE / name, out / name)
                break
        # 给不习惯看 .md 的人留一份纯文本快速上手（带 BOM，记事本不乱码）
        (out / "先看这个.txt").write_text(
            "SBpakTool —— 快速上手\n"
            "====================================\n"
            "\n"
            "1. 这个文件夹里的东西要【整体保留】，别把 pak_tool.exe 单独拿走\n"
            "   （旁边的 _internal 是运行库，缺了打不开）\n"
            "   直接拖到别处用的话，请整个文件夹一起移动或复制。\n"
            "\n"
            "2. 把要打包的【文件夹】拖到 pak_tool.exe 图标上\n"
            "      → 在旁边生成同名的 .pak\n"
            "   把【.pak 文件】拖到 pak_tool.exe 图标上\n"
            "      → 在旁边生成同名的文件夹\n"
            "   可以一次拖多个。\n"
            "\n"
            "3. 想在右键菜单里用：\n"
            "      pak_tool.exe --install-menu\n"
            "   （不需要管理员权限，卸载用 --uninstall-menu）\n"
            "\n"
            "打包 Mod 时注意：_metadata 必须放在你要打包的那个文件夹的\n"
            "根目录，而且不能带 .json 后缀。放错了程序会提醒你。\n"
            "\n"
            "完整说明书：README.md\n"
            "（用记事本打开也行，只是会看到一些 # 和 | 排版符号）\n"
            "\n"
            "------------------------------------\n"
            "杀毒软件报毒 / Windows 提示「已保护你的电脑」怎么办：\n"
            "  1) 右键 pak_tool.exe → 属性 → 勾选「解除锁定」→ 确定\n"
            "  2) 杀毒软件里把这个文件夹加进信任区\n"
            "本程序不需要管理员权限，只读写你自己选的那些文件夹。\n"
            "\n"
            "本工具由人工智能 DeepSeek 编写，免费分享，随便用随便改随便发。\n"
            "使用前请自行备份重要数据；因使用本工具造成的任何损失，\n"
            "作者与 AI 均不承担责任。\n"
            "\n"
            "asset_packer.exe / asset_unpacker.exe 来自 OpenStarbound 项目，\n"
            "版权归其作者，本工具只原样调用、未做修改。\n",
            encoding="utf-8-sig")
        for extra in ("METADATA_FIELDS.txt",):        # 写 Mod 的人会用到的字段速查表
            if (HERE / extra).is_file():
                shutil.copy2(HERE / extra, out / extra)

        # 校验：文件夹版必须带上 _internal，否则别人拿到手根本打不开。
        # （曾经出现过复制静默失败、发布包里少一整个 _internal 的情况）
        missing = [n for n in ("pak_tool.exe", "_internal") if not (out / n).exists()]
        count = sum(1 for _ in out.rglob("*"))
        if missing:
            print(f"      [错误] 发布文件夹不完整，缺少：{', '.join(missing)}")
            print("            通常是有文件被占用或被杀软扫描锁住，关掉相关程序后重跑一次本文件")
            return None
        print(f"      发布文件夹已校验：{count} 个文件，含 _internal 运行库")
        return out
    except OSError as exc:
        print(f"      （发布文件夹创建失败：{exc}，可手动复制 pak_tool\\ 文件夹里的全部内容）")
        return None


if __name__ == "__main__":
    raise SystemExit(main())
