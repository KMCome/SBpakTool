# SBpakTool 使用说明书

**Starbound Mod 打包 / 解包工具：把 `资源包文件夹` 一键打成 `.pak`，或把 `.pak` 解开**
**Drag-and-drop packer / unpacker for Starbound mods and `.pak` assets**

中文说明在前，English 在后 ｜ 版本 2.0

> 把「文件夹」拖进来 → 打包成 `<文件夹名>.pak`（可上传 Steam 创意工坊）
> 把「`.pak`」拖进来 → 解包成 `<文件名>` 文件夹
>
> Starbound mod packing, Starbound .pak unpacking, Workshop-ready output.
> 中英双语界面 · 不需要安装 Python · 支持中文路径

⬇️ **下载成品（Windows）：[Releases](https://github.com/KMCome/SBpakTool/releases)**
本仓库只放源码和文档，可执行文件在 Release 附件里，解压即用。

⬇️ **Download (Windows): [Releases](https://github.com/KMCome/SBpakTool/releases)**
This repository holds source and docs only — the executables are attached to
the Releases page. Unzip and run.

---

## ⚠️ 关于这个工具 & 免责声明

本工具由人工智能 **DeepSeek** 编写。

它免费分享给所有需要的人：随便用、随便改、随便再发。
源代码就摆在 `pak_tool.py` 里，没有任何保留，也不需要署名。

写它的理由很朴素 —— Starbound 的打包解包本来不该这么折腾。
如果你被它省下了时间，把它转给下一个同样折腾的人就好。

几句实在话：

- AI 不是神，代码难免有疏漏，也没人替你试过每一种情况。
- 使用前请自行备份重要数据（尤其是 Mod 文件夹和 `.pak` 文件）。
- 因使用本工具造成的任何损失，DeepSeek 与委托发布的人都不承担责任，
  也不提供任何担保。
- 这不是推卸，而是希望你在知情的前提下，用得放心。

不接受以上条款，请不要使用本工具。

> **About & Disclaimer (English)** — This tool was written by **DeepSeek**,
> an AI. It is shared freely: use it, modify it, pass it on, no attribution
> required. AI is not infallible and nobody has tested every case — back up
> important data before use. Any loss caused by using this tool is not the
> responsibility of DeepSeek or of the person who published it, and no
> warranty is given. That is not an excuse; it is so you know exactly where
> you stand. If you do not accept these terms, please do not use this tool.

---

## 目录

**中文**

1. [这是什么](#1-这是什么)
2. [文件清单（每个文件的来源与作用）](#2-文件清单每个文件的来源与作用)
3. [30 秒上手](#3-30-秒上手)
4. [右键菜单](#4-右键菜单)
5. [界面语言](#5-界面语言)
6. [发给别人用](#6-发给别人用)
7. [特点一览](#7-特点一览)
8. [常见问题](#8-常见问题)
9. [命令行参数](#9-命令行参数)
10. [支持这个项目](#10-支持这个项目)

**English**

1. [What it is](#1-what-it-is)
2. [Files](#2-files-origin-and-purpose-of-each)
3. [Quick start](#3-quick-start)
4. [Right-click menu](#4-right-click-menu)
5. [Language](#5-language)
6. [Sharing it](#6-sharing-it-with-other-people)
7. [Features](#7-features)
8. [FAQ](#8-faq)
9. [Command line](#9-command-line)
10. [Support this project](#10-support-this-project)

---

# 中文

## 1. 这是什么

SBpakTool 是一个「拖拽即用」的小工具，帮你完成 Starbound 资源包
（`.pak`）的打包与解包：

- 拖一个**文件夹**进来 → 在旁边生成 `<文件夹名>.pak`
- 拖一个 **`.pak` 文件**进来 → 在旁边生成 `<文件名>` 文件夹

它自己不实现打包算法，而是调用同目录下的两个命令行工具
（`asset_packer.exe` / `asset_unpacker.exe`，见下一节）来完成实际工作，
并为它们补上：图形界面、结果提示、中文路径支持、错误翻译、
防误删保护、打包前检查。

适合：做 Starbound Mod、需要把 Mod 文件夹打成 `.pak` 上传工坊，
或者需要把别人发的 `.pak` 解开来看的人。

## 2. 文件清单（每个文件的来源与作用）

每个文件都写清楚：谁做的、干什么用的、发给别人时要不要带上。
（标 ★ 的是分发时必须要的）

> **文档（本仓库里有的）和程序（在 Release 里的）是分开的**：
> 仓库里只有源码、说明书、授权这些文本文件（几百 KB）；
> 三个 `.exe` 都在 [Releases](https://github.com/KMCome/SBpakTool/releases)
> 的附件 zip 里 —— 想直接用工具的话，去那里下载解压即可。

- **`pak_tool.py`** —— 主程序源码
  - 来源：本项目 ｜ 分发：不需要
  - 可读可改，需要装 Python 才能直接运行
- **`pak_tool.exe`** —— 主程序
  - 来源：本项目，由 `pak_tool.py` 打包生成 ｜ 分发：★ 需要
  - 拖拽用的就是它，**对方不需要装 Python**
- **`asset_packer.exe`** —— 官方打包工具
  - 来源：**OpenStarbound 项目**（不是本工具作者写的）｜ 分发：★ 需要
  - 真正干打包这件事的就是它，不能删
- **`asset_unpacker.exe`** —— 官方解包工具
  - 来源：**OpenStarbound 项目**（不是本工具作者写的）｜ 分发：★ 需要
  - 真正干解包这件事的就是它，不能删
- **`README.md`** —— 本说明书
  - 来源：本项目 ｜ 分发：需要
- **`METADATA_FIELDS.txt`** —— `_metadata` 字段速查表
  - 来源：本项目整理 ｜ 分发：可选（写 Mod 的人用得上）
  - 程序会照着它检查你写的 `_metadata`
- **`LICENSE`** —— MIT 开源授权
  - 来源：本项目 ｜ 分发：不需要（只在仓库里有用）
- **`.gitignore` / `.github/FUNDING.yml`** —— 发布到 GitHub 用
  - 来源：本项目 ｜ 分发：不需要
- **`icon.ico`** —— 程序图标
  - 来源：本项目 ｜ 分发：不需要（只有打包 exe 时用到）
- **`build_exe.py` / `build_exe.bat`** —— 一键生成 exe 和发布文件夹
  - 来源：本项目 ｜ 分发：不需要（给你自己用的）
- **`tests\`** —— 自测脚本
  - 来源：本项目 ｜ 分发：不需要（改过代码后跑一遍就知道有没有弄坏）
- **`donate_wechat.jpg`** —— 微信收款码
  - 来源：本项目 ｜ 分发：不需要（想收赞助就放进仓库）
- **`pak_tool.log`** —— 运行日志
  - 来源：程序自动生成 ｜ 分发：不需要（出问题时可以拿它排查）

**关于 `asset_packer.exe` 和 `asset_unpacker.exe`**

这两个程序**不是本工具作者写的**，它们来自
[OpenStarbound](https://github.com/OpenStarbound/OpenStarbound) 项目
—— 一个开源的 Starbound 游戏引擎重制项目。

它们是 OpenStarbound 官方提供的命令行工具，版权归该项目的作者所有，
本工具只是**原样调用**它们，没有做任何修改。

为什么要调用它们而不是自己写：打包/解包 `.pak` 的格式细节由它们保证，
本工具只负责把「难用的命令行」变成「拖一下就完事」，并在它们出错时
把英文报错翻译成人话。

如果游戏版本更新导致 `.pak` 格式变化，可以从上面那个项目获取新版
`asset_packer.exe` / `asset_unpacker.exe`，直接替换同目录的旧文件即可，
本工具不需要改动。

## 3. 30 秒上手

0. 先去 [Releases](https://github.com/KMCome/SBpakTool/releases) 下载最新
   的 zip，解压出来（仓库里没有 exe）
1. 确认 `pak_tool.exe`、`asset_packer.exe`、`asset_unpacker.exe`
   在**同一个文件夹**里
2. 把要处理的文件夹（或 `.pak` 文件）**拖到 `pak_tool.exe` 图标上**
   （可以一次拖多个）
3. 等一两秒，会弹出一个结果窗口
   - 成功 → 告诉你文件生成在哪、多大
   - 失败 → 用中文说明原因和解决办法

**打包 Mod 的一个关键点**：`_metadata` 必须放在**你要打包的那个
文件夹的根目录**。

```text
正确：  mymod\_metadata          <- 拖 mymod 这个文件夹
错误：  mymod\mymod2\_metadata   <- 拖错了外层，程序会提醒你
错误：  mymod\_metadata.json     <- 名字多了 .json，游戏不认
```

放错了程序会直接告诉你，不用自己猜。

## 4. 右键菜单

装好之后：

- 右键一个**文件夹**（可多选）→「SBpakTool 打包」
- 右键一个**文件**（可多选）→「SBpakTool 解包」

**安装**

```bat
pak_tool.exe --install-menu
:: 还没生成 exe 就用：python pak_tool.py --install-menu
```

**卸载**

```bat
pak_tool.exe --uninstall-menu
```

说明：

- 只写入**当前用户**的注册表，不需要管理员权限，卸载干净
- 装完如果没看到菜单，重新打开一次右键菜单（必要时重启资源管理器）
- 一次选中多个文件夹/文件也行：程序会把同一批合并，
  只弹**一个**结果窗口

**把文件夹挪到别的位置之后怎么办？**

注册表里记的是绝对路径，所以菜单会指向旧位置而失效。但现在不用你操心：
移动后随便运行一次程序（拖一个文件夹，或双击一下），程序会自动发现并把
菜单改指到新位置。也可以手动在新位置重新执行一次 `--install-menu`。

另外，如果你重新生成了 exe，建议重装一次菜单指向最新 exe。

## 5. 界面语言

默认**跟随系统**：中文系统显示中文，其它系统显示英文。

想强制指定：

```bat
pak_tool.exe --lang en        命令行
set PAK_TOOL_LANG=en          环境变量（当前窗口有效）
```

右键菜单的文字也跟着语言走：用哪种语言执行一次 `--install-menu`，
菜单就显示哪种语言。

> `pak_tool.log` 内部诊断记录固定用中文（方便排查），但结果窗口、
> 报错、帮助全都会跟着语言切换。

## 6. 发给别人用

**给别人请给 `pak_tool.exe`，不要给 `pak_tool.py`。**

| 你给的 | 对方需要 Python 吗 |
| --- | --- |
| `pak_tool.exe` | 不需要，双击/拖拽就能用 |
| `pak_tool.py` | 需要，得自己装 Python |

只有**你生成 exe** 这一步需要 Python，用的人完全不需要。

**最小可分发套装**（4 个文件放同一个文件夹里）：

```text
pak_tool.exe
asset_packer.exe
asset_unpacker.exe
README.md
```

可选再带上 `METADATA_FIELDS.txt`（对方要自己写 Mod 时用得上）。
压缩成 zip 发出去即可。

**最省事的做法**：双击 `build_exe.py`，它会直接生成一个
`SBpakTool-release` 文件夹 —— 程序、两个官方工具、说明书全都在里面，
而且会自动校验完整性（缺 `_internal` 这种"拿到手打不开"的残包会被当场拦下）。

你直接把这个文件夹压缩发人就行。构建过程不产生多余的中间副本。

> ⚠️ **自己构建的前提**：本目录里必须有 `asset_packer.exe` 和 `asset_unpacker.exe`。
> **本仓库只放源码，没有上传这两个 exe** —— 它们属于 OpenStarbound 项目。
> 请先从本项目的 [Releases](https://github.com/KMCome/SBpakTool/releases) 下载 zip
> 取出这两个文件（或从
> [OpenStarbound](https://github.com/OpenStarbound/OpenStarbound) 获取），
> 放到 `build_exe.py` 旁边再构建。
> 缺了它们 `build_exe.py` 会**直接报错并告诉你去哪拿**，不会生成一个用不了的发布包。

> **为什么只有文件夹版、没有单文件版？**
> 单文件版每次运行都要把自己解压到系统临时目录，有两个硬伤：
> 系统临时目录不可写时会直接报 `Could not create temporary directory!`；
> 而且"自解压"正是杀毒软件最敏感的特征，误报多得多。文件夹版没有这两个问题。
> **注意：别人拿到后要把整个文件夹一起用**，别把 `pak_tool.exe` 单独拖出去
> （旁边的 `_internal` 是运行库，缺了打不开）。

## 7. 特点一览

1. **拖拽即用** —— 不用记命令、不用开命令行，成功失败都有明确提示
2. **中英双语界面** —— 自动跟随系统语言，可手动切换
3. **资源管理器右键菜单** —— 文件夹上直接「打包」，文件上直接「解包」，支持多选
4. **中文/非英文路径照样能用** ★
   两个官方工具在处理**命令行参数**时只认纯 ASCII，路径里有中文就会崩。
   本工具会自动在临时目录里给该路径建一个纯英文「替身」
   （目录联接，零拷贝、瞬间完成；不支持时退化为复制），用完立刻删除，
   **绝不改动你的任何文件**。
   注意：文件夹**内部**的文件名可以是中文，这个没问题。
5. **覆盖也安全** ★
   打包先写临时文件，成功后才替换目标 `.pak`。中途失败绝不会把你原来的
   `.pak` 弄成半截；实在放不到目标位置时，新打好的包也会保留下来并
   告诉你路径。
6. **打包前体检** —— 自动检查 `_metadata` 是否存在/是合法 JSON/字段类型
   对不对、是不是拖错了层级、有没有 `.git`/`*.psd` 之类会被打进包里的
   杂物、路径是否超过 Windows 260 字符限制。只提示，不擅自删你的文件。
7. **报错翻译成人话** —— 官方工具崩溃时吐的是英文异常 + 内存地址堆栈，
   本工具会翻译成「哪里错了 + 怎么办」。
8. **不留垃圾** —— 所有临时文件用完即删；联接只删联接本身，
   不会误删真实数据。
9. **写不进去也能出结果** —— 如果目标文件夹不允许创建文件
   （杀毒软件、Windows「受控文件夹访问」、受限环境等），程序会自动
   改存到自己的文件夹，并明确告诉你存哪了。

## 8. 常见问题

**Q1：对方没装 Python 能用吗？**
给 `pak_tool.exe` 就能用，对方什么都不用装。给 `.py` 就必须装 Python。
发人之前先双击 `build_exe.py`。

**Q2：中文路径能用吗？**
能，见「特点 4」。文件夹内部的中文文件名也完全没问题。

**Q3：提示「没有写入权限 / 拒绝访问」？**
目标文件夹不允许创建文件。常见原因：杀毒软件、Windows 的
「受控文件夹访问」保护了桌面/文档，或你在受限环境里运行。
程序会自动改存到自己的文件夹，并在结果里写明路径。

**Q4：提示「打包无法进行：`_metadata` 不是合法 JSON」？**
`_metadata` 写错了。官方打包器自己会解析它，写坏了必然失败，
所以程序提前拦下，并告诉你第几行第几列出错。

**Q5：提示「你可能选错了层级」？**
你拖的是外层文件夹，`_metadata` 在里面的子文件夹里。直接拖子文件夹。

**Q6：提示「源目录里有 `.git` ×1 / `*.psd` ×3」？**
这些杂物会被一起打进 `.pak`，上传 Steam 工坊前建议清理。
程序只提示，不会自动删你的文件。

**Q7：打包失败会不会把原来的 `.pak` 弄坏？**
不会，见「特点 5」。

**Q8：提示路径太长？**
Windows 有 260 字符限制。把 Mod 文件夹移到浅一点的目录
（比如 `D:\mods\`）就行。

**Q9：两个 `asset_*.exe` 能删吗？**
不能。它们是真正干活的官方工具，程序靠它们完成打包/解包。

**Q10：`pak_tool.log` 是什么？**
运行日志，出问题时可以拿它排查，平时随手删掉也没关系，
下次运行会重新生成。

**Q11：杀毒软件报毒 / Windows 提示「已保护你的电脑」？**
这是 PyInstaller 打包程序的通病（会把自己解压到临时目录再运行，而且没有
数字签名），**不是真的有病毒**。三种处理办法：

- Windows 弹窗时点「更多信息」→「仍要运行」
- 右键 `pak_tool.exe` → 属性 → 勾选「解除锁定」→ 确定（从网上下载的文件会带这个标记）
- 在杀毒软件里把这个文件夹加进信任区

如果反复被拦，用下面两步处理（**不是真的有病毒**）：

- 右键 `pak_tool.exe` → 属性 → 勾选「解除锁定」→ 确定
- 杀毒软件里把这个文件夹加进信任区

另外说明：本程序是**文件夹版**（不自解压，不需要系统临时目录），
**不需要管理员权限**（内嵌 manifest 是 `asInvoker`），
也不会向系统目录写任何东西，只会读写你自己选的那些文件夹。

## 9. 命令行参数

```text
SBpakTool [选项] <文件夹或 .pak ...>

  -h, --help           显示帮助
  -s, --silent         不弹结果窗口，只写日志
      --lang zh|en     强制界面语言
      --verbose        额外打印官方工具的原始输出
      --keep-temp      保留临时目录（排查问题用）
      --install-menu   添加资源管理器右键菜单
      --uninstall-menu 移除右键菜单
      不带参数运行      打开选择窗口
```

环境变量：

| 变量 | 作用 |
| --- | --- |
| `PAK_TOOL_SILENT=1` | 彻底不弹窗（自动化用） |
| `PAK_TOOL_LANG=zh\|en` | 强制语言 |
| `PAK_TOOL_DIR=<目录>` | 指定 `asset_*.exe` 所在目录 |

## 10. 支持这个项目

这个小工具是免费给的：不收费、不锁功能、不需要署名，源代码全在
`pak_tool.py` 里，随便用、随便改、随便再发。

如果你觉得它替你省了时间，想请作者喝杯咖啡：

- **爱发电**（微信 / 支付宝）
  https://afdian.com/a/KMCome
- **微信扫码**（扫码直接转账）

<p align="center">
  <img src="donate_wechat.jpg" alt="微信收款码" width="240">
</p>

当然，不赞助完全不影响使用 ——
把它分享给下一个需要的人，就是最好的支持。

---

# English

## 1. What it is

SBpakTool is a small drag-and-drop helper for Starbound asset packages
(`.pak` files):

- Drag a **folder** in → creates `<folder name>.pak` next to it
- Drag a **`.pak` file** in → creates a `<file name>` folder next to it

It does not implement the pack format itself. It drives the two official
command-line programs shipped next to it (`asset_packer.exe` /
`asset_unpacker.exe`, see the next section) and adds a GUI, clear results,
non-ASCII path support, translated error messages, overwrite protection and
pre-flight checks on top of them.

Who it is for: Starbound modders who need to turn a mod folder into a
`.pak` for the Workshop, or anyone who wants to unpack a `.pak`.

## 2. Files (origin and purpose of each)

For every file: who made it, what it does, and whether you need to include
it when you share this tool. (★ = required when sharing)

> **Docs live in this repository; the program lives in Releases.** The repo
> only holds text files (a few hundred KB). All three `.exe` files are in the
> zip attached to [Releases](https://github.com/KMCome/SBpakTool/releases) —
> download and unzip if you just want to use the tool.

- **`pak_tool.py`** — main program source
  - Origin: this project | Share: no
  - Readable and editable; needs Python installed to run directly
- **`pak_tool.exe`** — the main program
  - Origin: this project, built from `pak_tool.py` | Share: ★ yes
  - This is what you drag files onto; the other person needs **no Python**
- **`asset_packer.exe`** — official packing tool
  - Origin: the **OpenStarbound project** (NOT written by this tool's author)
    | Share: ★ yes
  - It does the actual packing work — do not delete it
- **`asset_unpacker.exe`** — official unpacking tool
  - Origin: the **OpenStarbound project** (NOT written by this tool's author)
    | Share: ★ yes
  - It does the actual unpacking work — do not delete it
- **`README.md`** — this manual
  - Origin: this project | Share: yes
- **`METADATA_FIELDS.txt`** — `_metadata` field reference
  - Origin: this project | Share: optional (useful if they write mods)
  - The program checks your `_metadata` against it
- **`LICENSE`** — MIT licence
  - Origin: this project | Share: no (only meaningful in the repository)
- **`.gitignore` / `.github/FUNDING.yml`** — for publishing on GitHub
  - Origin: this project | Share: no
- **`icon.ico`** — program icon
  - Origin: this project | Share: no (only used when building the exe)
- **`build_exe.py` / `build_exe.bat`** — builds the exe and the release folder
  - Origin: this project | Share: no (this one is for you)
- **`tests\`** — self-test scripts
  - Origin: this project | Share: no (run them after editing the code)
- **`donate_wechat.jpg`** — WeChat payment QR code
  - Origin: this project | Share: no (include it if you want donations)
- **`pak_tool.log`** — run log
  - Origin: created automatically | Share: no (useful when reporting a bug)

**About `asset_packer.exe` and `asset_unpacker.exe`**

These two programs were **not** written by the author of this tool. They
come from the [OpenStarbound](https://github.com/OpenStarbound/OpenStarbound)
project — an open-source reimplementation of the Starbound engine.

They are the official command-line tools provided by that project. All
rights belong to the OpenStarbound authors. SBpakTool only **calls** them
as-is; it does not modify them in any way.

Why call them instead of reimplementing the format: they guarantee the
`.pak` format details. SBpakTool's job is to turn their awkward command
line into "drag and drop", and to translate their English crash output
into something readable.

If a game update ever changes the `.pak` format, get new copies of
`asset_packer.exe` / `asset_unpacker.exe` from the project above and simply
replace the old files next to this tool — no change needed here.

## 3. Quick start

0. Grab the latest zip from
   [Releases](https://github.com/KMCome/SBpakTool/releases) and unzip it
   (the executables are not in this repository)
1. Make sure `pak_tool.exe`, `asset_packer.exe` and `asset_unpacker.exe`
   are in the **same folder**
2. **Drag** the folder (or `.pak` file) you want to process **onto
   `pak_tool.exe`**. Multiple items are allowed.
3. Wait a second or two. A result window appears:
   - success → shows where the output is and how big it is
   - failure → explains the cause and what to do

**Key point when packing a mod**: `_metadata` must sit in the **root of the
folder you pack**.

```text
correct:  mymod\_metadata           <- drag the "mymod" folder
wrong:    mymod\mymod2\_metadata    <- wrong level, the tool warns you
wrong:    mymod\_metadata.json      <- extra .json, the game ignores it
```

The tool detects these and tells you — no guessing required.

## 4. Right-click menu

Once installed:

- right-click a **folder** (multi-select OK) → "SBpakTool Pack"
- right-click a **file** (multi-select OK) → "SBpakTool Unpack"

**Install**

```bat
pak_tool.exe --install-menu
:: if you have not built the exe yet:
:: python pak_tool.py --install-menu
```

**Remove**

```bat
pak_tool.exe --uninstall-menu
```

Notes:

- written to the **current user** registry only — no administrator rights,
  and it uninstalls cleanly
- if the menu does not show up, reopen the context menu once (restart
  Explorer if necessary)
- multi-selection is supported: Explorer starts one process per selected
  item, and the tool merges that batch into a single run with **one**
  result window

**What if I move the folder later?**

The registry stores an absolute path, so the menu would point at the old
location. You do not need to worry about it: just run the program once from
the new location (drag something, or double-click it) and it repairs the
menu automatically. You can also re-run `--install-menu` in the new
location. If you rebuild the exe, re-run `--install-menu` so the menu
points at the newest exe.

## 5. Language

Follows your system by default: Chinese systems get Chinese, everything
else gets English.

To force it:

```bat
pak_tool.exe --lang en        command line
set PAK_TOOL_LANG=en          environment variable (current window)
```

The context-menu labels follow the same setting: run `--install-menu` once
in the language you want the menu to use.

> `pak_tool.log` keeps its internal diagnostics in Chinese (for
> troubleshooting), but the result window, all error messages and the help
> text follow the selected language.

## 6. Sharing it with other people

**Give them `pak_tool.exe`, NOT `pak_tool.py`.**

| What you give | Do they need Python? |
| --- | --- |
| `pak_tool.exe` | No — just run it |
| `pak_tool.py` | Yes — they must install Python |

Only the **build** step needs Python on your machine.

**Minimum shareable set** (these files in one folder):

```text
pak_tool.exe
asset_packer.exe
asset_unpacker.exe
README.md
```

Optionally add `METADATA_FIELDS.txt` (useful if they write mods themselves).
Zip that folder and send it.

**Easiest way**: double-click `build_exe.py`. It produces a ready-to-ship
`SBpakTool-release` folder directly — the program, both official tools and the
docs — and verifies it (so you can never hand out a package that is missing
its `_internal` runtime and refuses to start).

Zip that folder and send it. No leftover intermediate copy is created.

> ⚠️ **Before you build**: `asset_packer.exe` and `asset_unpacker.exe` must be
> present in this folder. **They are not uploaded to this repository** (it holds
> source only) — they belong to the OpenStarbound project.
> Grab the zip from
> [Releases](https://github.com/KMCome/SBpakTool/releases) and take those two
> files out of it (or get them from
> [OpenStarbound](https://github.com/OpenStarbound/OpenStarbound)), put them
> next to `build_exe.py`, then build.
> Without them `build_exe.py` **stops with an error telling you where to get
> them** instead of producing a package that cannot run.

> **Why only a folder build, no single-file build?**
> A single-file build unpacks itself into the system temp folder on every run:
> it fails with `Could not create temporary directory!` when that folder is
> not writable, and self-extraction is exactly what antivirus heuristics flag.
> The folder build has neither problem.
> **Tell your users to keep the whole folder together** — do not move
> `pak_tool.exe` out on its own (the `_internal` folder next to it is required).

## 7. Features

1. **Drag and drop** — no commands to remember, clear feedback every time
2. **Bilingual UI** (Chinese / English), auto-detected, switchable by hand
3. **Explorer right-click menu** — "Pack" on folders, "Unpack" on files,
   multi-selection supported
4. **Non-ASCII paths work** ★
   The two official tools only accept pure-ASCII **command-line arguments**
   and crash on anything else. SBpakTool creates a temporary all-ASCII
   "stand-in" (a directory junction — zero copy, instant; it falls back to a
   real copy if junctions are unavailable), uses it for the call and removes
   it immediately. Your files are never modified.
   Note: file names *inside* the folder may contain any characters.
5. **Safe overwriting** ★
   Packing writes to a temporary file first and only replaces the target
   `.pak` once it succeeded. A failed run can never leave you with a
   half-written `.pak`; and if the result cannot be placed at the target,
   the finished build is kept somewhere safe and its path is reported.
6. **Pre-flight checks** — before packing it verifies that `_metadata`
   exists / is valid JSON / has correctly typed fields, whether you picked
   the wrong folder level, whether junk like `.git` or `*.psd` would be
   packed in, and whether the path exceeds the Windows 260-character limit.
   It only warns — it never deletes your files.
7. **Readable errors** — the official tools dump English exceptions plus
   memory-address stack traces; SBpakTool turns that into "what went wrong
   + what to do".
8. **No leftovers** — every temporary artefact is removed afterwards;
   junctions are removed as links only, never recursing into your real data.
9. **Automatic fallback when a folder is not writable** — if the target
   folder refuses new files (antivirus, Windows Controlled Folder Access,
   restricted environments), the result is saved into the tool's own folder
   instead and the exact path is reported.

## 8. FAQ

**Q1 Does the other person need Python?**
With `pak_tool.exe`: no, nothing at all. With `.py`: yes. Run
`build_exe.py` before sharing.

**Q2 Do non-English paths work?**
Yes — see feature 4. File names inside the folder are fine too.

**Q3 "No write permission" / access denied**
The target folder refuses new files: antivirus, Windows Controlled Folder
Access protecting Desktop/Documents, or a restricted environment. The tool
saves the result into its own folder and tells you the path.

**Q4 "Cannot pack: `_metadata` is not valid JSON"**
`_metadata` is malformed. The official packer parses it itself and would
fail anyway, so the tool blocks early and reports the exact line/column.

**Q5 "You probably picked the wrong level"**
You dragged a parent folder while `_metadata` lives in a subfolder. Drag
that subfolder instead.

**Q6 "The source folder contains `.git` x1 / `*.psd` x3"**
Those files would be packed into the `.pak`. Consider cleaning up before
uploading to the Workshop. The tool only warns; it never deletes.

**Q7 Can a failed pack damage my existing `.pak`?**
No — see feature 5.

**Q8 "Path too long"**
Windows' 260-character limit. Move the mod to a shallower folder
(e.g. `D:\mods\`).

**Q9 Can I delete the two `asset_*.exe` files?**
No. They do the actual work; the tool only drives them.

**Q10 What is `pak_tool.log`?**
The run log. Useful when reporting a problem; safe to delete — it is
recreated on the next run.

**Q11 Antivirus flags it / "Windows protected your PC"**
That is a well-known PyInstaller trait (it unpacks itself into a temp folder
and has no code signature), **not an actual infection**. Three ways around it:

- On the Windows prompt click "More info", then "Run anyway"
- Right-click `pak_tool.exe` → Properties → tick **Unblock** → OK (files
  downloaded from the internet carry that mark)
- Add the folder to your antivirus' trusted list

If it keeps getting blocked, two steps are enough (**it is not an infection**):

- Right-click `pak_tool.exe` → Properties → tick **Unblock** → OK
- Add the folder to your antivirus' trusted list

For the record: this is the **folder build** (no self-extraction, no system
temp folder needed) and it needs **no administrator rights** (its embedded
manifest is `asInvoker`); it writes nothing outside the folders you pick.

## 9. Command line

```text
SBpakTool [options] <folders or .pak files ...>

  -h, --help           show help
  -s, --silent         no result dialog, log only
      --lang zh|en     force the UI language
      --verbose        also print the raw output of the official tools
      --keep-temp      keep temp folders (troubleshooting)
      --install-menu   add the Explorer right-click menu
      --uninstall-menu remove it
      no arguments     open a picker window
```

Environment variables:

| Variable | Purpose |
| --- | --- |
| `PAK_TOOL_SILENT=1` | never show dialogs (automation) |
| `PAK_TOOL_LANG=zh\|en` | force the language |
| `PAK_TOOL_DIR=<folder>` | where the `asset_*.exe` files live |

## 10. Support this project

This little tool is free: no paywall, no locked features, no attribution
required. The source is all in `pak_tool.py` — use it, modify it, pass it on.

If it saved you some time and you feel like buying the author a coffee:

- **Afdian** (WeChat / Alipay)
  https://afdian.com/a/KMCome
- **WeChat QR code** (scan to transfer)

<p align="center">
  <img src="donate_wechat.jpg" alt="WeChat QR code" width="240">
</p>

No donation is ever required — and if you are outside China, the easiest way
to support this project is simply to pass it on. Thank you.

---

## 致谢 / Credits

- **SBpakTool**（`pak_tool.py` / `pak_tool.exe` / 本文档）由人工智能
  **DeepSeek** 编写，以 [MIT](LICENSE) 授权免费分享。
  Written by **DeepSeek** (an AI), released under the [MIT](LICENSE) licence.
- **`asset_packer.exe` / `asset_unpacker.exe`** 来自
  [OpenStarbound](https://github.com/OpenStarbound/OpenStarbound) 项目，
  版权归其作者，本工具只原样调用，未做修改。
  From the OpenStarbound project, called as-is and unmodified.
