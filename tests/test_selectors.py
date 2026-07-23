"""
Test selectors for DeepSeek Chat UI against real HTML fragments.
Uses regex-based pattern matching to verify CSS/XPath selectors.
"""
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extractors import RegexExtractor

CODE_BLOCK_HTML = """
<div class="md-code-block md-code-block-dark">
  <div class="md-code-block-banner-wrap">
    <div class="md-code-block-banner md-code-block-banner-lite">
      <div class="_121d384">
        <div class="d2a24f03">
          <span class="d813de27">csharp</span>
        </div>
        <div class="d2a24f03 _246a029">
          <div class="efa13877">
            <div role="button" class="ds-button ds-button--borderlessNeutral ds-button--borderless ds-button--capsule ds-button--xs ds-button--icon-relative-m ds-button--min-width" tabindex="0" style="margin-right: 2px;">
              <span class="ds-button__content">
                <span class="code-info-button-text">Copy</span>
              </span>
            </div>
            <div role="button" class="ds-button ds-button--borderlessNeutral ds-button--borderless ds-button--capsule ds-button--xs ds-button--icon-relative-m ds-button--min-width" tabindex="0">
              <span class="ds-button__content">
                <span class="code-info-button-text">Download</span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <pre>
    <span class="token keyword">public</span> <span class="token keyword">class</span> <span class="token class-name">TestClass</span>
    <span class="token punctuation">{</span>
        <span class="token keyword">public</span> <span class="token return-type class-name"><span class="token keyword">string</span></span> Name <span class="token operator">=></span> <span class="token string">"Test"</span><span class="token punctuation">;</span>
    <span class="token punctuation">}</span>
  </pre>
</div>
"""

ATTACH_BUTTON_HTML = """
<div role="button" class="ds-button ds-button--iconLabelPrimary ds-button--icon ds-button--capsule ds-button--s ds-button--icon-relative-m f02f0e25" tabindex="0" style="--dsl-button-height: 34px;">
  <div class="ds-button__background"></div>
  <div class="ds-button__icon ds-button__icon--last-child">
    <div class="ds-icon" style="font-size: inherit;">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M5.5498 9.75V5H6.9502V9.75C6.9502 10.3299 7.4201 10.7998 8 10.7998C8.5799 10.7998 9.0498 10.3299 9.0498 9.75V4.5C9.0498 2.9536 7.7964 1.7002 6.25 1.7002C4.7036 1.7002 3.4502 2.9536 3.4502 4.5V9.75C3.4502 12.2629 5.4871 14.2998 8 14.2998C10.5129 14.2998 12.5498 12.2629 12.5498 9.75V4H13.9502V9.75C13.9502 13.0361 11.2861 15.7002 8 15.7002C4.71391 15.7002 2.0498 13.0361 2.0498 9.75V4.5C2.04981 2.1804 3.9304 0.299806 6.25 0.299805C8.5696 0.299805 10.4502 2.1804 10.4502 4.5V9.75C10.4502 11.1031 9.3531 12.2002 8 12.2002C6.6469 12.2002 5.5498 11.1031 5.5498 9.75Z" fill="currentColor"></path>
      </svg>
    </div>
  </div>
</div>
"""


def has_class(tag_html, class_name):
    """Check if an HTML tag has a specific class."""
    m = re.search(r'class="([^"]*)"', tag_html)
    if not m:
        return False
    classes = m.group(1).split()
    return class_name in classes


def has_attr(tag_html, attr_name, attr_value=None, contains=False):
    """Check if an HTML tag has a specific attribute."""
    if attr_value is None:
        return re.search(rf'\b{attr_name}\b', tag_html) is not None
    if contains:
        return re.search(rf'{attr_name}\s*=\s*"[^"]*{re.escape(attr_value)}[^"]*"', tag_html) is not None
    return re.search(rf'{attr_name}\s*=\s*"{re.escape(attr_value)}"', tag_html) is not None


def count_tags(html, tag, class_name=None, attrs=None):
    """Count HTML tags matching criteria."""
    pattern = rf'<{tag}\b[^>]*>'
    count = 0
    for m in re.finditer(pattern, html, re.DOTALL):
        tag_html = m.group()
        if class_name and not has_class(tag_html, class_name):
            continue
        if attrs:
            for k, v in attrs.items():
                if isinstance(v, tuple):
                    if not has_attr(tag_html, k, v[1], contains=v[0] == "contains"):
                        break
                elif isinstance(v, str):
                    if not has_attr(tag_html, k, v):
                        break
                else:
                    if not has_attr(tag_html, k):
                        break
            else:
                count += 1
        else:
            count += 1
    return count


