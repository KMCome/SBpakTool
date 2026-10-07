# -*- coding: utf-8 -*-
"""
把 pak_tool.py 打包成带图标的 pak_tool.exe（双击本文件即可运行）。

默认打成单文件（onefile）；如果单文件被杀毒软件拦截，可以用：
    python build_exe.py onedir
改成打包成文件夹形式（启动更快、更不容易被杀软误杀）。

用 Python 而不是 .bat 来做这件事，是为了避开 cmd 对中文/UTF-8 的编码坑。
"""

import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "pak_tool.exe"
ONEDIR = any(a.lower() in ("onedir", "--onedir", "/onedir", "dir") for a in sys.argv[1:])


def pause() -> None:
    try:
        input("\n按回车键关闭窗口 ...")
    except Exception:
        pass


def main() -> int:
    print("=" * 50)
    print("  把 pak_tool.py 打包成 pak_tool.exe（带图标）")
    print("=" * 50)
    print(f"  目录：{HERE}")
    print(f"  Python：{sys.version.split()[0]}")
    print(f"  模式：{'文件夹(onedir)' if ONEDIR else '单文件(onefile)'}")

    if not (HERE / "pak_tool.py").is_file():
        print("[错误] 同目录下找不到 pak_tool.py")
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

    if not ONEDIR and TARGET.exists():
        try:
            TARGET.unlink()
        except OSError:
            print("[错误] 旧的 pak_tool.exe 正在运行或被占用，请先关掉它再试")
            pause()
            return 1

    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--name", "pak_tool"]
    cmd += ["--onedir"] if ONEDIR else ["--onefile"]
    icon = HERE / "icon.ico"
    if icon.is_file():
        cmd += ["--icon", str(icon)]
        print("  图标：icon.ico")
    cmd += ["--distpath", str(HERE),
            "--workpath", str(HERE / "build" / "tmp"),
            "--specpath", str(HERE / "build"),
            str(HERE / "pak_tool.py")]

    print("\n[1/2] 正在打包，通常几秒到一分钟，请稍候 ...\n")
    started = time.time()
    code = subprocess.call(cmd, cwd=str(HERE))
    ok = code == 0 and ((HERE / "pak_tool" / "pak_tool.exe").is_file() if ONEDIR else TARGET.is_file())
    if not ok:
        print("\n[错误] 打包失败。build 目录已保留，可查看 build\\tmp\\pak_tool\\warn-pak_tool.txt")
        pause()
        return 1

    shutil.rmtree(HERE / "build", ignore_errors=True)
    print(f"\n[2/2] 完成，用时 {time.time() - started:.0f} 秒")
    if ONEDIR:
        print(f"      程序在：{HERE / 'pak_tool'}\\pak_tool.exe")
        print("      请把 asset_packer.exe / asset_unpacker.exe 也复制进那个 pak_tool 文件夹。")
    else:
        size = TARGET.stat().st_size / 1048576
        print(f"      程序：{TARGET.name}（{size:.1f} MB）")
        print("      请让它和 asset_packer.exe / asset_unpacker.exe 待在同一个文件夹里。")
    print("      然后把「文件夹」或「.pak 文件」拖到 pak_tool.exe 图标上就能用了。")

    release = make_release_folder()
    if release:
        print(f"\n[发布] 已经帮你要发给别人的东西打包好了：\n      {release}")
        print("      把这个文件夹整个压缩发给别人即可 —— 对方【不需要安装 Python】。")

    print("\n      提示：以后改了 pak_tool.py，重新运行一次本文件即可重新打包。")
    pause()
    return 0


def make_release_folder():
    """把「别人拿去就能用」的文件收集到一个文件夹里（对方不需要装 Python）。"""
    src = HERE / "pak_tool" if ONEDIR else HERE
    exe = src / "pak_tool.exe"
    if not exe.is_file():
        return None
    out = HERE / "SBpakTool-release"
    try:
        if out.exists():
            shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        if ONEDIR:                                  # 文件夹版：整个目录都带上
            for item in src.iterdir():
                target = out / item.name
                shutil.copytree(item, target) if item.is_dir() else shutil.copy2(item, target)
        else:
            shutil.copy2(exe, out / "pak_tool.exe")
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
            "1. 把 pak_tool.exe、asset_packer.exe、asset_unpacker.exe\n"
            "   放在同一个文件夹里（就是这个文件夹）\n"
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
        return out
    except OSError as exc:
        print(f"      （发布文件夹创建失败：{exc}，可手动复制两个 exe 和 pak_tool.exe）")
        return None


if __name__ == "__main__":
    raise SystemExit(main())
