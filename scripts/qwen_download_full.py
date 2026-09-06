"""
Скачивание ОРИГИНАЛОВ изображений из чата Qwen через штатную кнопку download
(div.qwen-chat-package-comp-new-action-control-container-download).

Чат отдаёт в <img> ужатые превью (~500 КБ), а кнопка скачивания — исходный
файл (~2 МБ). Поэтому этот скрипт не тянет src картинок, а кликает кнопки:
каталог приёма задаётся через CDP Browser.setDownloadBehavior, диалогов нет.

Пример:
    python scripts\\qwen_download_full.py --output d:\\Projects\\Demiurges\\assets\\full
    python scripts\\qwen_download_full.py --limit 2   (проверка размера)
    python scripts\\qwen_download_full.py --probe     (только посчитать кнопки)

Edge debug (порт 9222), чат открыт. Браузер остаётся открыт (--close — закрыть).
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from logger import Logger

DL_CLASS = "qwen-chat-package-comp-new-action-control-container-download"

FIND_JS = """
const out=[];
for(const d of document.querySelectorAll('div.%s')){
  const box=d.closest('div.image-tool-container')||d.parentElement;
  const img=box?box.querySelector('img'):null;
  out.push({box:box?box.className:'?',img:img?(img.currentSrc||img.src||''):''});
}
return out;
""" % DL_CLASS

CLICK_JS = """
const all=[...document.querySelectorAll('div.%s')];
const i=arguments[0];
if(i>=all.length)return 'no-index';
const d=all[i];
const box=d.closest('div.image-tool-container');
if(box){box.scrollIntoView({block:'center'});}
d.click();
return 'clicked';
""" % DL_CLASS


def snapshot_dir(path):
    try:
        return {f: os.path.getsize(os.path.join(path, f))
                for f in os.listdir(path)}
    except FileNotFoundError:
        return {}


def wait_downloads(path, before, timeout=120):
    """Ждёт появления новых файлов и исчезновения .crdownload."""
    deadline = time.time() + timeout
    started = set(before)
    while time.time() < deadline:
        time.sleep(1.0)
        cur = snapshot_dir(path)
        new = set(cur) - started
        if new and not any(f.endswith(".crdownload") for f in cur):
            # размер стабилизировался?
            time.sleep(1.5)
            cur2 = snapshot_dir(path)
            if all(cur2.get(f) == cur.get(f) for f in new):
                return sorted(new)
    cur = snapshot_dir(path)
    return sorted(set(cur) - started)


def build_parser():
    p = argparse.ArgumentParser(
        prog="qwen_download_full",
        description="Скачивание оригиналов изображений через кнопки download чата Qwen",
    )
    p.add_argument("--port", type=int, default=9222)
    p.add_argument("--output", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "pipeline_output", "qwen_full"),
        help="Каталог приёма (создаётся)")
    p.add_argument("--limit", type=int, default=0, help="Первые N кнопок (0 — все)")
    p.add_argument("--offset", type=int, default=0, help="Начать с N-й кнопки")
    p.add_argument("--probe", action="store_true", help="Только посчитать кнопки")
    p.add_argument("--close", action="store_true")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    logger = Logger(log_to_file=True, log_file="qwen_download_full.log")

    from selenium import webdriver
    from selenium.webdriver.edge.options import Options

    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:%d" % args.port)
    options.page_load_strategy = "eager"
    try:
        driver = webdriver.Edge(options=options)
    except Exception as e:
        logger.log("Нет Edge на порту %d: %s" % (args.port, e), "ERROR")
        return 2
    for h in driver.window_handles:
        driver.switch_to.window(h)
        if "chat.qwen.ai" in (driver.current_url or ""):
            break
    logger.log("Вкладка: %s" % driver.current_url)

    items = driver.execute_script(FIND_JS) or []
    logger.log("Кнопок download: %d" % len(items))
    if args.probe:
        for i, it in enumerate(items):
            logger.log("  #%d img=%s" % (i, it["img"][-60:]))
        return 0

    os.makedirs(args.output, exist_ok=True)
    try:
        driver.execute_cdp_cmd("Browser.setDownloadBehavior", {
            "behavior": "allow", "downloadPath": os.path.abspath(args.output)})
        logger.log("Каталог приёма: %s" % os.path.abspath(args.output))
    except Exception as e:
        logger.log("CDP downloadBehavior не встал: %s" % e, "ERROR")
        return 2

    total = len(items)
    lo, hi = args.offset, total if not args.limit else min(total, args.offset + args.limit)
    ok = 0
    for i in range(lo, hi):
        before = snapshot_dir(args.output)
        res = driver.execute_script(CLICK_JS, i)
        logger.log("#%d/%d: %s img=...%s" % (i, total, res, items[i]["img"][-40:]))
        new = wait_downloads(args.output, before)
        if new:
            sizes = ["%s (%d КБ)" % (f, snapshot_dir(args.output)[f] // 1024) for f in new]
            logger.log("  -> %s" % "; ".join(sizes))
            ok += 1
        else:
            logger.log("  -> ничего не скачалось за 120с", "WARNING")
        time.sleep(1.0)

    logger.log("Готово: %d/%d." % (ok, hi - lo))
    if args.close:
        try:
            driver.quit()
        except Exception:
            pass
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