def test_css(html, css_selector, expected_min=1):
    """Test a CSS-like selector against HTML."""
    # Parse simple CSS selector: tag.class[attr=val], tag.class, .class, tag[attr*=val]
    tag = "*"
    class_name = None
    attrs = {}

    parts = re.findall(r'[.#]?[a-zA-Z0-9_*-]+|\[[^\]]+\]', css_selector)
    for part in parts:
        if part.startswith("."):
            class_name = part[1:]
        elif part.startswith("#"):
            pass  # ignore id
        elif part.startswith("["):
            inner = part[1:-1]
            if "*=" in inner:
                k, v = inner.split("*=", 1)
                attrs[k.strip()] = ("contains", v.strip("'\""))
            elif "=" in inner:
                k, v = inner.split("=", 1)
                attrs[k.strip()] = ("exact", v.strip("'\""))
            else:
                attrs[inner.strip()] = ("exists", "")
        else:
            tag = part

    count = count_tags(html, tag, class_name, attrs)
    status = "PASS" if count >= expected_min else "FAIL"
    print(f"  [{status}] CSS '{css_selector}': found {count} (expected >= {expected_min})")
    return count >= expected_min


def test_regex(html, pattern, desc, expected_min=1):
    matches = re.findall(pattern, html)
    count = len(matches)
    status = "PASS" if count >= expected_min else "FAIL"
    print(f"  [{status}] Regex '{desc}': found {count} (expected >= {expected_min})")
    return count >= expected_min


def run_tests():
    print("=" * 55)
    print("TESTING DEEPSEEK CHAT UI SELECTORS")
    print("=" * 55)
    passed = 0
    total = 0

    # Code block structure
    print("\n[Code block]")
    total += 1; passed += test_css(CODE_BLOCK_HTML, "div.md-code-block", 1)
    total += 1; passed += test_css(CODE_BLOCK_HTML, "div.md-code-block-banner-wrap", 1)
    total += 1; passed += test_css(CODE_BLOCK_HTML, "div.md-code-block-dark", 1)
    total += 1; passed += test_css(CODE_BLOCK_HTML, "span.code-info-button-text", 2)
    total += 1; passed += test_css(CODE_BLOCK_HTML, "span.d813de27", 1)

    # Copy button specific
    print("\n[Copy button in code block]")
    total += 1
    p = r'<span[^>]*class="code-info-button-text"[^>]*>Copy</span>'
    passed += test_regex(CODE_BLOCK_HTML, p, "Copy button text with 'Copy'", 1)

    # Code from <pre>
    print("\n[Code from <pre>]")
    total += 1
    pre_m = re.search(r'<pre>(.*?)</pre>', CODE_BLOCK_HTML, re.DOTALL)
    if pre_m:
        code = re.sub(r'<[^>]+>', '', pre_m.group(1)).strip()
        ok = "public class TestClass" in code
        print(f"  [{'PASS' if ok else 'FAIL'}] Extracted code from <pre> (contains 'public class TestClass')")
        passed += ok
    else:
        print(f"  [FAIL] <pre> tag not found")

    # Attach button
    print("\n[Attach button]")
    total += 1; passed += test_css(ATTACH_BUTTON_HTML, "div.ds-button--iconLabelPrimary", 1)
    total += 1; passed += test_css(ATTACH_BUTTON_HTML, "div[role='button']", 1)
    total += 1
    svg_p = r'<path[^>]*d="M5\.5498\s*9\.75[^"]*"'
    passed += test_regex(ATTACH_BUTTON_HTML, svg_p, "SVG path starting with M5.5498 9.75", 1)

    # Legacy markdown extraction
    print("\n[RegexExtractor markdown parsing]")
    extractor = RegexExtractor()
    md = """```python\ndef hello():\n    print("Hello")\n```"""
    code = extractor.extract(md)
    total += 1
    ok = code and "def hello()" in code
    print(f"  [{'PASS' if ok else 'FAIL'}] RegexExtractor on python block: {code.strip()[:30] if code else 'None'}")
    passed += ok

    # TASK_COMPLETE
    print("\n[TASK_COMPLETE parsing]")
    total += 1
    m = re.search(r"TASK_COMPLETE\s*:\s*(.+)", "TASK_COMPLETE: task done", re.IGNORECASE | re.DOTALL)
    ok = m is not None and m.group(1).strip() == "task done"
    print(f"  [{'PASS' if ok else 'FAIL'}] TASK_COMPLETE parsed: '{m.group(1).strip() if m else 'None'}'")
    passed += ok

    # Input textarea
    print("\n[Input textarea]")
    input_html = '<textarea class="_27c9245" placeholder="Ask anything..."></textarea>'
    total += 1; passed += test_css(input_html, "textarea._27c9245", 1)

    print("\n" + "=" * 55)
    print(f"RESULT: {passed}/{total} tests passed")
    print("=" * 55)
    return passed == total


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
