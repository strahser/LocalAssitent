"""
Скачивание изображений (скриншотов/артов) из открытого чата chat.qwen.ai
напрямую в папку проекта — без кликов по кнопке download в UI.

Как находит: все <img> внутри div.qwen-chat-message-assistant
(фолбэк — вся страница), отсев аватарок/иконок по размеру, предварительный
скролл чата для догрузки ленивых картинок, приоритет полного размера
(родительский <a href>, если ведёт на картинку).

Как качает: http(s) — через urllib с куками и User-Agent текущей сессии
Selenium; blob: — через canvas.toDataURL внутри страницы; data: — напрямую.
Зависимостей сверх requirements нет (только stdlib + selenium).

Имена файлов: unix-timestamp как у Qwen (1788692438.png), при коллизии
суффикс _1, _2. Рядом пишется манифест manifest_<ts>.json {file, url, w, h}.

Пример:
    python scripts\\qwen_download_images.py --output d:\\Projects\\Demiurges\\assets\\new
    python scripts\\qwen_download_images.py --limit 5 --min-width 512

Edge должен быть запущен с --remote-debugging-port=<port>, нужный чат открыт.
Браузер по умолчанию НЕ закрывается (флаг --close — закрыть после работы).
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from logger import Logger

ASSISTANT_BLOCK = "div.qwen-chat-message-assistant"

COLLECT_JS = """
const out=[];
const blocks=[...document.querySelectorAll(%s)];
const scope=blocks.length?blocks:[document];
const seen=new Set();
for(const root of scope){
  for(const img of root.querySelectorAll('img')){
    const src=img.currentSrc||img.src||'';
    if(!src||seen.has(src))continue;seen.add(src);
    const a=img.closest('a');
    out.push({src:src,href:((a&&a.href)||''),
      w:img.naturalWidth||0,h:img.naturalHeight||0,
      dw:img.clientWidth||0,dh:img.clientHeight||0,
      alt:(img.alt||'').slice(0,80)});
  }
}
return out;
""" % json.dumps(ASSISTANT_BLOCK)

BLOB_JS = """
const url=arguments[0],done=arguments[arguments.length-1];
fetch(url).then(r=>r.blob()).then(b=>{
  const fr=new FileReader();
  fr.onload=()=>done({ok:true,dataUrl:fr.result,ctype:b.type});
  fr.onerror=()=>done({ok:false,error:String(fr.error)});
}).catch(e=>done({ok:false,error:String(e)}));
"""


def is_skippable(src, w, dw, min_width):
    """True, если картинку точно не качаем (иконка/svg/маленькая)."""
    if not src:
        return True
    if src.startswith("data:image/svg"):
        return True
    eff = w or dw
    return eff < min_width


def guess_ext(content_type, url):
    """Расширение по Content-Type, фолбэк — по URL, иначе .png."""
    ct = (content_type or "").lower()
    if "png" in ct:
        return ".png"
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    if "webp" in ct:
        return ".webp"
    if "gif" in ct:
        return ".gif"
    low = (url or "").lower().split("?")[0]
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        if low.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".png"


def make_filename(ts, i, ext):
    """Имя в конвенции Qwen: 1788692438.png, коллизии — 1788692438_1.png."""
    return "%d%s%s" % (ts, ("_%d" % i) if i else "", ext)


def data_url_to_bytes(data_url):
    header, _, b64 = data_url.partition(",")
    return base64.b64decode(b64), header


def download_http(url, cookies, user_agent, timeout=60):
    req = urllib.request.Request(url, headers={
        "User-Agent": user_agent,
        "Referer": "https://chat.qwen.ai/",
        "Cookie": "; ".join("%s=%s" % (c["name"], c["value"]) for c in cookies),
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get_content_type()


def download_blob(driver, url, timeout=60):
    res = driver.execute_async_script(BLOB_JS, url)
    if not res or not res.get("ok"):
        raise RuntimeError("blob fetch failed: %s" % ((res or {}).get("error"),))
    raw, _header = data_url_to_bytes(res["dataUrl"])
    return raw, res.get("ctype", "")


def pick_source(item):
    """Полный размер из родительского <a>, иначе src картинки."""
    href = item.get("href") or ""
    if href and any(href.lower().split("?")[0].endswith(e)
                    for e in (".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return href
    return item["src"]


def switch_to_chat(driver, logger):
    """Переключается на вкладку с chat.qwen.ai (драйвер цепляется к активной)."""
    try:
        handles = driver.window_handles
    except Exception as e:
        logger.log("Нет доступа к вкладкам: %s" % e, "WARNING")
        return False
    for h in handles:
        try:
            driver.switch_to.window(h)
            if "chat.qwen.ai" in (driver.current_url or ""):
                logger.log("Вкладка чата: %s" % driver.current_url)
                return True
        except Exception:
            continue
    logger.log("Вкладка chat.qwen.ai не найдена среди %d вкладок." % len(handles),
               "WARNING")
    return False


def scroll_chat(driver, logger, passes=4):
    for i in range(passes):
        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.0)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)
    logger.log("Чат проскроллен (%d проходов) для догрузки картинок." % passes)


def collect_images(driver):
    return driver.execute_script(COLLECT_JS) or []


def build_parser():
    p = argparse.ArgumentParser(
        prog="qwen_download_images",
        description="Скачивание изображений из открытого чата Qwen в папку",
        epilog=("Примеры:\n"
                "  python scripts\\qwen_download_images.py "
                "--output d:\\Projects\\Demiurges\\assets\\new\n"
                "  python scripts\\qwen_download_images.py --limit 5 --min-width 512\n"),
    )
    p.add_argument("--port", type=int, default=9222)
    p.add_argument("--output", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "pipeline_output", "qwen_images"),
        help="Папка для картинок (создаётся)")
    p.add_argument("--limit", type=int, default=0,
                   help="Максимум файлов (0 — без лимита)")
    p.add_argument("--min-width", type=int, default=256,
                   help="Минимальная ширина картинки, px (аватарки отсекаются)")
    p.add_argument("--min-bytes", type=int, default=20000,
                   help="Минимальный размер файла, байт")
    p.add_argument("--keep-small", action="store_true",
                   help="Не удалять файлы меньше --min-bytes")
    p.add_argument("--overwrite", action="store_true",
                   help="Перезаписывать существующие имена")
    p.add_argument("--close", action="store_true",
                   help="Закрыть браузер после работы (по умолчанию остаётся открыт)")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    logger = Logger(log_to_file=True, log_file="qwen_download_images.log")

    from selenium import webdriver
    from selenium.webdriver.edge.options import Options

    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:%d" % args.port)
    options.page_load_strategy = "eager"
    try:
        driver = webdriver.Edge(options=options)
    except Exception as e:
        logger.log("Не подключился к Edge на порту %d: %s" % (args.port, e), "ERROR")
        logger.log("Запустите Edge: msedge --user-data-dir=%%LOCALAPPDATA%%\\QwenDebugProfile "
                   "--remote-debugging-port=%d и откройте чат." % args.port, "ERROR")
        return 2
    logger.log("URL: %s" % driver.current_url)

    switch_to_chat(driver, logger)

    os.makedirs(args.output, exist_ok=True)
    scroll_chat(driver, logger)
    items = collect_images(driver)
    logger.log("Найдено <img>: %d" % len(items))

    cookies = driver.get_cookies()
    ua = driver.execute_script("return navigator.userAgent;")
    ts = int(time.time())
    saved, skipped, n = [], 0, 0

    for it in items:
        if args.limit and n >= args.limit:
            break
        if is_skippable(it["src"], it["w"], it["dw"], args.min_width):
            skipped += 1
            continue
        url = pick_source(it)
        try:
            if url.startswith("blob:"):
                raw, ctype = download_blob(driver, url)
            elif url.startswith("data:"):
                raw, _h = data_url_to_bytes(url)
                ctype = _h.split(";")[0].split(":")[-1]
            else:
                raw, ctype = download_http(url, cookies, ua)
        except Exception as e:
            logger.log("Пропуск %s: %s" % (url[:100], e), "WARNING")
            skipped += 1
            continue
        if len(raw) < args.min_bytes and not args.keep_small:
            logger.log("Маленький файл (%d байт), пропуск: %s" % (len(raw), url[:100]))
            skipped += 1
            continue
        ext = guess_ext(ctype, url)
        i = 0
        while True:
            name = make_filename(ts, i, ext)
            path = os.path.join(args.output, name)
            if args.overwrite or not os.path.exists(path):
                break
            i += 1
        with open(path, "wb") as f:
            f.write(raw)
        saved.append({"file": name, "url": url, "w": it["w"], "h": it["h"],
                      "bytes": len(raw)})
        n += 1
        logger.log("Сохранено %s (%d байт)" % (name, len(raw)))

    manifest = os.path.join(args.output, "manifest_%d.json" % ts)
    with open(manifest, "w", encoding="utf-8") as f:
        json.dump(saved, f, ensure_ascii=False, indent=1)
    logger.log("Готово: сохранено %d, пропущено %d. Манифест: %s"
               % (len(saved), skipped, manifest))

    if args.close:
        try:
            driver.quit()
        except Exception:
            pass
    return 0 if saved else 1


if __name__ == "__main__":
    sys.exit(main())
