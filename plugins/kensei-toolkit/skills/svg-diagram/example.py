#!/usr/bin/env python3
"""Reference diagram built with diagram_kit: the "How it works" picture of KenseiUnityMCP, in two
languages. Copy it, with diagram_kit.py, next to the README as docs/diagrams/<name>.py and rewrite
the TEXT and layout.

Run: python3 example.py [out_dir] [--strict] [--png]
  --strict  exit code 1 if any language has layout warnings (all languages are built and reported first)
  --png     also render each SVG to a PNG next to it, to look at
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # diagram_kit.py is copied next to this script
from diagram_kit import Diagram, finish, render_png  # noqa: E402

TEXT = {
    "en": {
        "title": "How KenseiUnityMCP works",
        "subtitle": "Claude drives a live Unity Editor — and keeps the connection through every domain reload",
        "claude": ("Claude Code", "MCP client"),
        "bridge": ("Bridge", "kensei-unity-mcp", "Node · outside Unity"),
        "unity": ("Unity Editor", "com.kensei.unitymcp", "tools run on the main thread"),
        "edge1": ("stdio", "MCP"),
        "edge2": ("TCP 127.0.0.1", "NDJSON + token"),
        "file": ("~/.kensei-unity-mcp/instances/<id>.json", "project path · pid · port · token"),
        "reads": "finds the Editor",
        "writes": "announces itself",
        "reload": "domain reload → reconnect, the call carries over",
        "badges": [
            ("🔁", "One call, one result", "recompile & play mode answer after reload"),
            ("🎯", "Right Editor, always", "picked by session directory, worktrees too"),
            ("🛠", "30 tools", "logs · tests · screenshots · C# · scenes"),
        ],
    },
    "ru": {
        "title": "Как устроен KenseiUnityMCP",
        "subtitle": "Claude управляет живым Unity Editor и не теряет связь при перезагрузке домена",
        "claude": ("Claude Code", "MCP-клиент"),
        "bridge": ("Мост", "kensei-unity-mcp", "Node · вне Unity"),
        "unity": ("Unity Editor", "com.kensei.unitymcp", "работа на главном потоке"),
        "edge1": ("stdio", "MCP"),
        "edge2": ("TCP 127.0.0.1", "NDJSON + токен"),
        "file": ("~/.kensei-unity-mcp/instances/<id>.json", "путь проекта · pid · порт · токен"),
        "reads": "находит Editor",
        "writes": "сообщает о себе",
        "reload": "перезагрузка домена → переподключение, вызов не теряется",
        "badges": [
            ("🔁", "Один вызов — один ответ", "ответ приходит после перезагрузки"),
            ("🎯", "Всегда нужный Editor", "выбор по папке сессии, ворктри тоже"),
            ("🛠", "30 инструментов", "логи · тесты · скриншоты · C# · сцены"),
        ],
    },
}


def build(t):
    d = Diagram(960, 462)
    d.background(t["title"], t["subtitle"], glows=[(125, 215, "orange", 70), (480, 215, "violet"), (835, 215, "teal")])

    y, h = 150, 130  # main row: actor → middle → target
    d.card(45, y, 160, h, "orange", "🤖", t["claude"][0], mono=t["claude"][1])
    d.card(380, y, 200, h, "violet", "🌉", t["bridge"][0], mono=t["bridge"][1], line=t["bridge"][2])
    d.card(735, y, 190, h, "teal", "🎮", t["unity"][0], mono=t["unity"][1], line=t["unity"][2])
    d.duplex(212, 372, y + h / 2, *t["edge1"])
    d.duplex(587, 727, y + h / 2, *t["edge2"])

    # the one special path of the story: dashed amber arc with its own label
    d.curve(f"M 560 {y - 4} C 610 {y - 40}, 690 {y - 40}, 760 {y - 4}", "magic", t["reload"], at=(660, y - 38))

    fy = 322  # supporting store under the row, with who writes and who reads it
    d.box(300, fy, 360, 54, "📄", *t["file"])
    d.curve(f"M 830 {y + h + 6} C 830 {fy + 10}, 760 {fy + 27}, 666 {fy + 27}", "teal", t["writes"],
            at=(846, y + h + 36), dashed=False, label_color="#99f6e4", anchor="start")
    d.arrow(480, fy - 2, 480, y + h + 10, "violet")
    d.text(490, fy - 14, t["reads"], 11.5, "#ddd6fe", anchor="start")
    d.badges(404, t["badges"])
    return d


if __name__ == "__main__":
    # default: next to this script (docs/diagrams/), wherever it is run from
    out = Path(next((a for a in sys.argv[1:] if not a.startswith("--")), Path(__file__).resolve().parent))
    for lang, name in (("en", "how-it-works.svg"), ("ru", "how-it-works.ru.svg")):
        build(TEXT[lang]).save(out / name)
    if "--png" in sys.argv:
        for name in ("how-it-works.svg", "how-it-works.ru.svg"):
            print(render_png(out / name, out / (Path(name).stem + ".png")))
    finish()  # with --strict: exit 1 if any language above warned
